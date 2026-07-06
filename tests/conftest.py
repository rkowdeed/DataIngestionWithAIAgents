import json
from pathlib import Path

import pytest

SAMPLE_DATA_DIR = Path(__file__).resolve().parent.parent / "sample_data"


@pytest.fixture
def sample_lot_payload() -> dict:
    with open(SAMPLE_DATA_DIR / "sample_lot_wafer.json") as f:
        return json.load(f)


@pytest.fixture
def plasma_etch_json_schema() -> dict:
    return {
        "type": "object",
        "required": ["lot", "equipment"],
        "properties": {
            "lot": {
                "type": "object",
                "required": ["id", "wafers"],
                "properties": {
                    "id": {"type": "string"},
                    "wafers": {"type": "array"},
                },
            },
            "equipment": {
                "type": "object",
                "required": ["toolId", "recipeId"],
                "properties": {
                    "toolId": {"type": "string"},
                    "recipeId": {"type": "string"},
                },
            },
        },
    }


@pytest.fixture
def sample_mappings() -> list[dict]:
    return [
        {"json_path": "$.lot.id", "target_column": "lot_id", "transformation_rule": None, "execution_order": 1},
        {"json_path": "$.equipment.toolId", "target_column": "tool_id", "transformation_rule": None, "execution_order": 2},
        {"json_path": "$.equipment.recipeId", "target_column": "recipe_id", "transformation_rule": None, "execution_order": 3},
        {"json_path": "$.lot.wafers[*].id", "target_column": "wafer_id", "transformation_rule": None, "execution_order": 4},
        {"json_path": "$.lot.wafers[*].measurements.chamberPressure", "target_column": "chamber_pressure_mean",
         "transformation_rule": None, "execution_order": 5},
        {"json_path": "$.lot.wafers[*].measurements.chuckTemperature", "target_column": "chuck_temperature",
         "transformation_rule": "CELSIUS_TO_FAHRENHEIT", "execution_order": 6},
    ]


@pytest.fixture
def sample_flatten_configs() -> list[dict]:
    return [
        {
            "parent_json_path": "$.lot",
            "array_json_path": "$.lot.wafers[*]",
            "child_alias": "wafer",
            "grain_level": 1,
            "parent_key_column": "lot_id",
            "execution_order": 1,
        }
    ]


@pytest.fixture
def sample_validation_rules() -> list[dict]:
    return [
        {"json_path": "$.lot.id", "rule_type": "NOT_NULL", "rule_expression": "IS NOT NULL", "severity": "ERROR"},
        {"json_path": "$.lot.wafers[*].measurements.chamberPressure", "rule_type": "RANGE",
         "rule_expression": "0<=value<=50", "severity": "ERROR"},
    ]
