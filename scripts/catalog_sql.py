"""Regenerate ``db/05-catalog.sql`` from ``catalog/catalog.yaml``.

Run after any edit of the catalog: ``mise run catalog:sql``. The script refuses
a catalog naming an entity it does not declare.
"""

from pathlib import Path
import sys

from catalog.model import dangling_references, load_catalog
from catalog.sql import render_sql

ROOT = Path(__file__).resolve().parent.parent
"""Root of the repository."""

CATALOG_FILE = ROOT / "catalog" / "catalog.yaml"
"""The catalog as code."""

SQL_FILE = ROOT / "db" / "05-catalog.sql"
"""The script MySQL loads, generated from the catalog."""


def main() -> int:
    """Check the catalog, then write its SQL script.

    Returns:
        The process exit code.
    """
    catalog = load_catalog(CATALOG_FILE)
    broken = dangling_references(catalog)
    for line in broken:
        print(f"[catalog] {line}")
    if broken:
        return 1
    SQL_FILE.write_text(render_sql(catalog))
    print(f"[catalog] {SQL_FILE.relative_to(ROOT)} written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
