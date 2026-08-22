CREATE TABLE IF NOT EXISTS schedules (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    zone TEXT,
    template TEXT NOT NULL,
    cadence TEXT NOT NULL,
    interval_minutes INT,
    recipients JSONB NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    last_sent_at TIMESTAMPTZ,
    created_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_schedules_enabled ON schedules(enabled);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by TEXT
);

CREATE TABLE IF NOT EXISTS audit (
    id BIGSERIAL PRIMARY KEY,
    actor TEXT NOT NULL,
    method TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    path TEXT NOT NULL,
    status_code INT,
    duration_ms INT,
    ip TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit(actor);

CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    email TEXT NOT NULL,
    display_name TEXT,
    role TEXT NOT NULL DEFAULT 'viewer',
    auth_source TEXT NOT NULL DEFAULT 'local',
    password_hash TEXT,
    oidc_subject TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at TIMESTAMPTZ,
    CONSTRAINT users_email_uk UNIQUE (email)
);
