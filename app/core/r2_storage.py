"""Private Cloudflare R2 access through its S3-compatible endpoint."""

import uuid

import boto3
from botocore.config import Config

from app.core.config import R2PrivateSettings, r2_private_settings
from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessError


def private_settings() -> R2PrivateSettings:
    settings = r2_private_settings()
    if not all((settings.account_id, settings.access_key, settings.secret_key, settings.bucket)):
        raise BusinessError(503, ErrorCode.SYSTEM_BUSY, "私有文件存储尚未配置")
    return settings


def private_client(settings: R2PrivateSettings):
    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.access_key,
        aws_secret_access_key=settings.secret_key,
        region_name="auto",
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            connect_timeout=5, read_timeout=30,
            retries={"max_attempts": 2},
        ),
    )


def new_object_key(settings: R2PrivateSettings, user_id: int, extension: str) -> str:
    return f"{settings.path_prefix}/python-demo/users/{user_id}/{uuid.uuid4().hex}{extension}".lstrip("/")


def put_private_object(settings: R2PrivateSettings, object_key: str, data: bytes, mime_type: str) -> str | None:
    response = private_client(settings).put_object(
        Bucket=settings.bucket, Key=object_key, Body=data, ContentType=mime_type,
    )
    return response.get("ETag", "").strip('"') or None


def delete_private_object(settings: R2PrivateSettings, object_key: str) -> None:
    private_client(settings).delete_object(Bucket=settings.bucket, Key=object_key)


def presigned_read_url(settings: R2PrivateSettings, object_key: str, expires_seconds: int = 300) -> str:
    return private_client(settings).generate_presigned_url(
        "get_object", Params={"Bucket": settings.bucket, "Key": object_key},
        ExpiresIn=expires_seconds,
    )
