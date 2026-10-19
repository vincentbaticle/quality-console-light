"""Bucket checks: the same generic contract, checked on every team bucket."""

from collections.abc import Callable
import csv
import datetime
import io
import json
import re

from google.cloud import storage
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.acceptance.conftest import Context, Stack
from tests.metadata import metadata_test

pytestmark = [
    pytest.mark.acceptance,
    metadata_test(
        system="data-exchange",
        product="bucket-checks",
        business_capability="operate",
        component="bucket-checks",
        group="qa-core",
        testing_scope="acceptance",
        tags="gcs",
    ),
]

scenarios("bucket-checks")

READERS: dict[str, Callable[[str], object]] = {
    "csv": lambda text: list(csv.DictReader(io.StringIO(text))),
    "json": json.loads,
}
"""How each format is read; a file that does not read raises."""


@given(parsers.parse('the files of bucket "{bucket}" under "{prefix}"'))
def files_of(stack: Stack, context: Context, bucket: str, prefix: str) -> None:
    client = stack.storage_client()
    context.values["bucket"] = client.bucket(bucket)
    context.values["prefix"] = prefix
    context.values["blobs"] = [
        b for b in client.list_blobs(bucket, prefix=prefix) if b.name != prefix
    ]


def blobs(context: Context) -> list[storage.Blob]:
    return context.values["blobs"]


@then("there is at least one file")
def at_least_one(context: Context) -> None:
    assert blobs(context), f"no file under {context.values['prefix']}"


@then(parsers.parse('every file name matches "{pattern}"'))
def names_match(context: Context, pattern: str) -> None:
    wrong = [b.name for b in blobs(context) if not re.match(pattern, b.name)]
    assert wrong == []


@then("no file is empty")
def none_empty(context: Context) -> None:
    assert [b.name for b in blobs(context) if not b.size] == []


@then(parsers.parse("every file reads as {file_format}"))
def reads_as(context: Context, file_format: str) -> None:
    for blob in blobs(context):
        assert READERS[file_format](blob.download_as_text()), blob.name


@then(parsers.parse("the newest file is less than {hours:d} hours old"))
def fresh(context: Context, hours: int) -> None:
    newest = max(b.updated for b in blobs(context))
    age = datetime.datetime.now(datetime.UTC) - newest
    assert age < datetime.timedelta(hours=hours), f"newest file is {age} old"


@when(parsers.parse('the manifest "{name}" of the bucket is read'))
def read_manifest(context: Context, name: str) -> None:
    text = context.values["bucket"].blob(name).download_as_text()
    context.values["manifest"] = set(json.loads(text)["files"])


@then("every file it lists exists")
def listed_exist(context: Context) -> None:
    present = {b.name for b in blobs(context)}
    assert context.values["manifest"] - present == set()


@then("every file under the prefix is listed")
def all_listed(context: Context) -> None:
    present = {b.name for b in blobs(context)}
    assert present - context.values["manifest"] == set()
