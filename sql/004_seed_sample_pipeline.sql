-- =============================================================================
-- Seed Data: Sample pipeline for the Plasma Etch use case described in the HLD
-- (Lot -> Wafers -> Measurements/SPC/Defects)
-- =============================================================================

INSERT INTO metadata.pipeline_master
    (pipeline_name, source_system, source_format, target_schema, target_table, load_strategy, schedule, active_flag, version)
VALUES
    ('plasma_etch_wafer_ingest', 'MES', 'JSON', 'fab_ops', 'wafer_measurements', 'MERGE', '*/5 * * * *', TRUE, 1)
ON CONFLICT (pipeline_name) DO NOTHING;

INSERT INTO metadata.source_config
    (pipeline_id, bucket_name, folder_path, filename_pattern, compression, encryption, archive_path)
SELECT pipeline_id, 'fab-ops-raw-landing', 'mes/plasma_etch/incoming/', '*.json', 'NONE', 'SSE-KMS', 'mes/plasma_etch/archive/'
FROM metadata.pipeline_master WHERE pipeline_name = 'plasma_etch_wafer_ingest';

INSERT INTO metadata.json_schema_registry
    (source_id, schema_name, schema_version, json_schema, checksum, status)
SELECT sc.source_id, 'plasma_etch_lot_schema', '1.0',
    '{
        "type": "object",
        "required": ["lot", "equipment"],
        "properties": {
            "lot": {
                "type": "object",
                "required": ["id", "wafers"],
                "properties": {
                    "id": {"type": "string"},
                    "wafers": {"type": "array"}
                }
            },
            "equipment": {
                "type": "object",
                "required": ["toolId", "recipeId"],
                "properties": {
                    "toolId": {"type": "string"},
                    "recipeId": {"type": "string"}
                }
            }
        }
    }'::jsonb,
    'placeholder-checksum-will-be-computed-on-registration',
    'ACTIVE'
FROM metadata.source_config sc
JOIN metadata.pipeline_master pm ON pm.pipeline_id = sc.pipeline_id
WHERE pm.pipeline_name = 'plasma_etch_wafer_ingest'
ON CONFLICT (source_id, schema_name, schema_version) DO NOTHING;

-- Field definitions (source_json_schema)
INSERT INTO metadata.source_json_schema (schema_id, json_path, field_name, datatype, mandatory, validation_rule)
SELECT jsr.schema_id, v.json_path, v.field_name, v.datatype, v.mandatory, v.validation_rule
FROM metadata.json_schema_registry jsr,
(VALUES
    ('$.lot.id',                                  'lot_id',        'STRING',    TRUE,  'NOT NULL'),
    ('$.equipment.toolId',                         'tool_id',       'STRING',    TRUE,  'NOT NULL'),
    ('$.equipment.recipeId',                       'recipe_id',     'STRING',    TRUE,  'NOT NULL'),
    ('$.lot.wafers[*].id',                         'wafer_id',      'STRING',    TRUE,  'NOT NULL'),
    ('$.lot.wafers[*].measurements.chamberPressure','chamber_pressure_mean', 'FLOAT', FALSE, 'RANGE:0,50'),
    ('$.lot.wafers[*].measurements.rfPowerMax',     'rf_power_max',  'FLOAT',     FALSE, 'RANGE:0,5000'),
    ('$.lot.wafers[*].measurements.gasFlowVariance','gas_flow_variance', 'FLOAT', FALSE, NULL),
    ('$.lot.wafers[*].measurements.chuckTemperature','chuck_temperature', 'FLOAT', FALSE, 'RANGE:-50,300'),
    ('$.lot.wafers[*].measurements.endpointDuration','endpoint_duration_ms', 'INTEGER', FALSE, NULL)
) AS v(json_path, field_name, datatype, mandatory, validation_rule)
WHERE jsr.schema_name = 'plasma_etch_lot_schema' AND jsr.schema_version = '1.0'
ON CONFLICT (schema_id, json_path) DO NOTHING;

-- JSON path -> target column mapping
INSERT INTO metadata.json_path_mapping (schema_id, json_path, target_column, execution_order)
SELECT jsr.schema_id, v.json_path, v.target_column, v.execution_order
FROM metadata.json_schema_registry jsr,
(VALUES
    ('$.lot.id',                                   'lot_id',                1),
    ('$.equipment.toolId',                          'tool_id',               2),
    ('$.equipment.recipeId',                        'recipe_id',             3),
    ('$.lot.wafers[*].id',                          'wafer_id',              4),
    ('$.lot.wafers[*].measurements.chamberPressure','chamber_pressure_mean', 5),
    ('$.lot.wafers[*].measurements.rfPowerMax',     'rf_power_max',          6),
    ('$.lot.wafers[*].measurements.gasFlowVariance','gas_flow_variance',     7),
    ('$.lot.wafers[*].measurements.chuckTemperature','chuck_temperature',    8),
    ('$.lot.wafers[*].measurements.endpointDuration','endpoint_duration_ms', 9)
) AS v(json_path, target_column, execution_order)
WHERE jsr.schema_name = 'plasma_etch_lot_schema' AND jsr.schema_version = '1.0'
ON CONFLICT (schema_id, json_path, target_column) DO NOTHING;

-- Flatten configuration: explode Lot -> Wafers
INSERT INTO metadata.json_flatten_config (schema_id, parent_json_path, array_json_path, child_alias, grain_level, parent_key_column, execution_order)
SELECT jsr.schema_id, '$.lot', '$.lot.wafers[*]', 'wafer', 1, 'lot_id', 1
FROM metadata.json_schema_registry jsr
WHERE jsr.schema_name = 'plasma_etch_lot_schema' AND jsr.schema_version = '1.0';

-- Validation rules
INSERT INTO metadata.validation_rules (schema_id, json_path, rule_type, rule_expression, severity)
SELECT jsr.schema_id, v.json_path, v.rule_type, v.rule_expression, v.severity
FROM metadata.json_schema_registry jsr,
(VALUES
    ('$.lot.id',                                    'NOT_NULL', 'IS NOT NULL',      'ERROR'),
    ('$.lot.wafers[*].id',                           'NOT_NULL', 'IS NOT NULL',      'ERROR'),
    ('$.lot.wafers[*].measurements.chamberPressure', 'RANGE',    '0<=value<=50',     'ERROR'),
    ('$.lot.wafers[*].measurements.chuckTemperature','RANGE',    '-50<=value<=300',  'WARNING')
) AS v(json_path, rule_type, rule_expression, severity)
WHERE jsr.schema_name = 'plasma_etch_lot_schema' AND jsr.schema_version = '1.0';

-- Load configuration: merge on lot_id + wafer_id
INSERT INTO metadata.load_config (pipeline_id, target_table, load_type, business_key_columns)
SELECT pm.pipeline_id, 'wafer_measurements', 'MERGE', 'lot_id,wafer_id'
FROM metadata.pipeline_master pm
WHERE pm.pipeline_name = 'plasma_etch_wafer_ingest';

-- Lookup: resolve tool_id -> tool_name via equipment reference table
INSERT INTO metadata.lookup_config (lookup_name, lookup_schema, lookup_table, lookup_key_column, lookup_value_column, source_column, target_column)
VALUES ('Equipment', 'fab_ops', 'ref_equipment', 'tool_id', 'tool_name', 'tool_id', 'tool_name')
ON CONFLICT (lookup_name) DO NOTHING;
