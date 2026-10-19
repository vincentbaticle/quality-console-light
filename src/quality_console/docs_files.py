"""Reading the documentation of the repository, ``docs/**/*.md``.

The pages stay in the repository, versioned beside the code they describe;
the console only shows them, grouped, each link to another page turned into a
link inside the console.
"""

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import posixpath
import re

from markdown_it import MarkdownIt

MARKDOWN = MarkdownIt("commonmark", {"html": False}).enable("table")
"""Renders a page, raw HTML disabled so a page cannot script the console."""

DOCS_PATH = "/tools/docs"
"""Where the console shows the documentation."""

GUIDES = ("testing-with-testcontainers", "sonar-decom")
"""Pages that are not about one tool or one product, shown first."""

PRODUCTS = ("order-workflow", "account-access")
"""Pages about a product of the storefront."""

DEMOS_FOLDER = "demos"
"""Folder of the demo scripts."""

GROUP_ORDER = ("Guides", "Tools", "Products", "Demo scripts")
"""Groups of the sidebar, in order."""

DOC_LINK = re.compile(r'href="(?![a-z]+:|/|#)([^"#]+)\.md(#[^"]*)?"')
"""A link of a rendered page to another page of the documentation."""


@dataclass(frozen=True)
class Doc:
    """One page of the documentation."""

    slug: str
    title: str
    group: str
    html: str


def _group(slug: str) -> str:
    """Say which group of the sidebar a page belongs to."""
    if slug in GUIDES:
        return "Guides"
    if slug in PRODUCTS:
        return "Products"
    if slug.startswith(f"{DEMOS_FOLDER}/"):
        return "Demo scripts"
    return "Tools"


def _title(text: str, slug: str) -> str:
    """The first level-one heading, the slug when there is none."""
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return slug


def _console_links(html: str, slug: str) -> str:
    """Point the links to other pages at the console's documentation tool."""
    folder = PurePosixPath(slug).parent.as_posix()

    def replace(match: re.Match[str]) -> str:
        target = posixpath.normpath(posixpath.join(folder, match.group(1)))
        return f'href="{DOCS_PATH}?page={target}{match.group(2) or ""}"'

    return DOC_LINK.sub(replace, html)


def load_docs(root: Path) -> list[Doc]:
    """Read every page under a folder.

    Args:
        root: The ``docs`` folder; absent means no documentation.

    Returns:
        The pages, by group then by title.
    """
    if not root.is_dir():
        return []
    docs = []
    for path in root.rglob("*.md"):
        slug = path.relative_to(root).with_suffix("").as_posix()
        text = path.read_text()
        docs.append(
            Doc(
                slug=slug,
                title=_title(text, slug),
                group=_group(slug),
                html=_console_links(MARKDOWN.render(text), slug),
            )
        )
    return sorted(docs, key=lambda d: (GROUP_ORDER.index(d.group), d.title.lower()))
