"""Read what the dashboard shows: the indexed runs, one run in detail, a file.

Lists and counters come from the index only. A run's detail is read from its
own folder, since the index carries only what a list needs. Every path a
visitor sends is checked to stay inside the reports before it is read.
"""

from collections import Counter
from dataclasses import dataclass, field
import json
import mimetypes

from google.api_core.exceptions import NotFound
from google.cloud.storage import Bucket

from test_results.junit import parse_junit
from test_results.k6 import SUMMARY_FILE, parse_k6_summary
from test_results.layout import (
    COVERAGE_FILE,
    INDEX_HEADER,
    METADATA_FILE,
    is_report_path,
)
from test_results.models import IndexHeader, RunDetail, RunMetadata
from test_results.trends import normalize_status

STATUS_FILTERS = ("success", "failed", "unknown")
"""Run statuses a visitor can filter on; ``unknown`` is anything else."""


class RunNotFoundError(LookupError):
    """No run, or no file, at the path a visitor asked for."""


@dataclass
class RunFilters:
    """What the dashboard filters runs on; an empty value filters nothing."""

    env: str = ""
    artifact_type: str = ""
    status: str = ""
    job_name: str = ""
    facets: dict[str, str] = field(default_factory=dict)

    def keeps(self, run: RunMetadata) -> bool:
        """Say whether a run passes every active filter."""
        status = normalize_status(run.ci_job_status)
        checks = [
            not self.env or run.env == self.env,
            not self.artifact_type or run.artifact_type == self.artifact_type,
            not self.status or status == self.status,
            not self.job_name or run.job_name == self.job_name,
            *(
                not value or value in run.test_meta.get(name, [])
                for name, value in self.facets.items()
            ),
        ]
        return all(checks)


@dataclass(frozen=True)
class Stats:
    """Counters at the top of the dashboard."""

    total: int
    passed: int
    failed: int


class ResultsReader:
    """Reads the index and the run folders of the results bucket."""

    def __init__(self, bucket: Bucket) -> None:
        """Point at the bucket.

        Args:
            bucket: Results bucket.
        """
        self._bucket = bucket

    def header(self) -> IndexHeader | None:
        """Read the index header, None before the first indexing."""
        try:
            document = self._bucket.blob(INDEX_HEADER).download_as_text()
        except NotFound:
            return None
        return IndexHeader.model_validate_json(document)

    def runs(self, filters: RunFilters) -> list[RunMetadata]:
        """List the indexed runs passing the filters, newest first."""
        header = self.header()
        if header is None:
            return []
        runs = [
            RunMetadata.model_validate(item)
            for shard in header.shards
            for item in json.loads(self._bucket.blob(shard.path).download_as_text())
        ]
        return [run for run in runs if filters.keeps(run)]

    @staticmethod
    def stats(runs: list[RunMetadata]) -> Stats:
        """Count the runs, the successful ones and the failed ones."""
        statuses = Counter(run.ci_job_status for run in runs)
        return Stats(len(runs), statuses["success"], statuses["failed"])

    @staticmethod
    def facet_values(runs: list[RunMetadata]) -> dict[str, list[str]]:
        """Every value seen per filter, to fill the dropdowns."""
        values: dict[str, set[str]] = {
            "env": set(),
            "artifact_type": set(),
            "job_name": set(),
        }
        for run in runs:
            values["env"].add(run.env)
            values["artifact_type"].add(run.artifact_type)
            values["job_name"].add(run.job_name)
            for name, facet in run.test_meta.items():
                values.setdefault(name, set()).update(facet)
        return {name: sorted(found) for name, found in values.items()}

    def detail(self, run_id: str) -> RunDetail:
        """Read a run from its folder: metadata, files, JUnit and k6 results.

        Raises:
            RunNotFoundError: When the id is outside the reports or has no run.
        """
        if not is_report_path(run_id):
            raise RunNotFoundError(run_id)
        names = [blob.name for blob in self._bucket.list_blobs(prefix=f"{run_id}/")]
        metadata_path = f"{run_id}/{METADATA_FILE}"
        if metadata_path not in names:
            raise RunNotFoundError(run_id)
        metadata = RunMetadata.model_validate(
            {**json.loads(self._text(metadata_path)), "id": run_id}
        )
        xml = [
            self._text(name)
            for name in names
            if name.endswith(".xml") and not name.endswith(f"/{COVERAGE_FILE}")
        ]
        summaries = [name for name in names if name.endswith(f"/{SUMMARY_FILE}")]
        return RunDetail(
            metadata=metadata,
            artifacts=[name for name in names if name != metadata_path],
            junit=parse_junit(xml) if xml else None,
            perf_summary=parse_k6_summary(self._text(summaries[0]))
            if summaries
            else None,
        )

    def artifact(self, path: str) -> tuple[bytes, str]:
        """Read one report file and guess its content type.

        Raises:
            RunNotFoundError: When the path is outside the reports or missing.
        """
        if not is_report_path(path):
            raise RunNotFoundError(path)
        try:
            content = self._bucket.blob(path).download_as_bytes()
        except NotFound as exc:
            raise RunNotFoundError(path) from exc
        content_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
        return content, content_type

    def _text(self, name: str) -> str:
        """Download one object as text."""
        return self._bucket.blob(name).download_as_text()
