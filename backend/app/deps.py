"""FastAPI dependencies: JWT authentication and server-side role checks (NFR1, NFR2)."""
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import BUSINESS_ROLES, Role, User
from .security import decode_access_token

bearer = HTTPBearer(auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]


def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_signed_in_user(
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
    if user is None or not user.is_active or (user.business is not None and not user.business.is_active):
        raise _unauthorized("Account not found or disabled")
    return user


# Any signed-in account, including a System Admin (used by /api/auth/me).
SignedInUser = Annotated[User, Depends(get_signed_in_user)]


def get_current_user(user: SignedInUser) -> User:
    """A Manager or Staff member of a business. System Admins can't use shop endpoints:
    they see business metadata through /api/platform only."""
    if user.role not in BUSINESS_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This is for shop accounts only")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_manager(user: CurrentUser) -> User:
    # Role is read from the database, not the token, so a demoted user loses access immediately.
    if user.role != Role.MANAGER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Manager role required")
    return user


ManagerUser = Annotated[User, Depends(require_manager)]


def require_system_admin(user: SignedInUser) -> User:
    if user.role != Role.SYSTEM_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="System Admin role required")
    return user


SystemAdminUser = Annotated[User, Depends(require_system_admin)]
