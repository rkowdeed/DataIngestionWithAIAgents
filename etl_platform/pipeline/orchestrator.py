"""
Pipeline Orchestrator.

Implements the end-to-end ETL Processing Flow from HLD Section 4:

    JSON arrives in S3
        -> Metadata Loaded
        -> JSON Schema Validation
        -> JSONPath Extraction
        -> Transformation Engine
        -> Lookup Engine
        -> Validation Engine
        -> Load Aurora
        -> Audit
        -> Archive

Individual JSON payload failures are diverted to the error repository /
self-healing queue rather than failing the whole batch (Section 6).
"""
import logging
from typing import Any

from etl_platform.agents.error_classification_agent import ErrorClassificationAgent
from etl_platform.agents.input_validation_agent import InputValidationAgent
from etl_platform.agents.schema_drift_agent import SchemaDriftAgent
from etl_platform.core import schema_validator
from etl_platform.core.audit import AuditLogger
from etl_platform.core.error_handler import ErrorHandler
from etl_platform.core.jsonpath_extractor import apply_mappings, flatten_records
from etl_platform.core.load_engine import LoadEngine
from etl_platform.core.lookup_engine import LookupEngine
from etl_platform.core.transformation_engine import apply_transformations
from etl_platform.core.validation_engine import validate_record
from etl_platform.db.connection import get_engine
from etl_platform.db.metadata_repository import MetadataRepository, PipelineDefinition

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    def __init__(self, pipeline_name: str, engine=None):
        self.engine = engine or get_engine()
        self.metadata_repo = MetadataRepository(self.engine)
        self.pipeline_def: PipelineDefinition = self.metadata_repo.get_pipeline_by_name(pipeline_name)
        self.json_schema = self.metadata_repo.get_json_schema_document(self.pipeline_def.schema_id)

        self.lookup_engine = LookupEngine(self.engine)
        self.load_engine = LoadEngine(self.engine, self.pipeline_def.target_schema)
        self.audit_logger = AuditLogger(self.engine)
        self.error_handler = ErrorHandler(self.engine)

        self.input_validation_agent = InputValidationAgent(self.engine)
        self.schema_drift_agent = SchemaDriftAgent(self.engine)
        self.error_classification_agent = ErrorClassificationAgent(self.engine)

    def process_document(self, document_id: str, payload: dict) -> dict[str, Any]:
        """
        Run a single JSON document through schema validation, extraction,
        transformation, lookup, and validation. Returns a dict describing
        success/failure and, on success, the list of curated records ready
        for load. Never raises for expected data-quality issues.
        """
        # 1. JSON Schema Validation
        schema_result = schema_validator.validate_document(payload, self.json_schema)
        if not schema_result.is_valid:
            agent_summary = self.input_validation_agent.run(schema_result, payload)
            logger.warning("Document %s failed schema validation: %s", document_id, agent_summary["summary"])
            return {"document_id": document_id, "status": "SCHEMA_INVALID", "errors": schema_result.errors,
                     "agent_summary": agent_summary}

        drift = schema_validator.detect_schema_drift(payload, self.json_schema)
        if drift:
            drift_result = self.schema_drift_agent.run(drift, self.json_schema.get("title", "unknown"))
            logger.info("Schema drift detected for document %s: %s", document_id, drift_result)

        # 2. JSONPath Extraction (with array flattening, e.g. Lot -> Wafers)
        flattened_rows = flatten_records(payload, self.pipeline_def.flatten_configs)
        extracted_records = [apply_mappings(row, self.pipeline_def.mappings) for row in flattened_rows]

        # 3. Transformation Engine
        transformed_records = [apply_transformations(r, self.pipeline_def.mappings) for r in extracted_records]

        # 4. Lookup Engine
        enriched_records = [self.lookup_engine.apply_lookups(r, self.pipeline_def.lookups) for r in transformed_records]

        # 5. Validation Engine
        valid_records, invalid_records = [], []
        for record in enriched_records:
            result = validate_record(record, self.pipeline_def.validation_rules, self.pipeline_def.mappings)
            if result.is_valid:
                valid_records.append(record)
            else:
                invalid_records.append({"record": record, "issues": result.errors})

        return {
            "document_id": document_id,
            "status": "OK" if not invalid_records else "PARTIAL",
            "valid_records": valid_records,
            "invalid_records": invalid_records,
        }

    def run_batch(self, documents: list[tuple[str, dict]], source_file: str = "unknown") -> dict[str, Any]:
        """Process a batch of (document_id, payload) tuples end to end, including load and audit."""
        batch_id, start_time = self.audit_logger.start_batch(self.pipeline_def.pipeline_id, source_file)

        all_valid_records: list[dict] = []
        processed, succeeded, failed = 0, 0, 0

        for document_id, payload in documents:
            processed += 1
            result = self.process_document(document_id, payload)

            if result["status"] == "SCHEMA_INVALID":
                failed += 1
                self.error_handler.record_error(
                    batch_id=batch_id, payload=payload, json_path=None,
                    error_message="; ".join(result["errors"]), error_category="SCHEMA",
                )
                continue

            all_valid_records.extend(result["valid_records"])
            succeeded += 1 if not result["invalid_records"] else 0

            for invalid in result["invalid_records"]:
                failed += 1
                error_message = "; ".join(i.message for i in invalid["issues"]) if hasattr(invalid["issues"][0], "message") \
                    else "; ".join(str(i) for i in invalid["issues"])
                classification = self.error_classification_agent.run(error_message)
                self.error_handler.record_error(
                    batch_id=batch_id, payload=invalid["record"], json_path=None,
                    error_message=error_message, error_category=classification["error_category"],
                )

        loaded_count = 0
        if all_valid_records and self.pipeline_def.load_config:
            loaded_count = self.load_engine.load(all_valid_records, self.pipeline_def.load_config)

        self.audit_logger.complete_batch(
            batch_id=batch_id, start_time=start_time,
            records_processed=processed, records_success=succeeded, records_failed=failed,
        )

        return {
            "batch_id": str(batch_id),
            "documents_processed": processed,
            "documents_succeeded": succeeded,
            "documents_failed": failed,
            "records_loaded": loaded_count,
        }
