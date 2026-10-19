"""An AsyncAPI document turned into what its page shows.

Swagger UI renders OpenAPI only; an event contract gets its own page, built
here from the document: the channels, who sends and receives what, and each
message with its payload fields and examples.
"""

from dataclasses import dataclass
import json
from typing import Any


@dataclass(frozen=True)
class Field:
    """One property of a payload."""

    name: str
    type: str
    required: bool
    description: str
    allowed: str


@dataclass(frozen=True)
class Message:
    """One message and its payload."""

    key: str
    name: str
    title: str
    summary: str
    fields: list[Field]
    examples: list[tuple[str, str]]


@dataclass(frozen=True)
class Operation:
    """Who sends or receives which messages on which channel."""

    key: str
    action: str
    title: str
    summary: str
    channel: str
    messages: list[str]


@dataclass(frozen=True)
class Channel:
    """Where messages travel."""

    key: str
    address: str
    title: str
    description: str


@dataclass(frozen=True)
class AsyncApiView:
    """Everything the page shows."""

    title: str
    version: str
    description: str
    servers: list[tuple[str, str]]
    channels: list[Channel]
    operations: list[Operation]
    messages: list[Message]


def resolve(document: dict[str, Any], node: Any) -> Any:
    """Follow a local ``$ref`` (``#/a/b``) until a real node.

    Args:
        document: The whole document.
        node: A node that may be a reference.

    Returns:
        The node the reference points to, or the node itself.
    """
    while isinstance(node, dict) and "$ref" in node:
        target: Any = document
        for part in node["$ref"].removeprefix("#/").split("/"):
            target = target[part]
        node = target
    return node


def _fields(document: dict[str, Any], schema: dict[str, Any]) -> list[Field]:
    """The properties of an object schema."""
    schema = resolve(document, schema)
    required = set(schema.get("required", []))
    rows = []
    for name, prop in schema.get("properties", {}).items():
        prop = resolve(document, prop)
        kind = prop.get("type", "")
        if prop.get("format"):
            kind = f"{kind} ({prop['format']})"
        rows.append(
            Field(
                name=name,
                type=kind,
                required=name in required,
                description=prop.get("description", ""),
                allowed=", ".join(str(v) for v in prop.get("enum", [])),
            )
        )
    return rows


def _message_key(document: dict[str, Any], ref: dict[str, Any]) -> str:
    """Name of the component message a channel or operation reference ends on."""
    return str(resolve(document, ref).get("name", ""))


def view(document: dict[str, Any]) -> AsyncApiView:
    """Build the page of an AsyncAPI 3 document.

    Args:
        document: The parsed YAML.

    Returns:
        What the page shows.
    """
    info = document.get("info", {})
    channels = [
        Channel(
            key,
            channel.get("address", key),
            channel.get("title", key),
            channel.get("description", ""),
        )
        for key, channel in document.get("channels", {}).items()
    ]
    addresses = {f"#/channels/{c.key}": c.address for c in channels}
    operations = [
        Operation(
            key=key,
            action=operation.get("action", ""),
            title=operation.get("title", key),
            summary=operation.get("summary", ""),
            channel=addresses.get(operation.get("channel", {}).get("$ref", ""), ""),
            messages=[_message_key(document, m) for m in operation.get("messages", [])],
        )
        for key, operation in document.get("operations", {}).items()
    ]
    messages = [
        Message(
            key=key,
            name=message.get("name", key),
            title=message.get("title", key),
            summary=message.get("summary", ""),
            fields=_fields(document, message.get("payload", {})),
            examples=[
                (example.get("name", ""), json.dumps(example.get("payload"), indent=2))
                for example in message.get("examples", [])
            ],
        )
        for key, message in document.get("components", {}).get("messages", {}).items()
    ]
    return AsyncApiView(
        title=info.get("title", ""),
        version=info.get("version", ""),
        description=info.get("description", ""),
        servers=[
            (f"{s.get('protocol', '')}://{s.get('host', '')}", s.get("description", ""))
            for s in document.get("servers", {}).values()
        ],
        channels=channels,
        operations=operations,
        messages=messages,
    )
