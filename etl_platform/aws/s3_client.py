"""
S3 Client.

Thin wrapper around boto3 for listing/reading landed JSON documents and
moving them to the archive path once a batch has been processed
(metadata.source_config.archive_path), per HLD Section 2 & 4.
"""
import gzip
import json
import logging
from typing import Any, Iterator

import boto3

from etl_platform.config import S3

logger = logging.getLogger(__name__)


def _client():
    kwargs = {"region_name": S3.region}
    if S3.endpoint_url:
        kwargs["endpoint_url"] = S3.endpoint_url
    return boto3.client("s3", **kwargs)


def list_objects(bucket: str, prefix: str) -> list[str]:
    client = _client()
    paginator = client.get_paginator("list_objects_v2")
    keys: list[str] = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            keys.append(obj["Key"])
    return keys


def read_json_object(bucket: str, key: str, compression: str = "NONE") -> dict[str, Any]:
    client = _client()
    body = client.get_object(Bucket=bucket, Key=key)["Body"].read()
    if compression.upper() == "GZIP":
        body = gzip.decompress(body)
    return json.loads(body)


def iter_json_documents(bucket: str, prefix: str, compression: str = "NONE") -> Iterator[tuple[str, dict]]:
    for key in list_objects(bucket, prefix):
        try:
            yield key, read_json_object(bucket, key, compression)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to read/parse S3 object s3://%s/%s", bucket, key)
            raise


def archive_object(bucket: str, source_key: str, archive_path: str) -> str:
    client = _client()
    archive_key = archive_path.rstrip("/") + "/" + source_key.split("/")[-1]
    client.copy_object(Bucket=bucket, CopySource={"Bucket": bucket, "Key": source_key}, Key=archive_key)
    client.delete_object(Bucket=bucket, Key=source_key)
    logger.info("Archived s3://%s/%s -> s3://%s/%s", bucket, source_key, bucket, archive_key)
    return archive_key
