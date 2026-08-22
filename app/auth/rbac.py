from app.constants import Role


def user_has_role(user: dict | None, required: str) -> bool:
    if user is None:
        return False
    return Role.at_least(user.get("role", Role.VIEWER), required)
