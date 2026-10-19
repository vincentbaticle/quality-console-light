"""Everything the integration tests need to know about their neighbours.

Two provisioning modes, one switch:

- On a laptop, each neighbour is a throwaway container started by testcontainers.
- In CI, where the job has no Docker daemon, the neighbours are sidecars declared
  by the job (``services:``), and the suite attaches to them instead.
"""

import os
from pathlib import Path

import docker
from docker.errors import DockerException
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
"""Root of the repository, the build context of the API image."""

FRONTEND_DIR = PROJECT_ROOT / "frontend"
"""Build context of the front image."""

REDIS_IMAGE = "redis:7.4-alpine"
"""Same Redis as ``docker-compose.yml``, so the tests run what a user runs."""

REDIS_PORT = 6379
"""Port Redis listens on inside its container, never the one the host sees."""

REDIS_HOST_VARIABLE = "REDIS_HOST"
"""Hostname of the Redis sidecar, set by the CI job in sidecar mode."""

MYSQL_IMAGE = "mysql:8.4"
"""Same MySQL as ``docker-compose.yml``, a long-term release like most production."""

MYSQL_PORT = 3306
"""Port MySQL listens on inside its container, never the one the host sees."""

MYSQL_HOST_VARIABLE = "MYSQL_HOST"
"""Hostname of the MySQL sidecar, set by the CI job in sidecar mode."""

MYSQL_ROOT_PASSWORD = "root"
"""Root password of a server that lives and dies with the test session."""

GCS_IMAGE = "fsouza/fake-gcs-server:1.55.1"
"""Cloud Storage emulator, the same as ``docker-compose.yml``: a real server."""

GCS_PORT = 4443
"""Port the emulator listens on inside its container or sidecar."""

GCS_URL_VARIABLE = "GCS_URL"
"""Root URL of the emulator sidecar, set by the CI job in sidecar mode."""

RABBITMQ_IMAGE = "rabbitmq:3.13-management"
"""Message broker of the order workflow, the same as ``docker-compose.yml``."""

AMQP_PORT = 5672
"""Port RabbitMQ listens on for AMQP inside its container or sidecar."""

RABBITMQ_HOST_VARIABLE = "RABBITMQ_HOST"
"""Hostname of the RabbitMQ sidecar, set by the CI job in sidecar mode."""

MAILPIT_IMAGE = "axllent/mailpit:v1.31.4"
"""The QA mailbox: an SMTP server keeping every email, read through its API."""

SMTP_PORT = 1025
"""Port Mailpit accepts emails on inside its container or sidecar."""

MAILPIT_API_PORT = 8025
"""Port Mailpit serves its API and web UI on."""

MAILPIT_HOST_VARIABLE = "MAILPIT_HOST"
"""Hostname of the Mailpit sidecar, set by the CI job in sidecar mode."""

MOCKS_DIR = PROJECT_ROOT / "mocks"
"""Prism 5.15.10 on node, built from ``mocks/Dockerfile`` for the machine's own
platform, serving every OpenAPI contract of ``contracts/`` through
``mocks/router.mjs``."""

MOCKS_IMAGE_TAG = "quality-console/mocks:test"
"""Tag of the contract mocks image built for the tests."""

MOCKS_PORT = 4010
"""Port the contract mocks listen on, every contract under its own path."""

MOCKS_READY_MARKER = "mocks ready:"
"""Log line the router prints once every Prism answers."""

EXTERNAL_SERVICES_VARIABLE = "INTEGRATION_EXTERNAL_SERVICES"
"""Set to ``true`` by a CI job whose neighbours are sidecars, not containers."""

TRUE_VALUES = frozenset({"1", "true", "yes"})
"""Spellings of an enabled switch."""


def uses_external_services() -> bool:
    """Say whether the neighbours are CI sidecars rather than our own containers.

    Returns:
        True when the CI job provisioned the neighbours itself.
    """
    return os.environ.get(EXTERNAL_SERVICES_VARIABLE, "").lower() in TRUE_VALUES


def require_docker() -> None:
    """Skip the calling test, with the reason, when no Docker daemon answers.

    A missing daemon is a machine problem, not a product bug: the test must say
    so and step aside instead of failing red.
    """
    try:
        docker.from_env().ping()
    except DockerException as exc:
        pytest.skip(f"Docker unavailable, start Rancher Desktop or Docker: {exc}")
