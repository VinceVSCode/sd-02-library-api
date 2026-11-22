"""Tests for scripts/validate_portfolio.py."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import validate_portfolio as vp

REPO_ROOT = Path(__file__).resolve().parent.parent


def valid_manifest() -> dict[str, Any]:
    """Return a manifest that passes every rule."""
    return {
        "id": "sd-01",
        "title": "Example",
        "track": "software-developer",
        "summary": "An example project.",
        "skills": ["Python"],
        "repo": "https://github.com/example/sd-01-example",
        "demo_url": None,
        "thumbnail": "docs/media/thumbnail.png",
        "demo_media": "docs/media/demo.png",
        "run_command": "python -m example",
        "status": "complete",
        "version": "1.0.0",
    }


def test_valid_manifest_has_no_errors() -> None:
    assert vp.validate_manifest(valid_manifest()) == []


@pytest.mark.parametrize("key", vp.REQUIRED_KEYS)
def test_each_required_key_is_enforced(key: str) -> None:
    manifest = valid_manifest()
    del manifest[key]
    assert any(key in error for error in vp.validate_manifest(manifest))


@pytest.mark.parametrize("bad_id", ["sd-1", "SD-01", "xx-01", "sd-001", "sd01", "", 7, None])
def test_bad_id_is_rejected(bad_id: object) -> None:
    manifest = valid_manifest()
    manifest["id"] = bad_id
    assert any('"id"' in error for error in vp.validate_manifest(manifest))


@pytest.mark.parametrize("good_id", ["sd-01", "sd-12", "ml-01", "ml-12"])
def test_good_id_is_accepted(good_id: str) -> None:
    manifest = valid_manifest()
    manifest["id"] = good_id
    assert vp.validate_manifest(manifest) == []


@pytest.mark.parametrize("bad_track", ["software", "Machine-Learning", "", None])
def test_bad_track_is_rejected(bad_track: object) -> None:
    manifest = valid_manifest()
    manifest["track"] = bad_track
    assert any('"track"' in error for error in vp.validate_manifest(manifest))


@pytest.mark.parametrize("track", vp.TRACKS)
def test_both_tracks_are_accepted(track: str) -> None:
    manifest = valid_manifest()
    manifest["track"] = track
    assert vp.validate_manifest(manifest) == []


@pytest.mark.parametrize(
    "bad_url", ["not a url", "example.com", "ftp://example.com", "https://", "", 5]
)
def test_bad_demo_url_is_rejected(bad_url: object) -> None:
    manifest = valid_manifest()
    manifest["demo_url"] = bad_url
    assert any('"demo_url"' in error for error in vp.validate_manifest(manifest))


@pytest.mark.parametrize("demo_url", [None, "https://example.com/demo", "http://example.com"])
def test_good_demo_url_is_accepted(demo_url: str | None) -> None:
    manifest = valid_manifest()
    manifest["demo_url"] = demo_url
    assert vp.validate_manifest(manifest) == []


def test_missing_demo_url_is_treated_as_null() -> None:
    manifest = valid_manifest()
    del manifest["demo_url"]
    assert vp.validate_manifest(manifest) == []


@pytest.mark.parametrize("not_an_object", [[], "text", 3, None])
def test_manifest_must_be_an_object(not_an_object: object) -> None:
    assert vp.validate_manifest(not_an_object) != []


def test_main_returns_zero_for_a_valid_file(tmp_path: Path) -> None:
    path = tmp_path / "portfolio.json"
    path.write_text(json.dumps(valid_manifest()), encoding="utf-8")
    assert vp.main([str(path)]) == 0


def test_main_returns_one_for_an_invalid_file(tmp_path: Path) -> None:
    manifest = valid_manifest()
    manifest["track"] = "other"
    path = tmp_path / "portfolio.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert vp.main([str(path)]) == 1


def test_main_returns_one_for_broken_json(tmp_path: Path) -> None:
    path = tmp_path / "portfolio.json"
    path.write_text("{ not json", encoding="utf-8")
    assert vp.main([str(path)]) == 1


def test_main_returns_one_for_a_missing_file(tmp_path: Path) -> None:
    assert vp.main([str(tmp_path / "missing.json")]) == 1


def test_this_repository_manifest_is_valid() -> None:
    assert vp.validate_file(REPO_ROOT / "portfolio.json") == []
