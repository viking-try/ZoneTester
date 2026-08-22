from fastapi import APIRouter

from app.db.pool import get_conn

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    db_ok = True
    try:
        with get_conn() as conn:
            conn.execute("SELECT 1")
    except Exception:  # noqa: BLE001
        db_ok = False
    return {"status": "ok" if db_ok else "degraded", "database": db_ok}
