"""The broker of the order workflow, reached from the tests."""

import time

import pika
from pika.exceptions import AMQPConnectionError

from order_workflow.broker import QUEUE

READINESS_TIMEOUT_SECONDS = 120
"""Budget for a RabbitMQ sidecar to accept connections."""

READINESS_POLL_SECONDS = 1.0
"""Delay between two connection attempts."""


def amqp_url(host: str, port: int) -> str:
    """AMQP URL of a broker with the default account and virtual host."""
    return f"amqp://guest:guest@{host}:{port}/%2F"


def wait_until_ready(url: str) -> None:
    """Connect until RabbitMQ accepts it: an open port is not a ready broker.

    Raises:
        RuntimeError: When it never accepted a connection in time.
    """
    deadline = time.monotonic() + READINESS_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        try:
            pika.BlockingConnection(pika.URLParameters(url)).close()
        except AMQPConnectionError:
            time.sleep(READINESS_POLL_SECONDS)
        else:
            return
    raise RuntimeError(f"RabbitMQ at {url} not ready")


def purge(url: str) -> None:
    """Empty the workflow queue, so a test starts with no event left over."""
    connection = pika.BlockingConnection(pika.URLParameters(url))
    try:
        channel = connection.channel()
        channel.queue_declare(queue=QUEUE, durable=True)
        channel.queue_purge(queue=QUEUE)
    finally:
        connection.close()
