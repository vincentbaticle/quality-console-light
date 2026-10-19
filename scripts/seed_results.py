"""Fill the results bucket with six weeks of plausible CI history.

A dashboard with three runs shows nothing. This writes what a few weeks of CI
would have left in the bucket: API, browser and load test jobs, on two
environments, a few failures that come and go, each run in the exact layout a
real upload produces (it goes through the same ``upload_run``). The data is
made up but deterministic: the same seed writes the same history.

Usage::

    python -m scripts.seed_results
"""

from dataclasses import dataclass
import datetime
import json
import os
from pathlib import Path
import random
import sys
import tempfile
from xml.sax.saxutils import escape, quoteattr

from catalog.model import load_catalog
from scripts.catalog_sql import CATALOG_FILE
from scripts.upload_results import BUCKET_VARIABLE
from test_results.k6 import SUMMARY_FILE
from test_results.layout import COVERAGE_FILE
from test_results.storage import open_bucket
from test_results.uploader import CiContext, build_metadata, upload_run

SEED = 20261008
"""Seed of the generator: the same history on every machine."""

HISTORY_DAYS = 28
"""How far back the history goes."""

FIRST_PIPELINE_ID = 184000
"""Pipeline id of the oldest seeded run; each run takes the next one."""

PROJECT_URL = "https://gitlab.example.com/qa/quality-console"
"""Project the seeded runs claim to come from."""


@dataclass(frozen=True)
class SeededJob:
    """A CI job of the made-up history."""

    name: str
    artifact_type: str
    envs: tuple[str, ...]
    meta: dict[str, str]
    tests: tuple[str, ...]
    flaky: tuple[str, ...]
    erroring: tuple[str, ...] = ()
    erroring_days: int = 0


JOBS = (
    SeededJob(
        "api-customer-welcome",
        "backend",
        ("int", "sta"),
        {
            "system": "storefront",
            "product": "customer-welcome",
            "business_capability": "engage",
            "component": "hello-api",
            "testing_scope": "integration",
            "group": "storefront-squad",
        },
        (
            "test_health",
            "test_first_visit_is_number_one",
            "test_second_visit_is_counted",
            "test_empty_username_is_refused",
            "test_closed_customer_is_refused",
            "test_unknown_username_is_refused",
            "test_balance_is_shown",
            "test_customer_without_account",
        ),
        ("test_balance_is_shown",),
    ),
    SeededJob(
        "api-bank-contract",
        "backend",
        ("int",),
        {
            "system": "bank",
            "product": "customer-welcome",
            "business_capability": "engage",
            "component": "bank-partner",
            "testing_scope": "contract",
            "group": "partners-squad",
            "tags": "microcks",
        },
        ("test_balance_contract", "test_not_found_contract", "test_currency_is_iso"),
        (),
    ),
    SeededJob(
        "api-checkout-workflow",
        "backend",
        ("int", "sta"),
        {
            "system": "orders",
            "product": "checkout",
            "business_capability": "sell",
            "component": "order-worker",
            "testing_scope": "integration",
            "group": "checkout-squad",
            "tags": "rabbitmq",
        },
        (
            "test_order_is_accepted_at_once",
            "test_order_is_paid_step_by_step",
            "test_out_of_stock_order_is_cancelled",
            "test_closed_customer_cannot_order",
        ),
        ("test_order_is_paid_step_by_step",),
    ),
    SeededJob(
        "api-account-access",
        "backend",
        ("int", "sta"),
        {
            "system": "identity",
            "product": "account-access",
            "business_capability": "protect",
            "component": "identity-service",
            "testing_scope": "integration",
            "group": "identity-squad",
            "tags": "mailbox",
        },
        (
            "test_sign_up_sends_the_set_password_email",
            "test_set_password_link_is_single_use",
            "test_sign_in_with_the_new_password",
            "test_ten_wrong_passwords_block_the_account",
            "test_reset_email_reaches_the_lowercase_address",
        ),
        ("test_reset_email_reaches_the_lowercase_address",),
    ),
    SeededJob(
        "e2e-storefront-chromium",
        "e2e",
        ("int", "sta"),
        {
            "system": "storefront",
            "product": "customer-welcome",
            "business_capability": "engage",
            "component": "front",
            "testing_scope": "e2e",
            "group": "qa-web",
            "tags": "smoke",
        },
        (
            "test_user_is_greeted_and_counted",
            "test_closed_customer_sees_an_error",
            "test_balance_is_displayed",
        ),
        ("test_user_is_greeted_and_counted",),
    ),
    SeededJob(
        "e2e-checkout-chromium",
        "e2e",
        ("int", "sta"),
        {
            "system": "orders",
            "product": "checkout",
            "business_capability": "sell",
            "component": "front",
            "testing_scope": "e2e",
            "group": "qa-web",
            "tags": "regression",
        },
        (
            "test_product_list_shows_the_stock",
            "test_order_form_refuses_a_quantity_of_zero",
            "test_order_form_refuses_six_items",
            "test_order_is_followed_until_paid",
            "test_out_of_stock_order_is_cancelled",
            "test_closed_customer_is_refused",
            "test_steps_turn_done_one_by_one",
            "test_invoice_number_is_shown",
            "test_payment_step_is_skipped_when_cancelled",
            "test_back_to_all_products",
        ),
        ("test_steps_turn_done_one_by_one",),
        ("test_invoice_number_is_shown", "test_payment_step_is_skipped_when_cancelled"),
        3,
    ),
    SeededJob(
        "perf-customer-welcome-baseline",
        "performance",
        ("sta",),
        {
            "system": "storefront",
            "product": "customer-welcome",
            "business_capability": "engage",
            "component": "hello-api",
            "testing_scope": "performance",
            "group": "qa-core",
        },
        (),
        (),
    ),
)
"""Jobs of the history, the flaky tests being the ones that sometimes fail."""

RUNS_PER_DAY = {"int": 2, "sta": 1}
"""How often each environment's pipeline runs."""

FLAKY_FAILURE_RATE = 0.15
"""Chance a flaky test fails on a given run."""


def junit_xml(
    job: SeededJob,
    failed: set[str],
    rng: random.Random,
    errors: frozenset[str] = frozenset(),
) -> str:
    """Write a JUnit report whose tests declare the job's metadata.

    A failed test broke an assertion; a test in error never reached one, its
    setup broke (a fixture, a page that never loaded). Both fail the job.
    """
    properties = "".join(
        f"<property name={quoteattr(k)} value={quoteattr(v)}/>"
        for k, v in job.meta.items()
    )
    cases = []
    for name in job.tests:
        time = f"{rng.uniform(0.05, 2.5):.3f}"
        outcome = ""
        if name in errors:
            outcome = (
                '<error message="TimeoutError: locator.click: Timeout 5000ms'
                ' exceeded">waiting for get_by_role("list", name="Workflow steps")'
                "</error>"
            )
        elif name in failed:
            outcome = (
                f'<failure message="AssertionError: {escape(name)} failed">'
                "assert response.status_code == 200</failure>"
            )
        cases.append(
            f'<testcase classname="tests.integration.{job.name.replace("-", "_")}" '
            f'name="{name}" time="{time}"><properties>{properties}</properties>'
            f"{outcome}</testcase>"
        )
    return (
        '<?xml version="1.0" encoding="utf-8"?><testsuites>'
        f'<testsuite name="pytest" tests="{len(cases)}" failures="{len(failed)}"'
        f' errors="{len(errors)}">'
        f"{''.join(cases)}</testsuite></testsuites>"
    )


def k6_summary(rng: random.Random) -> tuple[str, bool]:
    """Write a k6 summary export, and say whether its thresholds held."""
    p95 = rng.uniform(180, 560)
    failed_rate = rng.choice([0.0, 0.0, 0.0, 0.002, 0.03])
    p95_ok = p95 < 500
    failed_ok = failed_rate < 0.01
    summary = {
        "metrics": {
            "http_reqs": {
                "count": rng.randint(9000, 12000),
                "rate": rng.uniform(150, 200),
            },
            "http_req_failed": {
                "value": failed_rate,
                "thresholds": {"rate<0.01": {"ok": failed_ok}},
            },
            "http_req_duration": {
                "avg": p95 * 0.45,
                "p(95)": p95,
                "p(99)": p95 * 1.4,
                "thresholds": {"p(95)<500": {"ok": p95_ok}},
            },
        }
    }
    return json.dumps(summary, indent=2), p95_ok and failed_ok


SOURCE_ROOT = Path(__file__).resolve().parent.parent / "src"
"""The code a seeded coverage report describes, the repository's own."""

OWN_PACKAGE_RATE = (0.82, 0.97)
"""Coverage range of the package a seeded job tests."""

OTHER_PACKAGE_RATE = (0.35, 0.75)
"""Coverage range of the packages it only goes through."""

COVERAGE_DAYS = 5
"""Days of history whose backend runs carry a coverage report, the recent ones."""


def coverage_xml(job: SeededJob, rng: random.Random) -> str:
    """Write a Cobertura report over the real files of ``src/``.

    The package of the job's component is well covered, the others less: the
    shape of a real API test suite.
    """
    sources = {c.name: c.source for c in load_catalog(CATALOG_FILE).components}
    own = sources.get(job.meta["component"], "").removeprefix("src/") or "none"
    classes = []
    for file in sorted(SOURCE_ROOT.rglob("*.py")):
        path = file.relative_to(SOURCE_ROOT).as_posix()
        lines = [
            n
            for n, line in enumerate(file.read_text().splitlines(), 1)
            if line.strip() and not line.strip().startswith(("#", '"""'))
        ]
        low, high = OWN_PACKAGE_RATE if path.startswith(own) else OTHER_PACKAGE_RATE
        rate = rng.uniform(low, high)
        hits = "".join(
            f'<line number="{n}" hits="{1 if rng.random() < rate else 0}"/>'
            for n in lines
        )
        classes.append(f'<class filename="{path}"><lines>{hits}</lines></class>')
    return (
        '<?xml version="1.0" ?><coverage><packages><package name="src"><classes>'
        f"{''.join(classes)}</classes></package></packages></coverage>"
    )


def write_reports(
    job: SeededJob, reports: Path, rng: random.Random, day: int = HISTORY_DAYS
) -> bool:
    """Write one run's report files, and say whether the job succeeded.

    The tests a job lists as erroring are in error in its runs of the last
    ``erroring_days`` days: a job of ten tests, eight passing, failed as a whole.
    """
    if job.artifact_type == "performance":
        summary, ok = k6_summary(rng)
        (reports / SUMMARY_FILE).write_text(summary)
        verdict = "passed" if ok else "thresholds broken"
    else:
        failed = {t for t in job.flaky if rng.random() < FLAKY_FAILURE_RATE}
        errors = frozenset(job.erroring) if day <= job.erroring_days else frozenset()
        (reports / "junit.xml").write_text(junit_xml(job, failed - errors, rng, errors))
        ok = not failed and not errors
        broken = len(failed | errors)
        verdict = f"{len(job.tests) - broken}/{len(job.tests)} passed"
    (reports / "report.html").write_text(
        f"<!doctype html><title>{job.name}</title><h1>{job.name}</h1>"
        f"<p>Seeded run: {verdict}.</p>"
    )
    return ok


def main() -> int:
    """Write the whole history into the bucket.

    Returns:
        The process exit code.
    """
    rng = random.Random(SEED)  # noqa: S311
    bucket = open_bucket(os.environ[BUCKET_VARIABLE])
    today = datetime.datetime.now(datetime.UTC).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    pipeline_id = FIRST_PIPELINE_ID
    count = 0
    for day in range(HISTORY_DAYS, 0, -1):
        for env, per_day in RUNS_PER_DAY.items():
            for slot in range(per_day):
                pipeline_id += 1
                started = today - datetime.timedelta(days=day, hours=-6 - slot * 8)
                for job in (j for j in JOBS if env in j.envs):
                    with tempfile.TemporaryDirectory() as folder:
                        reports = Path(folder)
                        ok = write_reports(job, reports, rng, day)
                        if job.artifact_type == "backend" and day <= COVERAGE_DAYS:
                            (reports / COVERAGE_FILE).write_text(coverage_xml(job, rng))
                        ci = CiContext(
                            pipeline_id=str(pipeline_id),
                            job_id=str(pipeline_id * 10 + JOBS.index(job)),
                            job_name=job.name,
                            commit_sha=f"{rng.getrandbits(32):08x}",
                            job_status="success" if ok else "failed",
                            project_url=PROJECT_URL,
                        )
                        now = started + datetime.timedelta(minutes=JOBS.index(job) * 3)
                        metadata = build_metadata(
                            job.artifact_type, env, ci, reports, now
                        )
                        upload_run(bucket, metadata, reports, now)
                    count += 1
    print(f"[seed-results] {count} runs written to gs://{bucket.name}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
