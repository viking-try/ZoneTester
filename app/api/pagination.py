"""The one reusable server-side pagination contract every list endpoint uses. Sort columns
are never string-interpolated from user input directly — each endpoint passes an
`allowed_sort` dict mapping public sort keys to literal, developer-controlled SQL column
expressions; an unrecognized key is a 400, not a SQL-injection surface."""
from dataclasses import dataclass

from fastapi import HTTPException, Request

DEFAULT_LIMIT = 50
MAX_LIMIT = 500


@dataclass(slots=True)
class PageParams:
    limit: int
    offset: int
    sort_by: str
    sort_dir: str
    sort_sql: str  # the literal SQL column expression resolved from allowed_sort[sort_by]


def parse_page_params(
    request: Request, *, allowed_sort: dict[str, str], default_sort: str
) -> PageParams:
    q = request.query_params
    try:
        limit = int(q.get("limit", DEFAULT_LIMIT))
        offset = int(q.get("offset", 0))
    except ValueError:
        raise HTTPException(400, "limit/offset must be integers")

    if limit <= 0 or limit > MAX_LIMIT:
        raise HTTPException(400, f"limit must be between 1 and {MAX_LIMIT}")
    if offset < 0:
        raise HTTPException(400, "offset must be >= 0")

    sort_by = q.get("sort_by", default_sort)
    if sort_by not in allowed_sort:
        raise HTTPException(400, f"unknown sort_by {sort_by!r}; allowed: {sorted(allowed_sort)}")

    sort_dir = q.get("sort_dir", "asc").lower()
    if sort_dir not in ("asc", "desc"):
        raise HTTPException(400, "sort_dir must be 'asc' or 'desc'")

    return PageParams(
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_dir=sort_dir,
        sort_sql=allowed_sort[sort_by],
    )


def paginated_response(rows: list[dict], total: int, params: PageParams) -> dict:
    return {
        "rows": rows,
        "total": total,
        "limit": params.limit,
        "offset": params.offset,
        "sort_by": params.sort_by,
        "sort_dir": params.sort_dir,
    }
