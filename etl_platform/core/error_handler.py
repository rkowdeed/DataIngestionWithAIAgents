"""
Error Handling & Self-Healing Enqueue Module.

Instead of failing a whole batch, individual failed payloads are written
to metadata.error_record and, when classified as recoverable, enqueued
into metadata.self_healing_queue with a recovery policy (Section 6).
"""
import json
import logging
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

RECOVERABLE_CATEGORIES = {"TRANSFORMATION", "LOOKUP", "LOAD"}
NON_RECOVERABLE_CATEGORIES = {"SCHEMA"}


class ErrorHandler:
    def __init__(self, engine: Engine):
        self.engine = engine

    def record_error(
        self,
        batch_id: uuid.UUID,
        payload: dict[str, Any],
        json_path: str | None,
        error_message: str,
        error_category: str,
    ) -> int:
        with self.engine.begin() as conn:
            result = conn.execute(
                text("""
                    INSERT INTO metadata.error_record
                        (batch_id, payload_json, json_path, error_message, error_category)
                    VALUES (:batch_id, :payload_json, :json_path, :error_message, :error_category)
                    RETURNING error_id
                """),
                {
                    "batch_id": str(batch_id),
                    "payload_json": json.dumps(payload),
                    "json_path": json_path,
                    "error_message": error_message,
                    "error_category": error_category,
                },
            )
            error_id = result.scalar_one()

        logger.warning("Recorded error_id=%s category=%s message=%s", error_id, error_category, error_message)

        if error_category in RECOVERABLE_CATEGORIES:
            self._enqueue_self_healing(error_id, error_message, error_category)

        return error_id

    def _enqueue_self_healing(self, error_id: int, failure_reason: str, error_category: str) -> None:
        policy = "IMMEDIATE_RETRY" if error_category == "LOOKUP" else "DELAYED_RETRY"
        with self.engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO metadata.self_healing_queue
                        (payload_id, failure_reason, recovery_policy, assigned_agent, status)
                    VALUES (:payload_id, :failure_reason, :recovery_policy, 'Self-Healing Agent', 'QUEUED')
                """),
                {
                    "payload_id": error_id,
                    "failure_reason": failure_reason,
                    "recovery_policy": policy,
                },
            )
        logger.info("Enqueued error_id=%s into self-healing queue with policy=%s", error_id, policy)
