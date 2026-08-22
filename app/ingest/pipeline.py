"""Glues detect -> parse -> normalize -> load into one call used by both the upload endpoint
and the S3 connector's ingest task."""
import importlib
import logging

import psycopg

from app.config import settings
from app.ingest.detect import sniff_format
from app.ingest.loader import PARSERS, create_batch, load_batch, mark_batch_error
from app.ingest.normalize import normalize

logger = logging.getLogger(__name__)


class IngestError(ValueError):
    pass


def ingest_bytes(
    conn: psycopg.Connection,
    raw: bytes,
    *,
    filename: str | None,
    source: str = "upload",
    uploaded_by: str | None = None,
    forced_format: str | None = None,
) -> dict:
    fmt = forced_format or sniff_format(raw)
    parser_module = importlib.import_module(PARSERS[fmt])
    raw_records = parser_module.parse(raw)

    if len(raw_records) > settings.upload_max_rows:
        raise IngestError(
            f"dump has {len(raw_records)} rows, exceeds the {settings.upload_max_rows}-row cap"
        )

    batch_id = create_batch(conn, filename=filename, fmt=fmt, source=source, uploaded_by=uploaded_by)
    try:
        normalized = normalize(raw_records)
        result = load_batch(conn, batch_id, normalized, source=source)
        result["format"] = fmt
        return result
    except Exception as exc:
        mark_batch_error(conn, batch_id, str(exc))
        raise
