# Secrets & AWS setup

Zoneguard never stores a secret in the database or the repository. Every connector (SMTP,
Jira, ServiceNow, the S3 ingest connector, Secrets Manager itself) resolves its credentials at
call time, from one of two backends selected by `SECRETS_BACKEND`.

## `SECRETS_BACKEND=env` (default)

Every secret is a plain environment variable — `SMTP_PASSWORD`, `JIRA_API_TOKEN`,
`SERVICENOW_PASSWORD`, etc. (see `.env.example`). Fine for a single-account dev/demo
deployment; for anything shared, prefer Secrets Manager below.

## `SECRETS_BACKEND=aws_secrets_manager`

`app/integrations/secrets.py`'s `resolve_secret(env_var_name)` looks the value up from AWS
Secrets Manager instead, with an in-process TTL cache
(`SECRETS_CACHE_TTL_SECONDS`, default 300s) so a burst of report sends or ticket creations
doesn't hammer the Secrets Manager API. Two layouts are supported:

- **One secret per credential** — `AWS_SECRETS_BUNDLE_ID` unset; the secret id looked up is
  the env var name itself (e.g. a secret literally named `SMTP_PASSWORD`).
- **One JSON bundle** — set `AWS_SECRETS_BUNDLE_ID` to a single secret ARN/name whose
  `SecretString` is a JSON object; each credential is read as a field of that object keyed by
  the same env var name (e.g. `{"SMTP_PASSWORD": "...", "JIRA_API_TOKEN": "..."}`).

If Secrets Manager lookup itself fails (network blip, missing IAM permission, secret doesn't
exist), `resolve_secret` falls back to the plain environment variable — so a partially
migrated deployment degrades gracefully rather than hard-failing.

**IAM policy** needed on the ECS task role / EKS service account for this path:

```json
{
  "Effect": "Allow",
  "Action": "secretsmanager:GetSecretValue",
  "Resource": "arn:aws:secretsmanager:<region>:<account>:secret:<name-or-bundle>*"
}
```

## Database credentials in production

The default `DATABASE_URL` embeds a password for local dev convenience. In a real deployment,
either:

- Source the password itself from Secrets Manager / your platform's secret injection and
  build `DATABASE_URL` from environment substitution at deploy time, or
- Use RDS IAM authentication (generate a short-lived auth token per connection) — this
  requires a small change to `app/db/pool.py`'s connection setup to fetch a fresh token per
  connect rather than a static password; not implemented in this repo since it's
  RDS-IAM-specific, but the connection-pool boundary is the right place to add it.

Never ship a default database credential to a real environment — `POSTGRES_PASSWORD` in
`docker-compose.yml` is explicitly a dev default (`zoneguard_dev_password`) and should be
overridden via `.env` for anything beyond local development.

## S3 connector (Lambda → S3 → Zoneguard flow)

`app/ingest/s3_connector.py` uses the **container's IAM role** via boto3's default credential
provider chain — no access keys are ever entered into the app. For cross-account access, pass
an `assume_role_arn` in the `/api/batches/s3-fetch` request; the connector calls
`sts:AssumeRole` and uses the resulting temporary credentials for that one fetch.

Minimum IAM policy for the role/profile the container runs as:

```json
{
  "Effect": "Allow",
  "Action": ["s3:ListBucket"],
  "Resource": "arn:aws:s3:::<bucket>"
},
{
  "Effect": "Allow",
  "Action": ["s3:GetObject"],
  "Resource": "arn:aws:s3:::<bucket>/<prefix>/*"
}
```

If using `assume_role_arn`, the container's own role additionally needs `sts:AssumeRole` on
the target role, and the target role's trust policy must allow it.

## OIDC / SSO setup

Set all three of `OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET` and local
username/password login is automatically disabled in favor of the IdP. Register Zoneguard as
an OIDC client with your IdP with the redirect URI:

```
https://<your-domain>/api/auth/oidc/callback
```

requesting the `openid email profile` scopes. First login for a given IdP `sub` claim
provisions a `viewer`-role user automatically (`app/auth/oidc.py`); promote via **Admin →
Users** (or the `/api/users/{id}/role` endpoint) as an existing admin.

## Corporate TLS-inspection (MITM) proxies

If your egress path terminates and re-signs TLS, set `REQUESTS_CA_BUNDLE` (or `SSL_CERT_FILE`)
to the corporate root CA bundle inside the container — this is honored consistently by
Python's `ssl` module, `httpx`, and the `openssl` CLI invocations used for TLS1.3/PQC probing
(`app/scanning/openssl_utils.py:ca_bundle_path()`). `ALLOW_INSECURE_TLS_FALLBACK=true` is an
escape hatch for the *scan-target* TLS path only when the proper CA bundle genuinely isn't
available yet — it defaults to `false` and is never honored for credentialed calls (SMTP,
Jira, ServiceNow all always verify).
