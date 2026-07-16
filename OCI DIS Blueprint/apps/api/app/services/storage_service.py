"""Authoritative S3-compatible storage for application artifacts."""

from __future__ import annotations

import json
import mimetypes
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import boto3
from botocore.client import BaseClient
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import get_settings


_S3_SCHEME = "s3://"
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def safe_filename(value: str) -> str:
    """Return a storage-safe filename while retaining a useful extension."""

    normalized = _SAFE_NAME.sub("-", Path(value).name).strip("-.")
    return normalized or "artifact"


@lru_cache(maxsize=1)
def _client() -> BaseClient:
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.STORAGE_ENDPOINT or None,
        region_name=settings.STORAGE_REGION,
        aws_access_key_id=settings.STORAGE_ACCESS_KEY or None,
        aws_secret_access_key=settings.STORAGE_SECRET_KEY or None,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": settings.STORAGE_ADDRESSING_STYLE},
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    )


@lru_cache(maxsize=1)
def ensure_bucket() -> None:
    """Create the configured bucket when the local S3-compatible runtime is empty."""

    settings = get_settings()
    client = _client()
    try:
        client.head_bucket(Bucket=settings.STORAGE_BUCKET)
        return
    except ClientError as exc:
        status = int(exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0))
        error_code = str(exc.response.get("Error", {}).get("Code", ""))
        if status not in {400, 404} and error_code not in {"404", "NoSuchBucket", "NotFound"}:
            raise
    client.create_bucket(Bucket=settings.STORAGE_BUCKET)


def object_reference(key: str) -> str:
    """Build the canonical persisted reference for one object key."""

    bucket = get_settings().STORAGE_BUCKET
    return f"{_S3_SCHEME}{bucket}/{key.lstrip('/')}"


def _parse_reference(reference: str) -> tuple[str, str]:
    if not reference.startswith(_S3_SCHEME):
        raise ValueError("Reference is not an S3 object URI")
    bucket_and_key = reference[len(_S3_SCHEME) :]
    bucket, separator, key = bucket_and_key.partition("/")
    if not separator or not bucket or not key:
        raise ValueError("Invalid S3 object URI")
    return bucket, key


def put_bytes(
    key: str,
    contents: bytes,
    *,
    content_type: str | None = None,
    metadata: dict[str, str] | None = None,
) -> str:
    """Persist bytes and return their canonical S3 URI."""

    ensure_bucket()
    normalized_key = key.lstrip("/")
    guessed_type = content_type or mimetypes.guess_type(normalized_key)[0]
    arguments: dict[str, Any] = {
        "Bucket": get_settings().STORAGE_BUCKET,
        "Key": normalized_key,
        "Body": contents,
    }
    if guessed_type:
        arguments["ContentType"] = guessed_type
    if metadata:
        arguments["Metadata"] = metadata
    _client().put_object(**arguments)
    return object_reference(normalized_key)


def put_json(key: str, payload: dict[str, object]) -> str:
    """Persist deterministic UTF-8 JSON."""

    return put_bytes(
        key,
        json.dumps(payload, indent=2, sort_keys=True).encode("utf-8"),
        content_type="application/json",
    )


def read_bytes(reference: str) -> bytes:
    """Read an object, with read-only compatibility for legacy local references."""

    if not reference.startswith(_S3_SCHEME):
        path = Path(reference)
        if not path.is_file():
            raise FileNotFoundError(reference)
        return path.read_bytes()
    bucket, key = _parse_reference(reference)
    try:
        response = _client().get_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        status = int(exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0))
        if status == 404 or str(exc.response.get("Error", {}).get("Code", "")) in {
            "404",
            "NoSuchKey",
            "NotFound",
        }:
            raise FileNotFoundError(reference) from exc
        raise
    return bytes(response["Body"].read())


def read_json(reference: str) -> dict[str, object]:
    """Read one JSON object."""

    payload = json.loads(read_bytes(reference).decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Stored JSON payload must be an object")
    return payload


def delete(reference: str) -> None:
    """Delete an object; legacy local files are removed only when explicitly referenced."""

    if not reference:
        return
    if not reference.startswith(_S3_SCHEME):
        Path(reference).unlink(missing_ok=True)
        return
    bucket, key = _parse_reference(reference)
    _client().delete_object(Bucket=bucket, Key=key)


def delete_prefix(prefix: str) -> int:
    """Delete every object below a bounded application-owned key prefix."""

    ensure_bucket()
    normalized_prefix = prefix.strip("/") + "/"
    deleted = 0
    continuation_token: str | None = None
    while True:
        arguments: dict[str, Any] = {
            "Bucket": get_settings().STORAGE_BUCKET,
            "Prefix": normalized_prefix,
        }
        if continuation_token:
            arguments["ContinuationToken"] = continuation_token
        response = _client().list_objects_v2(**arguments)
        objects = [{"Key": item["Key"]} for item in response.get("Contents", [])]
        if objects:
            _client().delete_objects(
                Bucket=get_settings().STORAGE_BUCKET,
                Delete={"Objects": objects, "Quiet": True},
            )
            deleted += len(objects)
        if not response.get("IsTruncated"):
            break
        continuation_token = str(response.get("NextContinuationToken", "")) or None
    return deleted


def list_keys(prefix: str = "") -> list[str]:
    """List object keys below an application-owned prefix for diagnostics and smoke tests."""

    ensure_bucket()
    normalized_prefix = prefix.lstrip("/")
    keys: list[str] = []
    continuation_token: str | None = None
    while True:
        arguments: dict[str, Any] = {
            "Bucket": get_settings().STORAGE_BUCKET,
            "Prefix": normalized_prefix,
        }
        if continuation_token:
            arguments["ContinuationToken"] = continuation_token
        response = _client().list_objects_v2(**arguments)
        keys.extend(str(item["Key"]) for item in response.get("Contents", []))
        if not response.get("IsTruncated"):
            return sorted(keys)
        continuation_token = str(response.get("NextContinuationToken", "")) or None


def exists(reference: str) -> bool:
    """Return whether an artifact reference can be resolved."""

    if not reference.startswith(_S3_SCHEME):
        return Path(reference).is_file()
    bucket, key = _parse_reference(reference)
    try:
        _client().head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as exc:
        status = int(exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0))
        if status == 404 or str(exc.response.get("Error", {}).get("Code", "")) in {
            "404",
            "NoSuchKey",
            "NotFound",
        }:
            return False
        raise


def reset_clients_for_tests() -> None:
    """Clear cached clients after tests override storage settings."""

    _client.cache_clear()
    ensure_bucket.cache_clear()
