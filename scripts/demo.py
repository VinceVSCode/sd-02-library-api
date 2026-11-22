"""Print a short session with a running API: the requests and the real answers.

Usage: python scripts/demo.py [BASE_URL]   (default http://localhost:8000)

Run it on a freshly seeded database (scripts/seed.py). It lends a book, tries
to lend it again, and returns it, so it changes the data. The README image
docs/media/demo.png is this output, drawn by scripts/render_terminal.ps1.
"""

from __future__ import annotations

import json
import sys

from seed import DemoLogin
from smoke_test import call


def show(request: str, status: int, body: bytes, keep: tuple[str, ...] = ()) -> dict:
    """Print one request and its answer (only the ``keep`` fields, if given)."""
    data = json.loads(body)
    shown = {key: data[key] for key in keep} if keep else data
    print(f"$ {request}")
    print(f"  {status}  {json.dumps(shown)}")
    print()
    return data


def main() -> int:
    base = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
    login = DemoLogin()  # type: ignore[call-arg]  # values come from the environment

    show("GET /members   (no token)", *call(f"{base}/members"))
    form = {"username": login.username, "password": login.password}
    token = show("POST /auth/token", *call(f"{base}/auth/token", form=form), keep=("token_type",))[
        "access_token"
    ]
    page = json.loads(call(f"{base}/books?available=true&limit=2")[1])
    print("$ GET /books?available=true&limit=2")
    print(f"  200  total {page['total']}, first page: {[book['title'] for book in page['items']]}")
    print()

    loan_body = {"book_id": page["items"][0]["id"], "member_id": 1, "days": 14}
    request = f"POST /loans {json.dumps(loan_body)}"
    loan = show(
        request,
        *call(f"{base}/loans", token=token, body=loan_body),
        keep=("id", "loaned_on", "due_on", "overdue"),
    )
    show(request + "   (again)", *call(f"{base}/loans", token=token, body=loan_body))
    show(
        f"POST /loans/{loan['id']}/return",
        *call(f"{base}/loans/{loan['id']}/return", token=token, method="POST"),
        keep=("id", "returned_on"),
    )
    open_loans = json.loads(call(f"{base}/loans?open=true", token=token)[1])
    overdue = [item["id"] for item in open_loans["items"] if item["overdue"]]
    print("$ GET /loans?open=true")
    print(f"  200  {open_loans['total']} open loans, overdue: loan {overdue}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
