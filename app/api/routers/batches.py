"""Upload endpoint for R53 dumps + paginated ingest history. Upload hardening per spec:
streamed with a hard size cap (413 if exceeded), extension allowlist, and a parsed-row-count
cap enforced inside the ingest pipeline."""
import importlib
import logging
from pathlib import Path

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from pydantic import BaseModel

from app.api.deps import get_db, require_role
from app.api.pagination import paginated_response, parse_page_params
from app.config import settings
from app.constants import Role
from app.ingest.detect import sniff_format
from app.ingest.loader import PARSERS, create_batch, load_batch, mark_batch_error
from app.ingest.normalize import normalize
from app.ingest.pipeline import IngestError, ingest_bytes
from app.ingest.s3_connector import build_s3_client, fetch_object, list_objects, select_objects

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/batches", tags=["batches"])

_ALLOWED_SORT = {
    "created_at": "created_at",
    "filename": "filename",
    "status": "status",
    "row_count": "row_count",
}


@router.post("", dependencies=[Depends(require_role(Role.OPERATOR))])
async def upload_batch(request: Request, file: UploadFile, db: psycopg.Connection = Depends(get_db)) -> dict:
    ext = Path(file.filename or "").suffix.lower()
    if ext not in settings.upload_allowed_extensions:
        raise HTTPException(
            415, f"file extension {ext!r} not allowed; expected one of {settings.upload_allowed_extensions}"
        )

    chunks: list[bytes] = []
    total = 0
    cap = settings.upload_max_bytes
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > cap:
            raise HTTPException(413, f"upload exceeds the {cap} byte limit")
        chunks.append(chunk)
    raw = b"".join(chunks)

    actor = getattr(request.state, "actor", None) or "anonymous"
    try:
        result = ingest_bytes(db, raw, filename=file.filename, source="upload", uploaded_by=actor)
    except IngestError as exc:
        raise HTTPException(422, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, f"could not parse dump: {exc}") from exc

    logger.info("upload ingested by %s: %s", actor, result)
    return result


class S3FetchRequest(BaseModel):
    bucket: str
    prefix: str = ""
    mode: str = "new"  # latest | all | new
    assume_role_arn: str | None = None
    region: str | None = None


@router.post("/s3-fetch", dependencies=[Depends(require_role(Role.OPERATOR))])
def s3_fetch(request: Request, body: S3FetchRequest, db: psycopg.Connection = Depends(get_db)) -> dict:
    """Lambda -> S3 -> Zoneguard ingest: fetches R53 dump object(s) under a prefix, one
    object per hosted zone, using the container's IAM role (no stored keys) unless an
    assume-role ARN is given for cross-account access."""
    if body.mode not in ("latest", "all", "new"):
        raise HTTPException(400, "mode must be one of latest|all|new")

    try:
        client = build_s3_client(assume_role_arn=body.assume_role_arn, region=body.region)
        objects = list_objects(client, body.bucket, body.prefix)
    except Exception as exc:  # noqa: BLE001 - surface any boto3/credentials error to the caller
        raise HTTPException(502, f"could not list s3://{body.bucket}/{body.prefix}: {exc}") from exc

    known_keys: set[str] = set()
    if body.mode == "new":
        known_keys = {
            row["s3_key"]
            for row in db.execute("SELECT DISTINCT s3_key FROM batches WHERE source = 's3' AND s3_key IS NOT NULL").fetchall()
        }
    selected = select_objects(objects, mode=body.mode, known_keys=known_keys)

    actor = getattr(request.state, "actor", None) or "anonymous"
    ingested = []
    for obj in selected:
        try:
            raw = fetch_object(client, body.bucket, obj.key)
            fmt = sniff_format(raw)
            parser = importlib.import_module(PARSERS[fmt])
            raw_records = parser.parse(raw)
            if len(raw_records) > settings.upload_max_rows:
                raise IngestError(f"{obj.key}: {len(raw_records)} rows exceeds the {settings.upload_max_rows}-row cap")

            batch_id = create_batch(db, filename=obj.key, fmt=fmt, source="s3", uploaded_by=actor)
            db.execute("UPDATE batches SET s3_key = %s WHERE id = %s", (obj.key, batch_id))
            try:
                result = load_batch(db, batch_id, normalize(raw_records), source="s3")
                ingested.append({"key": obj.key, **result})
            except Exception as exc:  # noqa: BLE001
                mark_batch_error(db, batch_id, str(exc))
                raise
        except Exception as exc:  # noqa: BLE001 - one bad object must not abort the rest of the fetch
            logger.error("s3 ingest failed for %s: %s", obj.key, exc)
            ingested.append({"key": obj.key, "error": str(exc)})

    return {"objects_found": len(objects), "objects_selected": len(selected), "results": ingested}


@router.get("")
def list_batches(request: Request, db: psycopg.Connection = Depends(get_db)) -> dict:
    params = parse_page_params(request, allowed_sort=_ALLOWED_SORT, default_sort="created_at")
    total = db.execute("SELECT count(*) AS n FROM batches").fetchone()["n"]
    rows = db.execute(
        f"""
        SELECT id, filename, format, source, s3_key, row_count, domain_count,
               uploaded_by, status, error, created_at
        FROM batches
        ORDER BY {params.sort_sql} {params.sort_dir}
        LIMIT %s OFFSET %s
        """,  # noqa: S608  # nosec B608 - sort_sql/sort_dir come from the fixed _ALLOWED_SORT allowlist only
        (params.limit, params.offset),
    ).fetchall()
    return paginated_response(rows, total, params)
