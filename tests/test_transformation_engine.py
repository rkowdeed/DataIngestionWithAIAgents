from etl_platform.core.transformation_engine import apply_transformation, apply_transformations


def test_celsius_to_fahrenheit():
    assert apply_transformation(0, "CELSIUS_TO_FAHRENHEIT") == 32
    assert apply_transformation(100, "CELSIUS_TO_FAHRENHEIT") == 212


def test_normalize_string():
    assert apply_transformation("  etch-tool-07  ", "NORMALIZE_STRING") == "ETCH-TOOL-07"


def test_unknown_rule_passes_value_through(caplog):
    assert apply_transformation(42, "NOT_A_REAL_RULE") == 42


def test_none_rule_name_is_noop():
    assert apply_transformation("value", None) == "value"


def test_apply_transformations_only_touches_mapped_columns(sample_mappings):
    record = {"lot_id": "LOT-1", "chuck_temperature": 20.0, "chamber_pressure_mean": 4.5}
    transformed = apply_transformations(record, sample_mappings)
    assert transformed["chuck_temperature"] == 68.0  # 20C -> 68F
    assert transformed["chamber_pressure_mean"] == 4.5  # no rule attached, unchanged
