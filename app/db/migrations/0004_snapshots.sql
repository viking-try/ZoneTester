CREATE TABLE IF NOT EXISTS snapshots (
    id BIGSERIAL PRIMARY KEY,
    snapshot_date DATE NOT NULL,
    zone TEXT NOT NULL DEFAULT '__all__',
    total_records INT,
    scanned_records INT,
    up_count INT,
    down_count INT,
    grade_distribution JSONB,
    pqc_count INT,
    weak_cipher_count INT,
    dangling_count INT,
    dnssec_summary JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT snapshots_uk UNIQUE (snapshot_date, zone)
);
CREATE INDEX IF NOT EXISTS idx_snapshots_zone_date ON snapshots(zone, snapshot_date);
