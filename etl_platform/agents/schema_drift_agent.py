"""
Schema Drift Agent.

Responsibility (HLD Section 5): detect schema evolution and recommend
metadata updates. Compares undeclared fields found by
core.schema_validator.detect_schema_drift against history and proposes
new source_json_schema / json_path_mapping rows for human approval —
it never writes metadata directly (governance: Section 7).
"""
from typing import Any

from etl_platform.agents.base_agent import BaseAgent


class SchemaDriftAgent(BaseAgent):
    agent_name = "Schema Drift Agent"

    def run(self, undeclared_paths: list[str], schema_name: str) -> dict[str, Any]:
        if not undeclared_paths:
            return {"drift_detected": False, "recommendation": None}

        prompt = (
            f"New, undeclared JSON fields were observed in source '{schema_name}': "
            f"{undeclared_paths}. Recommend a datatype and mandatory flag for each field, "
            "and a one-line rationale, formatted as a short bullet list for a data engineer "
            "to review before updating the metadata registry."
        )
        recommendation = self.call_model(
            prompt, system="You are a metadata governance assistant for a semiconductor ETL platform."
        )
        return {
            "drift_detected": True,
            "undeclared_paths": undeclared_paths,
            "recommendation": recommendation or "Manual review required: new fields detected.",
        }
