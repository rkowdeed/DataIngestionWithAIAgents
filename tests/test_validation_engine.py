from etl_platform.core.validation_engine import validate_record


def test_valid_record_passes_all_rules(sample_validation_rules, sample_mappings):
    record = {"lot_id": "LOT-1", "chamber_pressure_mean": 4.8}
    result = validate_record(record, sample_validation_rules, sample_mappings)
    assert result.is_valid
    assert result.errors == []


def test_null_business_key_fails_not_null_rule(sample_validation_rules, sample_mappings):
    record = {"lot_id": None, "chamber_pressure_mean": 4.8}
    result = validate_record(record, sample_validation_rules, sample_mappings)
    assert not result.is_valid
    assert any(i.rule_type == "NOT_NULL" for i in result.errors)


def test_out_of_range_value_fails_range_rule(sample_validation_rules, sample_mappings):
    record = {"lot_id": "LOT-1", "chamber_pressure_mean": 55.10}
    result = validate_record(record, sample_validation_rules, sample_mappings)
    assert not result.is_valid
    assert any(i.rule_type == "RANGE" for i in result.errors)


def test_warning_severity_does_not_fail_record(sample_mappings):
    rules = [
        {"json_path": "$.lot.wafers[*].measurements.chamberPressure", "rule_type": "RANGE",
         "rule_expression": "0<=value<=50", "severity": "WARNING"},
    ]
    record = {"lot_id": "LOT-1", "chamber_pressure_mean": 55.10}
    result = validate_record(record, rules, sample_mappings)
    assert result.is_valid  # only warnings, no errors
    assert len(result.warnings) == 1


def test_enum_rule():
    from etl_platform.core.validation_engine import _check_enum
    assert _check_enum("A", "IN ('A','B','C')") is True
    assert _check_enum("Z", "IN ('A','B','C')") is False
