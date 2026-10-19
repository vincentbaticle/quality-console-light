"""The pure parts of the MCP server: reading a redirect, shaping an answer."""

import pytest

from quality_mcp.tools import experiment_id, footprint_answer
from tests.metadata import metadata_test

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

STATE = {
    "target": "API using tables: GET /api/hello?username=ada",
    "done": True,
    "error": None,
    "checked": True,
    "exact": ["bank_accounts", "customers"],
    "found": ["customers", "bank_accounts", "audit_logs"],
    "traced": [{"service": "hello-api", "operation": "read", "table": "customers"}],
    "sql": [],
    "trace_ids": ["0cc4"],
    "runs": [{}] * 10,
}
"""An experiment whose database saw one table no trace names."""


def test_the_experiment_id_comes_from_the_redirect() -> None:
    location = "/devx/retro-footprint?target=hello&experiment=ed89331d3bc9"

    assert experiment_id(location) == "ed89331d3bc9"
    assert experiment_id("/devx/retro-footprint") == ""


def test_the_answer_comes_from_the_traces_and_names_untraced_tables() -> None:
    answer = footprint_answer(STATE)

    assert answer["answer_source"] == "traces"
    assert answer["tables"] == ["bank_accounts", "customers"]
    assert answer["accesses"] == ["hello-api read customers"]
    assert answer["untraced_tables"] == ["audit_logs"]
    assert answer["runs"] == 10


def test_without_trace_the_database_is_the_answer() -> None:
    answer = footprint_answer({**STATE, "checked": False, "exact": []})

    assert answer["answer_source"] == "database counters"
    assert answer["tables"] == STATE["found"]
    assert answer["untraced_tables"] == []
