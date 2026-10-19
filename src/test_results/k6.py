"""Reading a k6 summary (``k6 run --summary-export``) into the dashboard's terms."""

import json
from typing import Any

from test_results.models import PerfSummary

SUMMARY_FILE = "summary.json"
"""Name a load test run gives its k6 summary export."""

MILLISECONDS_DECIMALS = 1
"""Precision kept for durations, enough for a dashboard."""


def parse_k6_summary(document: str) -> PerfSummary:
    """Extract request counts, error rate, durations and broken thresholds.

    Args:
        document: Text of the k6 summary export.

    Returns:
        The performance summary of the run.
    """
    metrics: dict[str, Any] = json.loads(document)["metrics"]
    requests = metrics["http_reqs"]
    durations = metrics["http_req_duration"]
    breaches = [
        f"{name}: {threshold}"
        for name, metric in sorted(metrics.items())
        for threshold, verdict in sorted(metric.get("thresholds", {}).items())
        if not verdict.get("ok", True)
    ]
    return PerfSummary(
        req_count=int(requests["count"]),
        req_rate=round(float(requests["rate"]), 2),
        error_rate=round(float(metrics["http_req_failed"]["value"]), 4),
        duration_avg=round(float(durations["avg"]), MILLISECONDS_DECIMALS),
        duration_p95=round(float(durations["p(95)"]), MILLISECONDS_DECIMALS),
        duration_p99=round(float(durations["p(99)"]), MILLISECONDS_DECIMALS),
        threshold_breaches=len(breaches),
        breaches=breaches,
    )
