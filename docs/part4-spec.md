# Part 4 database decision and test contract

## ADR 2: Local PostgreSQL and model ownership

Status: accepted. Part 4 uses the existing local PostgreSQL database `todo_api` through SQLAlchemy 2 async sessions and `asyncpg`. The database already has eight tasks; setup must preserve them. `models/base.py` owns the declarative base, `models/task.py` owns the table mapping, and `database.py` owns the engine, sessions, and table initialization. This avoids the circular import in the example shown at the start of Part 5.

Supabase and its transaction-pool settings were considered but are unnecessary for the local Postgres.app server. Manual SQL for all application queries was considered; the practice requires an ORM model. Automatic table creation is used only to create missing tables. It does not migrate an existing table; schema changes in later parts will need a separate migration or explicit SQL. The existing in-memory API remains in place until the router refactor in Part 5. Its list moves to `memory_store.py` and is re-exported from `database.py` to preserve the Part 3 API and its tests during this stage.

## Function specification

`get_async_session() -> AsyncGenerator[AsyncSession, None]` yields one session and closes it after use. It reads the URL from `.env` through the module-level engine. A missing `DATABASE_URL` raises a clear configuration error before connection. Connection and SQL errors propagate to the caller.

`init_db() -> None` creates tables registered in `Base.metadata` if absent. It does not delete or rewrite existing rows. SQL errors propagate. `drop_db() -> None` drops registered tables; it is available for development but is not called by the application or tests.

`Task.to_dict() -> dict` returns the nine mapped fields: `id`, `title`, `description`, `is_important`, `is_urgent`, `quadrant`, `completed`, `created_at`, and `completed_at`. The mapping matches the existing PostgreSQL `tasks` table, including time zone aware timestamp columns and a nullable completion timestamp.

`test_connection.py` runs `SELECT 1`, initializes missing tables, reads the task count, reports success, and disposes the engine. It exits with an error when the database is unavailable. It never inserts seed rows into an existing table.

## Acceptance criteria and test contract

Test Freeze: yes. Revision 2 fixes the ORM object assertion to use a session; the acceptance criteria are unchanged.

| ID | Scenario | Exact contract | Test |
| --- | --- | --- | --- |
| AC-10 | Live connection | `engine` executes `SELECT 1` and returns integer `1` against `todo_api` | `test_connection_and_existing_rows` |
| AC-11 | Model mapping | `Task` maps exactly the nine named columns; `created_at` and `completed_at` use time zone aware SQL types; `to_dict()` returns the same keys | `test_model_mapping` |
| AC-12 | Session and preservation | `get_async_session` yields an `AsyncSession`; `init_db()` leaves the existing row count and IDs unchanged | `test_connection_and_existing_rows` |
| AC-13 | Check script | Running `test_connection.py` exits 0 and reports `SELECT 1` and the unchanged task count | `test_connection_script` |

Test level: integration with the local PostgreSQL server on port 8000. Fixture: the existing `todo_api.tasks` table with eight rows. No mocks. Tests read the live table and call only idempotent table initialization; they do not add, update, or delete rows. The backup is stored outside the repository before implementation.

## Validation report

ADR 2 → `get_async_session`, `init_db`, `drop_db`, `Task.to_dict`, and `test_connection` → AC-10–AC-13 → the integration contract above → `tests/test_part4_database.py` → `database.py`, `models/base.py`, `models/task.py`, `test_connection.py` → VAL-05–VAL-10.

- VAL-05: The frozen test failed before implementation because `database.engine` did not exist.
- VAL-06: All three Part 4 tests and both existing Part 3 tests passed after implementation.
- VAL-07: Running `test_connection.py` printed `SELECT 1: 1` and `Задач в базе: 8`.
- VAL-08: The table still had IDs 1–8 after `init_db`; the original four tasks and four independent-work tasks remained present.
- VAL-09: `pip check`, Python compilation, and `git diff --check` passed. `.env` is ignored by Git.
- VAL-10: The API started on port 8001 beside PostgreSQL on port 8000. GET `/api/v1/tasks` and `/docs` both returned 200.

Verified: local async PostgreSQL access, ORM mapping, session lifecycle, idempotent table initialization, no duplicate task insertion, and preservation of the Part 3 HTTP API. Not exercised: `drop_db`, because it deletes data. The database connection remains local to this computer. Part 5 will move the HTTP routers to the database.
