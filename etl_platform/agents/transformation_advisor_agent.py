"""
Transformation Advisor Agent.

Responsibility (HLD Section 5): recommend new mappings and
transformations, e.g. when a Schema Drift Agent finds a new field that
needs a target column and (optionally) a transformation rule before it
can be onboarded into metadata.json_path_mapping.
"""
from typing import Any

from etl_platform.agents.base_agent import BaseAgent
from etl_platform.core.transformation_engine import TRANSFORMATION_REGISTRY


class TransformationAdvisorAgent(BaseAgent):
    agent_name = "Transformation Advisor"

    def run(self, field_name: str, sample_values: list[Any]) -> dict[str, Any]:
        available_rules = list(TRANSFORMATION_REGISTRY.keys())
        prompt = (
            f"Field '{field_name}' has sample values: {sample_values}. "
            f"Available transformation rules in the registry: {available_rules}. "
            "Recommend the target Aurora column name (snake_case), the most appropriate "
            "transformation rule from the list (or 'PASSTHROUGH' if none apply), and a "
            "one-sentence rationale."
        )
        recommendation = self.call_model(
            prompt, system="You are a data mapping assistant for a semiconductor ETL platform."
        )
        return {"field_name": field_name, "recommendation": recommendation or "PASSTHROUGH (no recommendation available)"}
