"""The rules of the audio asset generator, and a track read back from disk."""

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from quality_console.audio_assets import (
    PEAK_CEILING,
    AudioRequest,
    estimated_megabytes,
    generate,
    list_assets,
    problems,
    synthesize,
)
from tests.metadata import metadata_test

pytestmark = [
    pytest.mark.unit,
    metadata_test(
        system="quality",
        product="quality-console",
        business_capability="operate",
        component="quality-console",
        group="qa-core",
        testing_scope="unit",
    ),
]

VALID = AudioRequest(duration_seconds=1, sample_rate=48_000, bit_depth=24)
"""A request the rules accept: one second of 24-bit stereo WAV at 48 kHz."""


def test_the_default_request_is_valid() -> None:
    assert problems(AudioRequest()) == []


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ({"file_format": "flac", "bit_depth": 32}, "FLAC has no 32-bit encoding"),
        ({"bit_depth": 16, "sample_rate": 48_000}, "48000 Hz is not accepted at 16"),
        ({"bit_depth": 24, "sample_rate": 44_100}, "44100 Hz is not accepted at 24"),
        ({"file_format": "mp3"}, "Format must be one of wav, flac"),
        ({"channels": "quad"}, "Channels must be one of"),
        ({"duration_seconds": 0}, "Duration must be 1 to 600"),
        ({"files": 21}, "Number of files must be 1 to 20"),
        ({"prefix": "../etc"}, "Prefix must be"),
        (
            {"duration_seconds": 600, "sample_rate": 192_000, "channels": "5.1"},
            "MB at most",
        ),
    ],
)
def test_a_request_the_rules_exclude_says_why(
    change: dict[str, object], expected: str
) -> None:
    found = problems(replace(VALID, **change))  # type: ignore[arg-type]

    assert any(expected in problem for problem in found), found


def test_the_weight_counts_every_channel_and_file() -> None:
    request = replace(VALID, channels="5.1", files=2)

    assert estimated_megabytes(request) == pytest.approx(
        1 * 48_000 * 3 * 6 * 2 / 1024 / 1024
    )


@pytest.mark.parametrize(
    ("channels", "shape"), [("mono", (48_000,)), ("5.1", (48_000, 6))]
)
def test_a_track_has_one_column_per_channel_below_the_ceiling(
    channels: str, shape: tuple[int, ...]
) -> None:
    signal = synthesize(replace(VALID, channels=channels), np.random.default_rng(1))

    assert signal.shape == shape
    assert np.max(np.abs(signal)) == pytest.approx(PEAK_CEILING)


def test_two_tracks_never_sound_the_same() -> None:
    first = synthesize(VALID, np.random.default_rng(1))
    second = synthesize(VALID, np.random.default_rng(2))

    assert not np.allclose(first, second)


@pytest.mark.parametrize(
    ("file_format", "bit_depth", "rate", "subtype"),
    [("wav", 16, 44_100, "PCM_16"), ("flac", 24, 96_000, "PCM_24")],
)
def test_written_tracks_are_read_back_as_asked(
    tmp_path: Path, file_format: str, bit_depth: int, rate: int, subtype: str
) -> None:
    request = replace(
        VALID,
        file_format=file_format,
        bit_depth=bit_depth,
        sample_rate=rate,
        files=2,
        prefix="qa-take",
    )

    written = generate(request, tmp_path)

    assert len(written) == 2
    for path in written:
        info = sf.info(str(path))
        assert path.name.startswith("qa-take_")
        assert path.suffix == f".{file_format}"
        assert (info.samplerate, info.channels, info.subtype) == (rate, 2, subtype)
        assert info.duration == pytest.approx(1)
    assert {a.name for a in list_assets(tmp_path)} == {p.name for p in written}


def test_an_invalid_request_writes_nothing(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="FLAC has no 32-bit"):
        generate(replace(VALID, file_format="flac", bit_depth=32), tmp_path)

    assert list(tmp_path.iterdir()) == []


def test_the_folder_lists_audio_files_only(tmp_path: Path) -> None:
    (tmp_path / ".gitkeep").touch()
    (tmp_path / "notes.txt").write_text("not audio")
    (tmp_path / "broken.wav").write_bytes(b"not a wav")

    assert list_assets(tmp_path) == []
    assert list_assets(tmp_path / "missing") == []
