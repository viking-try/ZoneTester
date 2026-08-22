CREATE TABLE IF NOT EXISTS domains (
    id BIGSERIAL PRIMARY KEY,
    domain TEXT NOT NULL,
    hosted_zone TEXT,
    source TEXT NOT NULL DEFAULT 'upload',
    dnssec_status TEXT,
    dnssec_detail JSONB,
    last_scan_at TIMESTAMPTZ,
    record_count INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT domains_domain_uk UNIQUE (domain)
);
CREATE INDEX IF NOT EXISTS idx_domains_hosted_zone ON domains(hosted_zone);

CREATE TABLE IF NOT EXISTS batches (
    id BIGSERIAL PRIMARY KEY,
    filename TEXT,
    format TEXT,
    source TEXT NOT NULL DEFAULT 'upload',
    s3_key TEXT,
    row_count INT,
    domain_count INT,
    uploaded_by TEXT,
    status TEXT NOT NULL DEFAULT 'processing',
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS records (
    id BIGSERIAL PRIMARY KEY,
    domain_id BIGINT NOT NULL REFERENCES domains(id) ON DELETE CASCADE,
    batch_id BIGINT REFERENCES batches(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    rtype TEXT NOT NULL,
    value TEXT NOT NULL,
    ttl INT,
    hosted_zone TEXT,
    scannable BOOLEAN NOT NULL DEFAULT FALSE,
    state TEXT NOT NULL DEFAULT 'unscanned',
    down_reason TEXT,
    scan_state TEXT NOT NULL DEFAULT 'pending',
    protocol TEXT,
    protocols_supported JSONB,
    negotiated_cipher TEXT,
    forward_secrecy BOOLEAN,
    pqc_supported BOOLEAN,
    weak_cipher_present BOOLEAN,
    vuln_flags JSONB,
    cert_json JSONB,
    cert_expires_at TIMESTAMPTZ,
    headers_json JSONB,
    server_header TEXT,
    x_powered_by TEXT,
    handshake_trust_failed BOOLEAN NOT NULL DEFAULT FALSE,
    tls_grade TEXT,
    tls_score INT,
    header_grade INT,
    grade TEXT,
    grade_score INT,
    cleanup BOOLEAN NOT NULL DEFAULT FALSE,
    cleanup_confidence INT,
    cleanup_action TEXT,
    cleanup_reasons JSONB,
    cleanup_ack BOOLEAN NOT NULL DEFAULT FALSE,
    consecutive_failures INT NOT NULL DEFAULT 0,
    first_seen TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_scanned TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT records_uk UNIQUE (name, rtype, value)
);
CREATE INDEX IF NOT EXISTS idx_records_domain ON records(domain_id);
CREATE INDEX IF NOT EXISTS idx_records_zone ON records(hosted_zone);
CREATE INDEX IF NOT EXISTS idx_records_state ON records(state);
CREATE INDEX IF NOT EXISTS idx_records_grade ON records(grade);
CREATE INDEX IF NOT EXISTS idx_records_cleanup ON records(cleanup);
CREATE INDEX IF NOT EXISTS idx_records_scannable ON records(scannable);
CREATE INDEX IF NOT EXISTS idx_records_rtype ON records(rtype);
