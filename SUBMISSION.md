# Submission: Problem 5, Sales Import & Dashboard

## A. What I built

I built a Sales Import & Dashboard for a six-store retail chain, with a FastAPI and PostgreSQL backend and a React UI, hosted on Render, Neon and Vercel. All Core features are complete: idempotent CSV upload (file hash plus per-row transaction ids), row-level validation with a downloadable error report, return rules across files, concurrency-safe imports, and a background job for 20,000-row files. The dashboard shows revenue by day and store, top 10 products, return rate by store and payment split over an IST date range, plus a transaction explorer. I did not attempt any Stretch item. Partial: the UI has unit tests only for helper functions, and imports run inside the API process, not in a separate queue.

## B. Three design decisions

**1. Sales first, then returns.**
Decision: validate every row, then insert sales before returns. Alternative: process rows in file order and reject a return whose original comes later. Why: billing machine files have no guaranteed order, and "return before its original" is a listed edge case; this gives the same result for any order. Cost: the whole file is held in memory and processed in two passes, and a sale and a return sharing an id resolve by type, not position.

**2. One import at a time.**
Decision: a Postgres advisory lock serialises imports. Alternative: row-level locks on the original transactions, or serializable transactions with retries. Why: return limits depend on earlier returns across files, so two parallel imports could both pass the check. The lock is simple and clearly correct for six stores' volume. Cost: no parallel imports, so a 20k import makes other uploads wait.

**3. In-process background task with polling.**
Decision: return 202 at once and import in a FastAPI background task; the UI polls the batch status. Alternative: a separate worker with a queue. Why: the free tier gives one service, and the unique `file_hash` row makes a retry safe. Cost: a restart mid-import loses the job. Start-up marks it `FAILED` and the file must be uploaded again. Only one worker is supported.

## C. The hardest part

Getting the first hosted deployment working took longest, because none of the failures showed up locally. CI failed on `ruff format --check` because Windows files used CRLF line endings; I found it in the CI log and set `line-ending = "lf"` (6cee352). Render crashed at start-up with a SQLAlchemy URL parse error because `DATABASE_URL` was not a clean URL; the log showed it, and I re-entered it as plain text. The UI said "Cannot reach the server" because `VITE_API_BASE_URL` ended in `/docs`; the browser console showed the wrong URL, and I redeployed, since Vite bakes the value in at build time. Then CORS blocked the Vercel origin until I added it to `CORS_ORIGINS`. The code change: `config.py` now accepts plain `postgres://` URLs (14e2265).

## D. How I handle failure

| Case | Path | User sees | Logged |
|---|---|---|---|
| Bad request (wrong type, out-of-range paging, bad date) | FastAPI validation handler | 422 `VALIDATION_ERROR` with field list | WARNING with path |
| Rule violation | Row rule: saved to `import_errors`. Whole-request rule (duplicate file, too large): `AppError` handler | Error report row, or 409/413 with `request_id` | WARNING with `batch_id` and top reasons |
| Database error | In the import job: transaction rolls back, batch set `FAILED`. In a request: catch-all | `FAILED` status (retry by re-upload) or 500 | ERROR with traceback and `batch_id` |
| Unexpected exception | Catch-all handler | 500 `INTERNAL_ERROR`, generic text, no stack trace | ERROR with traceback and `request_id` |

## E. Milestone log

| Milestone | Date completed | Commit |
|---|---|---|
| M0 Scaffold | 18th october | 7c46249|
| M1 Domain model | 18th october | 176898b |
| M2 Business rules | 20th october | 974aea2 |
| M3 API | 20th october | 88ac65e |
| M4 UI | 20th october | 5537f39 |
| M5 Deployment | 20th october |2367a32 |
| M6 Documentation | 20th october | dce5a6f |

## F. If I had two more days

1. Move imports to a separate worker with a queue, which removes the restart weakness and the single-worker limit.
2. Add UI component tests (upload flow, error states), the weakest tested area.
3. Add the anomaly flag (store revenue more than 40% off the 7-day average); the dashboard queries already exist.
4. Add dashboard CSV export, a small change on top of the same queries.
5. Add basic authentication and rate limiting on upload, before any real use.

## G. Self-assessment

| Criterion | Score | Why |
|---|---|---|
| Business logic correctness | 4 | All Core rules enforced in the backend with boundary tests; concurrency covered by tests. Not load-tested beyond 20k rows. |
| Code clarity and structure | 4 | Clear API, service, rules and repository layers; ruff enforced. `_run_import` in `service.py` is long. |
| Error and exception handling | 4 | Distinct error types, one response shape, transactions roll back. No retry on transient database errors. |
| Logging and observability | 4 | JSON logs with request id and batch id, warnings on rejects, health endpoint. No log shipping beyond Render's viewer. |
| Data modelling and persistence | 4 | Constraints, indexes, migration, paise integers; line total stored on purpose. Return totals are re-summed per import. |
| API design | 4 | Versioned paths, paging, OpenAPI. No transaction filter by batch. |
| UI usability | 3 | All core flows with loading and error states. Phone width checked by hand only. |
| Testing | 4 | Boundary tests per numeric rule, API and concurrency tests, 98% on rules. UI tests are minimal. |
| Deployment and operability | 4 | Dockerfiles, compose, render.yaml, CI, bootstrap script. Neon and Vercel setup is manual. |
| Git hygiene | 3 | Milestone commits and the required format. A few follow-up fix and format commits after CI and deploy failures. |
| Documentation and write-up | 4 | README follows the required structure with assumptions and limitations. |