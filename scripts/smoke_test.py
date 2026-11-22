"""Check a running API from outside, the way a visitor would use it.

Usage: python scripts/smoke_test.py [BASE_URL]   (default http://localhost:8000)

It needs the demo data (scripts/seed.py) and the demo login in the environment
or .env. CI runs it against `docker compose up`. Standard library only.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request

from seed import DemoLogin


def call(
    url: str,
    token: str | None = None,
    form: dict[str, str] | None = None,
    body: dict[str, object] | None = None,
    method: str | None = None,
) -> tuple[int, bytes]:
    """Send a request and return the status code and the body.

    It is a GET, or a POST when ``form`` (a login form) or ``body`` (JSON) is given.
    """
    request = urllib.request.Request(url, method=method)
    if form is not None:
        request.data = urllib.parse.urlencode(form).encode()
    elif body is not None:
        request.data = json.dumps(body).encode()
        request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=10) as answer:
            return answer.status, answer.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def main() -> int:
    base = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
    login = DemoLogin()  # type: ignore[call-arg]  # values come from the environment
    status, body = call(
        f"{base}/auth/token", form={"username": login.username, "password": login.password}
    )
    token = json.loads(body)["access_token"] if status == 200 else None
    checks = [
        ("log in as the demo librarian", status, 200),
        ("OpenAPI page", call(f"{base}/docs")[0], 200),
        ("health", call(f"{base}/health")[0], 200),
        ("books without a token", call(f"{base}/books")[0], 200),
        ("members without a token", call(f"{base}/members")[0], 401),
        ("loans with a forged token", call(f"{base}/loans", token="a.b.c")[0], 401),
        ("members with the token", call(f"{base}/members", token=token)[0], 200),
    ]
    failed = 0
    for name, got, expected in checks:
        failed += got != expected
        print(f"{'ok  ' if got == expected else 'FAIL'} {name}: {got} (expected {expected})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
