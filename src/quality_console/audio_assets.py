"""Audio assets generated on demand: placeholder tracks for test data.

A track is noise shaped by a slow modulation plus a frequency sweep, different
on each file, held just below full scale so no decoder clips it. The rules are
the ones a music distribution platform applies: sixteen bit at disc rate only,
no 32-bit FLAC, a ceiling on what one request may weigh.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import re
from typing import Final
from uuid import uuid4

import numpy as np
import soundfile as sf

FORMATS: Final[dict[str, tuple[int, ...]]] = {
    "wav": (16, 24, 32),
    "flac": (16, 24),
}
"""Each format, and the bit depths it has a PCM encoding for."""

SAMPLE_RATES: Final[dict[int, tuple[int, ...]]] = {
    16: (44_100,),
    24: (48_000, 96_000, 192_000),
    32: (48_000, 96_000, 192_000),
}
"""Rates accepted at each bit depth, sixteen bit being disc rate only."""

CHANNELS: Final[dict[str, int]] = {"mono": 1, "stereo": 2, "5.1": 6}
"""Each channel layout, and how many channels a track of it carries."""

SUBTYPES: Final[dict[int, str]] = {16: "PCM_16", 24: "PCM_24", 32: "PCM_32"}
"""The PCM encoding of each bit depth."""

MAX_DURATION_SECONDS: Final[int] = 600
"""Longest track one request may ask for."""

MAX_FILES: Final[int] = 20
"""Most files one request may ask for."""

MAX_TOTAL_MB: Final[int] = 90
"""What one request may weigh before encoding, in megabytes."""

PEAK_CEILING: Final[float] = 0.95
"""Loudest sample a track carries, just below the full scale."""

NOISE_INTENSITY: Final[tuple[float, float]] = (0.05, 0.4)
MODULATION_HZ: Final[tuple[float, float]] = (0.02, 0.6)
SWEEP_START_HZ: Final[tuple[int, int]] = (50, 600)
SWEEP_END_HZ: Final[tuple[int, int]] = (800, 4000)
"""Bounds each random part of a track is drawn between."""

SWEEP_LEVEL: Final[float] = 0.1
"""Amplitude of the sweep before the track is scaled to the ceiling."""

PREFIX: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9-]{1,40}")
"""What a file name may start with: safe in any file system and URL."""

FILE_SUFFIXES: Final[tuple[str, ...]] = tuple(f".{f}" for f in FORMATS)
"""Extensions of the files the folder lists."""


@dataclass(frozen=True)
class AudioRequest:
    """What the form asks for.

    Attributes:
        duration_seconds: Length of each track.
        file_format: ``wav`` or ``flac``.
        bit_depth: 16, 24 or 32.
        sample_rate: In Hz.
        channels: ``mono``, ``stereo`` or ``5.1``.
        files: How many tracks to write.
        prefix: Start of each file name.
    """

    duration_seconds: int = 1
    file_format: str = "wav"
    bit_depth: int = 24
    sample_rate: int = 48_000
    channels: str = "stereo"
    files: int = 1
    prefix: str = "track"


@dataclass(frozen=True)
class AudioAsset:
    """A file of the folder, as the page lists it."""

    name: str
    size_bytes: int
    created: datetime
    duration_seconds: float
    sample_rate: int
    channels: int
    subtype: str


def estimated_megabytes(request: AudioRequest) -> float:
    """What the samples of the request weigh before encoding.

    Args:
        request: The tracks asked for.

    Returns:
        The weight in megabytes, FLAC files end up lighter on disk.
    """
    per_file = (
        request.duration_seconds
        * request.sample_rate
        * request.bit_depth
        / 8
        * CHANNELS.get(request.channels, 1)
    )
    return per_file * request.files / (1024 * 1024)


def problems(request: AudioRequest) -> list[str]:
    """Every reason the request cannot be served, none when it can.

    Args:
        request: The tracks asked for.

    Returns:
        One sentence per problem.
    """
    found = []
    if not 1 <= request.duration_seconds <= MAX_DURATION_SECONDS:
        found.append(f"Duration must be 1 to {MAX_DURATION_SECONDS} seconds.")
    if not 1 <= request.files <= MAX_FILES:
        found.append(f"Number of files must be 1 to {MAX_FILES}.")
    if request.channels not in CHANNELS:
        found.append(f"Channels must be one of {', '.join(CHANNELS)}.")
    if request.file_format not in FORMATS:
        found.append(f"Format must be one of {', '.join(FORMATS)}.")
    elif request.bit_depth not in FORMATS[request.file_format]:
        depths = ", ".join(str(d) for d in FORMATS[request.file_format])
        found.append(
            f"{request.file_format.upper()} has no {request.bit_depth}-bit"
            f" encoding: {depths} only."
        )
    if request.bit_depth in SAMPLE_RATES:
        if request.sample_rate not in SAMPLE_RATES[request.bit_depth]:
            rates = ", ".join(str(r) for r in SAMPLE_RATES[request.bit_depth])
            found.append(
                f"{request.sample_rate} Hz is not accepted at"
                f" {request.bit_depth}-bit: {rates} Hz only."
            )
    else:
        found.append(f"Bit depth must be one of {', '.join(map(str, SAMPLE_RATES))}.")
    if not found and estimated_megabytes(request) > MAX_TOTAL_MB:
        found.append(
            f"About {estimated_megabytes(request):.0f} MB asked, {MAX_TOTAL_MB} MB"
            " at most: shorten the tracks, lower the rate or ask fewer files."
        )
    if not PREFIX.fullmatch(request.prefix):
        found.append("Prefix must be 1 to 40 letters, digits or dashes.")
    return found


def _hold_below_the_ceiling(signal: np.ndarray) -> np.ndarray:
    """Scale a signal so its loudest sample sits at the ceiling."""
    peak = float(np.max(np.abs(signal)))
    return PEAK_CEILING * signal / peak if peak > 0 else signal


def _one_channel(
    rng: np.random.Generator, samples: int, duration_seconds: int
) -> np.ndarray:
    """Noise under a slow modulation, plus a sweep, for one channel."""
    time_axis = np.linspace(0, duration_seconds, samples, endpoint=False)
    noise = rng.normal(0, rng.uniform(*NOISE_INTENSITY), samples)
    modulation = 0.5 * (1 + np.sin(2 * np.pi * rng.uniform(*MODULATION_HZ) * time_axis))
    start = rng.integers(SWEEP_START_HZ[0], SWEEP_START_HZ[1] + 1)
    end = rng.integers(SWEEP_END_HZ[0], SWEEP_END_HZ[1] + 1)
    frequency = start + (end - start) * time_axis / duration_seconds
    sweep = SWEEP_LEVEL * np.sin(2 * np.pi * frequency * time_axis)
    return _hold_below_the_ceiling(noise * modulation + sweep)


def synthesize(request: AudioRequest, rng: np.random.Generator) -> np.ndarray:
    """The samples of one track, floats between minus and plus the ceiling.

    Args:
        request: The track asked for.
        rng: Draws the random parts, one generator per track.

    Returns:
        One column per channel, a flat array in mono.
    """
    samples = request.duration_seconds * request.sample_rate
    count = CHANNELS[request.channels]
    if count == 1:
        return _one_channel(rng, samples, request.duration_seconds)
    columns = [
        _one_channel(rng, samples, request.duration_seconds) for _ in range(count)
    ]
    return _hold_below_the_ceiling(np.column_stack(columns))


def file_name(request: AudioRequest, index: int, now: datetime) -> str:
    """Name of one track: what it is, readable in a file list.

    Args:
        request: The tracks asked for.
        index: Position of the track in the request, from 1.
        now: When the request was served.

    Returns:
        A name no other request gives, ending with the format.
    """
    channels = request.channels.replace(".", "_")
    return (
        f"{request.prefix}_{now:%Y%m%d-%H%M%S}_{uuid4().hex[:6]}_{index:02d}_"
        f"{request.bit_depth}bit_{request.sample_rate}Hz_{channels}_"
        f"{request.duration_seconds}s.{request.file_format}"
    )


def generate(request: AudioRequest, folder: Path) -> list[Path]:
    """Write the tracks of a valid request into the folder.

    Args:
        request: The tracks asked for, with no problem.
        folder: Where the files land.

    Returns:
        The files written, in order.

    Raises:
        ValueError: When the request has a problem.
    """
    found = problems(request)
    if found:
        raise ValueError(" ".join(found))
    folder.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC)
    written = []
    for index in range(1, request.files + 1):
        signal = synthesize(request, np.random.default_rng())
        path = folder / file_name(request, index, now)
        sf.write(
            path,
            signal,
            request.sample_rate,
            subtype=SUBTYPES[request.bit_depth],
            format=request.file_format.upper(),
        )
        written.append(path)
    return written


def list_assets(folder: Path) -> list[AudioAsset]:
    """The audio files of the folder, newest first.

    Args:
        folder: Where the files land.

    Returns:
        One entry per readable audio file, nothing when the folder is missing.
    """
    if not folder.is_dir():
        return []
    assets = []
    for path in folder.iterdir():
        if path.suffix not in FILE_SUFFIXES or not path.is_file():
            continue
        try:
            info = sf.info(str(path))
        except sf.LibsndfileError:
            continue
        stat = path.stat()
        assets.append(
            AudioAsset(
                name=path.name,
                size_bytes=stat.st_size,
                created=datetime.fromtimestamp(stat.st_mtime, UTC),
                duration_seconds=info.duration,
                sample_rate=info.samplerate,
                channels=info.channels,
                subtype=info.subtype,
            )
        )
    return sorted(assets, key=lambda a: (a.created, a.name), reverse=True)
