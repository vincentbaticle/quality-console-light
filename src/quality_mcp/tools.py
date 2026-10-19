"""What the MCP tools do, as plain methods over the stack's HTTP and bucket.

The server (``server.py``) only registers them; tests call them directly,
with the console and the runner served in process.
"""

from collections.abc import Callable
from dataclasses import dataclass
import datetime
from pathlib import Path
import time
from typing import Any
from urllib.parse import parse_qs, urlparse

from google.cloud.storage import Bucket
import httpx

from company_db import DatabaseSettings, connect
from quality_console.footprint import TARGETS
from quality_console.gherkin_files import load_features
from quality_console.recording_scrub import clean_session
from quality_console.scenario_template import problems
from test_results.index import build_index
from test_results.reader import ResultsReader, RunFilters

OUTPUT_TAIL_CHARACTERS = 1500
"""End of a run's pytest output kept in an answer, where the verdict is."""

FOOTPRINT_TIMEOUT_SECONDS = 240
"""Budget of one retro-footprint experiment, about a minute when all goes well."""

FOOTPRINT_POLL_SECONDS = 2
"""Pause between two reads of a running experiment."""

MAX_RUNS = 50
"""Most runs one answer lists."""

ACCOUNTS_QUERY = (
    "SELECT email, has_password, has_totp, blocked, created_at"
    " FROM accounts ORDER BY created_at"
)
"""The accounts of the identity tenant, through the console's read-only view."""

GENERATED_ACCOUNT_MARK = "+bdd-"
"""What the address of an account a scenario created carries."""


def account_profile(has_password: bool, has_totp: bool, blocked: bool) -> str:
    """Say in business words what an account can do, the way an actor line does.

    Args:
        has_password: Whether a password is set.
        has_totp: Whether a second factor is enrolled.
        blocked: Whether ten wrong passwords blocked it.

    Returns:
        A customer account profile, as the scenario template words it.
    """
    if blocked:
        return "a blocked customer account who must unblock it from their email"
    if not has_password:
        return "a customer account who has no password yet"
    if has_totp:
        return "a customer account who signs in with a password and a second factor"
    return "a customer account who can sign in with a password"


def experiment_id(location: str) -> str:
    """The experiment id the console redirects to after a start.

    Args:
        location: The ``Location`` header of the start's ``303``.

    Returns:
        The id, empty when the redirect names none.
    """
    return parse_qs(urlparse(location).query).get("experiment", [""])[0]


def footprint_answer(state: dict[str, Any]) -> dict[str, Any]:
    """Keep what answers "which tables does this test touch" from an experiment.

    Args:
        state: The experiment as the console's JSON gives it.

    Returns:
        The answer (from the traces, or the database when no trace was found),
        every access the traces name, and what the database saw in every run.
    """
    accesses = [
        f"{a['service']} {a['operation']} {a['table']}"
        for a in [*state["traced"], *state["sql"]]
    ]
    return {
        "test": state["target"],
        "done": state["done"],
        "error": state["error"],
        "answer_source": "traces" if state["checked"] else "database counters",
        "tables": state["exact"] if state["checked"] else state["found"],
        "accesses": accesses,
        "seen_by_database_in_every_run": state["found"],
        "untraced_tables": sorted(set(state["found"]) - set(state["exact"]))
        if state["checked"]
        else [],
        "trace_ids": state["trace_ids"],
        "runs": len(state["runs"]),
    }


@dataclass
class QualityTools:
    """The stack, as the MCP tools reach it.

    Attributes:
        console: HTTP client of the Quality Console.
        runner: HTTP client of the Gherkin runner.
        bucket: The test results bucket.
        features: The ``features/`` folder.
        identity: The identity database, read-only, for the test accounts.
        clock: Gives the time an index is rebuilt at.
        sleep: Waits between two reads of an experiment.
    """

    console: httpx.Client
    runner: httpx.Client
    bucket: Bucket
    features: Path
    identity: DatabaseSettings | None = None
    clock: Callable[[], datetime.datetime] = lambda: datetime.datetime.now(datetime.UTC)
    sleep: Callable[[float], None] = time.sleep

    def list_scenarios(self) -> list[dict[str, Any]]:
        """Every Gherkin feature with its scenarios and the goal of each."""
        return [
            {
                "feature": feature.path,
                "name": feature.name,
                "scenarios": [
                    {"name": s.name, "goal": s.goal} for s in feature.scenarios
                ],
            }
            for feature in load_features(self.features)
        ]

    def run_scenario(self, feature: str, scenario: str = "") -> dict[str, Any]:
        """Run a feature, or one of its scenarios, on the stack.

        Args:
            feature: Its path under ``features/``, as ``list_scenarios`` gives it.
            scenario: The exact name of one scenario, empty for the whole feature.

        Returns:
            The verdict, the counts, the run id in the results bucket and the
            end of the pytest output.
        """
        response = self.runner.post(
            "/runs", json={"feature": feature, "scenario": scenario}
        )
        if response.status_code == httpx.codes.NOT_FOUND:
            return {"error": f"Unknown feature {feature}: see list_scenarios"}
        response.raise_for_status()
        result = response.json()
        result["output"] = result["output"][-OUTPUT_TAIL_CHARACTERS:]
        return result

    def recent_runs(
        self, job_name: str = "", status: str = "", limit: int = 10
    ) -> list[dict[str, Any]]:
        """The last test runs of the results bucket, newest first.

        Args:
            job_name: Only this CI job, empty for every job.
            status: ``success`` or ``failed``, empty for both.
            limit: How many runs, at most 50.

        Returns:
            One line per run: job, environment, kind, status, time, run id.
        """
        build_index(self.bucket, self.clock())
        runs = ResultsReader(self.bucket).runs(
            RunFilters(job_name=job_name, status=status)
        )
        return [
            {
                "job": run.job_name,
                "env": run.env,
                "kind": run.artifact_type,
                "status": run.ci_job_status,
                "time": run.timestamp,
                "run_id": run.id,
            }
            for run in runs[: min(limit, MAX_RUNS)]
        ]

    def footprint_targets(self) -> dict[str, str]:
        """The tests retro-footprint plays for real, by key: no simulated example."""
        return {
            key: target.title for key, target in TARGETS.items() if target.demo is None
        }

    def table_footprint(self, target: str) -> dict[str, Any]:
        """Play a test 10 times and say which tables it touches.

        Args:
            target: A key of ``footprint_targets``.

        Returns:
            The tables and accesses of the answer, what the database saw in
            every run, the tables only the database saw.
        """
        if target not in self.footprint_targets():
            return {"error": f"Unknown test {target}: see footprint_targets"}
        started = self.console.post(
            "/devx/retro-footprint/run",
            params={"target": target},
            follow_redirects=False,
        )
        if not started.is_redirect:
            started.raise_for_status()
        location = started.headers["location"]
        if "busy=true" in location:
            return {
                "error": "Another real retro-footprint analysis is running:"
                " try again in a minute"
            }
        found = experiment_id(location)
        deadline = time.monotonic() + FOOTPRINT_TIMEOUT_SECONDS
        while True:
            state = self.console.get(f"/devx/retro-footprint/experiments/{found}")
            state.raise_for_status()
            body = state.json()
            if body["done"] or time.monotonic() > deadline:
                return footprint_answer(body)
            self.sleep(FOOTPRINT_POLL_SECONDS)

    def check_scenario(self, gherkin: str) -> dict[str, Any]:
        """Check a scenario draft against the template of a recorded scenario.

        Args:
            gherkin: The feature and its scenario: one Given per actor
                (``"<actor>", a <account type> who <rights>``), the data
                recipe, what is observed.

        Returns:
            Whether it is ready to become a test, and what it misses.
        """
        found = problems(gherkin)
        return {"ready": not found, "problems": found}

    def test_accounts(self) -> list[dict[str, str]]:
        """The seeded accounts of the identity tenant and what each can do.

        Returns:
            One account per line, its email and its profile in the words of
            an actor line, to pick who plays a scenario. Accounts the
            scenarios created for themselves are left out.
        """
        if self.identity is None:
            return [{"error": "No identity database configured"}]
        with connect(self.identity) as connection, connection.cursor() as cursor:
            cursor.execute(ACCOUNTS_QUERY)
            rows = cursor.fetchall()
        return [
            {
                "email": str(email),
                "profile": account_profile(bool(password), bool(totp), bool(blocked)),
            }
            for email, password, totp, blocked, _ in rows
            if GENERATED_ACCOUNT_MARK not in str(email)
        ]

    def scrub_recording(self, recording: str, har: str = "") -> dict[str, Any]:
        """Remove the secrets of a recorded journey, then delete the raw files.

        Args:
            recording: Path of the raw Codegen script, ``raw-<name>.<ext>``.
            har: Path of the raw network capture, ``raw-<name>.har``, if any.

        Returns:
            Where the cleaned copies are (the same names without ``raw-``),
            and what was removed where, never a removed value.
        """
        raw = Path(recording)
        if not raw.name.startswith("raw-"):
            return {"error": "Name the raw files raw-<name>: the clean copy drops it"}
        raw_har = Path(har) if har else None
        return clean_session(
            raw,
            raw.with_name(raw.name.removeprefix("raw-")),
            raw_har,
            raw_har.with_name(raw_har.name.removeprefix("raw-")) if raw_har else None,
        )
