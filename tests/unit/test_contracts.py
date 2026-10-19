"""The contracts of ``contracts/`` say what the code does."""

import pytest
import yaml

from order_workflow.steps import STEPS
from quality_console.asyncapi import view
from scripts.export_contracts import ROOT, SERVICES, contract
from tests.metadata import metadata_test

pytestmark = [
    pytest.mark.unit,
    metadata_test(
        system="quality",
        product="quality-console",
        business_capability="operate",
        component="quality-console",
        group="qa-core",
        testing_scope="contract",
    ),
]

ORDER_EVENTS = ROOT / "contracts" / "order-workflow-asyncapi.yaml"
"""The event contract of the order workflow."""


@pytest.mark.parametrize("name", SERVICES)
def test_openapi_contract_is_the_one_the_service_generates(name: str) -> None:
    written = (ROOT / "contracts" / name).read_text()

    assert written == contract(SERVICES[name]), "run mise run contracts:export"


def test_event_contract_lists_every_step_of_the_workflow() -> None:
    document = yaml.safe_load(ORDER_EVENTS.read_text())

    page = view(document)

    assert [m.name for m in page.messages] == list(STEPS)
    schema = document["components"]["schemas"]["stepEvent"]
    assert schema["properties"]["type"]["enum"] == list(STEPS)


def test_event_page_shows_who_sends_and_receives_what() -> None:
    page = view(yaml.safe_load(ORDER_EVENTS.read_text()))

    operations = {o.key: o for o in page.operations}
    assert operations["startWorkflow"].messages == ["reserve_stock"]
    assert operations["runStep"].action == "receive"
    assert operations["runStep"].channel == "order-workflow"
    fields = {f.name: f for f in page.messages[0].fields}
    assert fields["workflow_id"].type == "string (uuid)"
    assert fields["type"].required
