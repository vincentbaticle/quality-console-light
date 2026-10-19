"""Upload a finished test run to the results bucket, the way a CI job does.

One folder per run, named from the UTC clock at upload time; ``metadata.json``
first, carrying the run's metadata also as object metadata so the index crawl
can skip downloading it; then every report file the run produced. A file the
bucket refuses is counted and reported, never raised: results are
observability, not a gate.
"""

from dataclasses import dataclass, field
import datetime
import json
import os
from pathlib import Path

from google.api_core.exceptions import GoogleAPIError
from google.cloud.storage import Bucket

from test_results.junit import aggregate_test_meta, parse_junit
from test_results.layout import (
    COVERAGE_FILE,
    METADATA_FILE,
    RUN_INDEX_METADATA_KEY,
    run_folder_name,
    run_id,
)
from test_results.models import RunMetadata

MAX_RUN_INDEX_BYTES = 6 * 1024
"""Size above which the object metadata annotation is skipped (GCS caps at 8 KiB)."""

JSON_CONTENT_TYPE = "application/json"
"""Content type of ``metadata.json``."""


@dataclass(frozen=True)
class CiContext:
    """What the CI tells about the job, from its predefined variables."""

    pipeline_id: str
    job_id: str
    job_name: str
    commit_sha: str
    job_status: str | None
    project_url: str

    @classmethod
    def from_environment(cls) -> CiContext:
        """Read the GitLab CI predefined variables, as a job exports them.

        Returns:
            The CI context. Outside CI the local tasks set the same variables.
        """
        return cls(
            pipeline_id=os.environ["CI_PIPELINE_ID"],
            job_id=os.environ["CI_JOB_ID"],
            job_name=os.environ["CI_JOB_NAME"],
            commit_sha=os.environ["CI_COMMIT_SHORT_SHA"],
            job_status=os.environ.get("CI_JOB_STATUS"),
            project_url=os.environ.get("CI_PROJECT_URL", ""),
        )


@dataclass
class UploadReport:
    """What an upload did, for the job log."""

    run_id: str
    uploaded: list[str] = field(default_factory=list)
    refused: list[str] = field(default_factory=list)


COUNT_FIELDS = {"total", "passed", "failed", "errors", "skipped"}
"""What a run keeps of its JUnit reports in its metadata, for the index."""


def build_metadata(
    artifact_type: str,
    env: str,
    ci: CiContext,
    reports_dir: Path,
    now: datetime.datetime,
) -> RunMetadata:
    """Describe a run, with the facets its JUnit reports declare.

    Args:
        artifact_type: Kind of run, see ``layout.ARTIFACT_TYPES``.
        env: Environment the tests ran against.
        ci: CI job context.
        reports_dir: Local folder holding the run's report files.
        now: Upload time.

    Returns:
        The run metadata, as ``metadata.json`` will hold it.
    """
    junit = parse_junit(
        [
            p.read_text()
            for p in sorted(reports_dir.rglob("*.xml"))
            if p.name != COVERAGE_FILE
        ]
    )
    return RunMetadata(
        pipeline_id=ci.pipeline_id,
        job_id=ci.job_id,
        job_name=ci.job_name,
        artifact_type=artifact_type,
        commit_sha=ci.commit_sha,
        env=env,
        timestamp=now.astimezone(datetime.UTC).isoformat(),
        ci_job_status=ci.job_status,
        project_url=ci.project_url,
        test_meta=aggregate_test_meta(junit),
        test_counts=junit.model_dump(include=COUNT_FIELDS) if junit.total else {},
    )


def _annotation(payload: str) -> dict[str, str] | None:
    """Object metadata letting the index crawl skip the download, when it fits."""
    if len(payload.encode()) > MAX_RUN_INDEX_BYTES:
        return None
    return {RUN_INDEX_METADATA_KEY: payload}


def upload_run(
    bucket: Bucket,
    metadata: RunMetadata,
    reports_dir: Path,
    now: datetime.datetime,
) -> UploadReport:
    """Write one run folder: ``metadata.json`` first, then every report file.

    Args:
        bucket: Results bucket.
        metadata: The run's metadata, see ``build_metadata``.
        reports_dir: Local folder holding the run's report files.
        now: Upload time, which names the run folder.

    Returns:
        The run id, and which files were uploaded or refused.
    """
    folder = run_folder_name(now, metadata.pipeline_id)
    prefix = run_id(metadata.env, metadata.artifact_type, folder, metadata.job_name)
    report = UploadReport(run_id=prefix)
    payload = metadata.model_dump_json(exclude={"id"})
    blob = bucket.blob(f"{prefix}/{METADATA_FILE}")
    blob.metadata = _annotation(payload)
    blob.upload_from_string(
        json.dumps(json.loads(payload), indent=2), content_type=JSON_CONTENT_TYPE
    )
    report.uploaded.append(blob.name)
    for path in sorted(p for p in reports_dir.rglob("*") if p.is_file()):
        name = f"{prefix}/{path.relative_to(reports_dir).as_posix()}"
        try:
            bucket.blob(name).upload_from_filename(str(path))
        except GoogleAPIError:
            report.refused.append(name)
        else:
            report.uploaded.append(name)
    return report
