"""
JSONPath Extraction Engine.

Extracts values from JSON documents using metadata-defined JSONPath
expressions (metadata.json_path_mapping) and flattens nested arrays
according to metadata.json_flatten_config (e.g. Lot -> Wafers ->
Measurements/SPC/Defects), all without any code change.
"""
import logging
from typing import Any

from jsonpath_ng.ext import parse as jsonpath_parse

logger = logging.getLogger(__name__)


def extract_value(payload: dict, json_path: str) -> Any:
    """Extract the first match for a JSONPath expression, or None."""
    expr = jsonpath_parse(json_path)
    matches = [m.value for m in expr.find(payload)]
    return matches[0] if matches else None


def extract_all(payload: dict, json_path: str) -> list[Any]:
    """Extract all matches for a JSONPath expression (used for array paths)."""
    expr = jsonpath_parse(json_path)
    return [m.value for m in expr.find(payload)]


def flatten_records(payload: dict, flatten_configs: list[dict]) -> list[dict]:
    """
    Explode a nested JSON document into one flat record per leaf grain,
    per the ordered list of flatten_configs (lowest grain_level first).

    Each output record is a dict `{child_alias: element, parent: payload}`
    carrying enough context for downstream JSONPath extraction relative
    to the exploded element.
    """
    if not flatten_configs:
        return [{"__root__": payload}]

    # Start with a single "row" representing the whole document.
    rows: list[dict] = [{"__root__": payload}]

    for cfg in sorted(flatten_configs, key=lambda c: c["execution_order"]):
        next_rows: list[dict] = []
        array_path = cfg["array_json_path"]
        alias = cfg["child_alias"]

        for row in rows:
            elements = extract_all(row["__root__"], array_path)
            if not elements:
                # No child elements found; keep the parent row with a null child.
                new_row = dict(row)
                new_row[alias] = None
                next_rows.append(new_row)
                continue
            for element in elements:
                new_row = dict(row)
                new_row[alias] = element
                next_rows.append(new_row)

        rows = next_rows

    return rows


def apply_mappings(flattened_row: dict, mappings: list[dict]) -> dict:
    """
    Apply metadata.json_path_mapping entries to a flattened row, producing
    a flat dict of {target_column: raw_value}. JSONPath expressions are
    evaluated against the root document; if the path targets an exploded
    child element, the relative element is substituted automatically.
    """
    root = flattened_row["__root__"]
    result: dict[str, Any] = {}

    for mapping in sorted(mappings, key=lambda m: m["execution_order"]):
        json_path = mapping["json_path"]
        target_column = mapping["target_column"]

        # If the path references an exploded array (contains '[*]'), resolve
        # it against the specific child element carried in this row instead
        # of re-expanding the whole array from root.
        if "[*]" in json_path and any(k != "__root__" for k in flattened_row):
            child_alias = next(k for k in flattened_row if k != "__root__")
            relative_path = json_path.split("[*].", 1)[-1]
            child_element = flattened_row.get(child_alias)
            value = extract_value(child_element, "$." + relative_path) if child_element else None
        else:
            value = extract_value(root, json_path)

        result[target_column] = value

    return result
