"""Fetches R53 dump objects from S3 for the Lambda -> S3 -> Zoneguard flow: one object per
hosted zone under a prefix. Uses the container's IAM role via boto3's default credential
chain (instance/task role) — no stored access keys. An optional assume-role ARN lets the
ingest be cross-account. Three selection modes:
  - latest: only the most-recently-modified object under the prefix
  - all: every object under the prefix
  - new: objects not already recorded as ingested (caller supplies the known-keys set,
    typically `SELECT DISTINCT s3_key FROM batches WHERE source='s3'`)
"""
from dataclasses import dataclass

import boto3


@dataclass(slots=True)
class S3Object:
    key: str
    last_modified: str  # ISO-8601 string; compared lexicographically per Postgres-dialect lesson
    etag: str
    size: int


def build_s3_client(*, assume_role_arn: str | None, region: str | None = None):
    session_kwargs = {"region_name": region} if region else {}
    if assume_role_arn:
        sts = boto3.client("sts", **session_kwargs)
        creds = sts.assume_role(RoleArn=assume_role_arn, RoleSessionName="zoneguard-ingest")["Credentials"]
        return boto3.client(
            "s3",
            aws_access_key_id=creds["AccessKeyId"],
            aws_secret_access_key=creds["SecretAccessKey"],
            aws_session_token=creds["SessionToken"],
            **session_kwargs,
        )
    # No explicit credentials: relies on the container's IAM role (ECS task role / EKS IRSA /
    # EC2 instance profile) via boto3's default credential provider chain.
    return boto3.client("s3", **session_kwargs)


def list_objects(client, bucket: str, prefix: str) -> list[S3Object]:
    objects: list[S3Object] = []
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            objects.append(
                S3Object(
                    key=obj["Key"],
                    last_modified=obj["LastModified"].isoformat(),
                    etag=obj.get("ETag", "").strip('"'),
                    size=obj.get("Size", 0),
                )
            )
    return objects


def fetch_object(client, bucket: str, key: str) -> bytes:
    resp = client.get_object(Bucket=bucket, Key=key)
    return resp["Body"].read()


def select_objects(objects: list[S3Object], *, mode: str, known_keys: set[str] | None = None) -> list[S3Object]:
    if mode == "all":
        return list(objects)
    if mode == "latest":
        return [max(objects, key=lambda o: o.last_modified)] if objects else []
    if mode == "new":
        known = known_keys or set()
        return [o for o in objects if o.key not in known]
    raise ValueError(f"unknown S3 ingest mode: {mode!r} (expected latest|all|new)")
