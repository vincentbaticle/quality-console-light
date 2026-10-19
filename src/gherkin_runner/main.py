"""Runs the Gherkin scenarios on demand, the service behind the console's Run buttons.

A run is ``pytest`` on ``tests/acceptance`` with pytest-bdd, narrowed to one
feature or one scenario, against the stack ``mise run up`` started. Its JUnit
report is parsed for the verdict and, like a CI job, uploaded to the results
bucket, so the run shows up in the console's test results too.
"""

from collections.abc import Callable
from dataclasses import dataclass
import datetime
from http import HTTPStatus
import os
from pathlib import Path
import subprocess  # noqa: S404
import sys
import tempfile

from fastapi import FastAPI, HTTPException
from google.cloud.storage import Bucket
from pydantic import BaseModel, Field

from test_results.junit import parse_junit
from test_results.storage import is_reachable, open_bucket
from test_results.uploader import CiContext, build_metadata, upload_run

ACCEPTANCE_TESTS = "tests/acceptance"
"""Where the step definitions and scenario bindings live."""

FEATURES_DIR = "features"
"""Where the feature files live, one folder per product."""

RUN_TIMEOUT_SECONDS = 300
"""Budget of one run, after which it is reported as an error."""

OUTPUT_TAIL_CHARACTERS = 6000
"""How much of the pytest output a run returns."""

ARTIFACT_TYPE = "acceptance"
"""Kind of run in the results bucket."""

ENVIRONMENT = {
    "project_root": "PROJECT_ROOT",
    "bucket": "RESULTS_BUCKET",
    "env": "TEST_ENV",
    "commit": "GIT_COMMIT",
}
"""Environment variable of each setting of the runner."""


class RunRequest(BaseModel):
    """What to run: a feature, or one scenario of it."""

    feature: str = Field(min_length=1, max_length=200)
    scenario: str = Field(default="", max_length=200)


class RunResult(BaseModel):
    """How a run went."""

    feature: str
    scenario: str
    status: str
    exit_code: int
    total: int
    passed: int
    failed: int
    skipped: int
    output: str
    run_id: str


@dataclass(frozen=True)
class Verdict:
    """The counts of a JUnit report and what they amount to."""

    status: str
    total: int
    passed: int
    failed: int
    skipped: int


def pytest_command(feature: str, scenario: str, reports: Path) -> list[str]:
    """The pytest command of a run.

    Args:
        feature: Feature path relative to ``features/``.
        scenario: Scenario name, empty for every scenario of the feature.
        reports: Folder the JUnit and HTML reports go to.

    Returns:
        The command, to run from the project root.
    """
    command = [
        sys.executable,
        "-m",
        "pytest",
        ACCEPTANCE_TESTS,
        "-m",
        "acceptance",
        "-p",
        "no:cacheprovider",
        f"--only-feature={feature}",
        f"--junitxml={reports / 'junit.xml'}",
        f"--html={reports / 'report.html'}",
        "--self-contained-html",
    ]
    if scenario:
        command.append(f"--only-scenario={scenario}")
    return command


def verdict(junit: str | None, exit_code: int) -> Verdict:
    """Read the verdict of a run from its JUnit report.

    Args:
        junit: The report, None when pytest wrote none.
        exit_code: pytest's exit code.

    Returns:
        ``passed`` when every selected scenario passed, ``failed`` when one
        failed, ``skipped`` when none ran (the stack is down), ``error``
        when pytest could not even report.
    """
    if junit is None:
        return Verdict("error", 0, 0, 0, 0)
    results = parse_junit([junit])
    failed = results.failed + results.errors
    if failed or exit_code not in (0, 5):
        status = "failed"
    elif results.passed:
        status = "passed"
    else:
        status = "skipped"
    return Verdict(status, results.total, results.passed, failed, results.skipped)


def create_app(
    project_root: Path,
    bucket: Bucket | None,
    env: str,
    commit: str,
    clock: Callable[[], datetime.datetime] = lambda: datetime.datetime.now(
        datetime.UTC
    ),
) -> FastAPI:
    """Build the runner.

    Args:
        project_root: Folder holding ``features/`` and ``tests/``.
        bucket: Results bucket a run is uploaded to, None to keep runs local.
        env: Environment name a run is filed under in the bucket.
        commit: Commit the scenarios come from.
        clock: Gives the current time, which names a run folder.

    Returns:
        The FastAPI application.
    """
    app = FastAPI(title="Gherkin runner")
    features = project_root / FEATURES_DIR

    @app.get("/health")
    def health() -> dict[str, str]:
        """Answer ``ok``."""
        return {"status": "ok"}

    @app.post("/runs")
    def run(request: RunRequest) -> RunResult:
        """Run a feature or a scenario and report how it went."""
        known = {
            p.relative_to(features).as_posix() for p in features.glob("*/*.feature")
        }
        if request.feature not in known:
            raise HTTPException(HTTPStatus.NOT_FOUND, "Unknown feature")
        with tempfile.TemporaryDirectory() as folder:
            reports = Path(folder)
            try:
                completed = subprocess.run(  # noqa: S603
                    pytest_command(request.feature, request.scenario, reports),
                    cwd=project_root,
                    capture_output=True,
                    text=True,
                    timeout=RUN_TIMEOUT_SECONDS,
                    check=False,
                )
                exit_code, output = (
                    completed.returncode,
                    completed.stdout + completed.stderr,
                )
            except subprocess.TimeoutExpired:
                exit_code, output = -1, f"Run stopped after {RUN_TIMEOUT_SECONDS}s"
            junit_file = reports / "junit.xml"
            junit = junit_file.read_text() if junit_file.exists() else None
            result = verdict(junit, exit_code)
            run_id = ""
            if bucket is not None and junit is not None and is_reachable(bucket):
                now = clock()
                section = request.feature.split("/", 1)[0]
                ci = CiContext(
                    pipeline_id="gherkin",
                    job_id="",
                    job_name=f"acceptance-{section}",
                    commit_sha=commit,
                    job_status="success" if result.status != "failed" else "failed",
                    project_url="",
                )
                metadata = build_metadata(ARTIFACT_TYPE, env, ci, reports, now)
                run_id = upload_run(bucket, metadata, reports, now).run_id
        return RunResult(
            feature=request.feature,
            scenario=request.scenario,
            status=result.status,
            exit_code=exit_code,
            total=result.total,
            passed=result.passed,
            failed=result.failed,
            skipped=result.skipped,
            output=output[-OUTPUT_TAIL_CHARACTERS:],
            run_id=run_id,
        )

    return app


def app_from_environment() -> FastAPI:
    """Build the runner from its environment, the entry point uvicorn serves.

    Returns:
        The FastAPI application.
    """
    bucket_name = os.environ.get(ENVIRONMENT["bucket"], "")
    return create_app(
        Path(os.environ[ENVIRONMENT["project_root"]]),
        open_bucket(bucket_name) if bucket_name else None,
        os.environ.get(ENVIRONMENT["env"], "local"),
        os.environ.get(ENVIRONMENT["commit"], "local"),
    )
