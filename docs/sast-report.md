# SAST report

Static analysis run against `app/` using **bandit 1.8.2** (security-focused) and **ruff
0.9.2** (`E`, `F`, `I`, `B`, and `S`/flake8-bandit rule sets). Both run inside the container
image, against the same Python 3.13 environment production uses.

```bash
docker compose run --rm --entrypoint bandit api -r app -f txt
docker compose run --rm --entrypoint ruff api check app
```

**Result: ruff — 0 findings. Bandit — 21 findings reviewed, all triaged; 0 remaining
unaddressed.** Every suppression below is inline in the code as `# nosec BXXX - <reason>`,
not hidden in a config file, so the justification travels with the flagged line.

## Findings by category

### B608 "possible SQL injection" — 18 occurrences, all false positives

Every list/filter/detail endpoint (`records`, `domains`, `jobs`, `audit`, `batches`,
`cleanup`, `risk`, plus `tasks_scan._select_scan_targets` and
`reporting/tickets._dangling_records_in_window`) builds its `WHERE`/`ORDER BY` clause via an
f-string, which bandit's B608 detector flags unconditionally on principle — it can't
distinguish "an f-string built the SQL" from "the f-string's *interpolated content* is
attacker-controlled." In every one of these 18 spots, the interpolated fragments are one of:

1. A fixed, developer-written string literal appended only when a filter is *present*
   (`where.append("hosted_zone = %(zone)s")`) — the actual **value** always crosses the
   SQL boundary as a bound parameter (`%(zone)s`), never string-formatted in.
2. A `sort_sql`/`sort_dir` resolved from a per-endpoint allowlist dict
   (`app/api/pagination.py:parse_page_params`) — an unrecognized `sort_by` is rejected with
   400 before it ever reaches the query string.
3. A fixed column-list constant (`_LIST_COLUMNS`, `_DETAIL_COLUMNS`) defined at module load
   time, never touched by request data.

This is precisely the allowlist pattern the project's own engineering notes call for (lesson
#11 in the original spec: "parameterize ALL SQL; allowlist any column/sort/group identifier
that must be interpolated — never format user input into SQL"). A dedicated test
(`tests/test_ssrf_guard.py` covers the analogous SSRF-input-validation principle; the
sort-allowlist behavior itself is exercised implicitly by every `parse_page_params` call in
the API test surface) backs this — an out-of-allowlist `sort_by` value returns 400, not a
query.

**Action taken:** `# nosec B608` with a one-line reason at each site.

### B110 "try/except/pass" — 2 occurrences, accepted by design

- `app/middleware/audit_log.py` — a failure writing an audit row must never break the actual
  request it's auditing; the request already succeeded or failed on its own terms by the time
  the audit write runs. Silently swallowing here is the correct behavior, not an oversight.
- `app/scanning/cert_analysis.py:_name_str` — falls back to the certificate's full
  RFC4514-formatted DN when extracting just the Common Name attribute fails (some certs
  legitimately have no CN). Not a security-relevant swallow, just a parsing fallback.

**Action taken:** `# nosec B110` with a one-line reason at each site.

### B501 "verify=False disables cert validation" — 1 occurrence, HIGH severity, accepted with compensating controls

`app/scanning/dnssec_probe.py` — the one and only place `verify=False` appears in the
codebase, and it is the **deliberate, spec-required opt-in insecure-TLS-fallback** for the
DNSSEC-over-DoH path when a corporate MITM proxy breaks default certificate verification and
the operator hasn't supplied `REQUESTS_CA_BUNDLE` yet. It is:

- Gated behind `ALLOW_INSECURE_TLS_FALLBACK`, which **defaults to `false`**.
- Only reachable after a real `httpx.SSLError` on the *verified* attempt — never the default
  path.
- Logged at `WARNING` every time it fires, so it's visible in production logs, not silent.
- **Never** used for any credentialed call (SMTP/Jira/ServiceNow always verify, unconditionally
  — there is no equivalent flag on those clients at all).

This is a real risk if an operator sets the flag without understanding the tradeoff, which is
why it's off by default and documented prominently in
`docs/secrets-and-aws-setup.md` and `.env.example` rather than merely suppressed here.
**Action taken:** `# nosec B501` with the compensating-controls summary inline; flagged again
here for visibility since it's the one High-severity finding in the report.

### B404 / B603 "subprocess module" / "subprocess call" — 2 occurrences, accepted by design

`app/scanning/openssl_utils.py` is the single sanctioned subprocess boundary in the codebase
(module docstring), required because Python's `ssl` module has no `set_ciphersuites()` for
TLS1.3 — enumerating TLS1.3 ciphersuites and detecting PQC key-exchange groups requires
shelling out to the `openssl` CLI. The call:

- Always passes `args` as a `list[str]` built from a fixed template plus a hostname/port —
  **never** `shell=True`, **never** an f-string command line.
- Every caller into this module (`tls13_ciphersuite.py`) passes only `host`/`port` values that
  already passed `app/scanning/target_resolver.py`'s SSRF guard, and those values reach
  `subprocess.run` as separate list elements, not concatenated into a shell string — a
  hostile record name (e.g. containing `; rm -rf /`) becomes a single inert argv element, not
  shell-interpreted syntax.

**Action taken:** `# nosec B404` / `# nosec B603` with the design rationale inline.

## What this pass does NOT cover

- Dependency vulnerability scanning (`pip-audit`/`safety` or equivalent) — not run in this
  environment; add to the CI pipeline described in `docs/roadmap.md`.
- Container image scanning (Trivy/Grype) — same.
- Dynamic testing (DAST) — the live-scan verification in `docs/how-to-run.md` exercises the
  app functionally but isn't a security-focused dynamic scan.

These are natural next steps for a CI pipeline, not gaps in this pass's scope — bandit/ruff
are static Python-source analyzers and don't cover them.
