"""
Audit Module.

Writes pipeline execution telemetry to metadata.audit_log: records
processed/succeeded/failed, runtime, and throughput, per batch_id.
"""
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


class AuditLogger:
    def __init__(self, engine: Engine):
        self.engine = engine

    def start_batch(self, pipeline_id: int, source_file: str) -> tuple[uuid.UUID, datetime]:
        batch_id = uuid.uuid4()
        start_time = datetime.now(timezone.utc)
        with self.engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO metadata.audit_log
                        (batch_id, pipeline_id, source_file, start_time, status)
                    VALUES (:batch_id, :pipeline_id, :source_file, :start_time, 'RUNNING')
                """),
                {
                    "batch_id": str(batch_id),
                    "pipeline_id": pipeline_id,
                    "source_file": source_file,
                    "start_time": start_time,
                },
            )
        logger.info("Started batch %s for pipeline_id=%s file=%s", batch_id, pipeline_id, source_file)
        return batch_id, start_time

    def complete_batch(
        self,
        batch_id: uuid.UUID,
        start_time: datetime,
        records_processed: int,
        records_success: int,
        records_failed: int,
    ) -> None:
        end_time = datetime.now(timezone.utc)
        runtime_seconds = (end_time - start_time).total_seconds()
        throughput = records_processed / runtime_seconds if runtime_seconds > 0 else records_processed

        if records_failed == 0:
            status = "SUCCESS"
        elif records_success == 0:
            status = "FAILED"
        else:
            status = "PARTIAL_SUCCESS"

        with self.engine.begin() as conn:
            conn.execute(
                text("""
                    UPDATE metadata.audit_log
                    SET end_time = :end_time,
                        runtime_seconds = :runtime_seconds,
                        throughput_rps = :throughput,
                        records_processed = :records_processed,
                        records_success = :records_success,
                        records_failed = :records_failed,
                        status = :status
                    WHERE batch_id = :batch_id
                """),
                {
                    "end_time": end_time,
                    "runtime_seconds": runtime_seconds,
                    "throughput": throughput,
                    "records_processed": records_processed,
                    "records_success": records_success,
                    "records_failed": records_failed,
                    "status": status,
                    "batch_id": str(batch_id),
                },
            )
        logger.info(
            "Completed batch %s status=%s processed=%d success=%d failed=%d runtime=%.2fs",
            batch_id, status, records_processed, records_success, records_failed, runtime_seconds,
        )
