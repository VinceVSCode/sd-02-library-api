# Design decisions

One page on the choices made in this project and their trade-offs. "Owner" marks
a choice made by the project owner; the others were made while building it.

| Date | Decision | Options considered | Why this one |
|---|---|---|---|
| 2026-11-22 | FastAPI (owner) | FastAPI, Flask | It builds the OpenAPI page from the code and validates requests with Pydantic, so the documentation cannot drift from the API. |
| 2026-11-22 | Signed JWT access tokens that expire (owner) | JWT, random tokens stored in the database | The API checks a token without a database lookup. The cost: a token cannot be withdrawn before it expires, so tokens last 30 minutes. |
| 2026-11-22 | No hosted demo; it runs locally with Docker Compose (owner) | a hosted demo, local only | A visitor runs the whole stack with two commands; the README shows images of the running API. |
| 2026-11-22 | One row per physical copy of a book | a title table plus a copies table | A loan is about one copy, and the project stays small. The cost: the ISBN is unique, so a library cannot hold two copies of the same edition. See Considered improvements in the README. |
| 2026-11-22 | The loan rules are enforced in the database | checks in the code only | A partial unique index allows one open loan per book, foreign keys block deleting a book or member with loans, and check constraints keep dates in order. Two requests at the same moment cannot break them. The code checks first only to give clear messages. |
| 2026-11-22 | Reading books is public; members and loans need a login | protect only the writes | Members and loans are personal data (names, emails, who borrowed what). |
| 2026-11-22 | Passwords hashed with scrypt from the standard library | bcrypt or Argon2 libraries | No extra dependency, and scrypt is a recommended password hash. |
| 2026-11-22 | Paging with `limit` and `offset`, and a `total` count | cursor paging | Simple to use and enough for a library's size. |
| 2026-11-22 | Tests run on SQLite by default and on PostgreSQL in CI | PostgreSQL only | `pytest` works on a fresh clone without Docker. CI runs the same tests on PostgreSQL, the real database. Both databases are built by the real migrations. |
| 2026-11-22 | The API container runs the migrations before it starts | a separate migration step | `docker compose up` is the only command a visitor needs. |
| 2026-11-22 | Settings come from environment variables, with `.env.example` | a settings file | Docker Compose and CI pass environment variables; no secret is ever in the repository. |
| 2026-11-23 | Ids and offsets above 2,147,483,647 are refused with 422 (owner) | let the database fail (500), use bigint columns | A library will never need such numbers, so they are refused before they reach the database. |
| 2026-11-23 | Text with control characters is refused with 422 (owner) | strip them silently | PostgreSQL refuses NUL, and none of them belongs in a title, a name or a search. Refusing them tells the caller what is wrong. |
| 2026-11-23 | Search is plain text: `%` and `_` are not wildcards (owner) | keep the wildcards | A search finds the text that was typed, and nothing else. |
| 2026-11-23 | A warning at start-up when JWT_SECRET is the public example (owner) | refuse to start, only the README note | The one-command quick start keeps working, and the log says plainly what to change before others can reach the API. |

## Schema

```
users    id, username (unique), password_hash, created_at
books    id, isbn (unique, 13 digits), title, author, published_year, created_at
members  id, name, email (unique, lower case), joined_on
loans    id, book_id -> books, member_id -> members,
         loaned_on, due_on, returned_on (empty while the book is out)

loans: one open loan per book       (unique index on book_id where returned_on is empty)
       due_on >= loaned_on, returned_on >= loaned_on
       a book or member with loans cannot be deleted (foreign keys, RESTRICT)
```

## Trade-offs

- Tokens cannot be withdrawn before they expire. A logout or a stolen token needs a deny list, which brings back the database lookup that JWT avoids.
- scrypt uses N=2^14 (16 MB per login) to keep logins fast on a laptop. OWASP recommends N=2^17 for production.
- SQLite and PostgreSQL differ in small ways (for example in text comparison), so the PostgreSQL run in CI is the one that counts.
