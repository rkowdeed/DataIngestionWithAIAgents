-- =============================================================================
-- Metadata Repository DDL - Part 3: Audit, Error Repository, Self-Healing, AI Agents
-- HLD Reference: Section 3.11 - 3.14
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 3.11 audit_log
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS metadata.audit_log (
    audit_id          BIGSERIAL PRIMARY KEY,
    batch_id          UUID NOT NULL,
    pipeline_id       INTEGER NOT NULL REFERENCES metadata.pipeline_master(pipeline_id),
    source_file       VARCHAR(1000),
    records_processed INTEGER NOT NULL DEFAULT 0,
    records_success   INTEGER NOT NULL DEFAULT 0,
    records_failed    INTEGER NOT NULL DEFAULT 0,
    start_time        TIMESTAMPTZ NOT NULL DEFAULT now(),
    end_time          TIMESTAMPTZ,
    runtime_seconds   NUMERIC(10,3),
    throughput_rps    NUMERIC(10,3),          -- records per second
    status            VARCHAR(20) NOT NULL DEFAULT 'RUNNING' -- RUNNING / SUCCESS / PARTIAL_SUCCESS / FAILED
);

CREATE INDEX IF NOT EXISTS idx_audit_log_pipeline_id ON metadata.audit_log(pipeline_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_batch_id ON metadata.audit_log(batch_id);

-- -----------------------------------------------------------------------------
-- 3.12 error_record - failed JSON payloads
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS metadata.error_record (
    error_id          BIGSERIAL PRIMARY KEY,
    batch_id          UUID NOT NULL,
    payload_json      JSONB NOT NULL,
    json_path         VARCHAR(500),
    error_message     TEXT NOT NULL,
    error_category    VARCHAR(50),            -- SCHEMA / VALIDATION / TRANSFORMATION / LOAD / LOOKUP
    retry_status      VARCHAR(20) NOT NULL DEFAULT 'PENDING', -- PENDING / RETRYING / RESOLVED / REJECTED
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_error_record_batch_id ON metadata.error_record(batch_id);
CREATE INDEX IF NOT EXISTS idx_error_record_retry_status ON metadata.error_record(retry_status);

-- -----------------------------------------------------------------------------
-- 3.13 self_healing_queue - recoverable failures
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS metadata.self_healing_queue (
    queue_id          BIGSERIAL PRIMARY KEY,
    payload_id        BIGINT NOT NULL REFERENCES metadata.error_record(error_id),
    failure_reason    TEXT NOT NULL,
    recovery_policy   VARCHAR(30) NOT NULL DEFAULT 'DELAYED_RETRY', -- IMMEDIATE_RETRY / DELAYED_RETRY / DEPENDENCY_RETRY / MANUAL_REVIEW / PERMANENT_REJECTION
    retry_count       INTEGER NOT NULL DEFAULT 0,
    max_retries       INTEGER NOT NULL DEFAULT 3,
    next_retry_at     TIMESTAMPTZ,
    assigned_agent    VARCHAR(100),
    status            VARCHAR(20) NOT NULL DEFAULT 'QUEUED', -- QUEUED / IN_PROGRESS / RESOLVED / ESCALATED / REJECTED
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_self_healing_queue_status ON metadata.self_healing_queue(status);

-- -----------------------------------------------------------------------------
-- 3.14 agent_registry - AI agent configuration
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS metadata.agent_registry (
    agent_id          SERIAL PRIMARY KEY,
    agent_name        VARCHAR(100) NOT NULL UNIQUE, -- Input Validation Agent / Schema Drift Agent / ...
    agent_type        VARCHAR(50)  NOT NULL,
    model_provider    VARCHAR(50)  DEFAULT 'anthropic',
    model_name        VARCHAR(100) DEFAULT 'claude-sonnet-5',
    config_json       JSONB        NOT NULL DEFAULT '{}'::jsonb,
    active_flag       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT now()
);

INSERT INTO metadata.agent_registry (agent_name, agent_type, config_json) VALUES
    ('Input Validation Agent',     'VALIDATION',     '{"scope": "json_structure_mandatory_fields_datatypes"}'),
    ('Schema Drift Agent',         'SCHEMA_DRIFT',   '{"scope": "detect_new_fields_and_recommend_metadata_updates"}'),
    ('Transformation Advisor',     'ADVISORY',       '{"scope": "recommend_new_mappings_and_transformations"}'),
    ('Error Classification Agent', 'ERROR_CLASSIFY', '{"scope": "classify_failures_and_root_cause"}'),
    ('Self-Healing Agent',         'SELF_HEALING',   '{"scope": "retry_failed_payloads_using_recovery_metadata"}'),
    ('Documentation Agent',        'DOCUMENTATION',  '{"scope": "generate_metadata_documentation"}'),
    ('Observability Agent',        'OBSERVABILITY',  '{"scope": "analyze_pipeline_health_and_operational_metrics"}')
ON CONFLICT (agent_name) DO NOTHING;
