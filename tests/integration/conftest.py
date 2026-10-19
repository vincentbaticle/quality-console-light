"""Neighbours of the integration tests, started once per test session."""

from collections.abc import Iterator
from dataclasses import dataclass, replace
import datetime
import os
from pathlib import Path
import uuid

from fastapi.testclient import TestClient
from google.auth.credentials import AnonymousCredentials
from google.cloud import storage
import httpx
import pytest
from redis import Redis
from testcontainers.community.rabbitmq import RabbitMqContainer
from testcontainers.community.redis import RedisContainer
from testcontainers.core.container import DockerContainer
from testcontainers.core.image import DockerImage
from testcontainers.core.network import Network
from testcontainers.core.wait_strategies import (
    HttpWaitStrategy,
    LogMessageWaitStrategy,
)

from company_db import DatabaseSettings
from gherkin_runner.main import create_app as create_runner
from hello_api.main import create_app
from identity.emails import Mailer
from identity.main import create_app as create_identity
from order_workflow.store import OrderStore
from quality_console.main import create_app as create_console
from quality_console.settings import ConsoleSettings
from test_results.index import build_index
from test_results.reader import ResultsReader
from tests.broker import amqp_url, purge, wait_until_ready as wait_for_broker
from tests.database import (
    DATABASE_NAME,
    IDENTITY_DATABASE,
    ROOT_USER,
    load_company_database,
    reader_settings,
    restored,
)
from tests.mailbox import empty, wait_until_ready as wait_for_mailbox
from tests.microcks import (
    MICROCKS_ENV,
    MICROCKS_IMAGE,
    MICROCKS_PORT,
    MICROCKS_URL_VARIABLE,
    MOCK_PATH,
    READINESS_TIMEOUT_SECONDS,
    STARTUP_LOG_MARKER,
    load_bank_partner,
    wait_until_ready,
)
from tests.neighbours import (
    AMQP_PORT,
    FRONTEND_DIR,
    GCS_IMAGE,
    GCS_PORT,
    GCS_URL_VARIABLE,
    MAILPIT_API_PORT,
    MAILPIT_HOST_VARIABLE,
    MAILPIT_IMAGE,
    MOCKS_DIR,
    MOCKS_IMAGE_TAG,
    MOCKS_PORT,
    MOCKS_READY_MARKER,
    MYSQL_HOST_VARIABLE,
    MYSQL_IMAGE,
    MYSQL_PORT,
    MYSQL_ROOT_PASSWORD,
    PROJECT_ROOT,
    RABBITMQ_HOST_VARIABLE,
    RABBITMQ_IMAGE,
    REDIS_HOST_VARIABLE,
    REDIS_IMAGE,
    REDIS_PORT,
    SMTP_PORT,
    require_docker,
    uses_external_services,
)
from tests.story import MANAGEMENT_TOKEN, PUBLIC_URL

API_PORT = 8000
"""Port uvicorn listens on inside the API container."""

FRONT_PORT = 80
"""Port nginx listens on inside the front container."""

API_IMAGE_TAG = "quality-console/api:test"
"""Tag of the API image built from the repository for the browser test."""

FRONT_IMAGE_TAG = "quality-console/front:test"
"""Tag of the front image built from ``frontend/`` for the browser test."""


def microcks_container() -> DockerContainer:
    """Describe a Microcks container, ready to be started."""
    container = DockerContainer(MICROCKS_IMAGE).with_exposed_ports(MICROCKS_PORT)
    for name, value in MICROCKS_ENV.items():
        container.with_env(name, value)
    return container.waiting_for(
        LogMessageWaitStrategy(STARTUP_LOG_MARKER).with_startup_timeout(
            READINESS_TIMEOUT_SECONDS
        )
    )


def mocks_container(image: str) -> DockerContainer:
    """Describe the contract mocks: Prism on every contract of ``contracts/``."""
    return (
        DockerContainer(image)
        .with_volume_mapping(str(PROJECT_ROOT / "contracts"), "/contracts", "ro")
        .with_exposed_ports(MOCKS_PORT)
        .waiting_for(
            LogMessageWaitStrategy(MOCKS_READY_MARKER).with_startup_timeout(
                READINESS_TIMEOUT_SECONDS
            )
        )
    )


def mysql_container() -> DockerContainer:
    """Describe a MySQL container, ready to be started.

    No dedicated module here: a generic container, an environment variable and
    an exposed port are all MySQL needs, which shows what testcontainers does
    under every ``RedisContainer``-like helper.
    """
    return (
        DockerContainer(MYSQL_IMAGE)
        .with_env("MYSQL_ROOT_PASSWORD", MYSQL_ROOT_PASSWORD)
        .with_exposed_ports(MYSQL_PORT)
    )


def host_url(container: DockerContainer, port: int) -> str:
    """Return the URL the host reaches a container port on."""
    host = container.get_container_host_ip()
    return f"http://{host}:{container.get_exposed_port(port)}"


@pytest.fixture(scope="session")
def redis_url() -> Iterator[str]:
    """Give a real Redis: our own container locally, the CI sidecar in CI."""
    if uses_external_services():
        yield f"redis://{os.environ[REDIS_HOST_VARIABLE]}:{REDIS_PORT}/0"
        return
    require_docker()
    with RedisContainer(REDIS_IMAGE) as redis:
        host = redis.get_container_host_ip()
        port = redis.get_exposed_port(REDIS_PORT)
        yield f"redis://{host}:{port}/0"


@pytest.fixture(scope="session")
def microcks_url() -> Iterator[str]:
    """Give a Microcks playing every partner: our own container, or the CI sidecar.

    It replays the Bank Partner from its captured examples.
    """
    if uses_external_services():
        url = os.environ[MICROCKS_URL_VARIABLE]
        wait_until_ready(url)
        load_bank_partner(url)
        yield url
        return
    require_docker()
    with microcks_container() as microcks:
        url = host_url(microcks, MICROCKS_PORT)
        load_bank_partner(url)
        yield url


@pytest.fixture(scope="session")
def mocks_url() -> Iterator[str]:
    """Give the contract mocks, Prism on every contract of ``contracts/``.

    No CI sidecar: a GitLab service starts before the checkout, so it has no
    ``contracts/`` to serve. In sidecar mode the tests skip and say so.
    """
    if uses_external_services():
        pytest.skip("The contract mocks read contracts/, which a CI sidecar has not")
    require_docker()
    with (
        DockerImage(path=MOCKS_DIR, tag=MOCKS_IMAGE_TAG) as image,
        mocks_container(str(image)) as mocks,
    ):
        yield host_url(mocks, MOCKS_PORT)


@pytest.fixture(scope="session")
def partner_url(microcks_url: str) -> str:
    """The Bank Partner, as Microcks replays it."""
    return f"{microcks_url}{MOCK_PATH}"


@pytest.fixture(scope="session")
def database() -> Iterator[DatabaseSettings]:
    """Give the company database, 30 tables loaded from ``db/``."""
    if uses_external_services():
        yield load_company_database(os.environ[MYSQL_HOST_VARIABLE], MYSQL_PORT)
        return
    require_docker()
    with mysql_container() as mysql:
        host = mysql.get_container_host_ip()
        port = int(mysql.get_exposed_port(MYSQL_PORT))
        yield load_company_database(host, port)


@pytest.fixture(scope="session")
def gcs_url() -> Iterator[str]:
    """Give a Cloud Storage emulator: our own container locally, the sidecar in CI."""
    if uses_external_services():
        yield os.environ[GCS_URL_VARIABLE]
        return
    require_docker()
    with (
        DockerContainer(GCS_IMAGE)
        .with_command(f"-scheme http -port {GCS_PORT} -backend memory")
        .with_exposed_ports(GCS_PORT)
        .waiting_for(HttpWaitStrategy(GCS_PORT, "/storage/v1/b")) as gcs
    ):
        yield host_url(gcs, GCS_PORT)


@pytest.fixture
def results_bucket(gcs_url: str) -> storage.Bucket:
    """Create an empty results bucket of its own for each test."""
    client = storage.Client(
        project="local",
        credentials=AnonymousCredentials(),
        client_options={"api_endpoint": gcs_url},
    )
    return client.create_bucket(f"results-{uuid.uuid4().hex[:12]}")


@pytest.fixture(scope="session")
def broker_url() -> Iterator[str]:
    """Give a RabbitMQ: our own container locally, the CI sidecar in CI."""
    if uses_external_services():
        url = amqp_url(os.environ[RABBITMQ_HOST_VARIABLE], AMQP_PORT)
        wait_for_broker(url)
        yield url
        return
    require_docker()
    with RabbitMqContainer(RABBITMQ_IMAGE) as rabbitmq:
        yield amqp_url(
            rabbitmq.get_container_host_ip(), int(rabbitmq.get_exposed_port(AMQP_PORT))
        )


@pytest.fixture
def broker(broker_url: str) -> str:
    """The broker, its workflow queue emptied before the test."""
    purge(broker_url)
    return broker_url


@pytest.fixture
def order_store(database: DatabaseSettings) -> Iterator[OrderStore]:
    """Orders and workflows, the company data put back after the test."""
    with restored(database):
        yield OrderStore(database)


@pytest.fixture
def redis_client(redis_url: str) -> Iterator[Redis]:
    """Reach the same Redis as the API, emptied before each test."""
    client = Redis.from_url(redis_url, decode_responses=True)
    client.flushdb()
    yield client
    client.close()


@pytest.fixture
def api(
    redis_client: Redis,
    redis_url: str,
    partner_url: str,
    database: DatabaseSettings,
    broker: str,
) -> Iterator[TestClient]:
    """Drive the real application, in process, wired to its real neighbours."""
    with TestClient(create_app(redis_url, partner_url, database, broker)) as client:
        yield client


@dataclass(frozen=True)
class MailServer:
    """Where emails are sent (SMTP) and read (the Mailpit API)."""

    smtp_host: str
    smtp_port: int
    api_url: str


@pytest.fixture(scope="session")
def mail_server() -> Iterator[MailServer]:
    """Give a Mailpit, the QA mailbox: our own container locally, the CI sidecar."""
    if uses_external_services():
        host = os.environ[MAILPIT_HOST_VARIABLE]
        api_url = f"http://{host}:{MAILPIT_API_PORT}"
        wait_for_mailbox(api_url)
        yield MailServer(host, SMTP_PORT, api_url)
        return
    require_docker()
    with (
        DockerContainer(MAILPIT_IMAGE)
        .with_exposed_ports(SMTP_PORT, MAILPIT_API_PORT)
        .waiting_for(HttpWaitStrategy(MAILPIT_API_PORT, "/api/v1/info")) as mailpit
    ):
        yield MailServer(
            mailpit.get_container_host_ip(),
            int(mailpit.get_exposed_port(SMTP_PORT)),
            host_url(mailpit, MAILPIT_API_PORT),
        )


@pytest.fixture
def mailbox(mail_server: MailServer) -> str:
    """The QA mailbox, emptied before the test: the root URL of its API."""
    empty(mail_server.api_url)
    return mail_server.api_url


@pytest.fixture
def identity(
    database: DatabaseSettings, mail_server: MailServer, mailbox: str
) -> Iterator[TestClient]:
    """Drive the simulated Auth0 tenant, in process, sending to the QA mailbox."""
    app = create_identity(
        replace(database, name=IDENTITY_DATABASE),
        Mailer(mail_server.smtp_host, mail_server.smtp_port),
        PUBLIC_URL,
        MANAGEMENT_TOKEN,
    )
    with TestClient(app) as client:
        yield client


CONSOLE_LINKS = {
    "QA mailbox": "http://mailbox.test",
    "Observability": "http://o11y.test",
}
"""Links the console home page shows in tests, any URL does."""

UNSERVED_API = "http://127.0.0.1:9"
"""A storefront API nobody serves: the console tests never start a footprint."""


@pytest.fixture
def runner(results_bucket: storage.Bucket) -> Iterator[TestClient]:
    """Drive the Gherkin runner, in process, uploading to the test's bucket."""
    app = create_runner(PROJECT_ROOT, results_bucket, "local", "test")
    with TestClient(app) as client:
        yield client


@pytest.fixture
def console(
    database: DatabaseSettings,
    results_bucket: storage.Bucket,
    runner: TestClient,
    tmp_path: Path,
) -> Iterator[TestClient]:
    """Drive the Quality Console, in process, with its read-only account.

    Every tool is wired for real: the catalog and the databases in MySQL, the
    results and the bucket browser on the Cloud Storage emulator, the Gherkin
    runner in process, the repository's own contracts and features.
    """
    settings = ConsoleSettings(
        database=reader_settings(database),
        storefront="http://storefront.test",
        links=CONSOLE_LINKS,
        results=ResultsReader(results_bucket),
        rebuild_index=lambda: build_index(
            results_bucket, datetime.datetime.now(datetime.UTC)
        ),
        storage=results_bucket.client,
        contracts=PROJECT_ROOT / "contracts",
        features=PROJECT_ROOT / "features",
        designs=PROJECT_ROOT / "designs",
        capture=PROJECT_ROOT / "capture",
        docs=PROJECT_ROOT / "docs",
        audio_assets=tmp_path / "audio-assets",
        announcements=PROJECT_ROOT / "announcements",
        runner=runner,
        api=httpx.Client(base_url=UNSERVED_API),
        tempo=None,
    )
    with TestClient(create_console(settings)) as client:
        yield client


@pytest.fixture(scope="session")
def stack_url() -> Iterator[str]:
    """Build and start the whole product on a private network.

    MySQL, Redis, RabbitMQ, Microcks (playing the Bank Partner), Mailpit (the
    QA mailbox), the API, the order worker, the identity tenant and the front
    talk to each other by alias (``mysql``, ``redis``, ``rabbitmq``,
    ``microcks``, ``mailpit``, ``api``, ``identity``), like in
    ``docker-compose.yml``. Only the front, MySQL and Microcks are reached from
    the host (to browse, to load the data, to load the partner), on ports Docker
    picks at random. Telemetry is switched off: no collector runs in a test.
    """
    if uses_external_services():
        pytest.skip("The full stack needs a Docker daemon, CI only offers sidecars")
    require_docker()
    with (
        Network() as network,
        DockerImage(path=PROJECT_ROOT, tag=API_IMAGE_TAG) as api_image,
        DockerImage(path=FRONTEND_DIR, tag=FRONT_IMAGE_TAG) as front_image,
        RedisContainer(REDIS_IMAGE).with_network(network).with_network_aliases("redis"),
        mysql_container().with_network(network).with_network_aliases("mysql") as mysql,
        RabbitMqContainer(RABBITMQ_IMAGE)
        .with_network(network)
        .with_network_aliases("rabbitmq"),
        microcks_container()
        .with_network(network)
        .with_network_aliases("microcks") as microcks,
        DockerContainer(MAILPIT_IMAGE)
        .with_network(network)
        .with_network_aliases("mailpit"),
    ):
        load_bank_partner(host_url(microcks, MICROCKS_PORT))
        load_company_database(
            mysql.get_container_host_ip(), int(mysql.get_exposed_port(MYSQL_PORT))
        )
        with (
            DockerContainer(str(api_image))
            .with_network(network)
            .with_network_aliases("api")
            .with_env("REDIS_URL", f"redis://redis:{REDIS_PORT}/0")
            .with_env("PARTNER_URL", f"http://microcks:{MICROCKS_PORT}{MOCK_PATH}")
            .with_env("DB_HOST", "mysql")
            .with_env("DB_PORT", str(MYSQL_PORT))
            .with_env("DB_USER", ROOT_USER)
            .with_env("DB_PASSWORD", MYSQL_ROOT_PASSWORD)
            .with_env("DB_NAME", DATABASE_NAME)
            .with_env("RABBITMQ_URL", amqp_url("rabbitmq", AMQP_PORT))
            .with_env("OTEL_SDK_DISABLED", "true")
            .with_exposed_ports(API_PORT)
            .waiting_for(HttpWaitStrategy(API_PORT, "/api/health")),
            DockerContainer(str(api_image))
            .with_network(network)
            .with_command("python -m order_workflow.worker")
            .with_env("DB_HOST", "mysql")
            .with_env("DB_PORT", str(MYSQL_PORT))
            .with_env("DB_USER", ROOT_USER)
            .with_env("DB_PASSWORD", MYSQL_ROOT_PASSWORD)
            .with_env("DB_NAME", DATABASE_NAME)
            .with_env("RABBITMQ_URL", amqp_url("rabbitmq", AMQP_PORT))
            .with_env("WORKFLOW_STEP_DELAY_SECONDS", "0")
            .waiting_for(LogMessageWaitStrategy("consuming")),
            DockerContainer(str(api_image))
            .with_network(network)
            .with_network_aliases("identity")
            .with_command(
                "uvicorn identity.main:app_from_environment --factory"
                f" --host 0.0.0.0 --port {API_PORT}"
            )
            .with_env("DB_HOST", "mysql")
            .with_env("DB_PORT", str(MYSQL_PORT))
            .with_env("DB_USER", ROOT_USER)
            .with_env("DB_PASSWORD", MYSQL_ROOT_PASSWORD)
            .with_env("DB_NAME", IDENTITY_DATABASE)
            .with_env("SMTP_HOST", "mailpit")
            .with_env("SMTP_PORT", str(SMTP_PORT))
            .with_env("PUBLIC_URL", PUBLIC_URL)
            .with_env("MANAGEMENT_TOKEN", MANAGEMENT_TOKEN)
            .with_exposed_ports(API_PORT)
            .waiting_for(HttpWaitStrategy(API_PORT, "/api/identity/health")),
            DockerContainer(str(front_image))
            .with_network(network)
            .with_exposed_ports(FRONT_PORT)
            .waiting_for(HttpWaitStrategy(FRONT_PORT, "/")) as front,
        ):
            yield host_url(front, FRONT_PORT)
