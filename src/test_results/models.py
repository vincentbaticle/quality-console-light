"""Shapes of what the bucket holds, as the dashboard API declares them."""

from pydantic import BaseModel, Field


class RunMetadata(BaseModel):
    """``metadata.json`` of one CI job run, plus its id once read back.

    ``test_counts`` keeps what its JUnit reports count (``total``, ``passed``,
    ``failed``, ``errors``, ``skipped``): a job of ten tests with two errors
    fails as a whole, the counts say how much of it did.
    """

    id: str = ""
    pipeline_id: str
    job_id: str
    job_name: str
    artifact_type: str
    commit_sha: str
    env: str
    timestamp: str
    ci_job_status: str | None
    project_url: str = ""
    test_meta: dict[str, list[str]] = Field(default_factory=dict)
    test_counts: dict[str, int] = Field(default_factory=dict)


class JUnitTest(BaseModel):
    """One test case of a JUnit report."""

    name: str
    classname: str
    time: float
    status: str
    message: str | None
    meta: dict[str, list[str]] = Field(default_factory=dict)


class JUnitResults(BaseModel):
    """Counts and test cases of every JUnit report of a run."""

    total: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    tests: list[JUnitTest] = Field(default_factory=list)


class PerfSummary(BaseModel):
    """What a k6 load test summary says about a run."""

    req_count: int
    req_rate: float
    error_rate: float
    duration_avg: float
    duration_p95: float
    duration_p99: float
    threshold_breaches: int
    breaches: list[str]


class RunDetail(BaseModel):
    """Everything the run page shows."""

    metadata: RunMetadata
    artifacts: list[str]
    junit: JUnitResults | None
    perf_summary: PerfSummary | None


class ShardRef(BaseModel):
    """One month shard of the index, as the header lists it."""

    month: str
    path: str
    run_count: int


class IndexHeader(BaseModel):
    """The run index header the dashboard reads first."""

    generated_at: str
    run_count: int
    shards: list[ShardRef]
