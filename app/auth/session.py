"""Signed, timed session tokens (itsdangerous) carried in an httpOnly cookie. Not a JWT —
there's no third party ever verifying this token, so a simpler signed-and-timestamped blob is
the right tool: smaller, no algorithm-confusion surface, and expiry is enforced server-side
by the same secret that signed it."""
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import settings

_serializer = URLSafeTimedSerializer(settings.app_secret_key, salt="zoneguard-session")


def create_session_token(payload: dict) -> str:
    return _serializer.dumps(payload)


def verify_session_token(token: str) -> dict | None:
    try:
        return _serializer.loads(token, max_age=settings.session_ttl_seconds)
    except (BadSignature, SignatureExpired):
        return None
