# Part 3 API decision and test contract

## ADR 1: Versioned routes and shared task storage

Status: accepted. The application exposes task routes under `/api/v1/tasks` and statistics under `/api/v1/stats`. Both routers read the same in-memory list from `database.py`. This keeps the existing learning project simple and makes updates visible to statistics. A database and separate state per router were considered; a database adds setup outside this practice, while separate lists would produce inconsistent responses. In-memory data resets when the process restarts. This API path is a public change from Part 2.

## Function specification

The task schema has a required title of 3–100 characters, an optional description of at most 500 characters, and required boolean importance and urgency flags. Extra request fields are rejected. `TaskCreate` validates POST input. `TaskUpdate` accepts any subset of title, description, importance, urgency, and completion. `TaskResponse` exposes ID, task fields, quadrant, completion, and creation time. The completion timestamp is stored internally and is not exposed by this response schema.

`create_task(task: TaskCreate) -> TaskResponse` creates one task with the next ID, the quadrant implied by the flags, and `completed=False`. It returns 201. Invalid input returns 422 and changes no task.

`get_task_by_id(task_id: int) -> TaskResponse` returns the matching task or 404.

`update_task(task_id: int, task_update: TaskUpdate) -> TaskResponse` changes only submitted fields. Importance or urgency changes recalculate the quadrant. A missing task returns 404. Invalid fields return 422 and change no task. Explicit null is allowed only for description.

`complete_task(task_id: int) -> TaskResponse` marks the task complete and stores `completed_at`. A missing task returns 404.

`delete_task(task_id: int) -> None` removes the task and returns 204 with an empty body. A missing task returns 404.

`get_tasks_stats() -> dict` reads the same list and reports total tasks, counts by quadrant, and counts by completion status.

## Acceptance criteria and test contract

Test Freeze: yes

| ID | Scenario | Exact contract | Test |
| --- | --- | --- | --- |
| AC-01 | Versioned routing | GET `/api/v1/tasks` and GET `/api/v1/stats` return 200; old `/tasks` returns 404 | `test_part3_workflow` |
| AC-02 | Create and read | Valid POST `/api/v1/tasks` returns 201, the next ID, computed quadrant, and a timestamp; GET by ID and list contain it | `test_part3_workflow` |
| AC-03 | Boundaries and errors | Empty, one-character, and 101-character titles; invalid importance; missing title; extra field all return 422 and do not add tasks | `test_part3_workflow` |
| AC-04 | Optional description | POST without description returns 201 and `description=null` | `test_part3_workflow` |
| AC-05 | Update | PUT updates a submitted subset, preserves omitted fields, and recalculates quadrant | `test_part3_workflow` |
| AC-06 | Complete | PATCH `/api/v1/tasks/{id}/complete` returns completed task and the stored task has a completion timestamp | `test_part3_workflow` |
| AC-07 | Delete | DELETE returns 204 and empty body; subsequent GET returns 404 | `test_part3_workflow` |
| AC-08 | Statistics | Counts reflect created, updated, completed, and deleted tasks | `test_part3_workflow` |
| AC-09 | Missing IDs | GET, PUT, PATCH, DELETE for unknown ID return 404 | `test_part3_workflow` |

Test level: HTTP integration against a locally started Uvicorn process. Fixture: four seed tasks from `database.py`; the test uses one isolated server process, so it does not modify a running user's process. No mocks are used. The test checks status codes, response fields, list membership, state changes, and empty 204 responses.

## Validation report

ADR 1 → Task schemas and route functions → AC-01–AC-09 → HTTP integration contract above → `tests/test_part3_api.py` → `main.py`, `schemas.py`, `database.py`, `routers/tasks.py`, `routers/stats.py` → VAL-01–VAL-04.

- VAL-01: The test was run before implementation and failed because GET `/api/v1/tasks` returned 404.
- VAL-02: Both tests passed after implementation. They cover the HTTP workflow and storage of `completed_at`.
- VAL-03: Python compilation and `git diff --check` passed.
- VAL-04: All documented routes were exercised in Swagger UI. Parameterized routes were checked with valid and invalid inputs. POST was checked with the independent-work title boundaries, wrong type, omitted description, and extra field.

Verified: HTTP response codes and bodies, task state changes, shared statistics, and generated Swagger routes. Remaining limitation: the task list is in memory and resets when the server restarts, as required for this stage of the practice.
