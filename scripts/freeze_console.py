"""Freeze the running Quality Console into static pages, the demo GitHub Pages serves.

Reads the console page by page from its home, GET only (every GET of the
console is a read: crawling changes nothing), keeps ``PAGES_PER_SHAPE`` pages
of each kind, then writes them with their links rewritten and the banner of the
static demo. Run it once the stack is up and seeded:
``mise run demo:freeze`` (``mise run up`` and ``mise run results:seed`` first).
"""

from collections import Counter, deque
from dataclasses import dataclass
import html
import os
from pathlib import Path
import shutil
import sys

import httpx

from quality_console.snapshot import (
    LINK,
    LIVE_ONLY_PAGE,
    PAGES_PER_SHAPE,
    file_for,
    live_only_page,
    page_key,
    rewrite,
    same_origin_key,
    shape,
    with_banner,
    worth_a_file,
)

CONSOLE_VARIABLE = "SNAPSHOT_CONSOLE_URL"
"""Where the console answers, ``http://localhost:8081`` by default."""

OUTPUT_VARIABLE = "SNAPSHOT_OUTPUT"
"""The folder the snapshot is written to, ``site`` by default."""

REPOSITORY_VARIABLE = "SNAPSHOT_REPOSITORY_URL"
"""The repository the banner links to."""

DEFAULT_REPOSITORY = "https://github.com/vincentbaticle/quality-console-light"
"""The repository of this demo."""

TIMEOUT_SECONDS = 30
"""Budget of one page; the slowest read the whole results index."""


@dataclass(frozen=True)
class Page:
    """A page read from the console."""

    key: str
    url: str
    content_type: str
    body: bytes


def crawl(client: httpx.Client, origin: str) -> dict[str, Page]:
    """Read every page worth a file, breadth first from the home.

    Args:
        client: An HTTP client on the console.
        origin: Scheme, host and port of the console.

    Returns:
        The pages read, by the key of the address that was asked.
    """
    pages: dict[str, Page] = {}
    seen = {"/"}
    shapes: Counter[str] = Counter()
    queue = deque(["/"])
    while queue:
        key = queue.popleft()
        response = client.get(key)
        if response.status_code != httpx.codes.OK:
            print(f"[freeze] {response.status_code} {key}, skipped")
            continue
        content_type = response.headers.get("content-type", "")
        page = Page(key, str(response.url), content_type, response.content)
        pages[key] = page
        if not content_type.startswith("text/html"):
            continue
        for match in LINK.finditer(response.text):
            link = same_origin_key(html.unescape(match["url"]), page.url, origin)
            if link is None or link in seen or not worth_a_file(link):
                continue
            seen.add(link)
            if shapes[shape(link)] < PAGES_PER_SHAPE:
                shapes[shape(link)] += 1
                queue.append(link)
    return pages


def write(pages: dict[str, Page], origin: str, out: Path, repository: str) -> None:
    """Write the pages, their links rewritten, plus the live-only page.

    Args:
        pages: The pages read, by key.
        origin: Scheme, host and port of the console.
        out: The folder of the snapshot, emptied first.
        repository: The repository the banner links to.
    """
    files = {key: file_for(key, page.content_type) for key, page in pages.items()}
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    for key, page in pages.items():
        target = out / files[key]
        target.parent.mkdir(parents=True, exist_ok=True)
        if not page.content_type.startswith("text/html"):
            target.write_bytes(page.body)
            continue
        text = rewrite(
            page.body.decode("utf-8", errors="replace"),
            page.url,
            files[key],
            origin,
            files.get,
        )
        target.write_text(with_banner(text, repository), encoding="utf-8")
    (out / LIVE_ONLY_PAGE).write_text(live_only_page(repository), encoding="utf-8")
    (out / ".nojekyll").touch()


def main() -> int:
    """Crawl the console and write the snapshot.

    Returns:
        The process exit code: 1 when the home did not answer.
    """
    origin = os.environ.get(CONSOLE_VARIABLE, "http://localhost:8081").rstrip("/")
    out = Path(os.environ.get(OUTPUT_VARIABLE, "site"))
    repository = os.environ.get(REPOSITORY_VARIABLE, DEFAULT_REPOSITORY)
    with httpx.Client(
        base_url=origin, timeout=TIMEOUT_SECONDS, follow_redirects=True
    ) as client:
        pages = crawl(client, origin)
    if page_key("/", "") not in pages:
        print(f"[freeze] the console does not answer on {origin}")
        return 1
    write(pages, origin, out, repository)
    size = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    print(f"[freeze] {len(pages)} pages, {size / 1_000_000:.1f} MB in {out}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
