"""Every test declares who it belongs to, in the words of the software catalog."""

import ast
from pathlib import Path

import pytest

from catalog.model import Catalog, dangling_references, load_catalog
from catalog.sql import render_sql
from scripts.catalog_sql import CATALOG_FILE, SQL_FILE
from scripts.seed_results import JOBS
from tests.metadata import REQUIRED_FIELDS, TESTING_SCOPES, metadata_test
from tests.neighbours import PROJECT_ROOT

pytestmark = [
    pytest.mark.unit,
    metadata_test(
        system="quality",
        product="test-results",
        business_capability="operate",
        component="test-results-uploader",
        group="qa-core",
        testing_scope="unit",
    ),
]

TEST_MODULES = sorted((PROJECT_ROOT / "tests").rglob("test_*.py"))
"""Every test module of the repository."""


def declared_metadata(module: Path) -> list[dict[str, str]]:
    """Read the literal keyword arguments of every ``metadata_test`` call.

    A call unpacking a dict is skipped: it builds metadata on purpose, to test
    ``metadata_test`` itself.
    """
    calls = [
        node
        for node in ast.walk(ast.parse(module.read_text()))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "metadata_test"
        and all(k.arg for k in node.keywords)
    ]
    return [
        {
            k.arg: str(k.value.value)
            for k in call.keywords
            if k.arg and isinstance(k.value, ast.Constant)
        }
        for call in calls
    ]


def catalog_errors(meta: dict[str, str], catalog: Catalog) -> list[str]:
    """Name each metadata value the catalog does not know."""
    known = {
        "system": {s.name for s in catalog.systems},
        "product": {p.name for p in catalog.products},
        "business_capability": {c.name for c in catalog.business_capabilities},
        "component": {c.name for c in catalog.components},
        "group": {t.name for t in catalog.teams},
        "testing_scope": set(TESTING_SCOPES),
    }
    return [
        f"{field}={meta.get(field)!r}"
        for field in REQUIRED_FIELDS
        if meta.get(field) not in known[field]
    ]


@pytest.fixture(scope="module")
def catalog() -> Catalog:
    return load_catalog(CATALOG_FILE)


def test_catalog_references_only_what_it_declares(catalog: Catalog) -> None:
    assert dangling_references(catalog) == []


def test_catalog_sql_is_generated_from_the_catalog(catalog: Catalog) -> None:
    assert SQL_FILE.read_text() == render_sql(catalog), "run mise run catalog:sql"


@pytest.mark.parametrize(
    "module", TEST_MODULES, ids=lambda m: str(m.relative_to(PROJECT_ROOT))
)
def test_every_test_module_declares_catalog_metadata(
    module: Path, catalog: Catalog
) -> None:
    declared = declared_metadata(module)

    assert declared, "no metadata_test(...) in this module"
    for meta in declared:
        assert catalog_errors(meta, catalog) == []


@pytest.mark.parametrize("job", JOBS, ids=lambda job: job.name)
def test_seeded_history_uses_catalog_metadata(job, catalog: Catalog) -> None:
    assert catalog_errors(job.meta, catalog) == []


def test_metadata_test_refuses_a_missing_owner() -> None:
    without_group = {
        "system": "storefront",
        "product": "checkout",
        "business_capability": "sell",
        "component": "front",
        "testing_scope": "e2e",
    }

    with pytest.raises(TypeError, match="group"):
        metadata_test(**without_group)
