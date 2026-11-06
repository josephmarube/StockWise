"""FastAPI dependencies: JWT authentication and server-side role checks (NFR1, NFR2)."""
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import Role, User
from .security import decode_access_token

bearer = HTTPBearer(auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]


def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    db: DbSession,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    if creds is None or creds.scheme.lower() != "bearer":
        raise _unauthorized()
    try:
        payload = decode_access_token(creds.credentials)
        user_id = int(payload["sub"])
    except jwt.ExpiredSignatureError:
        raise _unauthorized("Session expired, please log in again")
    except (jwt.PyJWTError, KeyError, ValueError):
        raise _unauthorized("Invalid token")

    user = db.get(User, user_id)
    if user is None or not user.is_active or not user.business.is_active:
        raise _unauthorized("Account not found or disabled")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_admin(user: CurrentUser) -> User:
    # Role is read from the database, not the token, so a demoted user loses access immediately.
    if user.role != Role.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return user


AdminUser = Annotated[User, Depends(require_admin)]
