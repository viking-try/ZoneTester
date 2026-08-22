"""Single source of truth for all environment configuration. Everything else in the app
imports `settings` from here instead of reading os.environ directly."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Zoneguard"
    env: str = "development"
    app_secret_key: str = "dev-only-change-me-in-prod"

    database_url: str = "postgresql://zoneguard:zoneguard_dev_password@localhost:5432/zoneguard"
    db_pool_min_size: int = 2
    db_pool_max_size: int = 10

    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    redis_url: str = "redis://localhost:6379/2"

    seed_demo_data: bool = True

    # --- Auth ---
    oidc_issuer: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    session_cookie_name: str = "zoneguard_session"
    session_ttl_seconds: int = 60 * 60 * 12

    @property
    def oidc_enabled(self) -> bool:
        return bool(self.oidc_issuer and self.oidc_client_id and self.oidc_client_secret)

    # --- Secrets ---
    secrets_backend: str = "env"  # env | aws_secrets_manager
    aws_secrets_bundle_id: str = ""
    secrets_cache_ttl_seconds: int = 300

    # --- Scanning safety ---
    allow_insecure_tls_fallback: bool = False
    allow_rfc1918_scan_targets: bool = False
    requests_ca_bundle: str = ""
    doh_url: str = "https://cloudflare-dns.com/dns-query"

    # --- Scanning tuning ---
    tcp_connect_timeout_seconds: float = 3.0
    tls_probe_timeout_seconds: float = 6.0
    openssl_subprocess_timeout_seconds: float = 8.0
    http_headers_timeout_seconds: float = 6.0
    scan_max_consecutive_failures_before_down: int = 3
    scan_record_soft_time_limit_seconds: int = 45
    scan_record_hard_time_limit_seconds: int = 60
    scan_batch_soft_time_limit_seconds: int = 3600
    scan_batch_hard_time_limit_seconds: int = 3900

    # --- Job reconciliation / retention ---
    stuck_job_threshold_minutes: int = 15
    reconcile_interval_minutes: int = 5
    retention_jobs_days: int = 14
    retention_events_days: int = 90
    retention_audit_days: int = 180
    retention_snapshots_days: int = 400
    retention_prune_interval_minutes: int = 60

    # --- Upload hardening ---
    upload_max_bytes: int = 50 * 1024 * 1024
    upload_allowed_extensions: tuple[str, ...] = (".csv", ".txt", ".zone", ".json")
    upload_max_rows: int = 200_000

    # --- Rate limiting (requests per window per actor) ---
    rate_limit_scan_all_per_hour: int = 6
    rate_limit_discovery_per_hour: int = 12
    rate_limit_report_send_per_hour: int = 30
    rate_limit_ticket_create_per_hour: int = 30

    # --- Email ---
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_from: str = "zoneguard@example.com"
    smtp_username: str = ""
    smtp_password: str = ""

    # --- Ticketing ---
    jira_base_url: str = ""
    jira_api_token: str = ""
    jira_project_key: str = ""
    servicenow_base_url: str = ""
    servicenow_username: str = ""
    servicenow_password: str = ""

    @property
    def smtp_enabled(self) -> bool:
        return bool(self.smtp_host)

    @property
    def jira_enabled(self) -> bool:
        return bool(self.jira_base_url and self.jira_api_token)

    @property
    def servicenow_enabled(self) -> bool:
        return bool(self.servicenow_base_url and self.servicenow_username)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
