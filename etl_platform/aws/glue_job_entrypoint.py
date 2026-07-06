"""
AWS Glue Job Entrypoint.

Invoked by the Step Functions state machine (infra/step_functions) after
an EventBridge S3 PutObject trigger. Expects two Glue job arguments:

    --pipeline_name   Name of the row in metadata.pipeline_master to run
    --source_key      (optional) a single S3 key to process; if omitted,
                       all objects under the configured folder_path are
                       processed as one batch.

Usage (local dry run, without an actual Glue environment):

    python -m etl_platform.aws.glue_job_entrypoint --pipeline_name plasma_etch_wafer_ingest
"""
import argparse
import logging

from etl_platform.aws import s3_client
from etl_platform.pipeline.orchestrator import PipelineOrchestrator
from etl_platform.utils.logging_config import configure_logging

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pipeline_name", required=True)
    parser.add_argument("--source_key", required=False, default=None)
    # Glue injects --JOB_NAME automatically; accept and ignore it here.
    parser.add_argument("--JOB_NAME", required=False, default=None)
    return parser.parse_args()


def main() -> None:
    configure_logging()
    args = parse_args()

    orchestrator = PipelineOrchestrator(pipeline_name=args.pipeline_name)

    # Resolve S3 source configuration for this pipeline.
    with orchestrator.engine.connect() as conn:
        from sqlalchemy import text
        source_cfg = conn.execute(
            text("""
                SELECT bucket_name, folder_path, compression, archive_path
                FROM metadata.source_config
                WHERE pipeline_id = :pipeline_id
                LIMIT 1
            """),
            {"pipeline_id": orchestrator.pipeline_def.pipeline_id},
        ).mappings().first()

    if source_cfg is None:
        raise LookupError(f"No source_config found for pipeline '{args.pipeline_name}'")

    bucket = source_cfg["bucket_name"]
    prefix = source_cfg["folder_path"]
    compression = source_cfg["compression"]
    archive_path = source_cfg["archive_path"]

    if args.source_key:
        documents = [(args.source_key, s3_client.read_json_object(bucket, args.source_key, compression))]
    else:
        documents = list(s3_client.iter_json_documents(bucket, prefix, compression))

    logger.info("Processing %d document(s) for pipeline '%s'", len(documents), args.pipeline_name)
    result = orchestrator.run_batch(documents, source_file=f"s3://{bucket}/{prefix}")
    logger.info("Batch result: %s", result)

    for document_id, _ in documents:
        s3_client.archive_object(bucket, document_id, archive_path)


if __name__ == "__main__":
    main()
