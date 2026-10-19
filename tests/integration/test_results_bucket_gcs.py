"""Upload, index and read back runs on a real Cloud Storage emulator."""

import datetime
import json
from pathlib import Path

from google.cloud.storage import Bucket
import pytest

from test_results.index import build_index
from test_results.layout import INDEX_HEADER, RUN_INDEX_METADATA_KEY
from test_results.reader import ResultsReader, RunFilters, RunNotFoundError
from tests.metadata import metadata_test
from tests.sample_runs import upload_sample

pytestmark = [
    pytest.mark.integration,
    metadata_test(
        system="quality",
        product="test-results",
        business_capability="operate",
        component="test-results-uploader",
        group="qa-core",
        testing_scope="integration",
        tags="gcs",
    ),
]


INDEXED_AT = datetime.datetime(2026, 10, 1, 12, 0, tzinfo=datetime.UTC)
"""When the tests build the index."""


def test_upload_writes_the_run_folder_ci_writes(
    results_bucket: Bucket, tmp_path: Path
) -> None:
    metadata, report = upload_sample(results_bucket, tmp_path)

    run_id = "test-runner/reports/int/backend/20260915_083005_4242/api-tests"
    assert report.run_id == run_id
    assert sorted(blob.name for blob in results_bucket.list_blobs()) == [
        f"{run_id}/junit.xml",
        f"{run_id}/metadata.json",
        f"{run_id}/report.html",
    ]
    written = results_bucket.get_blob(f"{run_id}/metadata.json")
    assert written is not None
    document = json.loads(results_bucket.blob(written.name).download_as_text())
    assert document["test_meta"]["tags"] == ["redis", "smoke"]
    assert document["test_counts"] == {
        "total": 3,
        "passed": 2,
        "failed": 1,
        "errors": 0,
        "skipped": 0,
    }
    assert json.loads(written.metadata[RUN_INDEX_METADATA_KEY]) == json.loads(
        metadata.model_dump_json(exclude={"id"})
    )


def test_index_has_one_shard_per_month_and_its_header_last(
    results_bucket: Bucket, tmp_path: Path
) -> None:
    upload_sample(results_bucket, tmp_path / "a")
    upload_sample(
        results_bucket,
        tmp_path / "b",
        when=datetime.datetime(2026, 10, 2, 9, 0, tzinfo=datetime.UTC),
    )

    header = build_index(results_bucket, INDEXED_AT)

    assert header.run_count == 2
    assert [shard.month for shard in header.shards] == ["2026-10", "2026-09"]
    assert results_bucket.blob(INDEX_HEADER).exists()


def test_reader_filters_the_index_and_reads_a_run_in_detail(
    results_bucket: Bucket, tmp_path: Path
) -> None:
    upload_sample(results_bucket, tmp_path / "a", env="int", status="failed")
    upload_sample(
        results_bucket,
        tmp_path / "b",
        env="sta",
        status="success",
        when=datetime.datetime(2026, 9, 16, 8, 0, tzinfo=datetime.UTC),
    )
    build_index(results_bucket, INDEXED_AT)
    reader = ResultsReader(results_bucket)

    failed = reader.runs(RunFilters(status="failed"))
    tagged = reader.runs(RunFilters(facets={"tags": "smoke"}))
    detail = reader.detail(failed[0].id)

    assert [run.env for run in failed] == ["int"]
    assert len(tagged) == 2
    assert detail.junit is not None
    assert (detail.junit.total, detail.junit.failed) == (3, 1)
    assert detail.perf_summary is None


def test_reader_refuses_paths_outside_the_reports(results_bucket: Bucket) -> None:
    reader = ResultsReader(results_bucket)

    with pytest.raises(RunNotFoundError):
        reader.artifact(INDEX_HEADER)


def test_nothing_indexed_reads_as_empty_not_as_an_error(results_bucket: Bucket) -> None:
    reader = ResultsReader(results_bucket)

    assert reader.header() is None
    assert reader.runs(RunFilters()) == []
