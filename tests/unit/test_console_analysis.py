"""The analyses behind the newer console tools: footprint, designs, recordings."""

import json
from pathlib import Path
import random
import re
from typing import Any, cast

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from fastapi.testclient import TestClient
import httpx
import pytest

from company_db import DatabaseSettings
from quality_console.announcements import (
    load_announcements,
    parse_versions,
    starting_points,
)
from quality_console.designs import load_designs, mermaid, parse_design
from quality_console.docs_files import load_docs
from quality_console.footprint import (
    AMBIGUOUS,
    CALLED_AGAIN,
    COLLEAGUE_TABLES,
    COMPANY_TABLES,
    LOOPING_TABLES,
    ORPHAN,
    OWNED,
    PAUSE_SECONDS,
    RUNS,
    RUNS_PART,
    RUNS_PER_BATCH,
    SAME_CALL,
    SAME_QUERY,
    SEVERAL_CALLERS,
    SEVERAL_QUERIES,
    SEVERAL_SERVICES,
    SKIPPED,
    STOREFRONT,
    TARGETS,
    TEST_OWN,
    ApiCall,
    ApiHit,
    Experiment,
    FrontVisit,
    MessageHit,
    PathNode,
    Run,
    SpanAccess,
    StepSeen,
    TableHits,
    TracedAccess,
    api_hints,
    colleague_tables,
    demo_run,
    looping_colleague,
    merge_windows,
    message_hints,
    narrow,
    optimization_hints,
    pick_trace,
    span_accesses,
    span_count,
    tables_in_statement,
    touched,
    trace_api_hits,
    trace_id_of,
    trace_message_hits,
    trace_path,
    traced_accesses,
    window_tables,
)
from quality_console.footprint_lab import FootprintLab
from quality_console.gherkin_files import load_features, parse_feature
from quality_console.recordings import load_recordings
from quality_console.table_kinds import (
    bucket_kind,
    database_kind,
    feature_kind,
    table_kind,
)
from quality_console.tools import doc_of
from quality_console.tools.apis import mock_name
from quality_console.tools.footprint import footprint_router
from quality_console.tools.gherkin import driven_by, tool_counts
from tests.metadata import metadata_test
from tests.neighbours import PROJECT_ROOT

pytestmark = [
    pytest.mark.unit,
    metadata_test(
        system="quality",
        product="quality-console",
        business_capability="operate",
        component="quality-console",
        group="qa-core",
        testing_scope="unit",
    ),
]

DESIGN = """
title: Tiny
product: checkout
purpose: Two ways out.
nodes:
  - {id: a, label: "Start", kind: start}
  - {id: b, label: "Ok?", kind: check}
  - {id: c, label: "Done", kind: outcome}
  - {id: d, label: "Refused", kind: failure}
edges:
  - {from: a, to: b, label: go}
  - {from: b, to: c, label: "yes"}
  - {from: b, to: d, label: "no"}
scenarios:
  - scenario: It works
    feature: checkout/place-order.feature
    path: [a, b, c]
"""
"""A design with one scenario and one transition no scenario walks."""


def test_colleagues_are_loud_first_then_quieter_in_each_batch() -> None:
    rng = random.Random(4)  # noqa: S311

    picked = [colleague_tables(index, rng) for index in range(RUNS)]

    assert [len(tables) for tables in picked] == [
        count for batch in COLLEAGUE_TABLES for count in batch
    ]
    for batch in COLLEAGUE_TABLES:
        assert len(batch) == RUNS_PER_BATCH
        assert batch == tuple(sorted(batch, reverse=True))


def test_the_looping_colleague_is_there_for_the_whole_first_batch_only() -> None:
    rng = random.Random(4)  # noqa: S311
    looping = looping_colleague(rng)

    picked = [colleague_tables(index, rng, looping) for index in range(RUNS)]

    assert len(looping) == LOOPING_TABLES
    assert all(set(looping) <= set(tables) for tables in picked[:RUNS_PER_BATCH])
    assert not set(looping) <= set(picked[-1])


def test_counters_compared_give_the_tables_touched_in_between() -> None:
    before = {"customers": (10, 0), "orders": (5, 2), "reviews": (1, 0)}
    after = {
        "customers": (11, 0),
        "orders": (5, 3),
        "reviews": (1, 0),
        "coupons": (2, 0),
    }

    assert touched(before, after) == [
        TableHits("customers", 1, 0),
        TableHits("orders", 0, 1),
        TableHits("coupons", 2, 0),
    ]


def test_each_run_keeps_only_the_candidates_it_sees_again() -> None:
    first, _ = narrow(None, [TableHits("customers", 1, 0), TableHits("reviews", 1, 0)])
    kept, dropped = narrow(first, [TableHits("customers", 1, 0)])

    assert first == ["customers", "reviews"]
    assert (kept, dropped) == (["customers"], ["reviews"])


def test_a_statement_names_its_company_tables_and_what_it_does_to_them() -> None:
    statement = (
        "SELECT c.username, a.balance_cents FROM bank_accounts a"
        " JOIN `customers` c ON c.id = a.customer_id"
        " JOIN performance_schema.x p ON 1"
    )
    insert = "INSERT INTO payments (amount) SELECT 1 FROM payment_methods"

    assert tables_in_statement(statement) == [
        ("bank_accounts", "read"),
        ("customers", "read"),
    ]
    assert tables_in_statement(insert) == [
        ("payments", "write"),
        ("payment_methods", "read"),
    ]
    assert tables_in_statement("DELETE FROM coupons WHERE id = 1") == [
        ("coupons", "write")
    ]


TEMPO_TRACE = {
    "batches": [
        {
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "hello-api"}}
                ]
            },
            "scopeSpans": [
                {
                    "spans": [
                        {
                            "name": "SELECT",
                            "attributes": [
                                {"key": "db.system", "value": {"stringValue": "mysql"}},
                                {
                                    "key": "db.name",
                                    "value": {"stringValue": "mycompany"},
                                },
                                {
                                    "key": "db.statement",
                                    "value": {"stringValue": "SELECT * FROM customers"},
                                },
                            ],
                        },
                        {
                            "name": "INSERT",
                            "attributes": [
                                {"key": "db.system", "value": {"stringValue": "mysql"}},
                                {
                                    "key": "db.name",
                                    "value": {"stringValue": "orchestrator"},
                                },
                                {
                                    "key": "db.statement",
                                    "value": {"stringValue": "INSERT INTO workflows"},
                                },
                            ],
                        },
                        {
                            "name": "INSERT",
                            "attributes": [
                                {"key": "db.system", "value": {"stringValue": "mysql"}},
                                {
                                    "key": "db.name",
                                    "value": {"stringValue": "mycompany"},
                                },
                                {
                                    "key": "db.statement",
                                    "value": {
                                        "stringValue": "INSERT INTO orders VALUES (1)"
                                    },
                                },
                            ],
                        },
                        {
                            "name": "INCRBY",
                            "attributes": [
                                {"key": "db.system", "value": {"stringValue": "redis"}},
                                {
                                    "key": "db.statement",
                                    "value": {"stringValue": "INCRBY ? ?"},
                                },
                            ],
                        },
                    ]
                }
            ],
        }
    ]
}
"""A trace as Tempo's ``/api/traces/<id>`` answers it, cut to four spans."""


def test_a_trace_names_the_company_tables_its_sql_spans_touch() -> None:
    assert traced_accesses(TEMPO_TRACE) == [
        TracedAccess("hello-api", "customers", "read"),
        TracedAccess("hello-api", "orders", "write"),
    ]


def test_the_trace_picked_is_the_first_one_started_during_the_run() -> None:
    search = {
        "traces": [
            {"traceID": "before", "startTimeUnixNano": "900"},
            {"traceID": "second", "startTimeUnixNano": "1500"},
            {"traceID": "first", "startTimeUnixNano": "1100"},
            {"traceID": "after", "startTimeUnixNano": "2100"},
        ]
    }

    assert pick_trace(search, 1000, 2000) == "first"
    assert pick_trace({"traces": []}, 1000, 2000) is None


def test_an_experiment_reports_its_progress_and_the_tables_used() -> None:
    experiment = Experiment("x", TARGETS["hello"], trace_timeout=10)
    hits = [TableHits("customers", 1, 0), TableHits("reviews", 1, 0)]
    step = StepSeen("api", "GET /api/hello?username=ada", "HTTP 200", ["customers"])
    experiment.runs.append(
        Run(1, 900, hits, ["reviews"], ["customers", "reviews"], [], steps=[step])
    )

    assert 0 < experiment.progress < 100 / RUNS
    assert experiment.used == ["customers", "reviews"]
    state = experiment.to_json()
    assert state["runs"][0]["hits"][0] == {
        "table": "customers",
        "reads": 1,
        "writes": 0,
    }
    assert state["runs"][0]["batch"] == 1
    assert state["runs"][0]["steps"][0]["tables"] == ["customers"]
    assert not state["checked"]


def test_the_progress_follows_time_so_the_pause_weighs_its_seconds() -> None:
    experiment = Experiment("x", TARGETS["sql-only"], pause_seconds=PAUSE_SECONDS)
    experiment.runs += [Run(n, 1000, [], [], [], []) for n in range(RUNS_PER_BATCH)]
    total = RUNS + PAUSE_SECONDS

    experiment.pause_left = PAUSE_SECONDS
    first_batch = experiment.progress
    experiment.pause_left = 0
    after_pause = experiment.progress

    assert first_batch == pytest.approx(RUNS_PART * RUNS_PER_BATCH / total * 100, abs=1)
    assert after_pause == pytest.approx(
        RUNS_PART * (RUNS_PER_BATCH + PAUSE_SECONDS) / total * 100, abs=1
    )
    assert Run(RUNS_PER_BATCH + 1, 900, [], [], [], []).batch == 2


def test_the_targets_cover_api_only_sql_only_and_both() -> None:
    kinds = {key: [s.kind for s in t.steps] for key, t in TARGETS.items()}

    assert kinds["api-only"] == ["api"]
    assert kinds["sql-only"] == ["sql"]
    assert kinds["hello"] == ["api"]
    assert kinds["hello-then-sql"] == ["api", "sql"]
    assert kinds["front-api"] == ["front", "api"]
    assert kinds["front-api-redirect"] == ["front", "api", "front"]
    assert kinds["orphan-tables"] == ["api", "api"]
    hello = TARGETS["hello"].steps[0]
    assert isinstance(hello, ApiCall)
    assert hello.trace_query == (
        '{ resource.service.name = "hello-api" && name = "GET /api/hello" }'
    )


def test_the_test_own_sql_names_its_tables_without_a_trace() -> None:
    experiment = Experiment("x", TARGETS["sql-only"])

    assert experiment.checked
    assert experiment.exact == ["products", "stock_levels"]
    assert [node.kind for node in experiment.path] == ["sql", "table", "table"]


def test_an_api_call_waits_for_its_trace_then_joins_the_path() -> None:
    experiment = Experiment("x", TARGETS["hello-then-sql"])
    unchecked = experiment.path
    experiment.traced_steps[0] = trace_path(PATH_TRACE)

    assert [node.kind for node in unchecked][:2] == ["api", "sql"]
    assert experiment.checked
    assert [node.label for node in experiment.path] == [
        "GET /api/hello",
        "customers",
        "GET /accounts/{username}",
        "bank_accounts",
        "customers",
        "SQL: ada's address and preferences",
        "customers",
        "customer_addresses",
        "customer_preferences",
    ]
    assert [(api.label, api.service) for api in experiment.apis] == [
        ("GET /api/hello?username=ada", "the test"),
        ("GET /api/hello", "hello-api"),
        ("GET /accounts/{username}", "bank-partner"),
    ]


def test_a_front_opens_the_path_and_a_redirect_marks_the_next_one() -> None:
    experiment = Experiment("x", TARGETS["front-api-redirect"])
    experiment.traced_steps[1] = trace_path(PATH_TRACE)
    console_trace = {
        "batches": [
            _batch(
                "quality-console",
                _span(
                    "GET /databases/{database}/tables/{table}", 1, "SPAN_KIND_SERVER"
                ),
                _span("SELECT", 2, "SPAN_KIND_CLIENT", "SELECT * FROM customers"),
            )
        ]
    }
    unchecked = experiment.checked
    experiment.traced_steps[2] = trace_path(console_trace)

    assert not unchecked
    assert experiment.checked
    path = experiment.path
    assert [(n.kind, n.operation) for n in path if n.kind == "front"] == [
        ("front", ""),
        ("front", "redirect"),
    ]
    assert [n.label for n in path[-2:]] == [
        "Quality Console: the customers table",
        "customers",
    ]
    assert [f.service for f in experiment.fronts] == ["storefront", "quality-console"]
    assert experiment.to_json()["traced_steps"] == 2
    page = experiment.target.steps[2]
    assert isinstance(page, FrontVisit)
    assert page.trace_query == (
        '{ resource.service.name = "quality-console"'
        ' && name = "GET /databases/mycompany/tables/customers" }'
    )


def _span(name: str, start: int, kind: str, statement: str | None = None) -> dict:
    """One span of a Tempo trace, SQL on the company database when a statement."""
    attributes = []
    if statement:
        attributes = [
            {"key": "db.system", "value": {"stringValue": "mysql"}},
            {"key": "db.name", "value": {"stringValue": "mycompany"}},
            {"key": "db.statement", "value": {"stringValue": statement}},
        ]
    return {
        "name": name,
        "kind": kind,
        "startTimeUnixNano": str(start),
        "attributes": attributes,
    }


def _batch(service: str, *spans: dict) -> dict:
    """The spans of one service in a Tempo trace."""
    resource = [{"key": "service.name", "value": {"stringValue": service}}]
    return {"resource": {"attributes": resource}, "scopeSpans": [{"spans": spans}]}


PATH_TRACE = {
    "batches": [
        _batch(
            "hello-api",
            _span("GET /api/hello", 1, "SPAN_KIND_SERVER"),
            _span("SELECT", 2, "SPAN_KIND_CLIENT", "SELECT * FROM customers"),
            _span("SELECT", 3, "SPAN_KIND_CLIENT", "SELECT * FROM customers"),
            _span("GET", 4, "SPAN_KIND_CLIENT"),
        ),
        _batch(
            "bank-partner",
            _span("GET /accounts/{username}", 5, "SPAN_KIND_SERVER"),
            _span(
                "SELECT",
                6,
                "SPAN_KIND_CLIENT",
                "SELECT * FROM bank_accounts JOIN customers c",
            ),
        ),
    ]
}
"""The hello call: hello-api reads customers, then asks the bank partner."""


def test_a_trace_draws_the_apis_and_their_tables_in_the_order_they_ran() -> None:
    path = trace_path(PATH_TRACE)

    assert path == [
        PathNode("api", "GET /api/hello", "hello-api"),
        PathNode("table", "customers", "hello-api", "read"),
        PathNode("api", "GET /accounts/{username}", "bank-partner"),
        PathNode("table", "bank_accounts", "bank-partner", "read"),
        PathNode("table", "customers", "bank-partner", "read"),
    ]


def test_a_service_back_on_the_path_shows_its_api_again() -> None:
    trace = {
        "batches": [
            _batch(
                "hello-api",
                _span("POST /api/orders", 1, "SPAN_KIND_SERVER"),
                _span("SELECT", 2, "SPAN_KIND_CLIENT", "SELECT 1 FROM products"),
                _span("INSERT", 5, "SPAN_KIND_CLIENT", "INSERT INTO orders VALUES"),
            ),
            _batch(
                "order-worker",
                _span("order-workflow receive", 3, "SPAN_KIND_CONSUMER"),
                _span("UPDATE", 4, "SPAN_KIND_CLIENT", "UPDATE stock_levels SET"),
            ),
        ]
    }

    assert [(n.kind, n.label) for n in trace_path(trace)] == [
        ("api", "POST /api/orders"),
        ("table", "products"),
        ("event", "order-workflow receive"),
        ("table", "stock_levels"),
        ("api", "POST /api/orders"),
        ("table", "orders"),
    ]


def test_tables_written_by_the_storefront_are_live_the_others_static() -> None:
    assert table_kind("mycompany", "orders") == "live"
    assert table_kind("mycompany", "customers") == "static"
    assert table_kind("identity", "accounts") == "live"
    assert table_kind("catalog", "systems") == "static"
    assert [database_kind(d) for d in ("mycompany", "orchestrator", "catalog")] == [
        "mixed",
        "live",
        "static",
    ]


def test_the_footprint_knows_every_table_of_the_schema() -> None:
    schema = (PROJECT_ROOT / "db" / "01-schema.sql").read_text()

    assert list(COMPANY_TABLES) == re.findall(r"CREATE TABLE (\w+)", schema)


def test_a_design_shows_its_gaps_and_highlights_a_path() -> None:
    design = parse_design(DESIGN, "tiny")

    diagram = mermaid(design, "It works")

    assert [(e.source, e.target) for e in design.gaps] == [("b", "d")]
    assert "linkStyle 0 stroke:#2563eb" in diagram
    assert "linkStyle 2 stroke:#ef4444" in diagram
    assert 'b{{"Ok?"}}:::check' in diagram


def test_a_design_names_a_scenario_that_does_not_exist() -> None:
    design = parse_design(DESIGN.replace("It works", "Nothing"), "tiny")

    assert design.problems(set()) == [
        "no scenario 'Nothing' in checkout/place-order.feature"
    ]


def test_every_design_of_the_repository_holds_together() -> None:
    scenarios = {
        (f.path, s.name)
        for f in load_features(PROJECT_ROOT / "features")
        for s in f.scenarios
    }

    for design in load_designs(PROJECT_ROOT / "designs"):
        assert design.problems(scenarios) == [], design.key
        assert design.paths
        assert mermaid(design, design.paths[0].name).startswith("flowchart TD")


def test_an_outline_keeps_its_examples() -> None:
    feature = parse_feature(
        "Feature: F\n  Scenario Outline: O\n    Given <x>\n    Examples:\n"
        "      | x |\n      | 1 |\n      | 2 |\n",
        "s/f.feature",
    )

    assert feature.scenarios[0].examples == [["x"], ["1"], ["2"]]
    assert feature.scenarios[0].steps[0].table == []


def test_recordings_read_the_journals_and_the_committed_examples(
    tmp_path: Path,
) -> None:
    journal = {
        "captured_at": "2026-10-08T10:00:00+00:00",
        "records": [
            {
                "example": "ada",
                "request": {"username": "ada"},
                "status": 200,
                "body": {"balance_cents": 1},
            }
        ],
    }
    (tmp_path / "journal.json").write_text(json.dumps(journal))

    bank, events = load_recordings(tmp_path, PROJECT_ROOT / "contracts")

    assert bank.captured_at == journal["captured_at"]
    assert bank.entries[0].sent == "GET /balance?username=ada"
    origins = {e.name: e.origin for e in bank.examples}
    assert origins["ada"] == "captured, in the journal"
    assert origins["unknown-account"] == "written by hand"
    assert events.captured_at is None
    assert {e.name for e in events.examples} == {"paid-order", "out-of-stock-order"}


def test_buckets_and_features_tell_whether_using_the_stack_changes_them() -> None:
    assert bucket_kind("test-results") == "live"
    assert bucket_kind("finance-exports") == "static"
    assert feature_kind("checkout") == "live"
    assert feature_kind("bucket-checks") == "static"


def test_the_trace_id_is_read_from_the_traceparent_sent() -> None:
    trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"

    assert trace_id_of(f"00-{trace_id}-00f067aa0ba902b7-01") == trace_id
    assert trace_id_of("garbage") is None
    assert trace_id_of(None) is None
    assert span_count(TEMPO_TRACE) == 4


def test_the_documentation_groups_its_pages_and_keeps_links_inside() -> None:
    docs = {doc.slug: doc for doc in load_docs(PROJECT_ROOT / "docs")}

    assert docs["testing-with-testcontainers"].group == "Guides"
    assert docs["sonar-decom"].group == "Guides"
    assert docs["demos/testcontainers"].group == "Demo scripts"
    assert docs["order-workflow"].group == "Products"
    guide = docs["testing-with-testcontainers"].html
    assert 'href="/tools/docs?page=gherkin"' in guide
    assert 'href="/tools/docs?page=demos/testcontainers"' in guide


def test_each_tool_page_knows_its_documentation_page() -> None:
    assert doc_of("/test-results/trends") == "/tools/docs?page=test-results"
    assert doc_of("/databases/mycompany/tables/orders") == "/tools/docs?page=databases"
    assert doc_of("/devx/retro-footprint") == "/tools/docs?page=retro-footprint"
    assert doc_of("/") is None


def test_fronts_and_apis_say_in_how_many_runs_their_step_was_played() -> None:
    experiment = Experiment("x", TARGETS["front-api"])
    played = [
        StepSeen("front", STOREFRONT.title, "HTTP 200", []),
        StepSeen("api", "GET /api/hello?username=ada", "HTTP 200", []),
    ]
    skipped = [played[0], StepSeen("api", played[1].title, SKIPPED, [])]
    experiment.runs += [
        Run(1, 900, [], [], [], [], steps=played),
        Run(2, 900, [], [], [], [], steps=skipped),
    ]

    state = experiment.to_json()

    assert [front["runs"] for front in state["fronts"]] == [2]
    assert [api["runs"] for api in state["apis"]] == [1]
    assert not state["demo"]


def test_the_simulated_examples_are_drawn_the_same_every_time() -> None:
    def draw() -> list[list[str]]:
        rng = random.Random("demo-ambiguous")  # noqa: S311
        candidates: list[str] | None = None
        kept = []
        for index in range(RUNS):
            run = demo_run(AMBIGUOUS, index, rng, candidates)
            candidates = run.candidates
            kept.append(candidates)
        return kept

    assert draw() == draw()


def test_a_job_looping_seven_runs_hides_the_test_tables_until_run_eight() -> None:
    rng = random.Random("demo-ambiguous")  # noqa: S311
    candidates: list[str] | None = None
    after: dict[int, list[str]] = {}
    for index in range(RUNS):
        run = demo_run(AMBIGUOUS, index, rng, candidates)
        candidates = run.candidates
        after[run.number] = candidates
    job_only = set(AMBIGUOUS.looping) - {a.table for a in AMBIGUOUS.accesses}

    assert job_only <= set(after[AMBIGUOUS.looping_runs])
    assert not job_only & set(after[AMBIGUOUS.looping_runs + 1])


def test_a_simulated_experiment_calls_nothing_and_reads_its_own_traces() -> None:
    nowhere = DatabaseSettings("nowhere.invalid", 1, "nobody", "", "none")
    lab = FootprintLab(nowhere, httpx.Client(), None, pause_seconds=0, demo_run_ms=0)
    experiment = Experiment("x", TARGETS["demo-crowded"])

    lab.run(experiment)

    state = experiment.to_json()
    assert experiment.error is None
    assert state["done"] and state["checked"] and state["demo"]
    assert len(state["runs"]) == RUNS
    assert len(state["fronts"]) == 5
    assert len(state["apis"]) > 10
    assert any(api["runs"] < RUNS for api in state["apis"])
    assert any(s["outcome"] == SKIPPED for r in state["runs"] for s in r["steps"])


def test_the_gherkin_filter_counts_and_keeps_the_features_of_one_tool() -> None:
    features = load_features(PROJECT_ROOT / "features")
    counts = dict(tool_counts(features))

    assert counts["pytest"] >= counts["playwright"] > 0
    assert sum(counts.values()) >= len(features)
    assert {f.path for f in driven_by(features, "playwright")} == {
        f.path for f in features if "playwright" in f.tools
    }
    assert driven_by(features, "") == features
    untagged = parse_feature("Feature: no tool\n", "x/untagged.feature")
    assert driven_by([untagged], "other") == [untagged]


def _finished(key: str) -> Experiment:
    """A simulated experiment run to its end, without the lab."""
    target = TARGETS[key]
    assert target.demo is not None
    experiment = Experiment("x", target)
    rng = random.Random(key)  # noqa: S311
    candidates: list[str] | None = None
    for index in range(RUNS):
        run = demo_run(target.demo, index, rng, candidates)
        candidates = run.candidates
        experiment.runs.append(run)
    experiment.traced_steps = {n: s.path for n, s in enumerate(target.demo.steps)}
    experiment.traced = target.demo.accesses
    experiment.spans = target.demo.spans
    experiment.window_state = "skipped"
    return experiment


def test_the_final_answer_waits_for_both_witnesses() -> None:
    experiment = _finished("demo-wide")
    early = Experiment("x", TARGETS["demo-wide"])
    early.runs = experiment.runs[:3]

    assert early.final == []
    assert experiment.to_json()["final"] == experiment.final


def test_the_final_answer_waits_for_the_run_windows_but_not_for_their_success() -> None:
    experiment = _finished("demo-wide")
    experiment.window_state = "active"
    assert experiment.final == []

    experiment.window_state = "failed"
    assert experiment.final != []


def test_spans_only_from_off_the_path_make_a_counted_table_a_colleague() -> None:
    experiment = _finished("demo-wide")
    experiment.window_state = "done"

    experiment.windows = merge_windows([{"audit_logs": {"nightly-job"}}] * RUNS)
    sources = {n["label"]: n["source"] for n in experiment.final}
    assert sources["audit_logs"] == "colleague"

    on_path = sorted(experiment.path_services)[0]
    experiment.windows = merge_windows([{"audit_logs": {on_path}}] * RUNS)
    sources = {n["label"]: n["source"] for n in experiment.final}
    assert sources["audit_logs"] == "counted"


def test_the_test_s_own_sql_puts_the_console_on_its_path() -> None:
    assert "quality-console" in Experiment("x", TARGETS["sql-only"]).path_services
    assert "quality-console" not in Experiment("x", TARGETS["hello"]).path_services


def test_the_final_answer_adds_what_only_the_database_counted() -> None:
    final = _finished("demo-wide").final
    tables = [n for n in final if n["kind"] == "table"]
    kinds = [n["kind"] for n in final]

    assert kinds[:10] == ["front"] * 10
    assert len(tables) == len(COMPANY_TABLES)
    assert [t["label"] for t in tables if t["source"] == "counted"] == ["audit_logs"]
    assert tables[-1]["label"] == "audit_logs"
    assert "write" in tables[-1]["operation"]


def test_the_final_answer_marks_a_table_named_but_not_seen_every_run() -> None:
    final = _finished("demo-ambiguous").final

    sources = {n["label"]: n["source"] for n in final if n["kind"] == "table"}
    assert sources["customers"] == "both"
    assert sources["reviews"] == "named"


def test_a_real_analysis_running_refuses_another_but_not_a_simulated_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(FootprintLab, "run", lambda self, experiment, rng=None: None)
    nowhere = DatabaseSettings("nowhere.invalid", 1, "nobody", "", "none")
    lab = FootprintLab(nowhere, httpx.Client(), None)
    app = FastAPI()
    app.include_router(footprint_router(lab, Jinja2Templates(directory=".")))
    client = TestClient(app)

    def start(target: str) -> str:
        answer = client.post(
            "/devx/retro-footprint/run",
            params={"target": target},
            follow_redirects=False,
        )
        return answer.headers["location"]

    first = start("hello")
    running = lab.running()
    assert running is not None
    assert first.endswith(f"experiment={running.id}")
    assert start("api-only") == (
        f"/devx/retro-footprint?target=hello&experiment={running.id}&busy=true"
    )
    assert "busy" not in start("demo-wide")
    assert lab.running() is running
    running.done = True
    assert lab.running() is None


def test_an_openapi_contract_is_mocked_under_its_name() -> None:
    assert mock_name("contracts/bank-partner-openapi.yaml") == "bank-partner"
    assert mock_name("contracts/order-workflow-asyncapi.yaml") is None
    assert mock_name(None) is None


def test_the_versions_footer_says_where_the_next_announcement_starts() -> None:
    line = "_Versions: quality-console v1.2.0 · results-plugin (portal) v2.3.0_"

    assert parse_versions(line) == {
        "quality-console": "1.2.0",
        "results-plugin (portal)": "2.3.0",
    }


def test_the_announcements_of_the_repository_chain_their_versions() -> None:
    found = load_announcements(PROJECT_ROOT / "announcements")

    assert [(a.system, a.version) for a in found] == [
        ("quality", "1.2.0"),
        ("quality", "1.1.0"),
    ]
    newest = found[0]
    assert newest.title.startswith("🚀 Quality platform 1.2.0")
    assert newest.tickets == []
    assert 3 <= len(newest.blocks) <= 6
    assert sum(len(block) for block in newest.blocks) + 3 <= 15
    assert starting_points(found) == {"quality": {"quality-console": "1.2.0"}}


WINDOW_SEARCH = {
    "traces": [
        {
            "rootServiceName": "quality-console",
            "spanSets": [
                {
                    "spans": [
                        {
                            "attributes": [
                                {
                                    "key": "db.statement",
                                    "value": {"stringValue": "SELECT * FROM customers"},
                                },
                                {
                                    "key": "service.name",
                                    "value": {"stringValue": "hello-api"},
                                },
                            ]
                        }
                    ]
                }
            ],
        },
        {
            "rootServiceName": "quality-console",
            "spanSet": {
                "spans": [
                    {
                        "attributes": [
                            {
                                "key": "db.statement",
                                "value": {"stringValue": "SELECT 1 FROM `reviews`"},
                            }
                        ]
                    }
                ]
            },
        },
    ]
}
"""A Tempo search of one run window: the API's SQL inside a trace the lab
started, and a colleague's query, its span naming no service."""


def test_a_run_window_names_each_table_with_the_services_that_sent_its_sql() -> None:
    assert window_tables(WINDOW_SEARCH) == {
        "customers": {"hello-api"},
        "reviews": {"quality-console"},
    }
    merged = merge_windows([window_tables(WINDOW_SEARCH), {"customers": {"hello-api"}}])
    assert [(w.table, w.runs, w.services) for w in merged] == [
        ("customers", 2, ["hello-api"]),
        ("reviews", 1, ["quality-console"]),
    ]


def test_a_run_window_leaves_out_the_test_calls_of_the_other_runs() -> None:
    traces = cast(list[dict[str, Any]], WINDOW_SEARCH["traces"])
    search = {
        "traces": [
            {**traces[0], "traceID": "run-2-call"},
            {**traces[1], "traceID": "colleague"},
        ]
    }

    assert window_tables(search, others={"run-2-call"}) == {
        "reviews": {"quality-console"}
    }
    assert window_tables(search) == window_tables(WINDOW_SEARCH)


def test_the_final_answer_says_who_sent_the_sql_of_each_table() -> None:
    experiment = Experiment("x", TARGETS["sql-only"])
    experiment.runs = [
        Run(
            n,
            900,
            [TableHits("products", 1, 0), TableHits("stock_levels", 1, 0)],
            [],
            ["products", "stock_levels"],
            [],
        )
        for n in range(1, RUNS + 1)
    ]
    experiment.windows = merge_windows([{"products": {"the-test"}}] * RUNS)
    experiment.window_state = "done"

    details = {
        n["label"]: n["detail"] for n in experiment.final if n["kind"] == "table"
    }

    assert details["products"] == f"SQL from the-test in {RUNS}/{RUNS} windows"
    assert details["stock_levels"] == "no SQL span in the run windows"
    assert experiment.to_json()["window"]["tables"][0]["table"] == "products"


def _sql_span(service: str, team: str | None, statement: str) -> dict[str, object]:
    """One batch of an OTLP trace: a service, its team if declared, one SQL span."""
    resource = [{"key": "service.name", "value": {"stringValue": service}}]
    if team:
        resource.append({"key": "team", "value": {"stringValue": team}})
    span = {
        "name": "SELECT",
        "attributes": [
            {"key": "db.system", "value": {"stringValue": "mysql"}},
            {"key": "db.name", "value": {"stringValue": "mycompany"}},
            {"key": "db.statement", "value": {"stringValue": statement}},
        ],
    }
    return {"resource": {"attributes": resource}, "scopeSpans": [{"spans": [span]}]}


def test_each_traced_access_carries_the_team_its_service_declares() -> None:
    trace = {
        "batches": [
            _sql_span("hello-api", "storefront-squad", "SELECT 1 FROM customers"),
            _sql_span("newsletter-service", None, "SELECT 1 FROM newsletters"),
        ]
    }

    assert traced_accesses(trace) == [
        TracedAccess("hello-api", "customers", "read", "storefront-squad"),
        TracedAccess("newsletter-service", "newsletters", "read", ""),
    ]


def test_the_newsletter_call_is_searched_under_its_own_service() -> None:
    newsletters = TARGETS["orphan-tables"].steps[1]

    assert isinstance(newsletters, ApiCall)
    assert newsletters.api == "newsletter"
    assert newsletters.trace_query == (
        '{ resource.service.name = "newsletter-service"'
        ' && name = "GET /newsletters/ada" }'
    )


def _orphan_run() -> Experiment:
    """The orphan tables test run to its end: hello-api declared, newsletters not."""
    tables = [
        "customers",
        "bank_accounts",
        "customer_preferences",
        "newsletter_subscriptions",
        "newsletters",
    ]
    experiment = Experiment("x", TARGETS["orphan-tables"])
    experiment.runs = [
        Run(n, 900, [TableHits(t, 1, 0) for t in tables], [], tables, [])
        for n in range(1, RUNS + 1)
    ]
    hello = [
        TracedAccess("hello-api", "customers", "read", "storefront-squad"),
        TracedAccess("bank-partner", "bank_accounts", "read", "partners-squad"),
    ]
    newsletters = [
        TracedAccess("newsletter-service", "customers", "read"),
        TracedAccess("newsletter-service", "customer_preferences", "read"),
        TracedAccess("newsletter-service", "newsletter_subscriptions", "read"),
    ]
    experiment.traced = hello + newsletters
    experiment.traced_steps = {
        0: [PathNode("api", "GET /api/hello", "hello-api")]
        + [PathNode("table", a.table, a.service, a.operation) for a in hello],
        1: [PathNode("api", "GET /newsletters/{username}", "newsletter-service")]
        + [PathNode("table", a.table, a.service, a.operation) for a in newsletters],
    }
    experiment.window_state = "skipped"
    return experiment


def test_a_table_no_declared_team_names_is_an_orphan() -> None:
    ownership = {o["table"]: o for o in _orphan_run().ownership}

    assert ownership["customers"]["status"] == OWNED
    assert ownership["customers"]["teams"] == ["storefront-squad"]
    assert ownership["bank_accounts"]["teams"] == ["partners-squad"]
    assert ownership["customer_preferences"]["status"] == ORPHAN
    assert "newsletter-service" in ownership["customer_preferences"]["why"]
    assert ownership["newsletters"]["status"] == ORPHAN
    assert ownership["newsletters"]["why"] == (
        "counted by the database, no span names it"
    )
    assert [o["status"] for o in _orphan_run().to_json()["ownership"]][:3] == [
        ORPHAN
    ] * 3


def test_ownership_waits_for_the_final_answer_and_needs_a_trace() -> None:
    early = Experiment("x", TARGETS["orphan-tables"])
    sql_only = Experiment("x", TARGETS["sql-only"])
    sql_only.runs = [
        Run(n, 900, [TableHits("products", 1, 0)], [], ["products"], [])
        for n in range(1, RUNS + 1)
    ]
    sql_only.window_state = "skipped"

    assert early.ownership == []
    assert sql_only.final != []
    assert sql_only.ownership == []


def test_a_simulated_trigger_writes_an_orphan_table() -> None:
    ownership = {o["table"]: o["status"] for o in _finished("demo-wide").ownership}

    assert ownership["audit_logs"] == ORPHAN
    assert {s for t, s in ownership.items() if t != "audit_logs"} == {OWNED}
    assert TEST_OWN not in ownership.values()


CUSTOMER = "SELECT id FROM customers WHERE username = %s"
"""A read of ``customers`` some services repeat."""


def test_a_table_read_by_several_services_could_be_read_once() -> None:
    spans = [
        SpanAccess(0, "hello-api", "customers", "read", CUSTOMER),
        SpanAccess(0, "bank-partner", "customers", "read", CUSTOMER),
        SpanAccess(1, "newsletter-service", "customers", "read", CUSTOMER),
        SpanAccess(1, "newsletter-service", "newsletters", "read", "SELECT"),
    ]

    [hint] = optimization_hints(spans)

    assert (hint.item, hint.kind, hint.reads, hint.saved) == (
        "customers",
        SEVERAL_SERVICES,
        3,
        2,
    )
    assert hint.services == ["hello-api", "bank-partner", "newsletter-service"]
    assert hint.steps == [0, 1]
    assert hint.by[-1] == (1, "newsletter-service")


def test_the_same_query_again_in_one_step_comes_first() -> None:
    spans = [
        SpanAccess(0, "order-worker", "orders", "read", "SELECT * FROM orders"),
        SpanAccess(0, "order-worker", "orders", "read", "SELECT * FROM orders"),
        SpanAccess(0, "order-worker", "orders", "read", "SELECT * FROM orders"),
        SpanAccess(0, "order-worker", "products", "read", "SELECT a FROM products"),
        SpanAccess(0, "order-worker", "products", "read", "SELECT b FROM products"),
        SpanAccess(0, "order-worker", "payments", "write", "INSERT INTO payments"),
        SpanAccess(0, "order-worker", "payments", "write", "INSERT INTO payments"),
    ]

    hints = optimization_hints(spans)

    assert [(h.item, h.kind) for h in hints] == [
        ("orders", SAME_QUERY),
        ("products", SEVERAL_QUERIES),
    ]


def test_a_trace_gives_one_span_access_per_sql_span() -> None:
    trace = {
        "batches": [
            _sql_span("hello-api", "storefront-squad", CUSTOMER),
            _sql_span("bank-partner", "partners-squad", CUSTOMER),
        ]
    }

    assert span_accesses(trace, 2) == [
        SpanAccess(2, "hello-api", "customers", "read", CUSTOMER, "storefront-squad"),
        SpanAccess(2, "bank-partner", "customers", "read", CUSTOMER, "partners-squad"),
    ]


def test_the_hints_wait_for_the_traces_and_count_the_test_s_own_sql() -> None:
    experiment = Experiment("x", TARGETS["hello-then-sql"])
    experiment.spans = [SpanAccess(0, "hello-api", "customers", "read", CUSTOMER)]
    experiment.runs = [Run(n, 900, [], [], [], []) for n in range(1, RUNS + 1)]

    assert experiment.hints == []

    experiment.traced_steps = {0: []}
    [hint] = experiment.hints
    assert hint.services == ["hello-api", "the test"]
    assert experiment.to_json()["hints"][0]["saved"] == 1


def test_the_crowded_demo_has_tables_to_spare() -> None:
    assert _finished("demo-crowded").hints != []


def test_an_endpoint_called_again_is_an_api_to_spare() -> None:
    hits = [
        ApiHit(0, "hello-api", "GET /api/hello", "the test"),
        ApiHit(0, "bank-partner", "GET /balance", "hello-api"),
        ApiHit(1, "hello-api", "GET /api/hello", "the test"),
        ApiHit(1, "bank-partner", "GET /balance", "hello-api"),
        ApiHit(1, "bank-partner", "GET /balance", "newsletter-service"),
        ApiHit(1, "stock", "GET /stock", "order-worker"),
        ApiHit(1, "stock", "GET /stock", "order-worker"),
        ApiHit(1, "identity-service", "GET /me", "hello-api"),
    ]

    hints = {(h.owner, h.item): h for h in api_hints(hits)}

    assert hints["bank-partner", "GET /balance"].kind == SEVERAL_CALLERS
    assert hints["bank-partner", "GET /balance"].saved == 2
    assert hints["hello-api", "GET /api/hello"].kind == CALLED_AGAIN
    assert hints["stock", "GET /stock"].kind == SAME_CALL
    assert ("identity-service", "GET /me") not in hints
    assert {h.of for h in hints.values()} == {"api"}


def test_a_server_span_is_called_by_the_service_of_its_parent() -> None:
    def batch(service: str, spans: list[dict[str, object]]) -> dict[str, object]:
        resource = [{"key": "service.name", "value": {"stringValue": service}}]
        return {"resource": {"attributes": resource}, "scopeSpans": [{"spans": spans}]}

    trace = {
        "batches": [
            batch("quality-console", [{"spanId": "a", "kind": 3, "name": "GET"}]),
            batch(
                "hello-api",
                [
                    {"spanId": "b", "parentSpanId": "a", "kind": 2, "name": "GET /hi"},
                    {"spanId": "c", "parentSpanId": "b", "kind": 3, "name": "GET"},
                ],
            ),
            batch(
                "bank-partner",
                [{"spanId": "d", "parentSpanId": "c", "kind": 2, "name": "GET /b"}],
            ),
        ]
    }

    assert trace_api_hits(trace, 1) == [
        ApiHit(1, "hello-api", "GET /hi", "the test"),
        ApiHit(1, "bank-partner", "GET /b", "hello-api"),
    ]


def test_the_same_greeting_twice_is_a_real_run_of_its_own() -> None:
    assert [s.title for s in TARGETS["repeat-hello"].steps] == [
        "GET /api/hello?username=ada"
    ] * 2


def test_the_hints_list_the_endpoints_before_the_tables() -> None:
    experiment = _finished("demo-crowded")
    kinds = [h.of for h in experiment.hints]

    assert kinds == sorted(kinds)
    assert experiment.to_json()["hints"][0]["of"] == kinds[0]


def test_an_api_or_a_destination_is_owned_by_the_team_its_services_declare() -> None:
    experiment = _orphan_run()
    experiment.api_hits = [
        ApiHit(0, "hello-api", "GET /api/hello", "the test", "storefront-squad"),
        ApiHit(1, "newsletter-service", "GET /newsletters/{username}", "the test"),
    ]
    experiment.message_hits = [
        MessageHit(0, "hello-api", "order-workflow", "publish", "storefront-squad"),
        MessageHit(0, "order-worker", "order-workflow", "consume", "orders-squad"),
        MessageHit(1, "newsletter-service", "newsletters", "publish"),
    ]

    entries = {(e["of"], e["item"]): e for e in experiment.service_ownership}

    assert entries["api", "hello-api"]["status"] == OWNED
    assert entries["api", "hello-api"]["teams"] == ["storefront-squad"]
    assert entries["api", "newsletter-service"]["status"] == ORPHAN
    assert entries["api", "newsletter-service"]["why"] == (
        "GET /newsletters/{username}, no team declared"
    )
    assert entries["broker", "order-workflow"]["teams"] == [
        "orders-squad",
        "storefront-squad",
    ]
    assert entries["broker", "order-workflow"]["why"] == (
        "consumed by order-worker, published by hello-api"
    )
    assert entries["broker", "newsletters"]["status"] == ORPHAN
    assert [e["of"] for e in experiment.to_json()["service_ownership"]] == [
        "api",
        "api",
        "broker",
        "broker",
    ]


def test_a_destination_used_again_by_one_service_is_a_message_to_spare() -> None:
    hits = [
        MessageHit(0, "hello-api", "order-workflow", "publish", "storefront-squad"),
        MessageHit(1, "hello-api", "order-workflow", "publish", "storefront-squad"),
        MessageHit(1, "order-worker", "order-workflow", "consume"),
    ]

    [hint] = message_hints(hits)

    assert (hint.of, hint.item, hint.owner) == ("broker", "order-workflow", "hello-api")
    assert hint.kind == "published-again"
    assert hint.saved == 1
    assert hint.teams == ["storefront-squad"]


def test_the_hints_carry_the_teams_of_the_services_using_each_item() -> None:
    hits = [
        ApiHit(0, "bank-partner", "GET /balance", "hello-api", "partners-squad"),
        ApiHit(1, "bank-partner", "GET /balance", "hello-api", "partners-squad"),
    ]
    spans = [
        SpanAccess(0, "hello-api", "customers", "read", CUSTOMER, "storefront-squad"),
        SpanAccess(1, "newsletter-service", "customers", "read", CUSTOMER),
    ]

    assert api_hints(hits)[0].teams == ["partners-squad"]
    assert optimization_hints(spans)[0].teams == ["storefront-squad"]


def test_a_producer_or_consumer_span_is_a_message_of_its_destination() -> None:
    def batch(service: str, spans: list[dict[str, object]]) -> dict[str, object]:
        resource = [
            {"key": "service.name", "value": {"stringValue": service}},
            {"key": "team", "value": {"stringValue": "orders-squad"}},
        ]
        return {"resource": {"attributes": resource}, "scopeSpans": [{"spans": spans}]}

    destination = [
        {"key": "messaging.destination.name", "value": {"stringValue": "orders"}}
    ]
    trace = {
        "batches": [
            batch(
                "order-worker",
                [
                    {
                        "kind": "SPAN_KIND_PRODUCER",
                        "name": "orders publish",
                        "attributes": destination,
                        "startTimeUnixNano": "1",
                    },
                    {"kind": 5, "name": "invoices process", "startTimeUnixNano": "2"},
                    {
                        "kind": "SPAN_KIND_SERVER",
                        "name": "GET /orders",
                        "startTimeUnixNano": "3",
                    },
                ],
            )
        ]
    }

    assert trace_message_hits(trace, 2) == [
        MessageHit(2, "order-worker", "orders", "publish", "orders-squad"),
        MessageHit(2, "order-worker", "invoices process", "consume", "orders-squad"),
    ]
