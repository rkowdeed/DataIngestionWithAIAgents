"""
Metadata Repository access layer.

Centralizes every read against the `metadata` schema described in the HLD
(Section 3). All ETL behavior is externalized here so that onboarding a new
JSON source requires only metadata inserts, never code changes.
"""
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text

from etl_platform.db.connection import get_engine


@dataclass
class PipelineDefinition:
    pipeline_id: int
    pipeline_name: str
    source_system: str
    target_schema: str
    target_table: str
    load_strategy: str
    active_flag: bool
    schema_id: int
    fields: list = field(default_factory=list)
    mappings: list = field(default_factory=list)
    flatten_configs: list = field(default_factory=list)
    validation_rules: list = field(default_factory=list)
    lookups: list = field(default_factory=list)
    load_config: dict = field(default_factory=dict)


class MetadataRepository:
    """Read-only access to pipeline configuration metadata."""

    def __init__(self, engine=None):
        self.engine = engine or get_engine()

    def get_pipeline_by_name(self, pipeline_name: str) -> "PipelineDefinition":
        with self.engine.connect() as conn:
            pipeline_row = conn.execute(
                text("""
                    SELECT pipeline_id, pipeline_name, source_system, target_schema,
                           target_table, load_strategy, active_flag
                    FROM metadata.pipeline_master
                    WHERE pipeline_name = :name AND active_flag = TRUE
                """),
                {"name": pipeline_name},
            ).mappings().first()

            if pipeline_row is None:
                raise LookupError(f"No active pipeline found for name '{pipeline_name}'")

            schema_row = conn.execute(
                text("""
                    SELECT jsr.schema_id
                    FROM metadata.json_schema_registry jsr
                    JOIN metadata.source_config sc ON sc.source_id = jsr.source_id
                    WHERE sc.pipeline_id = :pipeline_id AND jsr.status = 'ACTIVE'
                    ORDER BY jsr.effective_date DESC
                    LIMIT 1
                """),
                {"pipeline_id": pipeline_row["pipeline_id"]},
            ).mappings().first()

            if schema_row is None:
                raise LookupError(f"No active JSON schema registered for pipeline '{pipeline_name}'")

            schema_id = schema_row["schema_id"]

            fields = conn.execute(
                text("""
                    SELECT json_path, field_name, datatype, mandatory, default_value, validation_rule
                    FROM metadata.source_json_schema WHERE schema_id = :schema_id
                """),
                {"schema_id": schema_id},
            ).mappings().all()

            mappings = conn.execute(
                text("""
                    SELECT json_path, target_column, transformation_rule, execution_order
                    FROM metadata.json_path_mapping WHERE schema_id = :schema_id
                    ORDER BY execution_order
                """),
                {"schema_id": schema_id},
            ).mappings().all()

            flatten_configs = conn.execute(
                text("""
                    SELECT parent_json_path, array_json_path, child_alias, grain_level,
                           parent_key_column, execution_order
                    FROM metadata.json_flatten_config WHERE schema_id = :schema_id
                    ORDER BY execution_order
                """),
                {"schema_id": schema_id},
            ).mappings().all()

            validation_rules = conn.execute(
                text("""
                    SELECT json_path, rule_type, rule_expression, severity
                    FROM metadata.validation_rules
                    WHERE schema_id = :schema_id AND active_flag = TRUE
                """),
                {"schema_id": schema_id},
            ).mappings().all()

            lookups = conn.execute(
                text("""
                    SELECT lookup_name, lookup_schema, lookup_table, lookup_key_column,
                           lookup_value_column, source_column, target_column, cache_ttl_seconds
                    FROM metadata.lookup_config
                """)
            ).mappings().all()

            load_config_row = conn.execute(
                text("""
                    SELECT target_table, load_type, business_key_columns,
                           scd2_effective_column, scd2_expiry_column,
                           scd2_current_flag_column, batch_size
                    FROM metadata.load_config WHERE pipeline_id = :pipeline_id
                """),
                {"pipeline_id": pipeline_row["pipeline_id"]},
            ).mappings().first()

            return PipelineDefinition(
                pipeline_id=pipeline_row["pipeline_id"],
                pipeline_name=pipeline_row["pipeline_name"],
                source_system=pipeline_row["source_system"],
                target_schema=pipeline_row["target_schema"],
                target_table=pipeline_row["target_table"],
                load_strategy=pipeline_row["load_strategy"],
                active_flag=pipeline_row["active_flag"],
                schema_id=schema_id,
                fields=[dict(r) for r in fields],
                mappings=[dict(r) for r in mappings],
                flatten_configs=[dict(r) for r in flatten_configs],
                validation_rules=[dict(r) for r in validation_rules],
                lookups=[dict(r) for r in lookups],
                load_config=dict(load_config_row) if load_config_row else {},
            )

    def get_json_schema_document(self, schema_id: int) -> dict[str, Any]:
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT json_schema FROM metadata.json_schema_registry WHERE schema_id = :id"),
                {"id": schema_id},
            ).mappings().first()
            return row["json_schema"] if row else {}

    def get_transformation_rule(self, rule_name: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT rule_id, rule_name, rule_type, expression, execution_order
                    FROM metadata.transformation_rules
                    WHERE rule_name = :name AND active_flag = TRUE
                """),
                {"name": rule_name},
            ).mappings().first()
            return dict(row) if row else None
