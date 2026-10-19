"""The MCP server: the tools of ``tools.py``, over stdio, wired to the local stack."""

import os
from pathlib import Path

import httpx
from mcp.server.fastmcp import FastMCP

from company_db import DatabaseSettings
from quality_mcp.tools import QualityTools
from test_results.storage import open_bucket

URLS = {
    "console": ("QC_CONSOLE_URL", "http://localhost:8081"),
    "runner": ("QC_RUNNER_URL", "http://localhost:8082"),
}
"""Where the console and the runner answer, the ports of docker-compose.yml."""

STORAGE_DEFAULTS = {
    "STORAGE_EMULATOR_HOST": "http://localhost:4443",
    "RESULTS_BUCKET": "test-results",
}
"""The results bucket of the stack, unless the environment says otherwise."""

IDENTITY = DatabaseSettings(
    host="127.0.0.1",
    port=3307,
    user="console_reader",
    password="reader",  # noqa: S106
    name="identity",
)
"""The identity database of the stack, through the console's read-only account."""

RUN_TIMEOUT_SECONDS = 330
"""Budget of one scenario run, the runner's own plus a margin."""

PROJECT_ROOT = Path(__file__).resolve().parents[2]
"""The repository, whose ``features/`` the scenarios come from."""


def build_server(tools: QualityTools) -> FastMCP:
    """Register each tool under its name, its docstring as its description.

    Args:
        tools: What the tools do.

    Returns:
        The server, ready to run.
    """
    server = FastMCP("quality-console")
    for method in (
        tools.list_scenarios,
        tools.run_scenario,
        tools.recent_runs,
        tools.footprint_targets,
        tools.table_footprint,
        tools.check_scenario,
        tools.test_accounts,
        tools.scrub_recording,
    ):
        server.add_tool(method)
    return server


def main() -> None:
    """Serve the tools over stdio, against the stack ``mise run up`` started."""
    for name, value in STORAGE_DEFAULTS.items():
        os.environ.setdefault(name, value)
    url = {name: os.environ.get(var, default) for name, (var, default) in URLS.items()}
    tools = QualityTools(
        console=httpx.Client(base_url=url["console"], timeout=30),
        runner=httpx.Client(base_url=url["runner"], timeout=RUN_TIMEOUT_SECONDS),
        bucket=open_bucket(os.environ["RESULTS_BUCKET"]),
        features=PROJECT_ROOT / "features",
        identity=IDENTITY,
    )
    build_server(tools).run()
