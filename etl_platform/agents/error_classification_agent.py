"""
Error Classification Agent.

Responsibility (HLD Section 5): classify failures and determine root
cause. Assigns an error_category (SCHEMA / VALIDATION / TRANSFORMATION /
LOAD / LOOKUP) used by core.error_handler to decide recoverability and
by the Self-Healing Agent to pick a recovery policy.
"""
from typing import Any

from etl_platform.agents.base_agent import BaseAgent

_KEYWORD_CATEGORY_MAP = {
    "schema": "SCHEMA",
    "required": "SCHEMA",
    "range": "VALIDATION",
    "enum": "VALIDATION",
    "not_null": "VALIDATION",
    "transform": "TRANSFORMATION",
    "lookup": "LOOKUP",
    "constraint": "LOAD",
    "duplicate key": "LOAD",
    "connection": "LOAD",
}


class ErrorClassificationAgent(BaseAgent):
    agent_name = "Error Classification Agent"

    def classify_heuristic(self, error_message: str) -> str:
        """Fast, deterministic first pass before falling back to the LLM."""
        lowered = error_message.lower()
        for keyword, category in _KEYWORD_CATEGORY_MAP.items():
            if keyword in lowered:
                return category
        return "UNKNOWN"

    def run(self, error_message: str, payload_context: dict | None = None) -> dict[str, Any]:
        category = self.classify_heuristic(error_message)
        if category != "UNKNOWN":
            return {"error_category": category, "root_cause": error_message, "source": "heuristic"}

        prompt = (
            f"Classify this ETL error into exactly one category: SCHEMA, VALIDATION, "
            f"TRANSFORMATION, LOAD, or LOOKUP. Error message: '{error_message}'. "
            f"Context: {payload_context or {}}. Respond with the category name only, "
            "followed by a one-sentence root cause explanation."
        )
        response = self.call_model(prompt, system="You are an ETL error triage assistant.")
        return {"error_category": response.split()[0] if response else "UNKNOWN", "root_cause": response, "source": "llm"}
