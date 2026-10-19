"""Build the run index: the job a scheduler runs every 30 minutes in production.

The dashboard never crawls the bucket on a page load. This job does, once:
it lists every ``metadata.json`` under the reports, reads each run's metadata
(from the listing's object metadata when the uploader annotated it, otherwise
by downloading the file), groups the runs by month of their timestamp, writes
one shard per month, then the header last, so a reader never sees a header
naming a shard that is not there yet.

The production version bounds the listing to recent months and reuses what the
previous index already knew; a demo bucket is small enough for a full crawl.
"""

from collections import defaultdict
import datetime
import json

from google.cloud.storage import Blob, Bucket

from test_results.layout import (
    INDEX_HEADER,
    INDEX_PREFIX,
    METADATA_FILE,
    REPORTS_PREFIX,
    RUN_INDEX_METADATA_KEY,
)
from test_results.models import IndexHeader, RunMetadata, ShardRef

MONTH_LENGTH = len("YYYY-MM")
"""Characters of an ISO timestamp naming its month, the shard key."""


def _metadata(blob: Blob) -> RunMetadata:
    """Read a run's metadata, from the listing when annotated, else downloaded.

    The download goes through a fresh handle rather than the listed one, whose
    media link is the server's public URL, not always the one this client uses.
    """
    annotated = (blob.metadata or {}).get(RUN_INDEX_METADATA_KEY)
    document = annotated or blob.bucket.blob(blob.name).download_as_text()
    run_id = blob.name.removesuffix(f"/{METADATA_FILE}")
    return RunMetadata.model_validate({**json.loads(document), "id": run_id})


def crawl(bucket: Bucket) -> list[RunMetadata]:
    """List every run of the bucket, newest first.

    Args:
        bucket: Results bucket.

    Returns:
        The metadata of every run, sorted by timestamp, newest first.
    """
    runs = [
        _metadata(blob)
        for blob in bucket.list_blobs(prefix=f"{REPORTS_PREFIX}/")
        if blob.name.endswith(f"/{METADATA_FILE}")
    ]
    return sorted(runs, key=lambda run: run.timestamp, reverse=True)


def build_index(bucket: Bucket, now: datetime.datetime) -> IndexHeader:
    """Crawl the reports and write the index: shards first, header last.

    Args:
        bucket: Results bucket.
        now: Generation time written into the header.

    Returns:
        The header just written.
    """
    by_month: dict[str, list[RunMetadata]] = defaultdict(list)
    for run in crawl(bucket):
        by_month[run.timestamp[:MONTH_LENGTH]].append(run)
    shards = []
    for month in sorted(by_month, reverse=True):
        path = f"{INDEX_PREFIX}/{month}.json"
        runs = [run.model_dump() for run in by_month[month]]
        bucket.blob(path).upload_from_string(
            json.dumps(runs), content_type="application/json"
        )
        shards.append(ShardRef(month=month, path=path, run_count=len(runs)))
    header = IndexHeader(
        generated_at=now.astimezone(datetime.UTC).isoformat(),
        run_count=sum(shard.run_count for shard in shards),
        shards=shards,
    )
    bucket.blob(INDEX_HEADER).upload_from_string(
        header.model_dump_json(indent=2), content_type="application/json"
    )
    return header
