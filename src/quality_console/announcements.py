"""Release announcements: the drafts ``/announce-release`` writes, as files.

One Markdown file per announcement in ``announcements/``, named
``<YYYY-MM-DD>-<system>-<version>.md``, holding the Slack text exactly as the
skill drafts it. The ``Versions:`` footer of the newest announcement of a
system is where the next run of the skill starts.
"""

from dataclasses import dataclass, field
from pathlib import Path
import re

FILE_NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})-([a-z0-9-]+?)-(\d+\.\d+\.\d+)\.md$")
"""``2026-10-13-quality-1.2.0.md``: the date, the system, the version."""

VERSION_ITEM = re.compile(r"^(?P<name>.+?)\s+v(?P<version>\d+\.\d+\.\d+)$")
"""``quality-console v1.2.0`` or ``plugin (shared repo) v1.3.0``."""

FOOTER_SEPARATOR = " · "
"""Between two items of a footer line."""

EMOJIS = {
    ":rocket:": "🚀",
    ":sparkles:": "✨",
    ":jigsaw:": "🧩",
    ":bug:": "🐛",
    ":warning:": "⚠️",
    ":lock:": "🔒",
    ":closed_lock_with_key:": "🔐",
    ":performing_arts:": "🎭",
}
"""The Slack codes the wording guide uses, drawn as Slack draws them."""


@dataclass
class Announcement:
    """One release announcement, as drafted for Slack."""

    date: str
    system: str
    version: str
    title: str
    blocks: list[list[str]]
    tickets: list[str] = field(default_factory=list)
    versions: dict[str, str] = field(default_factory=dict)


def slack_emojis(text: str) -> str:
    """Draw the Slack emoji codes of a line, leave the others as they are."""
    for code, emoji in EMOJIS.items():
        text = text.replace(code, emoji)
    return text


def parse_versions(line: str) -> dict[str, str]:
    """Read a ``Versions:`` footer, the next run's starting point.

    Args:
        line: ``Versions: quality-console v1.2.0 · other v0.3.1``, maybe
            wrapped in ``_…_`` as Slack italics.

    Returns:
        The version of each repository or component, by name.
    """
    body = line.strip().strip("_").removeprefix("Versions:").strip()
    found = {}
    for item in body.split(FOOTER_SEPARATOR):
        match = VERSION_ITEM.match(item.strip())
        if match:
            found[match["name"]] = match["version"]
    return found


def parse_announcement(name: str, text: str) -> Announcement | None:
    """Read one announcement file.

    Args:
        name: The file name, which gives the date, the system and the version.
        text: The Slack text.

    Returns:
        The announcement, ``None`` for a file not named like one.
    """
    matched = FILE_NAME.match(name)
    if not matched:
        return None
    date, system, version = matched.groups()
    lines = [line.rstrip() for line in text.strip().splitlines()]
    blocks: list[list[str]] = [[]]
    tickets: list[str] = []
    versions: dict[str, str] = {}
    for line in lines[1:]:
        if line.startswith("Tickets:"):
            body = line.removeprefix("Tickets:").strip()
            tickets = [
                t.strip()
                for t in body.split(FOOTER_SEPARATOR)
                if t.strip() not in {"", "none"}
            ]
        elif line.strip("_").startswith("Versions:"):
            versions = parse_versions(line)
        elif line:
            blocks[-1].append(slack_emojis(line))
        elif blocks[-1]:
            blocks.append([])
    return Announcement(
        date,
        system,
        version,
        slack_emojis(lines[0]) if lines else "",
        [block for block in blocks if block],
        tickets,
        versions,
    )


def load_announcements(root: Path) -> list[Announcement]:
    """Every announcement of the folder, newest first."""
    found = [
        parse_announcement(path.name, path.read_text()) for path in root.glob("*.md")
    ]
    return sorted(
        (a for a in found if a is not None),
        key=lambda a: (a.date, a.version),
        reverse=True,
    )


def starting_points(announcements: list[Announcement]) -> dict[str, dict[str, str]]:
    """Where the next ``/announce-release`` of each system starts.

    Returns:
        By system, the ``Versions:`` footer of its newest announcement.
    """
    points: dict[str, dict[str, str]] = {}
    for announcement in announcements:
        points.setdefault(announcement.system, announcement.versions)
    return points
