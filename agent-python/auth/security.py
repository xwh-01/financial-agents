from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import settings


DEV_JWT_SECRET = "dev-only-change-me"
JWT_ALGORITHM = "HS256"
DEV_ENVIRONMENTS = {"dev", "development", "local", "test", "testing"}


class TokenError(Exception):
    pass


def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    password_bytes = password.encode("utf-8")
    hash_bytes = password_hash.encode("utf-8")
    return bcrypt.checkpw(password_bytes, hash_bytes)


def create_access_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": user_id,
        "iat": now,
        "exp": now + timedelta(days=settings.token_expire_days),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("Access token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("Invalid access token") from exc


def validate_security_settings() -> None:
    env = settings.environment.strip().lower()
    if env not in DEV_ENVIRONMENTS and _jwt_secret() == DEV_JWT_SECRET:
        raise RuntimeError("JWT_SECRET must be configured outside development.")


def _jwt_secret() -> str:
    return settings.jwt_secret.strip() or DEV_JWT_SECRET
