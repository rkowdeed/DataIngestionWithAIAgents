-- =============================================================================
-- Metadata Repository DDL - Part 2: Transformation, Validation, Lookup, Load
-- HLD Reference: Section 3.7 - 3.10
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 3.7 transformation_rules
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS metadata.transformation_rules (
    rule_id           SERIAL PRIMARY KEY,
    rule_name         VARCHAR(200) NOT NULL UNIQUE,
    rule_type         VARCHAR(50)  NOT NULL,   -- UNIT_CONVERSION / STRING_NORMALIZE / TIMESTAMP_CONVERT / DERIVED_FIELD / BUSINESS_CALC
    expression        TEXT         NOT NULL,   -- safe expression / function reference, e.g. "celsius_to_fahrenheit(value)"
    execution_order   INTEGER      NOT NULL DEFAULT 0,
    version           INTEGER      NOT NULL DEFAULT 1,
    active_flag       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- 3.8 validation_rules
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS metadata.validation_rules (
    validation_id     SERIAL PRIMARY KEY,
    schema_id         INTEGER NOT NULL REFERENCES metadata.json_schema_registry(schema_id),
    json_path         VARCHAR(500) NOT NULL,
    rule_type         VARCHAR(30)  NOT NULL,   -- NOT_NULL / DATATYPE / RANGE / ENUM / CROSS_FIELD / NESTED_OBJECT
    rule_expression   VARCHAR(500) NOT NULL,   -- e.g. "0<=value<=100" or "IN ('A','B','C')"
    severity          VARCHAR(20)  NOT NULL DEFAULT 'ERROR', -- ERROR / WARNING
    active_flag       BOOLEAN      NOT NULL DEFAULT TRUE
);

-- -----------------------------------------------------------------------------
-- 3.9 lookup_config - reference data lookup definitions
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS metadata.lookup_config (
    lookup_id         SERIAL PRIMARY KEY,
    lookup_name       VARCHAR(200) NOT NULL UNIQUE, -- Equipment / Product / Recipe / Chamber / Customer
    lookup_schema     VARCHAR(100) NOT NULL,
    lookup_table      VARCHAR(100) NOT NULL,
    lookup_key_column VARCHAR(200) NOT NULL,
    lookup_value_column VARCHAR(200) NOT NULL,
    source_column     VARCHAR(200) NOT NULL,        -- column in the incoming record to match against lookup_key_column
    target_column     VARCHAR(200) NOT NULL,        -- column to populate with lookup_value_column
    cache_ttl_seconds INTEGER NOT NULL DEFAULT 300
);

-- -----------------------------------------------------------------------------
-- 3.10 load_config
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS metadata.load_config (
    load_config_id    SERIAL PRIMARY KEY,
    pipeline_id       INTEGER NOT NULL REFERENCES metadata.pipeline_master(pipeline_id),
    target_table      VARCHAR(200) NOT NULL,
    load_type         VARCHAR(20)  NOT NULL,  -- APPEND / MERGE / UPSERT / SCD1 / SCD2
    business_key_columns   VARCHAR(500) NOT NULL, -- comma-separated columns forming the natural/business key
    scd2_effective_column  VARCHAR(100) DEFAULT 'effective_start_date',
    scd2_expiry_column     VARCHAR(100) DEFAULT 'effective_end_date',
    scd2_current_flag_column VARCHAR(100) DEFAULT 'is_current',
    batch_size        INTEGER NOT NULL DEFAULT 5000
);
