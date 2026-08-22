"""Resolves connector secrets (SMTP/Jira/ServiceNow passwords/tokens) at call time — never
stored in the DB or the repo. Backend is selected by SECRETS_BACKEND: 'env' reads directly
from the environment; 'aws_secrets_manager' looks the key up either as its own secret id, or
as a field inside the one JSON bundle named by AWS_SECRETS_BUNDLE_ID, with an in-process TTL
cache so a busy report/ticket run doesn't hammer Secrets Manager, and an env fallback if the
Secrets Manager lookup itself fails."""
import json
import logging
import os
import time

from app.config import settings

logger = logging.getLogger(__name__)

_cache: dict[str, tuple[float, str]] = {}


def resolve_secret(env_var_name: str, *, secrets_manager_key: str | None = None) -> str | None:
    if settings.secrets_backend != "aws_secrets_manager":
        return os.environ.get(env_var_name) or None

    key = secrets_manager_key or env_var_name
    cached = _cache.get(key)
    if cached and (time.monotonic() - cached[0]) < settings.secrets_cache_ttl_seconds:
        return cached[1]

    value = _fetch_from_secrets_manager(key)
    if value is None:
        value = os.environ.get(env_var_name)
    if value is not None:
        _cache[key] = (time.monotonic(), value)
    return value


def _fetch_from_secrets_manager(key: str) -> str | None:
    import boto3

    client = boto3.client("secretsmanager")
    try:
        if settings.aws_secrets_bundle_id:
            resp = client.get_secret_value(SecretId=settings.aws_secrets_bundle_id)
            bundle = json.loads(resp["SecretString"])
            return bundle.get(key)
        resp = client.get_secret_value(SecretId=key)
        return resp["SecretString"]
    except Exception as exc:  # noqa: BLE001 - any Secrets Manager failure falls back to env
        logger.warning("could not resolve secret %r from Secrets Manager: %s", key, exc)
        return None
