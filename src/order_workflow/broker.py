"""RabbitMQ: where the workflow's events go, and how they are read back."""

from collections.abc import Callable
from dataclasses import dataclass
import json
import os
from urllib.parse import quote, urlsplit, urlunsplit

import pika
from pika.adapters.blocking_connection import BlockingChannel
from pika.spec import Basic

from company_secrets import read_env_file

QUEUE = "order-workflow"
"""Durable queue every step event goes through."""

JSON_CONTENT_TYPE = "application/json"
"""Content type of an event body."""

URL_VARIABLE = "RABBITMQ_URL"
"""Variable holding the AMQP URL of the broker."""

CREDENTIALS_FILE_VARIABLE = "RABBITMQ_CREDENTIALS_FILE"
"""File holding ``RABBITMQ_USER`` and ``RABBITMQ_PASSWORD``, kept fresh by the agent."""

BrokerUrl = str | Callable[[], str]
"""The broker's AMQP URL, or what gives it afresh (short-lived credentials)."""


def with_credentials(url: str, user: str, password: str) -> str:
    """Put a user and a password into an AMQP URL, in place of any there.

    Args:
        url: The broker's URL, with or without credentials.
        user: The user to connect as.
        password: Its password.

    Returns:
        The URL carrying them.
    """
    parts = urlsplit(url)
    host = parts.netloc.rsplit("@", 1)[-1]
    netloc = f"{quote(user, safe='')}:{quote(password, safe='')}@{host}"
    return urlunsplit(parts._replace(netloc=netloc))


def url_from_environment() -> BrokerUrl:
    """The broker's URL as the environment gives it.

    Returns:
        ``RABBITMQ_URL`` as it is, or, with a credentials file, a function
        reading the file again on every connection.
    """
    url = os.environ[URL_VARIABLE]
    credentials_file = os.environ.get(CREDENTIALS_FILE_VARIABLE)
    if not credentials_file:
        return url

    def fresh() -> str:
        values = read_env_file(credentials_file)
        return with_credentials(
            url, values["RABBITMQ_USER"], values["RABBITMQ_PASSWORD"]
        )

    return fresh


@dataclass(frozen=True)
class StepEvent:
    """A thin event: which workflow, which step to run now."""

    workflow_id: str
    type: str

    def to_json(self) -> bytes:
        """Serialise the event for the broker."""
        return json.dumps({"workflow_id": self.workflow_id, "type": self.type}).encode()

    @classmethod
    def from_json(cls, body: bytes) -> StepEvent:
        """Read an event back from the broker."""
        data = json.loads(body)
        return cls(workflow_id=data["workflow_id"], type=data["type"])


def _channel(url: BrokerUrl) -> tuple[pika.BlockingConnection, BlockingChannel]:
    """Open a connection and a channel, with the queue declared."""
    address = url() if callable(url) else url
    connection = pika.BlockingConnection(pika.URLParameters(address))
    channel = connection.channel()
    channel.queue_declare(queue=QUEUE, durable=True)
    return connection, channel


def publisher(url: BrokerUrl) -> Callable[[StepEvent], None]:
    """Return a function publishing one event, a connection per event.

    Args:
        url: AMQP URL of the broker, or what gives it afresh.

    Returns:
        The publish function.
    """

    def publish(event: StepEvent) -> None:
        connection, channel = _channel(url)
        try:
            channel.basic_publish(
                exchange="",
                routing_key=QUEUE,
                body=event.to_json(),
                properties=pika.BasicProperties(
                    content_type=JSON_CONTENT_TYPE, delivery_mode=2
                ),
            )
        finally:
            connection.close()

    return publish


def consume_forever(url: BrokerUrl, handle: Callable[[StepEvent], None]) -> None:
    """Handle every event of the queue as it arrives, one at a time.

    An event is acknowledged once handled, so a worker that dies mid-step
    gets it again on restart.

    Args:
        url: AMQP URL of the broker, or what gives it afresh.
        handle: What to do with each event.
    """
    connection, channel = _channel(url)
    channel.basic_qos(prefetch_count=1)

    def on_message(
        ch: BlockingChannel,
        method: Basic.Deliver,
        _properties: pika.BasicProperties,
        body: bytes,
    ) -> None:
        handle(StepEvent.from_json(body))
        ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_consume(queue=QUEUE, on_message_callback=on_message)
    try:
        channel.start_consuming()
    finally:
        if connection.is_open:
            connection.close()


def drain(url: BrokerUrl, handle: Callable[[StepEvent], None]) -> int:
    """Handle the events waiting in the queue, including the ones they publish.

    What a test calls instead of running the worker: it returns once the queue
    is empty, so the workflow is over.

    Args:
        url: AMQP URL of the broker, or what gives it afresh.
        handle: What to do with each event.

    Returns:
        How many events were handled.
    """
    connection, channel = _channel(url)
    handled = 0
    try:
        while True:
            method, _properties, body = channel.basic_get(queue=QUEUE)
            if method is None:
                return handled
            handle(StepEvent.from_json(body))
            channel.basic_ack(delivery_tag=method.delivery_tag)
            handled += 1
    finally:
        connection.close()
