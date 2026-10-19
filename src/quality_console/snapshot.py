"""Freezing the console into static pages: which page goes where, which to skip.

The demo of the repository is a snapshot of the running console, served as
plain files (GitHub Pages). A crawler (``scripts/freeze_console.py``) reads the
console page by page; these rules say which address becomes which file, which
addresses are not worth a file, and how a page's links are rewritten so the
snapshot browses on its own, without a server answering query strings.
"""

from collections.abc import Callable
import hashlib
import html
import posixpath
import re
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit

SKIPPED_PARAMETERS = frozenset(
    {"search", "column", "value", "offset", "order", "page_size"}
)
"""Query parameters of searches and paging: endless variants, no new content."""

SKIPPED_PREFIXES = (
    "/test-results/artifact",
    "/test-results/run",
    "/tools/bucket/object",
    "/utility/audio-assets/files",
    "/devx/retro-footprint/experiments",
)
"""Paths serving raw files or live JSON rather than a page to read."""

PAGES_PER_SHAPE = 40
"""Pages kept per shape (a path and the names of its parameters), first found first."""

LIVE_ONLY_PAGE = "live-only.html"
"""Where a link to a service beside the console (Grafana, the mailbox) leads."""

LINK = re.compile(r'(?P<attr>\b(?:href|src))="(?P<url>[^"]*)"')
"""A link or a resource of a page, the only addresses the snapshot rewrites."""

BODY = re.compile(r"<body[^>]*>", re.IGNORECASE)
"""The opening body tag the banner goes right after."""

UNTOUCHED_SCHEMES = ("mailto:", "javascript:", "data:", "tel:")
"""Links that are not addresses to fetch."""

EXTENSIONS = {
    "text/html": ".html",
    "application/json": ".json",
    "application/yaml": ".yaml",
    "text/plain": ".txt",
    "text/css": ".css",
    "application/javascript": ".js",
    "image/svg+xml": ".svg",
}
"""File extension of each content type the console serves."""

BANNER = """
<div class="snapshot-banner" role="note">
  <strong>Static demo.</strong> A snapshot of the Quality Console: every page reads as
  it was. Running a scenario, calling an API or writing data needs the live stack,
  <a href="{repository}#try-it-by-hand-in-five-minutes">five minutes with Docker</a>.
</div>
<style>
  .snapshot-banner {{ position: sticky; top: 0; z-index: 20; padding: 8px 24px;
    background: var(--info-bg, #dbeafe); color: var(--info, #1d4ed8);
    border-bottom: 1px solid var(--border, #d0d7e2); font-size: 13px; }}
  .snapshot-banner a {{ color: inherit; font-weight: 600; }}
  .topbar {{ top: 38px; }}
</style>
<script>
  document.addEventListener("submit", (event) => {{
    event.preventDefault();
    alert("Static demo: this action needs the live stack (see the banner on top).");
  }}, true);
</script>
"""
"""Banner of every page, styled with the console's own tokens, and its form guard."""

LIVE_ONLY = """<!doctype html>
<html lang="en"><head><meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Live stack only</title>
<style>
  body {{ margin: 0; padding: 48px 16px; font: 15px/1.6 system-ui, sans-serif;
    background: #f6f7f9; color: #111827; }}
  main {{ max-width: 560px; margin: 0 auto; }}
  @media (prefers-color-scheme: dark) {{ body {{ background: #0b0f17; color: #e5e7eb; }}
    a {{ color: #93c5fd; }} }}
</style></head>
<body><main>
<h1>Live stack only</h1>
<p>This link opens a service running beside the console (Grafana, the QA mailbox,
RabbitMQ, Vault, the storefront), a search, or a page the snapshot left out to
stay small. It only exists on the live stack:
<a href="{repository}#try-it-by-hand-in-five-minutes">run it in five minutes</a>
with Docker.</p>
<p><a href="javascript:history.back()">Back to the snapshot</a></p>
</main></body></html>
"""
"""The page every link to a neighbouring service leads to."""


def page_key(path: str, query: str) -> str:
    """One address per page, whatever the order of its parameters.

    Args:
        path: The path of the address.
        query: Its query string, possibly empty.

    Returns:
        The path, then the parameters sorted, empty ones dropped.
    """
    params = sorted((k, v) for k, v in parse_qsl(query) if v)
    return f"{path}?{urlencode(params)}" if params else path


def shape(key: str) -> str:
    """The path of a page and the names of its parameters, without their values.

    Args:
        key: A page key, as ``page_key`` gives it.

    Returns:
        What pages of the same kind share, the unit ``PAGES_PER_SHAPE`` counts.
    """
    path, _, query = key.partition("?")
    names = sorted({name for name, _ in parse_qsl(query)})
    return f"{path}?{','.join(names)}"


def worth_a_file(key: str) -> bool:
    """Whether a page belongs to the snapshot at all.

    Args:
        key: A page key.

    Returns:
        False for searches, paging, raw files and live JSON.
    """
    path, _, query = key.partition("?")
    if path.startswith(SKIPPED_PREFIXES):
        return False
    return not any(name in SKIPPED_PARAMETERS for name, _ in parse_qsl(query))


def file_for(key: str, content_type: str) -> str:
    """The file of the snapshot a page is written to.

    Args:
        key: A page key.
        content_type: The content type the console answered.

    Returns:
        A path relative to the root of the snapshot. A query becomes a short
        hash: a static host serves files, it ignores query strings.
    """
    path, _, query = key.partition("?")
    stem = path.strip("/") or "index"
    extension = EXTENSIONS.get(content_type.split(";")[0].strip(), "")
    if query:
        digest = hashlib.sha1(query.encode(), usedforsecurity=False).hexdigest()[:12]
        return f"{stem}@{digest}{extension}"
    if posixpath.splitext(stem)[1]:
        return stem
    return f"{stem}{extension}"


def same_origin_key(url: str, page_url: str, origin: str) -> str | None:
    """The page key of a link, when it points inside the console.

    Args:
        url: The link as written in the page, HTML entities decoded.
        page_url: The full address of the page holding it.
        origin: Scheme, host and port of the console.

    Returns:
        Its page key, None for an anchor, another site or a non-address.
    """
    if not url or url.startswith("#") or url.startswith(UNTOUCHED_SCHEMES):
        return None
    absolute = urlsplit(urljoin(page_url, url))
    if f"{absolute.scheme}://{absolute.netloc}" != origin:
        return None
    return page_key(absolute.path or "/", absolute.query)


def is_neighbour(url: str, origin: str) -> bool:
    """Whether a link opens a service beside the console on the same machine.

    Args:
        url: The link as written in the page.
        origin: Scheme, host and port of the console.

    Returns:
        True for another port of the console's host, or of ``localhost``.
    """
    target = urlsplit(url)
    console = urlsplit(origin)
    if not target.scheme.startswith("http") or target.netloc == console.netloc:
        return False
    return target.hostname in {console.hostname, "localhost", "127.0.0.1"}


def rewrite(
    page: str,
    page_url: str,
    page_file: str,
    origin: str,
    file_of: Callable[[str], str | None],
) -> str:
    """Point every link of a page at the files of the snapshot.

    Args:
        page: The HTML of the page.
        page_url: Its full address on the console.
        page_file: The file it is written to, relative to the root.
        origin: Scheme, host and port of the console.
        file_of: The file of a page key, None when the snapshot skipped it.

    Returns:
        The page, its links relative to its own file: frozen pages to their
        file, skipped pages and neighbouring services to ``LIVE_ONLY_PAGE``,
        anchors and other sites untouched.
    """
    folder = posixpath.dirname(page_file) or "."

    def relative(target: str, fragment: str) -> str:
        link = posixpath.relpath(target, folder)
        return f"{link}#{fragment}" if fragment else link

    def replace(match: re.Match[str]) -> str:
        raw = html.unescape(match["url"])
        fragment = urlsplit(raw).fragment
        key = same_origin_key(raw, page_url, origin)
        target = file_of(key) if key else None
        if target is not None:
            return f'{match["attr"]}="{html.escape(relative(target, fragment))}"'
        if key is not None or is_neighbour(raw, origin):
            return f'{match["attr"]}="{relative(LIVE_ONLY_PAGE, "")}"'
        return match.group(0)

    return LINK.sub(replace, page)


def with_banner(page: str, repository: str) -> str:
    """Add the banner of the static demo right after the opening body tag.

    Args:
        page: The HTML of a page.
        repository: The repository's URL, where the live stack is explained.

    Returns:
        The page with its banner, unchanged when it has no body.
    """
    match = BODY.search(page)
    if match is None:
        return page
    banner = BANNER.format(repository=html.escape(repository))
    return page[: match.end()] + banner + page[match.end() :]


def live_only_page(repository: str) -> str:
    """The page the links to neighbouring services lead to.

    Args:
        repository: The repository's URL.

    Returns:
        A standalone HTML page.
    """
    return LIVE_ONLY.format(repository=html.escape(repository))
