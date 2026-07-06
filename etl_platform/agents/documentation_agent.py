"""
Documentation Agent.

Responsibility (HLD Section 5): generate metadata documentation, e.g. a
human-readable data dictionary for a pipeline derived directly from its
metadata rows (source_json_schema, json_path_mapping, transformation
rules, validation rules), so documentation never drifts from the
metadata that actually governs execution.
"""
from typing import Any

from etl_platform.agents.base_agent import BaseAgent
from etl_platform.db.metadata_repository import PipelineDefinition


class DocumentationAgent(BaseAgent):
    agent_name = "Documentation Agent"

    def run(self, pipeline_def: PipelineDefinition) -> dict[str, Any]:
        field_lines = "\n".join(
            f"- `{f['json_path']}` -> `{f['field_name']}` ({f['datatype']}, "
            f"{'mandatory' if f['mandatory'] else 'optional'})"
            for f in pipeline_def.fields
        )
        prompt = (
            f"Write a concise markdown data dictionary section for pipeline "
            f"'{pipeline_def.pipeline_name}' (source system: {pipeline_def.source_system}, "
            f"target: {pipeline_def.target_schema}.{pipeline_def.target_table}). "
            f"Field list:\n{field_lines}\n\n"
            "Include a one-paragraph overview followed by a fields table."
        )
        doc = self.call_model(prompt, system="You are a technical writer documenting an ETL pipeline.")
        if not doc:
            doc = f"# {pipeline_def.pipeline_name}\n\n## Fields\n\n{field_lines}\n"
        return {"markdown": doc}
