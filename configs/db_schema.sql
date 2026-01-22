CREATE TABLE patients (
    id UUID PRIMARY KEY,
    metadata JSONB,  # Encrypted PHI
    consent_token TEXT UNIQUE
);

CREATE TABLE slides (
    id UUID PRIMARY KEY,
    patient_id UUID REFERENCES patients(id),
    file_path TEXT,
    metadata JSONB,  # Dimensions, annotations
    upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE annotations (
    id UUID PRIMARY KEY,
    slide_id UUID REFERENCES slides(id),
    data JSONB,
    user_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE ai_jobs (
    id UUID PRIMARY KEY,
    slide_id UUID REFERENCES slides(id),
    app_name TEXT,
    status TEXT,  # queued/running/done
    result JSONB,
    signature TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    user_id TEXT,
    action TEXT,
    resource_id UUID,
    details JSONB,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
-- Indexes
CREATE INDEX idx_slides_patient ON slides(patient_id);
-- TimescaleDB for logs (install extension first)
CREATE EXTENSION IF NOT EXISTS timescaledb;
SELECT create_hypertable('audit_logs', 'timestamp');

CREATE TABLE roles (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,  # admin, pathologist, viewer, researcher, auditor
    permissions JSONB  # e.g., {"upload": true, "retrieve": true}
);

CREATE TABLE user_roles (
    user_id TEXT NOT NULL,
    role_id INT REFERENCES roles(id),
    PRIMARY KEY (user_id, role_id)
);

-- Seed roles
INSERT INTO roles (name, permissions) VALUES
('admin', '{"*": true}'),
('pathologist', '{"upload": true, "retrieve": true, "list": true, "metadata": true, "ai_run": true}'),
('viewer', '{"list": true, "metadata": true}'),
('researcher', '{"ai_run": true, "list": true}'),
('auditor', '{"list": true, "metadata": true, "audit": true}');
