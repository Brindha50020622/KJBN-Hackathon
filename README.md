# Sales Import & Dashboard

**Problem 5: Sales Import & Dashboard.** Ingests daily store sales CSV files safely (idempotent upload, row-level validation, return rules, concurrency safe) and shows head office a dashboard.

## 2. Live links

| UI | https://kjbn-hackathon-p5oezth7f-kjbn-hackathon.vercel.app/ |
| API base URL | https://sales-api-3h8e.onrender.com |
| API docs (OpenAPI) | https://sales-api-3h8e.onrender.com/docs |
| Health | https://sales-api-3h8e.onrender.com/health |
| Repository | https://github.com/Brindha50020622/KJBN-Hackathon |

- There is no login. The app has no authentication.
- **Cold start:** the free Render service sleeps after about 15 minutes idle, so the first request can take about a minute. The free Neon database can also take a few seconds to wake.
- The hosted database is pre-loaded with 6 stores and 14 days of invented sales (`backend/seed_data/history_14days.csv`).

## 3. Tech stack

| Layer | Choice | Hosting |
|---|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2, Alembic | Render (Docker, free plan) |
| Database | PostgreSQL 16 | Neon (free plan) |
| Frontend | React 18, TypeScript, Vite, Recharts | Vercel |
| CI | GitHub Actions | |

PostgreSQL was chosen over SQLite because the concurrency rule needs a unique constraint on the file hash and an advisory lock.

## 4. Architecture

```
Browser (React UI, Vercel)
   |  JSON / multipart over HTTPS
   v
FastAPI (Render)
   api.py, api_reports.py   routes, input validation, error mapping
        |
   service.py               upload registration, background import job
        |
   rules.py, importer.py, dashboard.py     business rules (pure code, no HTTP, no DB)
        |
   repository.py            all SQL (parameterised, via SQLAlchemy)
        |
PostgreSQL (Neon)
```

**Upload flow.** `POST /api/v1/batches` reads the file (max 20 MB), computes its SHA-256 and inserts a batch row with a unique `file_hash` (`ON CONFLICT DO NOTHING`). A repeated file gets 409. A new file gets 202 straight away, and a background task parses the file, validates every row, takes a Postgres advisory lock, inserts in chunks of 1000 rows inside one transaction, and marks the batch `COMPLETED`. The UI polls `GET /api/v1/batches/{id}`.

**Folders**

| Folder | Contents |
|---|---|
| `backend/app` | API, service, business rules, repository, models, config, logging |
| `backend/tests` | Unit tests (rules) and API tests (real PostgreSQL) |
| `backend/migrations` | Alembic migration for the schema |
| `backend/seed_data` | 14-day history file loaded by the start-up script |
| `frontend/src` | React app: pages, API client, format helpers |
| `data` | `sample.csv` (published sample) and `edge_cases/` (small reviewer files) |
| `scripts` | `generate_files.py` creates the 20k file and the other test files |
| `.github/workflows` | CI: lint, tests, build |

**Where the rules live and why.** `rules.py` (field and return rules), `importer.py` (file parsing, duplicates, ordering) and `dashboard.py` (date range, return rate) contain no HTTP and no database code, so every rule is a fast unit test. The route handlers only translate requests and errors.

## 5. Running locally

**Prerequisites:** Python 3.11+ (3.12 in Docker and CI), Node 20+, Docker (for PostgreSQL 16), Git.

**Environment variables** (copy `.env.example` to `.env`)

| Variable | Meaning | Default |
|---|---|---|
| `DATABASE_URL` | Postgres URL. `postgres://` is accepted and converted | local Postgres |
| `CORS_ORIGINS` | Comma-separated UI origins allowed by the API | `http://localhost:5173` |
| `MAX_UPLOAD_MB` | Largest accepted file | 20 |
| `INSERT_CHUNK_SIZE` | Rows per insert statement | 1000 |
| `ENABLE_TEST_CLOCK` | Allow the `X-Test-Clock` header | true |
| `SEED_HISTORY` | Load the 14-day history on start-up | true |
| `LOG_LEVEL`, `APP_ENV` | Logging level, environment name | INFO, development |
| `VITE_API_BASE_URL` | API address used by the UI (read at build time) | `http://localhost:8000` |
| `TEST_DATABASE_URL` | Database for tests (name must end in `_test`) | local `sales_test` |

**One command (everything):**
```
docker compose up --build
```
UI: http://localhost:8080, API: http://localhost:8000/docs. Reset with `docker compose down -v`.

**Step by step (Windows PowerShell):**
```powershell
docker run --name sales-db -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=sales -p 5432:5432 -d postgres:16
Copy-Item .env.example .env
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
python -m app.bootstrap          # runs migrations, loads 6 stores and the history file
uvicorn app.main:app --reload    # API on http://localhost:8000
```
New terminal:
```powershell
cd frontend
npm ci
npm run dev                      # UI on http://localhost:5173
```
macOS/Linux: use `cp .env.example .env` and `source .venv/bin/activate`.

## 5a. Deployment

Files used: `backend/Dockerfile`, `frontend/Dockerfile`, `docker-compose.yml`, `render.yaml`, `frontend/vercel.json`, `backend/app/bootstrap.py` (migrate and seed), `.github/workflows/ci.yml`.

1. **Neon (manual):** create a project and copy the connection string.
2. **Render:** New, Blueprint, select this repo. Render reads `render.yaml` and builds `backend/Dockerfile`. **Manual step:** set `DATABASE_URL` (Neon string, plain text, no quotes) and `CORS_ORIGINS` (the Vercel address).
3. **Vercel (manual):** import the repo, Root Directory `frontend`, framework Vite, environment variable `VITE_API_BASE_URL` = the Render URL (no trailing slash, no path). `vercel.json` rewrites all paths to `index.html`.
4. On every start the container runs `python -m app.bootstrap` (migrate, seed stores, load history once) and then starts one `uvicorn` worker.

**Redeploy after a code change:** push to `main`. Render rebuilds automatically. In Vercel, redeploy the latest deployment (a changed `VITE_API_BASE_URL` needs a rebuild).

**Re-seed the hosted database:** in the Neon SQL editor run
`TRUNCATE transactions, import_errors, import_batches, product_aliases, products RESTART IDENTITY CASCADE;`
then use Render, Manual Deploy. The history file loads again.

## 6. Running tests and coverage

```
docker exec sales-db psql -U postgres -c "CREATE DATABASE sales_test"
cd backend
pytest                                          # all tests
pytest --cov=app --cov-report=term-missing      # tests and coverage
cd ../frontend && npm test                      # UI helper tests
```
Coverage summary is committed in `backend/coverage.txt`.

- **Backend overall: 96%**
- **Business-rules layer (`rules.py`, `importer.py`, `dashboard.py`): 98.6%**

**Covered:** every field rule with boundary tests, return rules, file-level cases (BOM, CRLF, blank lines, bad header, bad UTF-8), duplicates, concurrency (6 identical uploads at once, 2 overlapping files at once), a 20,000-row import, failed import and retry, dashboard maths, error shape and status codes.

**Not covered on purpose:** `run_migrations` in `bootstrap.py` (a subprocess, exercised by compose and the hosted deploy), `if __name__ == "__main__"` blocks, the start-up hook `mark_stale_imports_failed` (needs a real process restart), and UI components (only the format helpers have tests).

## 7. API overview

Base path `/api/v1`. Interactive docs at `/docs`. Errors use the shape in section 9.

| Method | Path | Purpose | Main errors |
|---|---|---|---|
| POST | `/batches` | Upload a CSV (multipart field `file`). Returns 202 and processes in the background | 409 `DUPLICATE_FILE`, 413 `FILE_TOO_LARGE`, 422 |
| GET | `/batches` | List batches with summary (`limit`, `offset`) | 422 |
| GET | `/batches/{id}` | One batch (poll for status) | 404, 422 |
| GET | `/batches/{id}/errors.csv` | Download the error report | 404 |
| GET | `/transactions` | Search: `store`, `sku`, `q`, `date_from`, `date_to`, `returns_only`, `limit` (max 200), `offset` | 422 |
| GET | `/dashboard` | Aggregates over `date_from`, `date_to` | 422 |
| GET | `/health` (no prefix) | Database check | 503 |

## 8. Business rules and assumptions

| # | Rule | Enforced in | Tests |
|---|---|---|---|
| 1 | Idempotent upload | `service.register_upload` (unique `file_hash`), `api.upload_batch` (409), `importer.import_file` (repeated ids) | `test_api_batches.py::test_same_file_twice_is_a_duplicate_and_changes_nothing`, `::test_other_file_with_seen_ids_accepts_new_rows_and_rejects_repeats`; `test_importer.py` duplicate tests |
| 2 | Row-level validation, whole file only on header error, CSV error report | `importer.import_file`, `rules.validate_row`, `rules.validate_header`, `api.download_error_report` | `test_importer.py::test_bad_row_is_rejected_with_row_number_and_rest_imported`; `test_api_batches.py::test_missing_column_rejects_whole_file`, `::test_error_report_lists_row_column_and_reason` |
| 3 | Field rules (store, time, quantity, price, discount, payment mode) | `rules.validate_row`, `parse_sold_at`, `parse_money_to_paise` | `test_row_validation.py`, `test_money_and_header.py` (boundary tests) |
| 4 | Return rules (original exists, same store and sku, total within original quantity) | `rules.check_return`, ordering in `importer.import_file` | `test_returns.py`; `test_importer.py` return tests; `test_api_batches.py::test_return_over_original_quantity_across_two_files` |
| 5 | Line total in integer paise | `rules.line_total_paise`, BIGINT columns | `test_money_and_header.py::test_line_total_*` |
| 6 | Concurrency and 20k rows | `service.register_upload`, `repository.lock_imports`, background task, `repository.insert_transactions` (chunks) | `test_api_batches.py::test_same_file_uploaded_at_the_same_time_only_one_wins`, `::test_overlapping_files_at_the_same_time_never_fail`, `::test_twenty_thousand_rows_are_imported_in_chunks` |
| - | Dashboard and search | `api_reports.py`, `repository.py`, `dashboard.py` | `test_api_reports.py`, `test_dashboard_helpers.py` |

**Assumptions**

1. A return that comes before its original in the same file is accepted. Sales are processed first, then returns, so file order does not matter.
2. A `transaction_id` repeated inside one file: the first wins, later ones are rejected.
3. The discount on a return is checked against |quantity| x unit_price.
4. A return's unit price is not forced to match the original's.
5. Return rate = returned units / sold units, per store, for rows inside the date range.
6. A rejected row's `transaction_id` is not treated as seen.
7. A return of a return is rejected.
8. A return dated before its original sale is rejected.
9. For a return with a discount, line total = quantity x unit_price + discount (the customer gets the discounted amount back). The literal formula would refund more than was paid. Rows without a discount follow the PDF exactly.
10. Extra columns are ignored and column order does not matter. `payment_mode` is case-sensitive.
11. A sale row must have an empty `original_transaction_id`.
12. Row numbers are record numbers with the header as row 1. Blank lines are skipped and not counted in the totals.
13. A row with the wrong number of columns is rejected as one row; the rest imports.
14. A file that is not valid UTF-8 or not valid CSV is rejected as a whole, like a header error.
15. A duplicate file means an identical SHA-256. It returns 409 `DUPLICATE_FILE` with the existing batch id and changes nothing.
16. Imports run one at a time (Postgres advisory lock), so return-quantity checks never race.
17. A batch that ended `FAILED` (server error, nothing saved) is retried when the same file is uploaded again. `COMPLETED` and `REJECTED` batches count as duplicates.
18. Limits: file 20 MB, quantity 100,000, amount 10,000,000.00, `transaction_id` and `sku` 50 characters, `product_name` 200.
19. A header or whole-file error appears in the error report as row 1, column `header`.
20. `date_from` and `date_to` are IST calendar dates, both included, years 2000 to 2100. Times are stored in UTC and shown in IST.
21. Revenue is net: the sum of line totals. A return reduces the day it was made, not the day of the original sale.
22. A store with no sales in the range has return rate 0.
23. Top products are ranked by net quantity (sold minus returned), ties by sku, using the first-seen product name.
24. The dashboard always lists all six stores and all three payment modes, with zeros when empty. Days without sales are not returned by the API.
25. Search text `q` is a case-insensitive "contains" match on transaction id or product name. Pages are capped at 200 rows.
26. The UI fills days without sales with zero on the revenue-by-day chart.
27. The payment pie shows only modes with positive net revenue.
28. The UI never sends the test clock header.
29. The 14-day history is loaded on start-up through the normal import path, once (the file hash blocks a repeat).
30. The API runs as a single worker, and the background import runs inside the API process.

## 9. Error handling and logging

**Response shape (all errors):**
```json
{"error": {"code": "DUPLICATE_FILE", "message": "This file was already uploaded", "request_id": "…", "details": {"batch_id": 1}}}
```

| Kind | How it travels | Client sees |
|---|---|---|
| Validation (bad query, path or form input) | FastAPI `RequestValidationError` handler | 422 `VALIDATION_ERROR` with field list |
| Domain (`AppError` subclasses: not found, duplicate file, file too large, invalid request) | `AppError` handler | 404, 409, 413 or 422 with a specific code |
| Row-level data problems | Not HTTP errors. Saved to `import_errors`, shown in the error report | Batch `COMPLETED` with a rejected count |
| Unexpected exception | Catch-all handler logs the traceback | 500 `INTERNAL_ERROR`, generic message, no stack trace |
| Failure inside the background job | Transaction rolled back, batch set to `FAILED` | Batch status `FAILED`, upload again to retry |

**Logging.** One JSON line per log event on stdout with `timestamp`, `level`, `logger`, `message`, `request_id` and domain ids (`batch_id`, row counts). Every request logs method, path, status and duration (never bodies). Rule violations log at WARNING (rejected rows with the top reasons, duplicate upload, rejected file). Unexpected errors log at ERROR with the traceback. The `X-Request-ID` header is echoed (or generated), returned in every error body, and passed into the background job. **Hosted logs:** Render dashboard, service `sales-api`, Logs.

## 10. Reviewer aids

- **Test clock.** Send an `X-Test-Clock` header (ISO 8601 with time zone) on `POST /api/v1/batches`. It replaces "now" for the "sold_at is not in the future" rule. Enabled on the hosted instance. Example: with this clock, sample rows after 12:00 IST on 11 Oct are rejected as future.
```
  curl.exe -X POST https://sales-api-3h8e.onrender.com/api/v1/batches -H "X-Test-Clock: 2026-10-11T12:00:00+05:30" -F "file=@data/sample.csv"
```
- **Re-seed:** see section 5a. Locally: `docker compose down -v`, then `docker compose up --build`.
- **Sample files:** `data/sample.csv`; small edge cases in `data/edge_cases/` (BOM, CRLF, quantity 0, return before original, return over original in two parts, same rows renamed, bad header, mixed errors). The 20,000-row file: `python scripts/generate_files.py` writes it to `data/generated/sales_20k.csv`.
- **Interactive API docs:** `/docs`.

## 11. Known limitations

- Free-tier hosting sleeps, so the first request is slow.
- The import runs in a background task inside the API process. A server restart during an import marks that batch `FAILED` at start-up; the file must be uploaded again. Only one API worker is supported.
- Imports run one at a time, so a large import delays other uploads.
- No authentication, no rate limiting.
- No Stretch items (email or S3 fetch, anomaly flag, dashboard CSV export).
- UI tests cover only the format helpers. Phone-width layout was checked by hand only.
- The test clock header is enabled on the hosted instance so reviewers can use it.
- Return with a discount differs from the literal PDF formula (assumption 9).

## 12. AI and third-party usage

- **Claude:** used for understanding and debugging.
- **ChatGPT:** wrote `scripts/generate_files.py` (the test data generator) from a prompt.
- **Libraries:** FastAPI, SQLAlchemy, Alembic, psycopg, pydantic-settings, pytest, ruff, React, Vite, Recharts, React Router.
- Prompt log: [PROMPTS.md](PROMPTS.md).