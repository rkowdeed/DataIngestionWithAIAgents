from etl_platform.core.jsonpath_extractor import apply_mappings, extract_value, flatten_records


def test_extract_value_simple_path(sample_lot_payload):
    assert extract_value(sample_lot_payload, "$.lot.id") == "LOT-2026-000451"
    assert extract_value(sample_lot_payload, "$.equipment.toolId") == "ETCH-TOOL-07"


def test_flatten_records_explodes_one_row_per_wafer(sample_lot_payload, sample_flatten_configs):
    rows = flatten_records(sample_lot_payload, sample_flatten_configs)
    assert len(rows) == len(sample_lot_payload["lot"]["wafers"])
    assert all("wafer" in row for row in rows)


def test_apply_mappings_produces_flat_record_per_wafer(sample_lot_payload, sample_flatten_configs, sample_mappings):
    rows = flatten_records(sample_lot_payload, sample_flatten_configs)
    records = [apply_mappings(row, sample_mappings) for row in rows]

    assert len(records) == 3
    assert records[0]["lot_id"] == "LOT-2026-000451"
    assert records[0]["tool_id"] == "ETCH-TOOL-07"
    assert records[0]["wafer_id"] == "WAF-001"
    assert records[0]["chamber_pressure_mean"] == 4.82
    assert records[2]["wafer_id"] == "WAF-003"
    assert records[2]["chamber_pressure_mean"] == 55.10
