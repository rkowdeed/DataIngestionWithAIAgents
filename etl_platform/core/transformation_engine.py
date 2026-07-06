"""
Transformation Engine.

Applies configurable transformation rules (metadata.transformation_rules)
to extracted field values: unit conversion, string normalization,
timestamp conversion, derived fields, and business calculations.

Rules are resolved to named Python functions in TRANSFORMATION_REGISTRY,
never to arbitrary eval() of user-supplied expressions, so the engine
stays safe while remaining metadata-configurable (the metadata selects
*which* registered function runs and in what order, not raw code).
"""
import logging
from datetime import datetime, timezone
from typing import Any, Callable

logger = logging.getLogger(__name__)


def celsius_to_fahrenheit(value: float) -> float:
    return None if value is None else (value * 9 / 5) + 32


def normalize_string(value: str) -> str:
    return None if value is None else str(value).strip().upper()


def epoch_to_iso8601(value: Any) -> str:
    if value is None:
        return None
    return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()


def passthrough(value: Any) -> Any:
    return value


TRANSFORMATION_REGISTRY: dict[str, Callable[[Any], Any]] = {
    "CELSIUS_TO_FAHRENHEIT": celsius_to_fahrenheit,
    "NORMALIZE_STRING": normalize_string,
    "EPOCH_TO_ISO8601": epoch_to_iso8601,
    "PASSTHROUGH": passthrough,
}


def apply_transformation(value: Any, rule_name: str | None) -> Any:
    """Apply a single named transformation rule to a value."""
    if not rule_name:
        return value
    func = TRANSFORMATION_REGISTRY.get(rule_name.upper())
    if func is None:
        logger.warning("Unknown transformation rule '%s'; passing value through unchanged", rule_name)
        return value
    return func(value)


def apply_transformations(record: dict, mappings: list[dict]) -> dict:
    """
    Apply the transformation_rule referenced by each json_path_mapping
    entry to the corresponding field in an already-extracted record.
    """
    transformed = dict(record)
    for mapping in mappings:
        target_column = mapping["target_column"]
        rule_name = mapping.get("transformation_rule")
        if target_column in transformed and rule_name:
            transformed[target_column] = apply_transformation(transformed[target_column], rule_name)
    return transformed
