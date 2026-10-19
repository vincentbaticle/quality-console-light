"""Cleaning a recorded journey: the secrets go, everything else stays."""

import json
from pathlib import Path

import pytest

from quality_console.recording_scrub import (
    REDACTED,
    clean_session,
    is_secret_name,
    scrub_har,
    scrub_recording,
    scrub_url,
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

SIGN_IN = {
    "request": {
        "method": "POST",
        "url": "http://localhost:8080/api/identity/login?session=abc",
        "headers": [
            {"name": "Content-Type", "value": "application/json"},
            {"name": "Cookie", "value": "sid=1"},
        ],
        "cookies": [{"name": "sid", "value": "1"}],
        "queryString": [{"name": "session", "value": "abc"}],
        "postData": {
            "mimeType": "application/json",
            "text": json.dumps({"email": "a@b.test", "password": "Foundation-2026"}),
        },
    },
    "response": {
        "headers": [{"name": "Set-Cookie", "value": "sid=2"}],
        "content": {
            "mimeType": "application/json",
            "text": json.dumps({"email": "a@b.test", "user_id": "auth0|1"}),
        },
    },
}
"""A sign-in through the storefront, its password in the body."""

TOKEN = {
    "request": {"url": "http://localhost:8080/oauth/token", "postData": {"text": "x"}},
    "response": {
        "content": {"mimeType": "application/json", "text": '{"access_token": "t"}'}
    },
}
"""A token exchange: dropped whole."""


@pytest.mark.parametrize(
    ("name", "secret"),
    [
        ("Authorization", True),
        ("newPassword", True),
        ("x-api-key", True),
        ("ticket", True),
        ("code", True),
        ("otpCode", True),
        ("footprint", False),
        ("username", False),
        ("email", False),
    ],
)
def test_a_name_is_secret_or_not(name: str, secret: bool) -> None:
    assert is_secret_name(name) is secret


def test_a_url_loses_its_userinfo_and_secret_parameters_only() -> None:
    url, removed = scrub_url("http://me:pw@localhost:8080/x?token=t&username=ada")

    assert url == f"http://localhost:8080/x?token={REDACTED}&username=ada"
    assert removed == ["userinfo", "token"]


def test_a_har_keeps_its_bodies_without_the_secrets() -> None:
    har = {"log": {"entries": [json.loads(json.dumps(SIGN_IN)), TOKEN]}}

    findings = scrub_har(har)

    [entry] = har["log"]["entries"]
    body = json.loads(entry["request"]["postData"]["text"])
    assert body == {"email": "a@b.test", "password": REDACTED}
    assert entry["request"]["headers"] == [
        {"name": "Content-Type", "value": "application/json"}
    ]
    assert entry["request"]["cookies"] == []
    assert entry["response"]["headers"] == []
    assert "auth0|1" in entry["response"]["content"]["text"]
    whats = {f["what"] for f in findings}
    assert {
        "request body password",
        "request header cookie",
        "dropped token exchange",
    } <= whats
    assert "Foundation-2026" not in json.dumps(findings)


def test_a_recording_loses_what_was_typed_into_secret_fields_only() -> None:
    source = "\n".join(
        [
            'page.get_by_label("Email").fill("qa-mailbox+ada@mycompany.test")',
            'page.get_by_label("Password").fill("Foundation-2026")',
            'page.get_by_label("Authenticator code").fill("123456")',
            'page.goto("http://localhost:8080/#account?ticket=abc")',
        ]
    )

    cleaned, findings = scrub_recording(source)

    assert "qa-mailbox+ada@mycompany.test" in cleaned
    assert "Foundation-2026" not in cleaned
    assert "123456" not in cleaned
    assert [f["line"] for f in findings] == [2, 3]


def test_a_session_is_cleaned_and_its_raw_files_deleted(tmp_path: Path) -> None:
    raw, clean = tmp_path / "raw-x.py", tmp_path / "x.py"
    raw_har, clean_har = tmp_path / "raw-x.har", tmp_path / "x.har"
    raw.write_text('page.get_by_label("Password").fill("secret-1")')
    raw_har.write_text(json.dumps({"log": {"entries": [SIGN_IN]}}))

    report = clean_session(raw, clean, raw_har, clean_har)

    assert not raw.exists()
    assert not raw_har.exists()
    assert "secret-1" not in clean.read_text()
    assert "Foundation-2026" not in clean_har.read_text()
    assert report["har"]["entries"] == 1


def test_an_unreadable_har_is_deleted_without_a_copy(tmp_path: Path) -> None:
    raw, raw_har = tmp_path / "raw-x.py", tmp_path / "raw-x.har"
    raw.write_text("")
    raw_har.write_text("not json")

    report = clean_session(raw, tmp_path / "x.py", raw_har, tmp_path / "x.har")

    assert report["har"]["path"] is None
    assert not raw_har.exists()
    assert not (tmp_path / "x.har").exists()
