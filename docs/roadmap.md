# Roadmap

Roughly in priority order for a real production rollout, past what's in this repo today.

## Near-term

- **RDS IAM authentication** for the database connection instead of a static password
  (`app/db/pool.py`) — see `docs/secrets-and-aws-setup.md`.
- **Session revocation list** — the session token embeds the user's role at login time, so a
  role change or deactivation takes effect on next login/session-expiry rather than
  immediately. A small Redis-backed revocation set (checked by `AuthMiddleware`) would close
  that gap.
- **Per-zone RBAC scoping** — today, role (viewer/operator/admin) is global. Larger orgs with
  many independently-owned hosted zones will likely want zone-scoped operator grants.
- **Bulk cleanup actions** — acknowledge/delete-request in bulk from the Cleanup list rather
  than one record at a time.
- **CI pipeline**: `docker compose run --rm -e ROLE=test api`, `ruff check`, `bandit -r app`,
  and an image build/push, wired into whatever CI system the deploying org uses (not included
  here since this repo doesn't assume a specific CI provider).

## Medium-term

- **Historical trend drill-down** — the daily snapshot table already captures the data;
  the dashboard trend chart currently shows only up-count. Grade-distribution-over-time and
  per-zone trend comparison are natural extensions.
- **Configurable grading weights** — the 0.7/0.3 TLS/header blend and the cleanup-confidence
  signal weights are currently constants (`app/grading/overall_grade.py`,
  `app/cleanup/confidence.py`). Making them admin-configurable (with the current values as
  defaults) would let teams tune false-positive rates for their environment.
- **Webhook-based S3 ingest** instead of polling — an SNS/EventBridge notification on new S3
  objects triggering ingest immediately, rather than relying on an operator (or a scheduled
  job, not yet built) calling `/api/batches/s3-fetch`.
- **Multi-region scan workers** — for orgs with a genuinely global DNS footprint, running
  worker pods in multiple regions/VPCs and routing scan jobs to the worker closest to (or with
  network reach to) the target.

## Longer-term / exploratory

- **Historical cert-transparency cross-check** — flag certificates that were issued but never
  appear in this inventory (a possible indicator of shadow IT or a compromised CA account).
- **Automated dangling-record cleanup PRs** — for teams whose Route 53 zones are managed via
  Terraform/CDK, generate a draft PR removing high-confidence dangling records rather than
  just flagging them (still human-reviewed, never auto-merged).
- **Anomaly-based alerting** — beyond the fixed event types (newly down, grade regression,
  etc.), a simple statistical baseline per zone to catch "unusual" changes that don't fit a
  named category.
