"""
Cloudflare R2 storage service.

R2 is S3-compatible, so we use boto3's S3 client pointed at the R2
endpoint. Objects are NEVER made public — every read goes through a
short-lived presigned URL (see `get_signed_download_url`), which matters
especially for the planned masked/redacted reports where access needs to
be tightly controlled and time-boxed.
"""
import logging
import uuid
from typing import BinaryIO

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import get_settings
from app.core.exceptions import StorageError

logger = logging.getLogger("specimen_inventory.storage")
settings = get_settings()


def _client():
    return boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        config=BotoConfig(signature_version="s3v4"),
        region_name="auto",
    )


def build_object_key(site_id: uuid.UUID, sample_id: uuid.UUID, filename: str) -> str:
    """
    Deterministic, collision-resistant key layout:
        reports/{site_id}/{sample_id}/{uuid4}_{original_filename}
    Namespacing by site+sample makes future bulk operations (e.g. "delete
    everything under this sample") trivial with a prefix list, and keeps
    one site's files logically separated from another's in the bucket.
    """
    safe_name = filename.replace("/", "_").replace("\\", "_")
    return f"reports/{site_id}/{sample_id}/{uuid.uuid4()}_{safe_name}"


def upload_file(file_obj: BinaryIO, object_key: str, content_type: str) -> None:
    try:
        _client().upload_fileobj(
            file_obj,
            settings.R2_BUCKET_NAME,
            object_key,
            ExtraArgs={"ContentType": content_type},
        )
    except (BotoCoreError, ClientError) as exc:
        logger.error("R2 upload failed for key=%s: %s", object_key, exc)
        raise StorageError(f"Failed to upload file to storage: {exc}")


def delete_object(object_key: str) -> None:
    """
    Deletes a single object. Logs a clear warning line on failure instead
    of raising — this is the exact log signal (`R2 object delete failed`)
    to grep for when diagnosing whether cleanup actually ran, mirroring
    the diagnosis approach used for the v1 orphaned-reports bug.
    """
    try:
        _client().delete_object(Bucket=settings.R2_BUCKET_NAME, Key=object_key)
    except (BotoCoreError, ClientError) as exc:
        logger.warning("R2 object delete failed for key=%s: %s", object_key, exc)
        raise StorageError(f"Failed to delete file from storage: {exc}")


def get_signed_download_url(object_key: str) -> str:
    try:
        return _client().generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.R2_BUCKET_NAME, "Key": object_key},
            ExpiresIn=settings.R2_SIGNED_URL_EXPIRY_SECONDS,
        )
    except (BotoCoreError, ClientError) as exc:
        logger.error("R2 signed URL generation failed for key=%s: %s", object_key, exc)
        raise StorageError(f"Failed to generate a download link: {exc}")
