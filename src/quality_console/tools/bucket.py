"""Bucket browser: the folders and files of the Cloud Storage buckets.

Folders are the ``/``-separated prefixes of object names, as the Cloud
Storage console shows them. A file opens in place, sandboxed so an HTML
report cannot script the console, or downloads.
"""

from dataclasses import dataclass
import datetime

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from google.api_core.exceptions import NotFound
from google.cloud import storage

from quality_console.tools import NotFoundError

SANDBOX_HEADERS = {
    "Content-Security-Policy": "sandbox",
    "X-Content-Type-Options": "nosniff",
}
"""Headers of a served object: no script, no same origin, no type guessing."""

MAX_OBJECTS = 500
"""Most objects listed in one folder, newest names last."""

DEFAULT_CONTENT_TYPE = "application/octet-stream"
"""Content type of an object stored without one."""


@dataclass(frozen=True)
class ObjectRow:
    """One file of a folder."""

    name: str
    short_name: str
    size: int
    content_type: str
    updated: datetime.datetime | None


def crumbs(prefix: str) -> list[tuple[str, str]]:
    """The folders of a prefix, each with the prefix that opens it.

    Args:
        prefix: A folder, ``a/b/`` or empty for the root.

    Returns:
        ``[("a", "a/"), ("b", "a/b/")]`` for ``a/b/``.
    """
    parts = [p for p in prefix.split("/") if p]
    return [(part, "/".join(parts[: i + 1]) + "/") for i, part in enumerate(parts)]


def bucket_router(client: storage.Client, templates: Jinja2Templates) -> APIRouter:
    """Build the routes of the bucket browser.

    Args:
        client: The Cloud Storage client, the emulator's locally.
        templates: The console's templates.

    Returns:
        The router to include in the console.
    """
    router = APIRouter(prefix="/tools/bucket")

    def known_bucket(name: str) -> storage.Bucket:
        """The bucket of that name, refused when the client does not list it."""
        if name not in {b.name for b in client.list_buckets()}:
            raise NotFoundError(f"Unknown bucket: {name}")
        return client.bucket(name)

    @router.get("", response_class=HTMLResponse)
    def browse(request: Request, bucket: str = "", prefix: str = "") -> HTMLResponse:
        """The buckets, or the folders and files of one folder of a bucket."""
        buckets = sorted(b.name for b in client.list_buckets())
        context: dict = {"section": "tools", "buckets": buckets, "bucket": bucket}
        if bucket:
            known_bucket(bucket)
            listing = client.list_blobs(
                bucket, prefix=prefix, delimiter="/", max_results=MAX_OBJECTS
            )
            objects = [
                ObjectRow(
                    blob.name,
                    blob.name.removeprefix(prefix),
                    blob.size or 0,
                    blob.content_type or DEFAULT_CONTENT_TYPE,
                    blob.updated,
                )
                for blob in listing
                if blob.name != prefix
            ]
            context |= {
                "prefix": prefix,
                "crumbs": crumbs(prefix),
                "folders": sorted(listing.prefixes),
                "objects": objects,
            }
        return templates.TemplateResponse(request, "bucket.html", context)

    @router.get("/object")
    def open_object(bucket: str, name: str, download: bool = False) -> Response:
        """One object, opened in place or downloaded."""
        blob = known_bucket(bucket).blob(name)
        try:
            content = blob.download_as_bytes()
        except NotFound as exc:
            raise NotFoundError(f"Unknown object: {name}") from exc
        headers = dict(SANDBOX_HEADERS)
        if download:
            headers["Content-Disposition"] = (
                f'attachment; filename="{name.rsplit("/", 1)[-1]}"'
            )
        return Response(
            content,
            media_type=blob.content_type or DEFAULT_CONTENT_TYPE,
            headers=headers,
        )

    return router
