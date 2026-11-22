"""Validate the portfolio.json manifest that the portfolio site reads.

Usage:
    python scripts/validate_portfolio.py [path/to/portfolio.json]

Exits with code 0 when the manifest is valid and 1 when it is not.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

REQUIRED_KEYS: tuple[str, ...] = (
    "id",
    "title",
    "track",
    "summary",
    "skills",
    "repo",
    "run_command",
    "status",
    "version",
)
ID_PATTERN = re.compile(r"^(sd|ml)-\d{2}$")
TRACKS: tuple[str, ...] = ("software-developer", "machine-learning")
DEFAULT_PATH = Path(__file__).resolve().parent.parent / "portfolio.json"


def is_url(value: object) -> bool:
    """Return True if the value is an http or https URL with a host."""
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def validate_manifest(manifest: Any) -> list[str]:
    """Return a list of problems found in a parsed manifest. Empty means valid."""
    if not isinstance(manifest, dict):
        return ["the manifest must be a JSON object"]

    errors = [f'missing required key "{key}"' for key in REQUIRED_KEYS if key not in manifest]

    if "id" in manifest:
        project_id = manifest["id"]
        if not isinstance(project_id, str) or not ID_PATTERN.fullmatch(project_id):
            errors.append('"id" must look like "sd-01" or "ml-12"')

    if "track" in manifest and manifest["track"] not in TRACKS:
        errors.append(f'"track" must be one of: {", ".join(TRACKS)}')

    demo_url = manifest.get("demo_url")
    if demo_url is not None and not is_url(demo_url):
        errors.append('"demo_url" must be null or an http(s) URL')

    return errors


def validate_file(path: Path) -> list[str]:
    """Read a manifest file and return a list of problems. Empty means valid."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        return [f"cannot read the file: {error}"]
    try:
        manifest = json.loads(text)
    except json.JSONDecodeError as error:
        return [f"not valid JSON: {error}"]
    return validate_manifest(manifest)


def main(argv: list[str] | None = None) -> int:
    """Validate the manifest named on the command line and return an exit code."""
    args = sys.argv[1:] if argv is None else argv
    path = Path(args[0]) if args else DEFAULT_PATH
    errors = validate_file(path)
    if errors:
        print(f"{path}: {len(errors)} problem(s)", file=sys.stderr)
        for message in errors:
            print(f"  - {message}", file=sys.stderr)
        return 1
    print(f"{path}: valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
