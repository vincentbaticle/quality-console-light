"""Who a test belongs to, declared the way the team's test runner does it.

A test module (or a class, or one test) carries a ``metadata`` marker built by
``metadata_test``, with the same fields as the runner's decorator: ``system``,
``product``, ``business_capability``, ``component``, ``group``,
``testing_scope`` and ``tags``. ``tests/conftest.py`` writes them as JUnit
properties, the uploader aggregates them into the run, the Quality Console
filters on them, and ``tests/unit/test_metadata_catalog.py`` checks that every
value names an entry of ``catalog/catalog.yaml``.
"""

import pytest

METADATA_MARKER = "metadata"
"""Name of the pytest marker holding the metadata."""

REQUIRED_FIELDS = (
    "system",
    "product",
    "business_capability",
    "component",
    "group",
    "testing_scope",
)
"""Fields every test must declare, so no run lands without an owner."""

OPTIONAL_FIELDS = ("tags",)
"""Fields a test may add, a comma-separated list of free labels."""

TESTING_SCOPES = (
    "unit",
    "integration",
    "contract",
    "e2e",
    "acceptance",
    "regression",
    "performance",
)
"""Scopes a test may declare, from the narrowest to the widest."""


def metadata_test(**fields: str) -> pytest.MarkDecorator:
    """Declare who a test belongs to.

    Use it as a decorator on a test or a class, or in a module's
    ``pytestmark`` list to cover every test of the module.

    Args:
        **fields: The metadata, every field of ``REQUIRED_FIELDS`` and at most
            those of ``OPTIONAL_FIELDS``.

    Returns:
        The marker carrying the metadata.

    Raises:
        TypeError: When a required field is missing or an unknown one is given.
    """
    missing = [name for name in REQUIRED_FIELDS if not fields.get(name)]
    unknown = sorted(set(fields) - set(REQUIRED_FIELDS) - set(OPTIONAL_FIELDS))
    if missing or unknown:
        raise TypeError(f"metadata_test: missing {missing}, unknown {unknown}")
    return getattr(pytest.mark, METADATA_MARKER)(**fields)
