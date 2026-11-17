# Part 5: PostgreSQL tasks and deadlines

## ADR 3: Database-backed API and deadline ownership

Status: accepted. The local PostgreSQL `todo_api` database is the single source of task data. Version 2 replaces the in-memory HTTP routes; `routers/tasks.py` owns task operations, `routers/stats.py` owns aggregates, and `scheduler.py` refreshes urgency and quadrant daily at 09:00 Europe/Moscow. The API stores `deadline_at` as a time-zone-aware timestamp. The database receives the new nullable column without dropping existing rows. The API process runs one scheduler; deployments with multiple workers require a separate scheduler process or a shared job lock.

The supplied example uses Supabase. Local PostgreSQL was selected because this project already has a working local server and the user explicitly requested it. Computing urgency only at read time was rejected because the assignment requires updating the stored urgency and quadrant without user action. A five-minute job is used only during verification, then removed.

The public API moves from `/api/v1` to `/api/v2`. The old in-memory routes are removed so every task endpoint uses PostgreSQL. No authentication is added by this practice; keep the service on localhost.

## Function specifications

`calculate_urgency(deadline_at, now=None) -> bool`: no deadline returns `False`; a deadline at most 72 hours away, including an overdue deadline, returns `True`. Naive timestamps are treated as UTC. No side effects.

`calculate_days_until_deadline(deadline_at, now=None) -> int | None`: no deadline returns `None`; otherwise returns signed calendar-day difference in UTC. The same UTC date returns `0`, a past date returns a negative integer. No side effects.

`determine_quadrant(is_important, is_urgent) -> str`: maps booleans to Q1, Q2, Q3, Q4. No side effects.

`TaskResponse` derives `days_until_deadline` and `status_message` from task timestamps. An overdue pending task says `Задача просрочена`; other tasks say `Все идет по плану!`. These fields are present in every task response.

Task routes accept valid title and importance. Create and update accept nullable `deadline_at`, calculate urgency and quadrant, and commit to PostgreSQL. Update rejects null for non-nullable fields. Completing a task sets `completed_at`; deleting returns 204. Search, status, quadrant, and today filters query PostgreSQL. Today returns pending tasks whose deadline is on the current UTC date. Missing task IDs return 404; invalid filters return 400 or 404 as described by the route.

`get_tasks_stats` returns total, counts for all four quadrants, and completed/pending counts. `get_timing_stats` returns four counts for tasks with deadlines: completed on time, completed late, pending on plan, and pending overdue. A task completed exactly at its deadline is on time. A pending task exactly at its deadline is overdue once current time passes it. Tasks without deadlines are excluded from timing counts.

`update_task_urgency` scans pending tasks, updates changed urgency and quadrant, and commits once. It leaves completed tasks unchanged. The scheduled job and direct invocation use the same function. `start_scheduler` registers one daily job; application shutdown stops it.

## Acceptance criteria and test contract

Test Freeze: yes. Revision 3. Revision 1 was unfrozen because its exact search count ignored a concurrent temporary scheduler task. Revision 2 was unfrozen to add the missing API case for a naive deadline, which the function specification already defines as UTC. The search criterion checks that all five tasks created by the main workflow are present. The acceptance criteria are unchanged.

| ID | Scenario | Required result | Test level |
| --- | --- | --- | --- |
| AC-20 | Startup and migration | Existing IDs remain; `deadline_at` exists; `/api/v2/health` reports database access | Integration |
| AC-21 | Create and read | +5 days is not urgent/Q2, +2 days is urgent/Q1, no deadline has null days and Q4 | HTTP integration |
| AC-22 | Update and complete | Changing deadline changes urgency/quadrant; completion stores a timestamp | HTTP integration |
| AC-23 | Filters and errors | List, ID, search, status, quadrant, today, 404 and validation errors reflect database rows | HTTP integration |
| AC-24 | Statistics | Overall and timing counts reflect created, updated, completed and overdue rows | HTTP integration |
| AC-25 | Scheduled refresh | A pending task crossing the threshold changes stored urgency and quadrant; completed tasks do not | Integration |
| AC-26 | Persistence and cleanup | A task survives a fresh session and deletion removes it | HTTP integration |

Fixture: local `todo_api` on port 8000, with eight existing rows. Test-created rows use a distinctive title and are deleted in teardown. The tests must not rewrite or remove the initial eight rows. No network mocks. The HTTP server runs on a free localhost port. The deadline tests use UTC timestamps and a frozen clock for calculation boundaries. Assertions cover status, body fields, stored values and cleanup. Errors must not insert or mutate records.

## Validation report

ADR 3 → function specifications → AC-20–AC-26 → the integration contracts above → `tests/test_part5_api.py` → `database.py`, `models/task.py`, `schemas.py`, `utils.py`, `routers/tasks.py`, `routers/stats.py`, `scheduler.py`, `main.py` → VAL-11–VAL-17.

- VAL-11: Before implementation, the frozen HTTP test returned 404 for `/api/v2/health`. This was the expected RED result for the absent version 2 API.
- VAL-12: Seven available tests passed after implementation, including the existing database tests, the full task workflow, calculation boundaries, timing statistics, and scheduler refresh.
- VAL-13: The local database kept the eight original IDs. `init_db` added the nullable deadline column without deleting rows. Temporary test rows were removed.
- VAL-14: Swagger returned 201 with Q2 for a five-day deadline, Q1 for a two-day deadline, and Q4 with null deadline fields for a task without a deadline. It also showed both statistics routes, the today filter, and a 422 validation error.
- VAL-15: A temporary five-minute APScheduler job changed a stored pending task from Q2 to Q1 without an HTTP request. The test row and temporary job were removed; the application retains its daily 09:00 Europe/Moscow job.
- VAL-16: `pip check`, Python compilation, and `git diff --check` passed. The connection URL remains in the ignored local `.env` file.
- VAL-17: The API ran on localhost port 8001 beside PostgreSQL on port 8000. The version 2 health route returned 200 and the removed version 1 task route returned 404.

Verified: local PostgreSQL persistence, deadline calculation, database-backed routes, aggregate statistics, and scheduled refresh. Remaining limits: the service depends on this computer's PostgreSQL instance, has no authentication, and must use one scheduler process when run with multiple API workers.
