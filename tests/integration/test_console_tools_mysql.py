"""The tools of the Quality Console, each wired to its real neighbour.

The catalog and the databases in MySQL, the bucket browser and the results on
the Cloud Storage emulator, the Gherkin runner in process running real
pytest, the repository's own contracts and features.
"""

from dataclasses import replace
from pathlib import Path
import time

from fastapi.testclient import TestClient
from google.cloud.storage import Bucket
import pytest

from company_db import DatabaseSettings
from quality_mcp.tools import QualityTools
from tests.database import reader_settings
from tests.metadata import metadata_test
from tests.neighbours import PROJECT_ROOT
from tests.sample_runs import upload_sample

pytestmark = [
    pytest.mark.integration,
    metadata_test(
        system="quality",
        product="quality-console",
        business_capability="operate",
        component="quality-console",
        group="qa-core",
        testing_scope="integration",
        tags="mysql, gcs",
    ),
]

UNREACHABLE_STACK = "http://127.0.0.1:9"
"""A storefront nobody serves: the scenarios a test runs skip, whatever runs locally."""


def test_home_lists_every_tool_and_the_services_beside(console: TestClient) -> None:
    response = console.get("/")

    assert response.status_code == 200
    for path in ("/catalog", "/tools/gherkin", "/tools/apis"):
        assert f'href="{path}"' in response.text
    assert "http://o11y.test" in response.text


def test_catalog_shows_systems_owners_and_links_to_their_data(
    console: TestClient,
) -> None:
    response = console.get("/catalog")

    assert response.status_code == 200
    for title in ("Storefront", "Orders", "Identity", "Bank", "Quality platform"):
        assert title in response.text
    assert 'href="/databases/identity"' in response.text
    assert 'href="/tools/apis/order-workflow-events"' in response.text
    assert "/test-results?date_range=all&component=hello-api" in response.text


def test_api_docs_list_every_api_of_the_catalog(console: TestClient) -> None:
    response = console.get("/tools/apis")

    assert "Bank Partner API" in response.text
    assert "Order workflow events" in response.text


def test_event_contract_has_its_own_page(console: TestClient) -> None:
    response = console.get("/tools/apis/order-workflow-events")

    assert response.status_code == 200
    assert 'id="message-reserve_stock"' in response.text
    assert "order-workflow" in response.text


def test_http_contract_opens_in_swagger_ui(console: TestClient) -> None:
    page = console.get("/tools/apis/bank-partner-api")
    definition = console.get("/tools/apis/bank-partner-api/definition")

    assert "SwaggerUIBundle" in page.text
    assert definition.headers["content-type"].startswith("application/yaml")
    assert "/balance" in definition.text


def test_unknown_api_is_a_404(console: TestClient) -> None:
    assert console.get("/tools/apis/nothing").status_code == 404


def test_gherkin_sections_are_the_products_of_the_catalog(console: TestClient) -> None:
    response = console.get("/tools/gherkin")

    assert response.status_code == 200
    for title, kind in (
        ("Customer welcome", "live"),
        ("Checkout", "live"),
        ("Account access", "live"),
        ("Partner contracts", "static"),
        ("Quality Console", "static"),
    ):
        assert f'<h3>{title} <span class="badge {kind}"' in response.text
    assert "Feature: Account emails reach the QA mailbox" in response.text


def test_release_announcements_show_the_drafts_and_the_next_start(
    console: TestClient,
) -> None:
    page = console.get("/tools/announcements")

    assert page.status_code == 200
    assert "🚀 Quality platform 1.2.0 release update" in page.text
    assert "<code>quality-console v1.2.0</code>" in page.text
    assert page.text.index("1.2.0 release update") < page.text.index(
        "1.1.0 release update"
    )


def test_the_api_docs_link_each_openapi_contract_to_its_mock(
    console: TestClient,
) -> None:
    page = console.get("/tools/apis")

    assert "They run with <code>mise run up</code>" in page.text


def test_gherkin_keeps_the_features_of_the_tool_picked(console: TestClient) -> None:
    every = console.get("/tools/gherkin")
    playwright = console.get("/tools/gherkin", params={"tool": "playwright"})

    assert 'href="/tools/gherkin?tool=playwright"' in every.text
    assert every.text.count("Feature: ") > playwright.text.count("Feature: ") > 0
    assert 'title="The scenarios of this feature are driven by pytest"' not in (
        playwright.text
    )
    assert "&tool=playwright" in playwright.text
    assert console.get("/tools/gherkin", params={"tool": "cobol"}).status_code == 404


def test_gherkin_and_live_experimentation_link_to_each_other(
    console: TestClient,
) -> None:
    gherkin = console.get("/tools/gherkin")
    home = console.get("/")

    assert 'href="http://storefront.test/#welcome"' in gherkin.text
    assert "<b>Goal</b> the happy path through the three neighbours" in gherkin.text
    for product in ("customer-welcome", "checkout", "account-access"):
        assert f'href="/tools/gherkin#{product}"' in home.text


def test_clicking_a_scenario_runs_it_and_files_the_run(
    console: TestClient, results_bucket: Bucket, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("STOREFRONT_URL", UNREACHABLE_STACK)

    response = console.post(
        "/tools/gherkin/run",
        params={
            "feature": "customer-welcome/greeting.feature",
            "scenario": "A closed customer is refused",
        },
    )

    assert response.status_code == 200
    assert "SKIPPED" in response.text
    assert "1 skipped" in response.text
    assert "The stack is not running" in response.text
    assert any(
        "/local/acceptance/" in blob.name for blob in results_bucket.list_blobs()
    )


def test_running_an_unknown_feature_is_a_404(console: TestClient) -> None:
    response = console.post("/tools/gherkin/run", params={"feature": "../etc.feature"})

    assert response.status_code == 404


def test_bucket_browser_walks_folders_and_opens_files_sandboxed(
    console: TestClient, results_bucket: Bucket, tmp_path: Path
) -> None:
    metadata, report = upload_sample(results_bucket, tmp_path)
    bucket = results_bucket.name

    root = console.get("/tools/bucket")
    folder = console.get(
        "/tools/bucket", params={"bucket": bucket, "prefix": f"{report.run_id}/"}
    )
    opened = console.get(
        "/tools/bucket/object",
        params={"bucket": bucket, "name": f"{report.run_id}/report.html"},
    )

    assert f"/tools/bucket?bucket={bucket}" in root.text
    assert "report.html" in folder.text
    assert opened.headers["content-security-policy"] == "sandbox"
    assert (
        metadata.job_name
        in console.get(
            "/tools/bucket/object",
            params={"bucket": bucket, "name": f"{report.run_id}/metadata.json"},
        ).text
    )


def test_bucket_browser_refuses_an_unknown_bucket(console: TestClient) -> None:
    response = console.get("/tools/bucket", params={"bucket": "someone-else"})

    assert response.status_code == 404


def test_home_separates_the_storefront_from_the_services_beside(
    console: TestClient,
) -> None:
    response = console.get("/")

    checkout = 'href="http://storefront.test/#checkout"'
    assert checkout in response.text
    assert f'{checkout} target="_blank"' not in response.text
    zones = [
        "<h2>Static Cockpit QA",
        "<h2>Live experimentation",
        "<h2>DevX",
    ]
    assert all(zone in response.text for zone in zones)
    positions = [response.text.index(zone) for zone in zones]
    assert positions == sorted(positions)
    assert 'href="/devx/retro-footprint"' in response.text
    assert 'class="badge mock"' in response.text
    assert "static, read-only" not in response.text
    assert "data-loading=" not in response.text
    assert 'id="snow-button"' not in response.text
    assert 'href="/devx/tips"' in response.text
    assert 'href="/tools/docs"' in response.text


def test_tips_live_in_devx_with_their_front_design_demos(console: TestClient) -> None:
    response = console.get("/devx/tips")

    for topic in ("GitLab", "Git", "SQL", "Docker", "QA", "Front design"):
        assert f'">{topic}</button>' in response.text
    assert 'id="snow-button"' in response.text
    assert '<span class="ribbon">Beta</span>' in response.text
    image = console.get("/static/bullet-hole.svg")
    assert image.headers["content-type"].startswith("image/svg+xml")


def test_documentation_shows_every_page_and_each_tool_links_to_its_own(
    console: TestClient,
) -> None:
    guide = console.get("/tools/docs")
    page = console.get("/tools/docs", params={"page": "gherkin"})
    tool = console.get("/tools/gherkin")

    assert "How to test a testcontainers test" in guide.text
    assert 'href="/tools/docs?page=gherkin"' in guide.text
    assert "Gherkin scenarios, run from the Quality Console" in page.text
    assert 'class="doc-link" href="/tools/docs?page=gherkin"' in tool.text
    assert console.get("/tools/docs", params={"page": "../README"}).status_code == 404


def test_scenario_design_draws_the_journey_and_its_gaps(console: TestClient) -> None:
    response = console.get(
        "/tools/designs",
        params={"design": "checkout", "scenario": "A closed customer cannot order"},
    )

    assert response.status_code == 200
    assert "flowchart TD" in response.text
    assert "Payment failed order unpaid" in response.text
    assert console.get("/tools/designs", params={"design": "x"}).status_code == 404


def test_recordings_list_what_was_captured_and_who_replays_it(
    console: TestClient,
) -> None:
    response = console.get("/tools/recordings")

    assert "Bank Partner answers (HTTP)" in response.text
    assert "Order workflow events (RabbitMQ)" in response.text
    assert "reserve_stock then issue_invoice then capture_payment" in response.text
    assert "tests/integration/test_orders_rabbitmq.py" in response.text


def test_leaving_sonarqube_is_a_guide_of_the_cockpit(console: TestClient) -> None:
    tools = console.get("/tools")
    guide = console.get("/tools/docs", params={"page": "sonar-decom"})

    assert 'href="/tools/docs?page=sonar-decom"' in tools.text
    assert guide.status_code == 200
    assert "a quality gate on new code without a server" in guide.text


def test_retro_footprint_offers_its_targets_and_refuses_others(
    console: TestClient,
) -> None:
    page = console.get("/devx/retro-footprint")

    assert page.status_code == 200
    assert "API only: GET /api/health" in page.text
    assert "SQL only: the backpack&#39;s stock" in page.text
    assert "API using tables: GET /api/hello?username=ada" in page.text
    assert "API using tables: POST /api/orders, until paid" in page.text
    assert "API using tables, then SQL" in page.text
    assert "Front, API, then a redirect to another front" in page.text
    assert "Run</button>" in page.text
    assert console.post("/devx/retro-footprint/run?target=x").status_code == 404
    assert console.get("/devx/retro-footprint/experiments/nope").status_code == 404


def test_a_retro_footprint_without_api_ends_failed_and_says_why(
    console: TestClient,
) -> None:
    started = console.post(
        "/devx/retro-footprint/run?target=hello", follow_redirects=False
    )
    state_url = started.headers["location"].replace(
        "/devx/retro-footprint?target=hello&experiment=",
        "/devx/retro-footprint/experiments/",
    )

    state = console.get(state_url).json()
    for _ in range(50):
        if state["done"]:
            break
        time.sleep(0.1)
        state = console.get(state_url).json()

    assert started.status_code == 303
    assert state["done"]
    assert state["phase"] == "Failed"
    assert "ConnectError" in state["error"]


def test_the_database_page_splits_live_tables_from_static_ones(
    console: TestClient,
) -> None:
    response = console.get("/databases/mycompany")

    live = response.text.index("Live experimentation")
    static = response.text.index(">Static <")
    assert live < response.text.index('/tables/orders"') < static
    assert static < response.text.index('/tables/customers"')
    assert 'data-loading="Reading orders"' in response.text


def test_utility_tools_hold_the_audio_asset_generator_with_its_doc(
    console: TestClient,
) -> None:
    home = console.get("/")
    utility = console.get("/utility")
    page = console.get("/utility/audio-assets")

    assert "Utility tools" in home.text
    assert 'href="/utility/audio-assets"' in utility.text
    assert page.status_code == 200
    assert "No track yet" in page.text
    assert "page=audio-assets" in page.text


def test_audio_assets_are_generated_listed_served_and_deleted(
    console: TestClient,
) -> None:
    body = {
        "duration_seconds": 1,
        "file_format": "flac",
        "bit_depth": 16,
        "sample_rate": 44100,
        "channels": "mono",
        "files": 2,
        "prefix": "qa",
    }

    written = console.post("/utility/audio-assets/generate", json=body)
    names = written.json()["files"]
    page = console.get("/utility/audio-assets")
    track = console.get(f"/utility/audio-assets/files/{names[0]}?inline=true")
    deleted = console.delete(f"/utility/audio-assets/files/{names[0]}")
    after = console.get("/utility/audio-assets")

    assert written.status_code == 200
    assert len(names) == 2
    assert all(name in page.text for name in names)
    assert track.headers["content-type"] == "audio/flac"
    assert track.content.startswith(b"fLaC")
    assert deleted.status_code == 204
    assert names[0] not in after.text
    assert names[1] in after.text


def test_audio_assets_refuse_what_the_rules_exclude_and_unknown_files(
    console: TestClient,
) -> None:
    body = {
        "duration_seconds": 1,
        "file_format": "flac",
        "bit_depth": 32,
        "sample_rate": 48000,
        "channels": "stereo",
        "files": 1,
        "prefix": "qa",
    }

    refused = console.post("/utility/audio-assets/generate", json=body)

    assert refused.status_code == 422
    assert any("FLAC has no 32-bit" in p for p in refused.json()["detail"])
    assert console.get("/utility/audio-assets/files/nope.wav").status_code == 404
    assert (
        console.delete("/utility/audio-assets/files/..%2Fpyproject.toml").status_code
        == 404
    )


def test_the_mcp_tools_reach_the_scenarios_the_results_and_retro_footprint(
    console: TestClient, runner: TestClient, results_bucket: Bucket, tmp_path: Path
) -> None:
    upload_sample(results_bucket, tmp_path, job_name="api-tests", status="failed")
    tools = QualityTools(
        console=console,
        runner=runner,
        bucket=results_bucket,
        features=PROJECT_ROOT / "features",
        sleep=lambda _: None,
    )

    scenarios = {f["feature"]: f for f in tools.list_scenarios()}
    failed = tools.recent_runs(status="failed")
    unknown = tools.run_scenario("nope/nope.feature")
    footprint = tools.table_footprint("hello")

    assert scenarios["partner-contracts/bank-partner.feature"]["scenarios"][0]["goal"]
    assert [run["job"] for run in failed] == ["api-tests"]
    assert "Unknown feature" in unknown["error"]
    assert "hello" in tools.footprint_targets()
    assert footprint["done"] is True
    assert footprint["error"]
    assert "Unknown test" in tools.table_footprint("x")["error"]


def test_the_mcp_tools_check_a_scenario_name_the_accounts_and_clean_a_recording(
    console: TestClient,
    runner: TestClient,
    results_bucket: Bucket,
    database: DatabaseSettings,
    tmp_path: Path,
) -> None:
    tools = QualityTools(
        console=console,
        runner=runner,
        bucket=results_bucket,
        features=PROJECT_ROOT / "features",
        identity=replace(reader_settings(database), name="identity"),
    )
    raw = tmp_path / "raw-sign-in.py"
    raw.write_text('page.get_by_label("Password").fill("Foundation-2026")')

    draft = tools.check_scenario(
        "Feature: x\n  Scenario: y\n    When I sign in\n    Then I am in"
    )
    accounts = {a["email"]: a["profile"] for a in tools.test_accounts()}
    cleaned = tools.scrub_recording(str(raw))

    assert draft["ready"] is False
    assert any("No actor" in p for p in draft["problems"])
    assert accounts["qa-mailbox+lin@mycompany.test"].endswith("and a second factor")
    assert "blocked" in accounts["qa-mailbox+grace@mycompany.test"]
    assert "Foundation-2026" not in (tmp_path / "sign-in.py").read_text()
    assert not raw.exists()
    assert cleaned["recording"]["findings"][0]["line"] == 1


def test_the_vault_page_says_when_no_vault_is_configured(console: TestClient) -> None:
    devx = console.get("/devx")
    page = console.get("/devx/vault")

    assert 'href="/devx/vault"' in devx.text
    assert page.status_code == 200
    assert "No Vault configured" in page.text
    assert "page=vault" in page.text
