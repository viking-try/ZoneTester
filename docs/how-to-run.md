# How to run Zoneguard

## Prerequisites

- Docker + Docker Compose v2. That's it — everything else (Postgres, Redis, Python 3.13,
  OpenSSL 3.5+) lives inside the built image. **Never run the app against a host Python
  interpreter or host OpenSSL** — PQC detection specifically requires OpenSSL ≥3.5, which the
  `python:3.13-slim-trixie` base image ships and most host installs do not.

## First boot

```bash
cp .env.example .env
docker compose up --build -d --scale worker=3
docker compose logs api --tail=20
```

Watch the `api` logs for two one-time events:

1. **Admin bootstrap** — a block like:
   ```
   === ZONEGUARD FIRST-BOOT ADMIN CREATED ===
     email:    admin@zoneguard.local
     password: <random>
   ```
   This only happens once, when the `users` table is empty and OIDC isn't configured. Copy
   the password now — it is never shown again. Set `ADMIN_BOOTSTRAP_EMAIL` /
   `ADMIN_BOOTSTRAP_PASSWORD` before first boot to choose your own instead of a generated one.

2. **Demo seed** — a small synthetic multi-zone dataset loads automatically
   (`SEED_DEMO_DATA=true` by default), through the same ingest pipeline a real upload uses.
   Set `SEED_DEMO_DATA=false` to skip this (e.g. once you've loaded real data and don't want
   the seed to re-fire — though it only ever fires when the `domains` table is empty anyway).

Open **http://localhost:8000** and sign in.

## Walkthrough

1. **Records / Domains** — the seeded demo data is already there: three fabricated hosted
   zones, a couple of dangling CNAMEs, and two ACM validation records. Everything shows
   `unscanned` until you trigger a scan.
2. **Scan Queue → Trigger scan** (scope: All scannable) — dispatches a `scan_batch` job that
   fans out one `scan_record` job per scannable record, load-balanced across whatever worker
   pods are running. Watch the queue counters update.
3. **Records** — grades populate as scans complete. Click a row for the full detail (cert
   info, negotiated cipher, header breakdown, cleanup reasons) and to trigger a manual rescan.
4. **Cleanup / Risk** — the dangling CNAMEs and validation records surface here with a
   confidence score and reasons; acknowledge one to mark it "keep" without deleting the
   underlying DNS record (Zoneguard never deletes anything itself — it's an advisory tool).
5. **Reports** — create a schedule, use *Preview digest* to see the rendered email before any
   schedule fires, or *Download* for an HTML/CSV export on demand.
6. **Settings** — shows what's configured (SMTP/Jira/ServiceNow/OIDC/Secrets Manager) without
   ever exposing the secret values themselves.

## Uploading your own data

Any of: an enriched CSV (`Name,Type,Value,TTL,Zone,...`), a bare CSV
(`Name,Type,Value[,TTL]`), a BIND zone file, or the literal output of
`aws route53 list-resource-record-sets` (optionally an array of several, one per hosted
zone). Format is auto-detected — see `app/ingest/detect.py`. Upload via the **Upload** page,
or:

```bash
curl -b cookies.txt -X POST http://localhost:8000/api/batches -F file=@my-dump.csv
```

(You'll need a session cookie from `/api/auth/login` first — the UI handles this for you.)

## Scaling workers

```bash
docker compose up -d --scale worker=6
```

Each worker subscribes to all four queues (`scans`, `reports`, `tickets`, `maintenance`) with
`--concurrency=$CELERY_CONCURRENCY` (default 4) prefork processes. `beat` must stay at
replica count 1 — running two would double-fire every periodic task.

## Configuration reference

All configuration is environment variables (see `.env.example` for the full list with
defaults and inline explanations, and `app/config.py` for the authoritative source of truth).
Notable groups:

- **Auth**: `OIDC_ISSUER`/`OIDC_CLIENT_ID`/`OIDC_CLIENT_SECRET` — all three set switches from
  local username/password to OIDC/SSO.
- **Secrets**: `SECRETS_BACKEND=env|aws_secrets_manager`, `AWS_SECRETS_BUNDLE_ID`.
- **Scanning safety**: `ALLOW_INSECURE_TLS_FALLBACK` (default `false` — leave it off unless
  you're behind a corporate MITM proxy *and* have deliberately decided to accept it),
  `ALLOW_RFC1918_SCAN_TARGETS`, `REQUESTS_CA_BUNDLE`.
- **Retention/reconciliation windows**: `RETENTION_JOBS_DAYS`, `RETENTION_EVENTS_DAYS`,
  `RETENTION_AUDIT_DAYS`, `RETENTION_SNAPSHOTS_DAYS`, `STUCK_JOB_THRESHOLD_MINUTES`,
  `RECONCILE_INTERVAL_MINUTES` — all tunable without a code change.

## Running tests

```bash
docker compose run --rm -e ROLE=test api          # whole suite
docker compose run --rm -e ROLE=test api tests/test_grading_tls.py -v
```

`ROLE=test` runs `pytest` via the same entrypoint the api/worker/beat roles use, so it's
exercised against the identical Python 3.13 / OpenSSL 3.5+ environment as production.

## Live-network verification (manual, not part of the automated suite)

```bash
docker compose run --rm --entrypoint python api -m scripts.manual_verify_scan www.cloudflare.com
```

Scans a real host through the actual pipeline and prints the full result — useful to sanity
check PQC/TLS1.3 detection against real internet infrastructure after any change to
`app/scanning/`. Not run in CI since it depends on real hosts' current configuration.
