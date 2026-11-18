# Part 6: users and task access

## ADR 4: authentication, ownership, and migration

Status: accepted. The local PostgreSQL database owns users, password hashes, roles, and task ownership. Public registration creates only a `user`; an administrator role is assigned through the local database for this practice. Passwords use bcrypt hashes. A signed JWT carries the user ID and expires after 24 hours; every protected request loads the current role from the database. The signing key is required in the ignored `.env` file and has no code fallback. All existing task and statistics routes stay under `/api/v2`, and new authentication and administrator routes use the same prefix.

Existing tasks must survive migration. The new `tasks.user_id` column is initially nullable so the eight existing rows can be assigned to users after registration. The application never creates an unowned task. A foreign key with cascading deletion and an index are added. A database backup precedes migration. Registration is public; task routes, statistics, `/auth/me`, `/auth/change-password`, and `/admin/users` require a valid bearer token. Users see and change only their tasks; administrators see and change all tasks. The login form uses an email in its `username` field to work with Swagger's OAuth2 password flow.

Alternatives: HTTP Basic would send credentials on every request; cookies would require browser session management; a token carrying an authoritative role would fail to reflect database role changes. A cloud database is unnecessary because the user explicitly chose local PostgreSQL. Consequences: users must sign in; old unauthenticated clients receive 401; changing a password does not revoke already issued JWTs; the application must remain on localhost or be served through HTTPS before wider exposure. The PDF calls the role `admin` and places routes inconsistently under `/api/v2` and `/api/v3`; the explicit independent-work URLs under `/api/v2` govern this implementation.

## Function specifications

`init_db() -> None`: create missing model tables and add the nullable `tasks.user_id` column, index, and foreign key without changing existing rows. Repeated calls are safe. SQL errors propagate.

`hash_password(password) -> str` and `verify_password(password, hash) -> bool`: hash with bcrypt and verify without storing plaintext. A wrong password returns `False`.

`create_access_token(user_id) -> str` and `decode_access_token(token) -> dict | None`: sign and verify HS256 JWT with a required secret; include `sub` and a 24-hour `exp`. A malformed, expired, or wrongly signed token returns `None`. No database effects.

`get_current_user(token, db) -> User`: require bearer credentials, decode the token, parse an integer user ID, load the existing user from the database, and return 401 with `WWW-Authenticate: Bearer` on failure. `get_current_admin(current_user) -> User` returns 403 for a non-admin.

`register(user_data, db) -> UserResponse`: require nickname length 3–50, valid email, and password length at least 6; reject duplicate email or nickname with 400; create a user role, hash the password, and return ID, nickname, email, and role without a hash.

`login(form_data, db) -> Token`: accept form `username=<email>&password=...`; return bearer JWT for valid credentials or 401 for invalid credentials. `get_me` returns the current user without a hash.

`change_password(data, current_user, db) -> dict`: require the current password and a new password of at least 6 characters; wrong current password returns 401; success replaces the hash and returns a confirmation. The old password fails the next login and the new password succeeds.

`get_admin_users(current_admin, db) -> list[UserWithTaskCount]`: return each user with ID, nickname, email, role, and the count of owned tasks. A normal user receives 403.

`find_task(task_id, db, user) -> Task`: return 404 if missing, 403 if present but owned by someone else and the caller is not admin. All task reads, filters, updates, completion, deletion, and statistics use this ownership rule or a matching user ID query. `create_task` always sets `user_id` from the authenticated user, including admin. The response includes `user_id`; password data is never included. Scheduler updates pending tasks regardless of owner and never changes ownership.

## Acceptance criteria, test specification, and contract

Test Freeze: yes. Revision 2. Revision 1 was unfrozen because `EmailStr` correctly rejected the reserved `.test` domain used by the fixture. Account emails now use `example.com`; no acceptance criterion changed. This supersedes the unauthenticated HTTP expectations in Part 5 because Part 6 explicitly changes the public API. Part 5 deadline and statistics behavior remains required for authorized users.

| ID | Scenario and exact contract | Level |
| --- | --- | --- |
| AC-30 | Startup adds `users` and `tasks.user_id` with a foreign key; pre-existing IDs and task values remain | Database integration |
| AC-31 | Registration creates two distinct `user` accounts; duplicate email and nickname return 400; invalid fields return 422; responses contain no password/hash | HTTP integration |
| AC-32 | Login returns a bearer token; wrong password returns 401; `/auth/me` returns the same account; missing, malformed, expired, and wrong-signature tokens return 401 | HTTP and unit |
| AC-33 | Users receive only their own tasks from list, search, quadrant, status, today, overall stats, and timing stats; admin sees both users' tasks | HTTP integration |
| AC-34 | User create sets their ownership; foreign task ID read/update/complete/delete return 403 without mutation; missing ID returns 404; admin can access and edit either task | HTTP integration |
| AC-35 | Authenticated password change rejects a wrong old password with 401; a correct change makes old login fail and new login succeed; missing auth returns 401 | HTTP integration |
| AC-36 | `/api/v2/admin/users` returns users and exact task counts to admin and 403 to user | HTTP integration |
| AC-37 | Existing deadline calculations, scheduler refresh, and task validation continue for authenticated callers; temporary test rows and users are removed | Regression/integration |

Test environment: local PostgreSQL `todo_api` on port 8000 and an API process on an available localhost port. Tests create unique temporary users with example.com email addresses and tasks, promote only one test user by direct database update, and remove all temporary rows on teardown. They do not modify the original eight tasks. Assertions check HTTP codes, response fields, task IDs, database ownership and hashes, forbidden-operation non-mutation, stats isolation, and cleanup. No network mocks. User-visible demo accounts and assignment of the original rows are a separate manual acceptance step after GREEN.

## Validation report

Trace: ADR 4 -> function specifications -> AC-30–AC-37 -> the frozen contracts above -> `tests/test_part6_auth.py` and the Part 4/5 regression tests -> authentication, ownership, migration, and router code -> VAL-6.

VAL-6: A database dump was taken before migration. Startup created `users`, added `tasks.user_id`, its index and foreign key, and preserved the eight original task IDs. The first Part 6 test run was RED because registration returned 404. After implementation, all eight available tests passed against local PostgreSQL. A second full run after the demo accounts and task assignment also passed: `8 passed in 5.58s`. Dependency checks, compilation, and `git diff --check` passed. Swagger UI confirmed a regular user's three-task list and profile, 403 on the admin-only user list, and the administrator's user counts and eight-task statistics. Three local demo accounts own the eight original tasks in groups of 3, 3, and 2.

The checks cover successful and failing authentication, task ownership for list and item routes, filters, today, both statistics routes, admin access, password change, token errors, and deadline regression. The demo data and database backup remain local. Live cloud deployment is outside this practice's chosen local PostgreSQL setup. Existing JWTs remain valid after password change until their 24-hour expiration; the application is intended for localhost unless HTTPS is configured for wider access.
