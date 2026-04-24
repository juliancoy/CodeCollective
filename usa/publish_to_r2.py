#!/usr/bin/env python3
"""Publish versioned USAJOBS shard artifacts to Cloudflare R2 and prune old versions."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

import boto3


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload shard artifacts to Cloudflare R2.")
    parser.add_argument("--input-root", default="usa/data/publish", help="Local root containing object keys.")
    parser.add_argument("--prefix", default="jobs", help="Object key prefix (default: jobs).")
    parser.add_argument("--bucket", default=os.getenv("R2_BUCKET", ""), help="R2 bucket name.")
    parser.add_argument("--endpoint-url", default=os.getenv("R2_ENDPOINT_URL", ""), help="R2 S3 endpoint URL.")
    parser.add_argument("--access-key-id", default=os.getenv("R2_ACCESS_KEY_ID", ""), help="R2 access key id.")
    parser.add_argument("--secret-access-key", default=os.getenv("R2_SECRET_ACCESS_KEY", ""), help="R2 secret access key.")
    parser.add_argument("--region", default=os.getenv("R2_REGION", "auto"), help="S3 region name (default: auto).")
    parser.add_argument("--keep-versions", type=int, default=30, help="Number of historical versions to keep.")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without writing.")
    return parser.parse_args()


def create_client(args: argparse.Namespace):
    if not args.bucket or not args.endpoint_url or not args.access_key_id or not args.secret_access_key:
        raise ValueError("Missing R2 credentials/endpoint. Set args or R2_* environment variables.")
    session = boto3.session.Session()
    return session.client(
        "s3",
        region_name=args.region,
        endpoint_url=args.endpoint_url,
        aws_access_key_id=args.access_key_id,
        aws_secret_access_key=args.secret_access_key,
    )


def content_type_for(path: Path) -> str:
    if path.name.endswith(".json.gz"):
        return "application/json"
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def upload_tree(client, bucket: str, input_root: Path, prefix: str, dry_run: bool = False) -> None:
    prefix_root = input_root / prefix
    if not prefix_root.exists():
        raise FileNotFoundError(f"Missing publish prefix directory: {prefix_root}")

    files = sorted(path for path in prefix_root.rglob("*") if path.is_file())
    for path in files:
        key = path.relative_to(input_root).as_posix()
        kwargs: dict[str, Any] = {
            "Bucket": bucket,
            "Key": key,
            "Body": path.read_bytes(),
            "ContentType": content_type_for(path),
            "CacheControl": "public, max-age=300",
        }
        if path.name.endswith(".json.gz"):
            kwargs["ContentEncoding"] = "gzip"
        if dry_run:
            print(f"[dry-run] upload {key}")
            continue
        client.put_object(**kwargs)
        print(f"uploaded {key}")


def list_versions(client, bucket: str, prefix: str) -> list[str]:
    marker = None
    versions: set[str] = set()

    while True:
        kwargs = {"Bucket": bucket, "Prefix": f"{prefix}/v"}
        if marker:
            kwargs["ContinuationToken"] = marker
        response = client.list_objects_v2(**kwargs)
        for item in response.get("Contents", []):
            key = str(item.get("Key") or "")
            parts = key.split("/", 2)
            if len(parts) >= 2 and parts[1].startswith("v"):
                versions.add(parts[1])
        if not response.get("IsTruncated"):
            break
        marker = response.get("NextContinuationToken")

    return sorted(versions)


def list_keys_for_version(client, bucket: str, prefix: str, version: str) -> list[str]:
    marker = None
    keys: list[str] = []
    version_prefix = f"{prefix}/{version}/"

    while True:
        kwargs = {"Bucket": bucket, "Prefix": version_prefix}
        if marker:
            kwargs["ContinuationToken"] = marker
        response = client.list_objects_v2(**kwargs)
        keys.extend(str(item.get("Key") or "") for item in response.get("Contents", []))
        if not response.get("IsTruncated"):
            break
        marker = response.get("NextContinuationToken")

    return keys


def prune_old_versions(
    client,
    bucket: str,
    prefix: str,
    keep_versions: int,
    pinned_versions: set[str],
    dry_run: bool = False,
) -> None:
    versions = list_versions(client, bucket, prefix)
    if keep_versions < 1:
        keep_versions = 1
    keep_set = set(versions[-keep_versions:]) | pinned_versions
    delete_versions = [version for version in versions if version not in keep_set]

    if not delete_versions:
        print("no old versions to prune")
        return

    by_batch: dict[str, list[str]] = defaultdict(list)
    for version in delete_versions:
        keys = list_keys_for_version(client, bucket, prefix, version)
        for key in keys:
            by_batch[version].append(key)

    for version, keys in by_batch.items():
        print(f"pruning version {version} ({len(keys)} objects)")
        if dry_run:
            for key in keys:
                print(f"[dry-run] delete {key}")
            continue
        # DeleteObjects max batch size is 1000.
        for idx in range(0, len(keys), 1000):
            chunk = keys[idx : idx + 1000]
            client.delete_objects(
                Bucket=bucket,
                Delete={"Objects": [{"Key": key} for key in chunk], "Quiet": True},
            )


def read_latest_version(input_root: Path, prefix: str) -> str:
    latest_path = input_root / prefix / "latest.json"
    payload = json.loads(latest_path.read_text(encoding="utf-8"))
    version = str(payload.get("version") or "").strip()
    if not version:
        raise ValueError(f"latest.json missing version: {latest_path}")
    return version


def main() -> int:
    args = parse_args()
    input_root = Path(args.input_root).resolve()
    prefix = args.prefix.strip("/ ")
    if not prefix:
        raise ValueError("Prefix cannot be empty")

    version = read_latest_version(input_root, prefix)
    client = create_client(args)
    upload_tree(client, args.bucket, input_root, prefix, dry_run=args.dry_run)
    prune_old_versions(
        client,
        args.bucket,
        prefix,
        keep_versions=args.keep_versions,
        pinned_versions={version},
        dry_run=args.dry_run,
    )
    print(json.dumps({"published_version": version, "bucket": args.bucket, "prefix": prefix}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
