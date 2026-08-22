# Contributing

## Layout

```
app/
  ingest/       format detection, 4 parsers, domain/zone normalization, S3 connector
  scanning/     liveness, TLS probing, TLS1.3/PQC (openssl subprocess), cert/header analysis, DNSSEC
  grading/      tls_grade / header_grade / overall_grade — pure functions, no I/O
  cleanup/      fingerprints, validation-record detection, confidence scoring, reconciliation
  jobs/         celery app, dispatch-then-record, scan/report/ticket/maintenance tasks
  api/          FastAPI routers, pagination contract, auth dependencies
  auth/         local + OIDC auth, RBAC, session tokens
  middleware/   security headers, audit log, rate limiting, auth gate
  integrations/ SMTP/Jira/ServiceNow clients, secrets resolution
  reporting/    digest building, Jinja2 rendering, ticket creation, schedule due-check
  web/          the SPA — vanilla JS/CSS, zero build step
  seed/         synthetic demo dataset
tests/          pytest, run inside the container (see below) — never against host Python
docs/           this documentation + rendered architecture diagrams
```

## Running tests

```bash
docker compose run --rm -e ROLE=test api
```

Always via the container. The host's Python/OpenSSL versions (whatever they happen to be on
a given dev machine) are not what production runs, and PQC-related tests specifically need
OpenSSL ≥3.5.

## Adding a new scan probe

1. Add the probe function to `app/scanning/` — keep it a pure function of
   `(ip, host, port, timeout) -> result`, no DB access. Look at `headers_probe.py` for the
   shape.
2. If it shells out to `openssl`, go through `app/scanning/openssl_utils.run_openssl()` —
   this is the one place subprocess touches the CLI, args always a `list[str]`, never
   `shell=True`.
3. Wire it into `app/scanning/pipeline.py:scan_host()`, respecting the fail-fast gate (skip
   deep probes if liveness already failed) and populate the corresponding field on
   `ScanResult`.
4. Add the new field to `app/jobs/tasks_scan.py`'s persist SQL and to the relevant migration
   if it needs a new column.
5. Unit-test the probe's *parsing* logic against a recorded fixture (see
   `tests/test_ingest_parsers.py` for the pattern) rather than a live network call in the
   test suite; use `scripts/manual_verify_scan.py` for live verification.

## Adding a new ingest format

Add a parser module under `app/ingest/parsers/` exposing `parse(raw: bytes) -> list[RawRecord]`,
register it in `app/ingest/loader.py:PARSERS`, and teach `app/ingest/detect.py:sniff_format()`
to recognize it. Add a fixture under `tests/fixtures/dumps/` and a test in
`tests/test_ingest_parsers.py`.

## Database schema changes

Add a new numbered file under `app/db/migrations/` — never edit an already-applied one. Every
migration must be safe to re-run (`CREATE TABLE IF NOT EXISTS`, guarded
`ALTER TABLE ... ADD COLUMN IF NOT EXISTS`); `app/db/migrate.py` tracks applied versions in
`schema_migrations` and skips anything already recorded.

## Style

- No comments explaining *what* code does — only *why*, when it's non-obvious (a workaround,
  a hidden constraint, a lesson learned the hard way).
- SQL is always parameterized; any column/sort/group identifier that must be interpolated
  comes only from a fixed, developer-controlled allowlist (see `app/api/pagination.py`).
- `ruff` and `bandit` run as part of the SAST pass (`docs/sast-report.md`) — keep new code
  clean against both.
