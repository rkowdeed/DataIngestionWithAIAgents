"""
Observability Agent.

Responsibility (HLD Section 5): analyze pipeline health and operational
metrics. Reads recent metadata.audit_log rows and produces a plain-
language health summary and anomaly callouts (e.g. throughput drop,
rising failure rate) for operators/dashboards.
"""
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from etl_platform.agents.base_agent import BaseAgent


class ObservabilityAgent(BaseAgent):
    agent_name = "Observability Agent"

    def __init__(self, engine: Engine):
        super().__init__(engine)

    def _recent_runs(self, pipeline_id: int, limit: int = 20) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT batch_id, records_processed, records_success, records_failed,
                           runtime_seconds, throughput_rps, status, start_time
                    FROM metadata.audit_log
                    WHERE pipeline_id = :pipeline_id
                    ORDER BY start_time DESC
                    LIMIT :limit
                """),
                {"pipeline_id": pipeline_id, "limit": limit},
            ).mappings().all()
        return [dict(r) for r in rows]

    def run(self, pipeline_id: int) -> dict[str, Any]:
        runs = self._recent_runs(pipeline_id)
        if not runs:
            return {"summary": "No execution history available for this pipeline yet.", "runs_analyzed": 0}

        avg_throughput = sum(r["throughput_rps"] or 0 for r in runs) / len(runs)
        failure_rate = sum(r["records_failed"] for r in runs) / max(sum(r["records_processed"] for r in runs), 1)

        prompt = (
            f"Recent pipeline runs (most recent first): {runs}. "
            f"Average throughput: {avg_throughput:.2f} records/sec. Failure rate: {failure_rate:.2%}. "
            "Summarize pipeline health in 2-3 sentences for an on-call engineer, calling out any "
            "concerning trend (e.g. degrading throughput, rising failure rate)."
        )
        summary = self.call_model(prompt, system="You are a pipeline observability assistant.")
        if not summary:
            summary = f"Avg throughput={avg_throughput:.2f} rec/s, failure_rate={failure_rate:.2%} over last {len(runs)} runs."

        return {"summary": summary, "runs_analyzed": len(runs), "avg_throughput_rps": avg_throughput, "failure_rate": failure_rate}
