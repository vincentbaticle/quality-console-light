"""Credentials from the files a Vault Agent writes, and what the Vault page reads."""

from pathlib import Path

import httpx
import pytest

from company_db import DatabaseSettings
from company_secrets import read_env_file
from order_workflow.broker import with_credentials
from quality_console.vault_view import VaultReader, seconds
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


def test_an_agent_file_reads_as_keys_and_values(tmp_path: Path) -> None:
    file = tmp_path / "db.env"
    file.write_text("# rendered by the agent\nDB_USER=v-hello-1\nDB_PASSWORD=a=b\n\n")

    assert read_env_file(str(file)) == {"DB_USER": "v-hello-1", "DB_PASSWORD": "a=b"}


def test_the_database_credentials_are_read_again_on_every_connection(
    tmp_path: Path,
) -> None:
    file = tmp_path / "db.env"
    settings = DatabaseSettings("mysql", 3306, "", "", "mycompany", str(file))

    file.write_text("DB_USER=v-hello-1\nDB_PASSWORD=first\n")
    first = settings.credentials()
    file.write_text("DB_USER=v-hello-2\nDB_PASSWORD=second\n")

    assert first == ("v-hello-1", "first")
    assert settings.credentials() == ("v-hello-2", "second")


def test_without_a_file_the_settings_keep_their_own_credentials() -> None:
    settings = DatabaseSettings("mysql", 3306, "root", "root", "mycompany")

    assert settings.credentials() == ("root", "root")


def test_a_broker_url_takes_the_short_lived_user_in_place_of_any() -> None:
    url = with_credentials("amqp://guest:guest@rabbitmq:5672/%2F", "v-root-x", "p@ss/1")

    assert url == "amqp://v-root-x:p%40ss%2F1@rabbitmq:5672/%2F"


@pytest.mark.parametrize(
    ("value", "expected"), [(120, 120), ("2m", 120), ("1h", 3600), ("45", 45)]
)
def test_a_vault_duration_reads_in_seconds(value: str | int, expected: int) -> None:
    assert seconds(value) == expected


def test_the_vault_page_lists_leases_and_never_reads_a_value() -> None:
    asked = []

    def vault(request: httpx.Request) -> httpx.Response:
        asked.append(f"{request.method} {request.url.path}")
        path = request.url.path
        if request.method == "LIST":
            return httpx.Response(200, json={"data": {"keys": ["abc"]}})
        if path == "/v1/sys/leases/lookup":
            return httpx.Response(
                200,
                json={
                    "data": {
                        "id": "database/creds/hello-api/abc",
                        "issue_time": "2026-10-12T16:00:00Z",
                        "expire_time": "2026-10-12T16:02:00Z",
                        "last_renewal": None,
                        "ttl": 90,
                    }
                },
            )
        if path.startswith("/v1/database/roles/"):
            return httpx.Response(
                200, json={"data": {"default_ttl": 120, "max_ttl": 360}}
            )
        if path == "/v1/rabbitmq/config/lease":
            return httpx.Response(200, json={"data": {"ttl": 120, "max_ttl": 360}})
        return httpx.Response(
            200,
            json={
                "data": {
                    "created_time": "2026-10-12T16:00:00Z",
                    "updated_time": "2026-10-12T16:00:00Z",
                    "current_version": 1,
                }
            },
        )

    client = httpx.Client(
        base_url="http://vault.test", transport=httpx.MockTransport(vault)
    )

    state = VaultReader(client).state()

    assert state.error == ""
    assert [len(role.leases) for role in state.roles] == [1, 1, 1, 1, 1]
    assert state.roles[0].leases[0].ttl_seconds == 90
    assert state.roles[0].max_ttl == 360
    assert state.secrets[0].version == 1
    assert not any("/secret/data/" in call for call in asked)
