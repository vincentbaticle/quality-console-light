"""Reading JUnit XML: counts, test cases, and the metadata facets tests declare.

Tests declare who they belong to with JUnit ``<properties>`` (``system``,
``product``, ``component``...). The uploader aggregates them into the run's
``test_meta``, the dashboard filters on them.
"""

from xml.etree.ElementTree import Element

from defusedxml import ElementTree

from test_results.models import JUnitResults, JUnitTest

META_FIELDS = (
    "system",
    "product",
    "business_capability",
    "component",
    "group",
    "testing_scope",
    "tags",
)
"""Properties a test may declare, each a facet of the dashboard."""

OUTCOME_TAGS = {"failure": "failed", "error": "error", "skipped": "skipped"}
"""Child element of a ``<testcase>`` that says how it ended, and its status."""


def _case_meta(case: Element) -> dict[str, list[str]]:
    """Read the metadata properties of one test case."""
    meta: dict[str, list[str]] = {}
    for prop in case.findall("./properties/property"):
        name = prop.get("name", "")
        if name in META_FIELDS:
            values = [v.strip() for v in prop.get("value", "").split(",")]
            meta.setdefault(name, []).extend(v for v in values if v)
    return meta


def _case(case: Element) -> JUnitTest:
    """Turn one ``<testcase>`` into a test result."""
    status = "passed"
    message = None
    for tag, outcome in OUTCOME_TAGS.items():
        child = case.find(tag)
        if child is not None:
            status = outcome
            message = child.get("message") or (child.text or "").strip() or None
            break
    return JUnitTest(
        name=case.get("name", ""),
        classname=case.get("classname", ""),
        time=float(case.get("time", "0") or 0),
        status=status,
        message=message,
        meta=_case_meta(case),
    )


def parse_junit(documents: list[str]) -> JUnitResults:
    """Merge every JUnit report of a run into one result.

    Args:
        documents: Text of each JUnit XML file.

    Returns:
        The counts and the test cases of all the files together.
    """
    results = JUnitResults()
    for document in documents:
        for case in ElementTree.fromstring(document).iter("testcase"):
            test = _case(case)
            results.tests.append(test)
            results.total += 1
            if test.status == "passed":
                results.passed += 1
            elif test.status == "failed":
                results.failed += 1
            elif test.status == "error":
                results.errors += 1
            else:
                results.skipped += 1
    return results


def aggregate_test_meta(results: JUnitResults) -> dict[str, list[str]]:
    """Aggregate the facets every test declared, sorted and without repeats.

    Args:
        results: Parsed JUnit results of a run.

    Returns:
        One sorted value list per facet that at least one test declared.
    """
    facets: dict[str, set[str]] = {}
    for test in results.tests:
        for name, values in test.meta.items():
            facets.setdefault(name, set()).update(values)
    return {name: sorted(values) for name, values in sorted(facets.items())}
