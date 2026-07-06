"""
Self-Healing Agent.

Responsibility (HLD Section 5 & 6): retry failed payloads using recovery
metadata. Pulls due items from metadata.self_healing_queue, re-runs them
through the pipeline, and updates queue status. Only failed JSON
payloads are replayed — never a full-batch rerun.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from sqlalchemy import text
from sqlalchemy.engine import Engine

from etl_platform.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

RETRY_DELAYS_SECONDS = {
    "IMMEDIATE_RETRY": 0,
    "DELAYED_RETRY": 300,
    "DEPENDENCY_RETRY": 900,
}


class SelfHealingAgent(BaseAgent):
    agent_name = "Self-Healing Agent"

    def __init__(self, engine: Engine):
        super().__init__(engine)

    def fetch_due_items(self, max_items: int = 100) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT q.queue_id, q.payload_id, q.recovery_policy, q.retry_count, q.max_retries,
                           e.payload_json, e.error_message, e.error_category
                    FROM metadata.self_healing_queue q
                    JOIN metadata.error_record e ON e.error_id = q.payload_id
                    WHERE q.status = 'QUEUED'
                      AND (q.next_retry_at IS NULL OR q.next_retry_at <= now())
                      AND q.recovery_policy != 'MANUAL_REVIEW'
                      AND q.recovery_policy != 'PERMANENT_REJECTION'
                    ORDER BY q.updated_at
                    LIMIT :max_items
                """),
                {"max_items": max_items},
            ).mappings().all()
        return [dict(r) for r in rows]

    def mark_result(self, queue_id: int, success: bool, retry_count: int, max_retries: int, policy: str) -> None:
        with self.engine.begin() as conn:
            if success:
                conn.execute(
                    text("UPDATE metadata.self_healing_queue SET status = 'RESOLVED', updated_at = now() WHERE queue_id = :id"),
                    {"id": queue_id},
                )
                return

            new_retry_count = retry_count + 1
            if new_retry_count >= max_retries:
                conn.execute(
                    text("UPDATE metadata.self_healing_queue SET status = 'ESCALATED', retry_count = :rc, updated_at = now() WHERE queue_id = :id"),
                    {"id": queue_id, "rc": new_retry_count},
                )
                return

            delay = RETRY_DELAYS_SECONDS.get(policy, 300)
            next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
            conn.execute(
                text("""
                    UPDATE metadata.self_healing_queue
                    SET retry_count = :rc, next_retry_at = :next_retry_at, updated_at = now()
                    WHERE queue_id = :id
                """),
                {"rc": new_retry_count, "next_retry_at": next_retry_at, "id": queue_id},
            )

    def run(self, reprocess_fn: Callable[[dict], bool], max_items: int = 100) -> dict[str, Any]:
        """
        `reprocess_fn` takes the original payload_json and returns True/False
        for success. This keeps the agent decoupled from the orchestrator.
        """
        items = self.fetch_due_items(max_items=max_items)
        resolved, escalated, retried = 0, 0, 0

        for item in items:
            success = False
            try:
                success = reprocess_fn(item["payload_json"])
            except Exception as exc:  # noqa: BLE001
                logger.warning("Self-healing retry raised an exception for queue_id=%s: %s", item["queue_id"], exc)

            self.mark_result(
                queue_id=item["queue_id"],
                success=success,
                retry_count=item["retry_count"],
                max_retries=item["max_retries"],
                policy=item["recovery_policy"],
            )
            if success:
                resolved += 1
            elif item["retry_count"] + 1 >= item["max_retries"]:
                escalated += 1
            else:
                retried += 1

        return {"items_considered": len(items), "resolved": resolved, "retried": retried, "escalated": escalated}
