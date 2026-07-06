"""
JSON Schema Validation Engine.

Validates incoming JSON documents against the version-controlled JSON
Schema stored in metadata.json_schema_registry before any extraction or
transformation happens. This is the first gate in the ETL processing flow.
"""
import hashlib
import json
import logging
from dataclasses import dataclass

import jsonschema

logger = logging.getLogger(__name__)


@dataclass
class SchemaValidationResult:
    is_valid: bool
    errors: list[str]
    checksum: str


def compute_schema_checksum(schema_document: dict) -> str:
    """SHA-256 checksum of a JSON schema document, used for drift detection."""
    canonical = json.dumps(schema_document, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_document(payload: dict, json_schema: dict) -> SchemaValidationResult:
    """
    Validate a single JSON payload against the registered JSON Schema.

    Returns all validation errors (not just the first) so the Input
    Validation Agent / Error Classification Agent has full context.
    """
    validator = jsonschema.Draft7Validator(json_schema)
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))

    error_messages = [
        f"{'.'.join(str(p) for p in err.path) or '<root>'}: {err.message}"
        for err in errors
    ]

    return SchemaValidationResult(
        is_valid=len(error_messages) == 0,
        errors=error_messages,
        checksum=compute_schema_checksum(json_schema),
    )


def detect_schema_drift(payload: dict, json_schema: dict) -> list[str]:
    """
    Best-effort detection of fields present in the payload but not declared
    in the schema (additive drift). Returns a list of undeclared JSON
    pointer-style paths. Feeds the Schema Drift Agent (Section 5).
    """
    declared_props = set((json_schema.get("properties") or {}).keys())
    actual_props = set(payload.keys()) if isinstance(payload, dict) else set()
    undeclared = actual_props - declared_props
    return sorted(f"$.{prop}" for prop in undeclared)
