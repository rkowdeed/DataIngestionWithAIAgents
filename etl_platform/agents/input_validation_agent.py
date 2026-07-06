"""
Input Validation Agent.

Responsibility (HLD Section 5): validate JSON structure, mandatory
fields, and data types. Wraps the deterministic schema_validator and
adds a natural-language summary of failures for operators, plus a
recommendation on whether the failure looks recoverable.
"""
from typing import Any

from etl_platform.agents.base_agent import BaseAgent
from etl_platform.core.schema_validator import SchemaValidationResult


class InputValidationAgent(BaseAgent):
    agent_name = "Input Validation Agent"

    def run(self, validation_result: SchemaValidationResult, payload: dict) -> dict[str, Any]:
        if validation_result.is_valid:
            return {"summary": "Payload passed schema validation.", "recoverable": True}

        prompt = (
            "The following JSON payload failed schema validation with these errors:\n"
            f"{validation_result.errors}\n\n"
            "Payload (truncated to relevant keys):\n"
            f"{list(payload.keys()) if isinstance(payload, dict) else 'N/A'}\n\n"
            "In one or two sentences, summarize the likely root cause for a data engineer, "
            "and state whether this looks like a recoverable data issue (e.g. missing optional "
            "field) or a structural/source-system issue."
        )
        summary = self.call_model(prompt, system="You are an ETL data-quality assistant.")
        return {
            "summary": summary or f"Schema validation failed: {validation_result.errors}",
            "recoverable": len(validation_result.errors) <= 2,
        }
