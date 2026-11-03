"""Password hashing (NFR1) and JWT issuing/verification (FR4.1)."""
import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from .config import get_settings


def hash_password(password: str) -> str:
    # bcrypt generates and embeds a per-password salt.
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=int(os.getenv("BCRYPT_ROUNDS", "12")))).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


# Used to keep login timing similar whether or not the email exists.
_DUMMY_HASH = hash_password("timing-equaliser")


def dummy_verify() -> None:
    verify_password("x", _DUMMY_HASH)


def create_access_token(user_id: int, role: str) -> tuple[str, int]:
    s = get_settings()
    expires_in = s.jwt_expire_minutes * 60
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm), expires_in


def decode_access_token(token: str) -> dict:
    s = get_settings()
    return jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
