"""Freezing the console into static pages: where each page goes, what is left out."""

import pytest

from quality_console.snapshot import (
    LIVE_ONLY_PAGE,
    file_for,
    is_neighbour,
    page_key,
    rewrite,
    shape,
    with_banner,
    worth_a_file,
)
from tests.metadata import metadata_test

pytestmark = [
    pytest.mark.unit,
    metadata_test(
        system="quality",
        product="quality-console",
        business_capability="operate",
        component="quality-console",
        group="qa-core",
        testing_scope="unit",
    ),
]

ORIGIN = "http://localhost:8081"
"""The console, as the crawler reaches it."""


def test_a_page_key_ignores_parameter_order_and_empty_values() -> None:
    assert page_key("/test-results", "run=r1&date_range=all&env=") == (
        "/test-results?date_range=all&run=r1"
    )
    assert page_key("/catalog", "") == "/catalog"


def test_pages_of_the_same_kind_share_a_shape() -> None:
    first = shape("/test-results?date_range=all&run=r1")
    second = shape("/test-results?date_range=all&run=r2")

    assert first == second == "/test-results?date_range,run"


def test_searches_raw_files_and_live_json_are_left_out() -> None:
    assert worth_a_file("/databases/mycompany/tables/orders")
    assert not worth_a_file("/databases/mycompany/tables/orders?search=ada")
    assert not worth_a_file("/tools/bucket/object?bucket=b&name=n")
    assert not worth_a_file("/devx/retro-footprint/experiments/x")


def test_a_query_becomes_a_hashed_file_beside_its_path() -> None:
    plain = file_for("/tools/docs", "text/html; charset=utf-8")
    queried = file_for("/tools/docs?page=gherkin", "text/html; charset=utf-8")

    assert file_for("/", "text/html") == "index.html"
    assert plain == "tools/docs.html"
    assert queried.startswith("tools/docs@") and queried.endswith(".html")
    assert queried == file_for("/tools/docs?page=gherkin", "text/html")
    assert file_for("/static/bullet-hole.svg", "image/svg+xml") == (
        "static/bullet-hole.svg"
    )


def test_links_point_at_frozen_files_or_at_the_live_only_page() -> None:
    files = {
        "/catalog": "catalog.html",
        "/tools/docs?page=gherkin": "tools/docs@abc.html",
    }
    page = (
        '<a href="/catalog">c</a>'
        '<a href="/tools/docs?page=gherkin#tldr">g</a>'
        '<a href="/databases/x?search=ada&amp;column=id">s</a>'
        '<a href="http://localhost:3000/explore">grafana</a>'
        '<a href="https://example.org">out</a>'
        '<a href="#top">top</a>'
    )

    result = rewrite(
        page, f"{ORIGIN}/tools/gherkin", "tools/gherkin.html", ORIGIN, files.get
    )

    assert 'href="../catalog.html"' in result
    assert 'href="docs@abc.html#tldr"' in result
    assert result.count(f'href="../{LIVE_ONLY_PAGE}"') == 2
    assert 'href="https://example.org"' in result
    assert 'href="#top"' in result


def test_only_other_ports_of_the_same_machine_are_neighbours() -> None:
    assert is_neighbour("http://localhost:8025/", ORIGIN)
    assert not is_neighbour(f"{ORIGIN}/catalog", ORIGIN)
    assert not is_neighbour("https://github.com/x", ORIGIN)


def test_the_banner_goes_right_after_the_body_tag() -> None:
    page = with_banner('<html><body class="x"><main></main></body></html>', "R&D")

    assert page.index('class="snapshot-banner"') < page.index("<main>")
    assert "R&amp;D#try-it-by-hand-in-five-minutes" in page
    assert with_banner("<p>no body</p>", "r") == "<p>no body</p>"
