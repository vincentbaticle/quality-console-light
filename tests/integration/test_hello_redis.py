"""The API against a real Redis: the counter must survive between two calls."""

from fastapi.testclient import TestClient
import pytest
from redis import Redis

from tests.metadata import metadata_test

pytestmark = [
    pytest.mark.integration,
    metadata_test(
        system="storefront",
        product="customer-welcome",
        business_capability="engage",
        component="hello-api",
        group="storefront-squad",
        testing_scope="integration",
        tags="redis",
    ),
]


def test_health_answers_once_redis_answers(api: TestClient) -> None:
    response = api.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_first_visit_is_number_one(api: TestClient) -> None:
    response = api.get("/api/hello", params={"username": "ada"})

    assert response.status_code == 200
    assert response.json()["visits"] == 1


def test_second_visit_is_counted_in_redis(api: TestClient, redis_client: Redis) -> None:
    api.get("/api/hello", params={"username": "ada"})
    response = api.get("/api/hello", params={"username": "Ada "})

    assert response.json()["visits"] == 2
    assert redis_client.get("visits:ada") == "2"


def test_empty_username_is_refused(api: TestClient) -> None:
    response = api.get("/api/hello", params={"username": ""})

    assert response.status_code == 422
