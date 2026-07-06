-- =============================================================================
-- Target Schema: fab_ops
-- Curated tables that the Load Engine writes into. These are illustrative
-- of the "wafer_measurements" target referenced in the sample pipeline
-- (sql/004_seed_sample_pipeline.sql) and the Equipment lookup table.
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS fab_ops;

CREATE TABLE IF NOT EXISTS fab_ops.wafer_measurements (
    lot_id                  VARCHAR(100) NOT NULL,
    wafer_id                VARCHAR(100) NOT NULL,
    tool_id                 VARCHAR(100),
    recipe_id               VARCHAR(100),
    tool_name               VARCHAR(200),
    chamber_pressure_mean   NUMERIC(10,4),
    rf_power_max            NUMERIC(10,2),
    gas_flow_variance       NUMERIC(10,4),
    chuck_temperature       NUMERIC(10,2),
    endpoint_duration_ms    INTEGER,
    loaded_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (lot_id, wafer_id)
);

CREATE TABLE IF NOT EXISTS fab_ops.ref_equipment (
    tool_id     VARCHAR(100) PRIMARY KEY,
    tool_name   VARCHAR(200) NOT NULL,
    chamber_id  VARCHAR(100),
    active_flag BOOLEAN NOT NULL DEFAULT TRUE
);

INSERT INTO fab_ops.ref_equipment (tool_id, tool_name, chamber_id) VALUES
    ('ETCH-TOOL-07', 'Applied Materials Centura AP - Etch 07', 'CHAMBER-A3')
ON CONFLICT (tool_id) DO NOTHING;
