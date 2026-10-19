"""How a job has been doing: its recent history, pass rate and current streak.

Pure functions over indexed runs, no I/O: the console draws them, the unit
tests pin them.
"""

from dataclasses import dataclass

from test_results.models import RunMetadata

HISTORY_LENGTH = 50
"""Runs of one job a trend covers, the newest ones."""

ROLLING_WINDOW = 3
"""Runs each point of the pass rate line averages, to smooth one-off failures."""

KNOWN_STATUSES = ("success", "failed")
"""CI statuses a trend tells apart; anything else counts as ``unknown``."""

OVERVIEW_LENGTH = 20
"""Last runs the jobs overview shows for each job."""


def normalize_status(status: str | None) -> str:
    """Fold every CI status into ``success``, ``failed`` or ``unknown``."""
    return status if status in KNOWN_STATUSES else "unknown"


def job_history(
    runs: list[RunMetadata], job_name: str, artifact_type: str, env: str
) -> list[RunMetadata]:
    """The last runs of one job on one environment, newest first.

    Args:
        runs: Indexed runs, newest first.
        job_name: CI job.
        artifact_type: Kind of run.
        env: Environment.

    Returns:
        At most ``HISTORY_LENGTH`` runs.
    """
    history = [
        run
        for run in runs
        if (run.job_name, run.artifact_type, run.env) == (job_name, artifact_type, env)
    ]
    return history[:HISTORY_LENGTH]


def rolling_pass_rate(history: list[RunMetadata]) -> list[int]:
    """Pass rate over the last ``ROLLING_WINDOW`` runs, oldest point first.

    Args:
        history: Runs of one job, newest first.

    Returns:
        One percentage per run, in chronological order.
    """
    chronological = list(reversed(history))
    rates = []
    for index in range(len(chronological)):
        window = chronological[max(0, index - ROLLING_WINDOW + 1) : index + 1]
        passed = sum(1 for run in window if run.ci_job_status == "success")
        rates.append(round(100 * passed / len(window)))
    return rates


def pass_rate(history: list[RunMetadata]) -> int:
    """Share of the runs that succeeded, as a percentage, 0 without runs."""
    if not history:
        return 0
    passed = sum(1 for run in history if run.ci_job_status == "success")
    return round(100 * passed / len(history))


@dataclass(frozen=True)
class Streak:
    """How many runs in a row ended like the newest one."""

    count: int
    status: str


def current_streak(history: list[RunMetadata]) -> Streak:
    """Count the newest runs sharing the newest run's status.

    Args:
        history: Runs of one job, newest first.

    Returns:
        The streak, ``unknown`` and 0 without runs.
    """
    if not history:
        return Streak(0, "unknown")
    status = normalize_status(history[0].ci_job_status)
    count = 0
    for run in history:
        if normalize_status(run.ci_job_status) != status:
            break
        count += 1
    return Streak(count, status)


@dataclass(frozen=True)
class JobSummary:
    """One line of the jobs overview."""

    job_name: str
    artifact_type: str
    env: str
    latest: RunMetadata
    statuses: list[str]
    pass_rate: int
    streak: Streak


def job_summaries(runs: list[RunMetadata]) -> list[JobSummary]:
    """Summarise every job and environment of the index.

    Args:
        runs: Indexed runs, newest first.

    Returns:
        One summary per job, environment and kind, sorted by job then env.
    """
    keys = sorted({(run.job_name, run.artifact_type, run.env) for run in runs})
    summaries = []
    for job_name, artifact_type, env in keys:
        history = job_history(runs, job_name, artifact_type, env)
        recent = history[:OVERVIEW_LENGTH]
        summaries.append(
            JobSummary(
                job_name=job_name,
                artifact_type=artifact_type,
                env=env,
                latest=history[0],
                statuses=[normalize_status(r.ci_job_status) for r in reversed(recent)],
                pass_rate=pass_rate(history),
                streak=current_streak(history),
            )
        )
    return summaries
