"""Removing the secrets of a recorded journey: the Codegen script and its HAR.

A person records a journey on the storefront with Playwright Codegen and its
network capture. Before anything leaves the machine, the secrets go: the
values typed into a password or one-time code field, the authentication
headers and cookies, the secret fields of every body, the credentials carried
by URLs. Every other body is kept, a test needs it. A token exchange is dropped
whole. The findings say what was removed and where, never the value.
"""

import base64
import json
from pathlib import Path
import re
from typing import Any, Final
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

REDACTED: Final[str] = "<REDACTED>"
"""What replaces a secret, so a reader sees something was there."""

SECRET_HEADERS: Final[frozenset[str]] = frozenset(
    {"authorization", "proxy-authorization", "cookie", "set-cookie"}
)
"""Headers that always carry a credential or a session."""

SECRET_NAME: Final[re.Pattern[str]] = re.compile(
    r"passw|pwd|secret|token|api[-_]?key|apikey|session|authorization|ticket",
    re.IGNORECASE,
)
"""A fragment marking a field, header or parameter name as secret.

``ticket`` is ours: the identity tenant's single-use password links carry one.
"""

OTP_NAME: Final[re.Pattern[str]] = re.compile(
    r"(?i:(?:^|[^a-z])otp(?:[^a-z]|$))|otp[A-Z]|Otp|(?i:^code$)"
)
"""A one-time code, ``otp`` as a word (not inside ``footprint``), or a bare ``code``."""

CREDENTIAL_MARKERS: Final[tuple[str, ...]] = (
    "client_secret",
    "access_token",
    "refresh_token",
    "id_token",
)
"""Words whose presence in a body makes the exchange a token exchange, dropped."""

SECRET_FIELD: Final[re.Pattern[str]] = re.compile(
    r"passw|pwd|secret|token|\botp|one[- ]time|authenticator|verification code|mfa"
    r"|2fa|\bpin\b",
    re.IGNORECASE,
)
"""Words in a locator marking the targeted field as secret."""

TYPING_CALL: Final[re.Pattern[str]] = re.compile(
    r"\.(?P<method>fill|press_sequentially|pressSequentially|type)\(\s*"
    r"(?P<quote>['\"`])(?:\\.|(?!(?P=quote)).)*(?P=quote)"
)
"""A Playwright call typing a value, followed by that value."""

URL_LITERAL: Final[re.Pattern[str]] = re.compile(
    r"(?P<quote>['\"`])(?P<url>https?://(?:\\.|(?!(?P=quote)).)*)(?P=quote)"
)
"""A string literal holding an absolute URL."""

Finding = dict[str, Any]
"""One thing removed: where (an entry and its URL, or a line) and what."""


def is_secret_name(name: str) -> bool:
    """Tell whether the value behind this name must not leave the machine.

    Args:
        name: A header, field or query parameter name.

    Returns:
        True for a secret.
    """
    return (
        name.lower() in SECRET_HEADERS
        or bool(OTP_NAME.search(name))
        or bool(SECRET_NAME.search(name))
    )


def scrub_url(url: str) -> tuple[str, list[str]]:
    """Redact the userinfo and the secret query parameters of a URL.

    Args:
        url: An absolute URL.

    Returns:
        The cleaned URL and the names of what was removed.
    """
    parts = urlsplit(url)
    removed = []
    netloc = parts.netloc
    if "@" in netloc:
        netloc = netloc.rsplit("@", 1)[1]
        removed.append("userinfo")
    query = []
    for name, value in parse_qsl(parts.query, keep_blank_values=True):
        if is_secret_name(name):
            removed.append(name)
            value = REDACTED
        query.append((name, value))
    if not removed:
        return url, []
    cleaned = urlunsplit(
        (parts.scheme, netloc, parts.path, urlencode(query, safe="<>"), parts.fragment)
    )
    return cleaned, removed


def _scrub_json(value: Any, removed: list[str]) -> Any:
    """Redact, in place, every scalar held under a secret key."""
    if isinstance(value, list):
        for item in value:
            _scrub_json(item, removed)
    elif isinstance(value, dict):
        for key, inner in value.items():
            if is_secret_name(key) and isinstance(inner, str | int | float):
                value[key] = REDACTED
                removed.append(key)
            else:
                _scrub_json(inner, removed)
    return value


def scrub_body(text: str, mime_type: str, removed: list[str]) -> str:
    """Redact the secret fields of a JSON or form body, keep anything else.

    Args:
        text: The body.
        mime_type: Its declared content type.
        removed: Collects the names of the redacted fields.

    Returns:
        The cleaned body, the same text when nothing was secret.
    """
    kind = mime_type.lower()
    before = len(removed)
    if "json" in kind:
        try:
            parsed = _scrub_json(json.loads(text), removed)
        except ValueError:
            return text
        return json.dumps(parsed) if len(removed) > before else text
    if "x-www-form-urlencoded" in kind:
        pairs = []
        for name, value in parse_qsl(text, keep_blank_values=True):
            if is_secret_name(name):
                removed.append(name)
                value = REDACTED
            pairs.append((name, value))
        return urlencode(pairs, safe="<>") if len(removed) > before else text
    return text


def _response_text(content: dict[str, Any]) -> str | None:
    """The text of a response body, decoded when stored as base64."""
    text = content.get("text")
    if text is None:
        return None
    if content.get("encoding") == "base64":
        return base64.b64decode(text).decode("utf-8", errors="replace")
    return str(text)


def _is_token_exchange(entry: dict[str, Any]) -> bool:
    """Whether the request or the response names a credential."""
    texts = [
        entry.get("request", {}).get("postData", {}).get("text") or "",
        _response_text(entry.get("response", {}).get("content", {})) or "",
    ]
    return any(marker in text for text in texts for marker in CREDENTIAL_MARKERS)


def _safe_headers(
    headers: list[dict[str, str]], where: str, removed: list[str]
) -> list:
    """Drop the secret headers, naming each one removed."""
    kept = []
    for header in headers:
        if is_secret_name(header["name"]):
            removed.append(f"{where} header {header['name'].lower()}")
        else:
            kept.append(header)
    return kept


def _scrub_request(request: dict[str, Any]) -> list[str]:
    """Clean a request in place: URL, headers, cookies, query, body."""
    removed: list[str] = []
    request["url"], parts = scrub_url(request.get("url", ""))
    removed += [f"url {part}" for part in parts]
    request["headers"] = _safe_headers(request.get("headers", []), "request", removed)
    if request.get("cookies"):
        request["cookies"] = []
        removed.append("request cookies")
    for pair in request.get("queryString", []):
        if is_secret_name(pair["name"]):
            pair["value"] = REDACTED
            removed.append(f"query {pair['name']}")
    post = request.get("postData")
    if post:
        fields: list[str] = []
        if "text" in post:
            post["text"] = scrub_body(post["text"], post.get("mimeType", ""), fields)
        for pair in post.get("params", []):
            if is_secret_name(pair["name"]):
                pair["value"] = REDACTED
                fields.append(pair["name"])
        removed += [f"request body {name}" for name in dict.fromkeys(fields)]
    return removed


def _scrub_response(response: dict[str, Any]) -> list[str]:
    """Clean a response in place: headers, cookies, redirect, body."""
    removed: list[str] = []
    response["headers"] = _safe_headers(
        response.get("headers", []), "response", removed
    )
    if response.get("cookies"):
        response["cookies"] = []
        removed.append("response cookies")
    if response.get("redirectURL"):
        response["redirectURL"], parts = scrub_url(response["redirectURL"])
        removed += [f"redirect {part}" for part in parts]
    content = response.get("content", {})
    text = _response_text(content)
    if text is not None:
        fields: list[str] = []
        cleaned = scrub_body(text, content.get("mimeType", ""), fields)
        if fields:
            content["text"] = cleaned
            content.pop("encoding", None)
            removed += [f"response body {name}" for name in dict.fromkeys(fields)]
    return removed


def scrub_har(har: dict[str, Any]) -> list[Finding]:
    """Remove the secrets of a parsed HAR, in place.

    Args:
        har: The HAR as Playwright writes it.

    Returns:
        One finding per removal: the entry, its cleaned URL, what was removed.
    """
    findings: list[Finding] = []
    kept = []
    for index, entry in enumerate(har.get("log", {}).get("entries", [])):
        if _is_token_exchange(entry):
            url, _ = scrub_url(entry.get("request", {}).get("url", ""))
            findings.append(
                {"entry": index, "url": url, "what": "dropped token exchange"}
            )
            continue
        removed = _scrub_request(entry.get("request", {}))
        removed += _scrub_response(entry.get("response", {}))
        url = entry.get("request", {}).get("url", "")
        findings += [{"entry": index, "url": url, "what": what} for what in removed]
        kept.append(entry)
    har.setdefault("log", {})["entries"] = kept
    return findings


def _scrub_line(line: str) -> tuple[str, list[str]]:
    """Redact the value typed into a secret field and the URL credentials of a line."""
    removed = []
    typed = TYPING_CALL.search(line)
    if typed and SECRET_FIELD.search(line[: typed.start()]):
        quote = typed["quote"]
        call = f".{typed['method']}({quote}{REDACTED}{quote}"
        line = line[: typed.start()] + call + line[typed.end() :]
        removed.append(f"value typed into a secret field ({typed['method']})")

    def clean(match: re.Match[str]) -> str:
        url, parts = scrub_url(match["url"])
        removed.extend(f"url {part}" for part in parts)
        return f"{match['quote']}{url}{match['quote']}" if parts else match[0]

    return URL_LITERAL.sub(clean, line), removed


def scrub_recording(source: str) -> tuple[str, list[Finding]]:
    """Remove the secrets of a recorded Codegen script, nothing else rewritten.

    Args:
        source: The script, TypeScript or Python.

    Returns:
        The cleaned script, and one finding per removal with its line.
    """
    findings: list[Finding] = []
    lines = []
    for number, original in enumerate(source.split("\n"), 1):
        cleaned, removed = _scrub_line(original)
        findings += [{"line": number, "what": what} for what in removed]
        lines.append(cleaned)
    return "\n".join(lines), findings


def clean_session(
    recording: Path,
    recording_out: Path,
    har: Path | None = None,
    har_out: Path | None = None,
) -> dict[str, Any]:
    """Clean what a Codegen session wrote, then delete the raw files.

    A HAR that cannot be read is deleted without a cleaned copy: nobody could
    check it for secrets.

    Args:
        recording: The raw script Codegen wrote.
        recording_out: Where the cleaned script goes.
        har: The raw network capture, if any.
        har_out: Where the cleaned capture goes.

    Returns:
        The report: each cleaned file, its findings, the HAR's entry count or
        why it was dropped. Never a removed value.
    """
    source, findings = scrub_recording(recording.read_text())
    recording_out.write_text(source)
    recording.unlink()
    report: dict[str, Any] = {
        "recording": {"path": str(recording_out), "findings": findings}
    }
    if har is not None and har_out is not None:
        try:
            parsed = json.loads(har.read_text())
            har_findings = scrub_har(parsed)
            har_out.write_text(json.dumps(parsed, indent=2))
            report["har"] = {
                "path": str(har_out),
                "entries": len(parsed["log"]["entries"]),
                "findings": har_findings,
            }
        except (OSError, ValueError, KeyError) as error:
            report["har"] = {"path": None, "error": f"unreadable, deleted: {error}"}
        finally:
            har.unlink(missing_ok=True)
    return report
