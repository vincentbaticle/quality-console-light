"""The newsletter service against the real company database."""

from collections.abc import Iterator

from fastapi.testclient import TestClient
import pytest

from company_db import DatabaseSettings
from newsletter.main import create_app
from tests.metadata import metadata_test
from tests.story import CLOSED_USERNAME

pytestmark = [
    pytest.mark.integration,
    metadata_test(
        system="storefront",
        product="customer-welcome",
        business_capability="engage",
        component="newsletter-service",
        group="storefront-squad",
        testing_scope="integration",
        tags="mysql",
    ),
]


@pytest.fixture
def newsletter(database: DatabaseSettings) -> Iterator[TestClient]:
    """Drive the newsletter service, in process, on the real company database."""
    with TestClient(create_app(database)) as client:
        yield client


def test_a_customer_gets_their_newsletters_in_their_language(
    newsletter: TestClient,
) -> None:
    response = newsletter.get("/newsletters/Ada")

    assert response.status_code == 200
    assert response.json() == {
        "username": "ada",
        "language": "en",
        "newsletters": ["January picks"],
    }


def test_a_closed_customer_gets_no_newsletter(newsletter: TestClient) -> None:
    response = newsletter.get(f"/newsletters/{CLOSED_USERNAME}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Unknown customer"}
