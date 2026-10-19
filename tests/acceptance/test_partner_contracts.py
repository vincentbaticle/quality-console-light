"""Partner contracts: the real Bank Partner checked against our copy of its contract.

Schemathesis builds the requests from ``contracts/bank-partner-openapi.yaml``
and runs its own checks on each answer. The generation runs inside a step,
through Hypothesis, so a Gherkin scenario stays the unit the console runs.
"""

from collections.abc import Callable

import hypothesis
import pytest
from pytest_bdd import given, parsers, scenarios, then, when
import schemathesis
from schemathesis.checks import (
    not_a_server_error,
    response_schema_conformance,
    status_code_conformance,
)
from schemathesis.core.failures import FailureGroup

from hello_api.bank_partner import API_KEY_HEADER
from tests.acceptance.conftest import Context, Stack
from tests.metadata import metadata_test
from tests.neighbours import PROJECT_ROOT

pytestmark = [
    pytest.mark.acceptance,
    metadata_test(
        system="bank",
        product="partner-contracts",
        business_capability="engage",
        component="bank-partner",
        group="partners-squad",
        testing_scope="contract",
        tags="schemathesis",
    ),
]

scenarios("partner-contracts")

CONTRACT = PROJECT_ROOT / "contracts" / "bank-partner-openapi.yaml"
"""Our copy of the contract the bank publishes."""

BALANCE = ("GET", "/balance")
"""The one operation of the contract."""

FAILURES_SHOWN = 3
"""Failing requests quoted in an assertion message, enough to reproduce."""

Exchange = tuple[schemathesis.Case, schemathesis.Response]
"""A request schemathesis built and what the partner answered."""


@pytest.fixture
def contract() -> schemathesis.BaseSchema:
    """The contract, generating only requests it allows."""
    config = schemathesis.Config.from_dict({"generation": {"mode": "positive"}})
    return schemathesis.openapi.from_path(CONTRACT, config=config)


@given("the contract of the Bank Partner")
def given_contract(contract: schemathesis.BaseSchema) -> None:
    assert contract[BALANCE[1]][BALANCE[0]] is not None


@when(parsers.parse("schemathesis sends {count:d} requests generated from it"))
def send_generated(
    stack: Stack,
    context: Context,
    contract: schemathesis.BaseSchema,
    partner_api_key: str,
    count: int,
) -> None:
    exchanges: list[Exchange] = []
    key = {API_KEY_HEADER: partner_api_key}
    operation = contract[BALANCE[1]][BALANCE[0]]

    @hypothesis.given(case=operation.as_strategy())
    @hypothesis.settings(
        max_examples=count,
        deadline=None,
        database=None,
        phases=[hypothesis.Phase.explicit, hypothesis.Phase.generate],
        suppress_health_check=list(hypothesis.HealthCheck),
    )
    def send(case: schemathesis.Case) -> None:
        exchanges.append((case, case.call(base_url=stack.partner, headers=key)))

    send()
    context.values["exchanges"] = exchanges


@when(parsers.parse('schemathesis asks the balance of "{username}"'))
def ask_balance(
    stack: Stack,
    context: Context,
    contract: schemathesis.BaseSchema,
    partner_api_key: str,
    username: str,
) -> None:
    case = contract[BALANCE[1]][BALANCE[0]].Case(query={"username": username})
    headers = {API_KEY_HEADER: partner_api_key}
    context.values["exchanges"] = [
        (case, case.call(base_url=stack.partner, headers=headers))
    ]


@when(parsers.parse('schemathesis asks the balance of "{username}" without the key'))
def ask_without_key(
    stack: Stack, context: Context, contract: schemathesis.BaseSchema, username: str
) -> None:
    case = contract[BALANCE[1]][BALANCE[0]].Case(query={"username": username})
    context.values["exchanges"] = [(case, case.call(base_url=stack.partner))]


def _failures(context: Context, check: Callable[..., object]) -> list[str]:
    """The exchanges the schemathesis check refuses, each as a short line."""
    failed = []
    for case, response in context.values["exchanges"]:
        try:
            case.validate_response(response, checks=[check])
        except (AssertionError, FailureGroup) as error:
            found = getattr(error, "exceptions", (error,))
            titles = "; ".join(getattr(f, "title", str(f)) for f in found)
            failed.append(f"{case.query} -> {response.status_code}: {titles}")
    return failed


def _assert_none_fails(context: Context, check: Callable[..., object]) -> None:
    failed = _failures(context, check)
    total = len(context.values["exchanges"])
    assert not failed, (
        f"{len(failed)} of {total} answers fail {check.__name__}:\n"
        + "\n".join(failed[:FAILURES_SHOWN])
    )


@then("no answer is a server error")
def no_server_error(context: Context) -> None:
    _assert_none_fails(context, not_a_server_error)


@then("every status code is documented by the contract")
def documented_status(context: Context) -> None:
    _assert_none_fails(context, status_code_conformance)


@then("every body matches the schema of its status code")
def body_matches(context: Context) -> None:
    _assert_none_fails(context, response_schema_conformance)


@then(parsers.parse("the partner answers {status:d}"))
def partner_answers(context: Context, status: int) -> None:
    statuses = [response.status_code for _, response in context.values["exchanges"]]
    assert set(statuses) == {status}, statuses
