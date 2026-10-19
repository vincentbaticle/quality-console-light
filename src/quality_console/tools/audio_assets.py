"""Audio asset generator: placeholder tracks written into a local folder.

The form asks for a duration, a format, a bit depth, a rate, a channel layout
and a number of files; the tracks land in ``audio-assets/`` of the repository,
a folder committed empty, its files never. The page lists them to play,
download or delete.
"""

from http import HTTPStatus
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from quality_console.audio_assets import (
    CHANNELS,
    FORMATS,
    MAX_DURATION_SECONDS,
    MAX_FILES,
    MAX_TOTAL_MB,
    SAMPLE_RATES,
    AudioRequest,
    generate,
    list_assets,
    problems,
)
from quality_console.tools import NotFoundError

AUDIO_ASSETS_PATH = "/utility/audio-assets"
"""The page of the audio asset generator."""

MEDIA_TYPES = {".wav": "audio/wav", ".flac": "audio/flac"}
"""What the browser is told each file is, so it can play it."""


class GenerateBody(BaseModel):
    """What the form sends."""

    duration_seconds: int
    file_format: str
    bit_depth: int
    sample_rate: int
    channels: str
    files: int
    prefix: str


class GeneratedFiles(BaseModel):
    """The names of the files written."""

    files: list[str]


def audio_assets_router(folder: Path, templates: Jinja2Templates) -> APIRouter:
    """Build the routes of the audio asset generator.

    Args:
        folder: Where the tracks land.
        templates: The console's templates.

    Returns:
        The router to include in the console.
    """
    router = APIRouter(prefix=AUDIO_ASSETS_PATH)

    def existing(name: str) -> Path:
        """The file of that name, only if the folder lists it."""
        if name not in {asset.name for asset in list_assets(folder)}:
            raise NotFoundError(f"Unknown audio asset: {name}")
        return folder / name

    @router.get("", response_class=HTMLResponse)
    def page(request: Request) -> HTMLResponse:
        """The form, then every track already written."""
        return templates.TemplateResponse(
            request,
            "audio_assets.html",
            {
                "section": "utility",
                "defaults": AudioRequest(),
                "formats": FORMATS,
                "sample_rates": SAMPLE_RATES,
                "all_rates": sorted(
                    {r for rates in SAMPLE_RATES.values() for r in rates}
                ),
                "channels": CHANNELS,
                "max_duration": MAX_DURATION_SECONDS,
                "max_files": MAX_FILES,
                "max_mb": MAX_TOTAL_MB,
                "assets": list_assets(folder),
            },
        )

    @router.post("/generate")
    def generate_tracks(body: GenerateBody) -> GeneratedFiles:
        """Write the tracks asked for, or say why not with a ``422``."""
        request = AudioRequest(**body.model_dump())
        found = problems(request)
        if found:
            raise HTTPException(HTTPStatus.UNPROCESSABLE_ENTITY, detail=found)
        return GeneratedFiles(files=[path.name for path in generate(request, folder)])

    @router.get("/files/{name}")
    def download(name: str, inline: bool = False) -> FileResponse:
        """One track, played in the page or downloaded."""
        path = existing(name)
        return FileResponse(
            path,
            media_type=MEDIA_TYPES[path.suffix],
            filename=name,
            content_disposition_type="inline" if inline else "attachment",
        )

    @router.delete("/files/{name}", status_code=HTTPStatus.NO_CONTENT)
    def delete(name: str) -> None:
        """Remove one track from the folder."""
        existing(name).unlink()

    return router
