CREATE TABLE IF NOT EXISTS jobs (
    id BIGSERIAL PRIMARY KEY,
    celery_task_id TEXT,
    type TEXT NOT NULL,
    payload JSONB,
    state TEXT NOT NULL DEFAULT 'queued',
    error TEXT,
    result JSONB,
    zone TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_jobs_state_created ON jobs(state, created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_type ON jobs(type);

CREATE TABLE IF NOT EXISTS events (
    id BIGSERIAL PRIMARY KEY,
    record_id BIGINT REFERENCES records(id) ON DELETE CASCADE,
    domain_id BIGINT REFERENCES domains(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    detail JSONB,
    zone TEXT,
    reported_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_events_type_created ON events(event_type, created_at);
CREATE INDEX IF NOT EXISTS idx_events_reported ON events(reported_at);
CREATE INDEX IF NOT EXISTS idx_events_zone ON events(zone);
