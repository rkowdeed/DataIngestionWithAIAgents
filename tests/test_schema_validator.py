from etl_platform.core import schema_validator


def test_valid_document_passes(sample_lot_payload, plasma_etch_json_schema):
    result = schema_validator.validate_document(sample_lot_payload, plasma_etch_json_schema)
    assert result.is_valid
    assert result.errors == []


def test_missing_required_field_fails(sample_lot_payload, plasma_etch_json_schema):
    del sample_lot_payload["equipment"]
    result = schema_validator.validate_document(sample_lot_payload, plasma_etch_json_schema)
    assert not result.is_valid
    assert any("equipment" in e for e in result.errors)


def test_checksum_is_stable():
    schema = {"type": "object", "properties": {"a": {"type": "string"}}}
    checksum1 = schema_validator.compute_schema_checksum(schema)
    checksum2 = schema_validator.compute_schema_checksum(dict(schema))
    assert checksum1 == checksum2
    assert len(checksum1) == 64  # sha256 hex digest length


def test_schema_drift_detects_undeclared_top_level_fields(sample_lot_payload, plasma_etch_json_schema):
    sample_lot_payload["operator"] = {"badgeId": "OP-4471"}
    drift = schema_validator.detect_schema_drift(sample_lot_payload, plasma_etch_json_schema)
    assert "$.operator" in drift
