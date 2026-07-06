-- =============================================================================
-- Metadata Repository DDL - Part 1: Pipeline, Source, and JSON Schema Metadata
-- Target: Amazon Aurora PostgreSQL
-- HLD Reference: Section 3.1 - 3.6
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS metadata;

-- -----------------------------------------------------------------------------
-- 3.1 pipeline_master - Pipeline-level configuration
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS metadata.pipeline_master (
    pipeline_id     SERIAL PRIMARY KEY,
    pipeline_name   VARCHAR(200) NOT NULL UNIQUE,
    source_system   VARCHAR(50)  NOT NULL,          -- MES / APC / SPC / ERP
    source_format   VARCHAR(20)  NOT NULL DEFAULT 'JSON',
    target_schema   VARCHAR(100) NOT NULL,
    target_table    VARCHAR(100) NOT NULL,
    load_strategy   VARCHAR(20)  NOT NULL DEFAULT 'APPEND', -- APPEND / MERGE / SCD1 / SCD2
    schedule        VARCHAR(100),                    -- cron expression
    active_flag     BOOLEAN      NOT NULL DEFAULT TRUE,
    version         INTEGER      NOT NULL DEFAULT 1,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- 3.2 source_config - S3 ingestion configuration
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS metadata.source_config (
    source_id        SERIAL PRIMARY KEY,
    pipeline_id       INTEGER NOT NULL REFERENCES metadata.pipeline_master(pipeline_id),
    bucket_name       VARCHAR(200) NOT NULL,
    folder_path       VARCHAR(500) NOT NULL,
    filename_pattern  VARCHAR(200) NOT NULL DEFAULT '*.json',
    compression       VARCHAR(20)  DEFAULT 'NONE',   -- NONE / GZIP
    encryption        VARCHAR(20)  DEFAULT 'SSE-KMS',
    archive_path      VARCHAR(500) NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- 3.3 json_schema_registry - version-controlled JSON schemas
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS metadata.json_schema_registry (
    schema_id       SERIAL PRIMARY KEY,
    source_id       INTEGER NOT NULL REFERENCES metadata.source_config(source_id),
    schema_name     VARCHAR(200) NOT NULL,
    schema_version  VARCHAR(20)  NOT NULL,
    json_schema     JSONB        NOT NULL,           -- full JSON Schema document
    checksum        VARCHAR(64)  NOT NULL,           -- sha256 of json_schema for drift detection
    effective_date  DATE         NOT NULL DEFAULT CURRENT_DATE,
    status          VARCHAR(20)  NOT NULL DEFAULT 'ACTIVE', -- ACTIVE / DEPRECATED / DRAFT
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    UNIQUE (source_id, schema_name, schema_version)
);

-- -----------------------------------------------------------------------------
-- 3.4 source_json_schema - every JSON element expected by the ETL engine
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS metadata.source_json_schema (
    field_id          SERIAL PRIMARY KEY,
    schema_id         INTEGER NOT NULL REFERENCES metadata.json_schema_registry(schema_id),
    json_path         VARCHAR(500) NOT NULL,         -- e.g. $.lot.id
    field_name        VARCHAR(200) NOT NULL,
    datatype          VARCHAR(30)  NOT NULL,         -- STRING/INTEGER/FLOAT/BOOLEAN/TIMESTAMP/ARRAY/OBJECT
    mandatory         BOOLEAN      NOT NULL DEFAULT FALSE,
    default_value     TEXT,
    validation_rule   VARCHAR(500),
    UNIQUE (schema_id, json_path)
);

-- -----------------------------------------------------------------------------
-- 3.5 json_path_mapping - maps JSON elements to Aurora columns
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS metadata.json_path_mapping (
    mapping_id           SERIAL PRIMARY KEY,
    schema_id            INTEGER NOT NULL REFERENCES metadata.json_schema_registry(schema_id),
    json_path             VARCHAR(500) NOT NULL,
    target_column         VARCHAR(200) NOT NULL,
    transformation_rule   VARCHAR(200),              -- FK reference (by rule_name) into transformation_rules
    execution_order       INTEGER NOT NULL DEFAULT 0,
    UNIQUE (schema_id, json_path, target_column)
);

-- -----------------------------------------------------------------------------
-- 3.6 json_flatten_config - controls exploding of nested arrays (Lot -> Wafers -> Measurements/SPC/Defects)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS metadata.json_flatten_config (
    flatten_id        SERIAL PRIMARY KEY,
    schema_id         INTEGER NOT NULL REFERENCES metadata.json_schema_registry(schema_id),
    parent_json_path  VARCHAR(500) NOT NULL,         -- e.g. $.lot
    array_json_path   VARCHAR(500) NOT NULL,         -- e.g. $.lot.wafers[*]
    child_alias       VARCHAR(100) NOT NULL,         -- e.g. wafer
    grain_level       INTEGER NOT NULL DEFAULT 1,    -- 1 = wafer level, 2 = measurement level, etc.
    parent_key_column VARCHAR(200),                  -- column used to join back to parent record
    execution_order   INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_source_json_schema_schema_id ON metadata.source_json_schema(schema_id);
CREATE INDEX IF NOT EXISTS idx_json_path_mapping_schema_id ON metadata.json_path_mapping(schema_id);
CREATE INDEX IF NOT EXISTS idx_json_flatten_config_schema_id ON metadata.json_flatten_config(schema_id);
