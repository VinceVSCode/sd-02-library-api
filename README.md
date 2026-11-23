# Library REST API with Database

A REST API for a small library: books, members and loans in PostgreSQL, with validation, paging, token login and an OpenAPI page.

> **Status:** complete. Passed its quality review on 2026-11-23 (version 1.0.1).

## Demo

![The OpenAPI page of the running API](docs/media/thumbnail.png)

The project has no hosted demo: it runs on your machine with Docker (see the quick start). More images are in `docs/media/`:

- [demo.png](docs/media/demo.png): a session with the running API, from `python scripts/demo.py`. A request without a token is refused, a book is lent, lending it again is refused with 409, and the loan is returned.
- [tests.png](docs/media/tests.png): the test run.

## Core focus

REST endpoint design, relational schema design, validation, authentication and containerization, in a small but complete API.

## Skills demonstrated

- Python with FastAPI and Pydantic
- REST API design: resources, status codes, paging, filtering
- SQL and PostgreSQL: keys, constraints, a partial unique index
- Database migrations with Alembic
- Authentication: hashed passwords and signed, expiring tokens (JWT)
- Docker Compose, and CI that tests on PostgreSQL and runs the whole stack

## Quick start

You need Docker. Run these in the project folder.

1. Copy the settings file. It holds values for a local run only:

   | System and shell | Command |
   |---|---|
   | Windows, PowerShell or Command Prompt | `copy .env.example .env` |
   | macOS, Linux or Git Bash | `cp .env.example .env` |

2. Start PostgreSQL and the API. The API applies the database migrations before it starts:

   ```bash
   docker compose up --build
   ```

3. In a second terminal, add the demo data (a librarian, 12 books, 4 members, 4 loans):

   ```bash
   docker compose exec api python scripts/seed.py
   ```

Then open **http://localhost:8000/docs**. Press **Authorize**, log in with the demo librarian from `.env` (`DEMO_USERNAME` and `DEMO_PASSWORD`), and try any endpoint. To stop, press Ctrl+C; `docker compose down --volumes` also deletes the data.

### Run without Docker

You need Python 3.12 or newer (tested with 3.13) and a PostgreSQL server; set its address in `.env` (`POSTGRES_HOST`, or a full `DATABASE_URL`). Create a virtual environment and activate it:

| System and shell | Command |
|---|---|
| Windows, PowerShell | `python -m venv .venv` then `.venv\Scripts\Activate.ps1` |
| Windows, Command Prompt | `python -m venv .venv` then `.venv\Scripts\activate.bat` |
| Windows, Git Bash | `python -m venv .venv` then `source .venv/Scripts/activate` |
| macOS or Linux | `python -m venv .venv` then `source .venv/bin/activate` |

```bash
pip install -e ".[dev]"
```

```bash
python -m library_api.migrate
```

```bash
uvicorn library_api.app:create_app --factory --reload
```

**The settings are read from the folder you start in**, through its `.env` file, so start the commands in the project folder.

### Endpoints

| Method and path | Login | What it does |
|---|---|---|
| `POST /auth/token` | | Exchanges a username and password for a token (valid 30 minutes). |
| `GET /books` | | Lists books. `q` searches title and author; `available=true` or `false` filters. |
| `GET /books/{id}` | | One book, with `available`. |
| `POST /books`, `PATCH /books/{id}`, `DELETE /books/{id}` | yes | Adds, changes or deletes a book. A book that has ever been lent cannot be deleted. |
| `GET /members`, `GET /members/{id}` | yes | Lists members (`q` searches name and email), or one member. |
| `POST /members`, `PATCH /members/{id}`, `DELETE /members/{id}` | yes | Adds, changes or deletes a member. |
| `GET /loans`, `GET /loans/{id}` | yes | Lists loans, newest first. Filters: `book_id`, `member_id`, `open`. Each loan says if it is `overdue`. |
| `POST /loans` | yes | Lends a book from today, for `days` days (1 to 60, default 14). |
| `POST /loans/{id}/return` | yes | Marks the loan as returned today. |
| `GET /health` | | Says whether the API and its database answer (503 if the database does not). |

Every list takes `limit` (1 to 100, default 20) and `offset`, and returns `items`, `total`, `limit` and `offset`. The search text `q` is plain text of up to 200 characters: `%` and `_` are searched as themselves, not as wildcards. Ids go from 1 to 2,147,483,647, the largest number PostgreSQL's `integer` column holds.

Answers use the usual status codes: 401 without a valid token, 404 for a missing item, 409 when a request clashes with the data (an ISBN or email already used, a book already lent, a loan already returned, deleting a book or member with loans), and 422 for invalid input, naming the field. Invalid input includes ids or offsets out of range, and text with control characters such as NUL or a tab.

## How it works

```
app.py          creates the FastAPI app; /health and the OpenAPI page
routers/        books.py, members.py, loans.py, auth.py: one module per resource
schemas.py      request and response shapes, and the validation rules
deps.py         database session per request, login check, paging, 404 and 409
security.py     scrypt password hashes, signed tokens (JWT, HS256)
models.py       the tables (SQLAlchemy)
migrations/     Alembic migrations; migrate.py applies them
config.py       every setting, from environment variables or .env
```

- **Validation:** ISBNs are checked (length and check digit), accepted as ISBN-10 or ISBN-13, and stored as 13 digits. Emails are stored in lower case. Text is trimmed and limited in length. Unknown fields are refused, so a typo is reported instead of ignored. In a `PATCH`, only the fields that are sent change.
- **The rules live in the database:** a partial unique index allows only one open loan per book, foreign keys stop a book or member with loans from being deleted, and check constraints keep the dates in order. The code checks first only to give a clear message; two requests arriving at the same moment still cannot break a rule.
- **Login:** passwords are stored as salted scrypt hashes. A login returns a token signed with `JWT_SECRET` that expires after `TOKEN_MINUTES`. An unknown username takes as long to refuse as a wrong password, so the answer time does not reveal which usernames exist.
- **Containers:** the `db` service is PostgreSQL 18 with a health check; the `api` service waits for it, applies the migrations, then starts. The data is kept in the Docker volume `library-data`.

The schema and the design choices are in [docs/decisions.md](docs/decisions.md).

## Results

| Check | Result |
|---|---|
| Tests | 191 pass, on SQLite and on PostgreSQL 18 |
| Protected endpoints | each of the 12 is tested without a token and with a forged one (401) |
| Lint (`ruff check .`) | passes |
| Migrations | a test checks that they match the models, and that they can be undone and redone |
| Whole stack | `docker compose up` starts both services, applies the migrations and passes all 7 checks of `scripts/smoke_test.py`; CI is set up to do the same on every push |
| Database down | `/health` answers 503 within about 3 seconds, and 200 again once the database is back |

## Tests

```bash
ruff check .
```

```bash
pytest
```

```bash
python scripts/validate_portfolio.py
```

`pytest` uses a temporary SQLite database and needs no Docker or network. To run the tests on PostgreSQL, set `TEST_DATABASE_URL` to an empty test database (its name must contain "test"; the tests delete every row).

## Limitations

- One row is one physical copy, and the ISBN is unique, so the library cannot hold two copies of the same edition.
- There is one kind of user, the librarian. Members cannot log in to see their own loans.
- A token cannot be withdrawn before it expires (there is no logout or deny list).
- Passwords use scrypt with N=2^14 to keep logins fast; OWASP recommends N=2^17 for production.
- No rate limiting on the login endpoint.
- The demo data is made up, including the ISBNs (valid check digits, but not real editions).

## Changes

**1.0.1** (2026-11-23), after the quality review:

- An id above 2,147,483,647 (in the address, a filter or a request body), or an `offset` above 9.2 quintillion, crashed the request with a 500 error, because PostgreSQL could not hold the number. Ids must now be 1 to 2,147,483,647 and offsets at most 2,147,483,647; anything else gets a 422 answer.
- A NUL character in a title, a name, an email or a search crashed the request with a 500 error, because PostgreSQL refuses it. Text with a control character (NUL, a tab, a line break and the like) now gets a 422 answer. A username with one is refused like a wrong password.
- `%` and `_` in a search worked as wildcards: `?q=%` listed every book. The search now treats every character as plain text.
- ISBNs written with other digit forms (for example Arabic-Indic digits) passed the format check. Only the digits 0 to 9 are accepted now.
- The API now logs a warning at start-up when `JWT_SECRET` is still the public example from `.env.example`.
- Each of these has a test that failed before the fix: 35 new tests, 191 in total.

## Considered improvements

- Separate titles from copies, so a library can hold several copies of one book.
- A member role that can log in and see only its own loans.
- Refresh tokens and a deny list for logout.
- Rate limiting on `POST /auth/token`.
- Fines or reminders for overdue loans.

## License

MIT. See [LICENSE](LICENSE).
