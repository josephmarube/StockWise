"""FR4.1 login, and self-service signup that creates a new business."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select

from ..deps import CurrentUser, DbSession
from ..models import Business, Role, User
from ..ratelimit import limit
from ..schemas import LoginRequest, MeOut, SignupRequest, TokenResponse
from ..security import create_access_token, dummy_verify, hash_password, verify_password
from .users import EMAIL_TAKEN, email_taken

router = APIRouter(prefix="/api/auth", tags=["auth"])

GENERIC_LOGIN_ERROR = "Invalid email or password"


def issue_token(user: User) -> TokenResponse:
    token, expires_in = create_access_token(user.id, user.role.value)
    return TokenResponse(access_token=token, expires_in=expires_in, user=MeOut.model_validate(user))


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(limit("login", 20, 300))])
def login(body: LoginRequest, db: DbSession):
    user = db.execute(
        select(User).where(func.lower(User.email) == body.email.lower())
    ).scalar_one_or_none()

    if user is None:
        dummy_verify()  # keep response time similar for unknown emails
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, GENERIC_LOGIN_ERROR)
    if (
        not verify_password(body.password, user.password_hash)
        or not user.is_active
        or not user.business.is_active
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, GENERIC_LOGIN_ERROR)
    return issue_token(user)


@router.post(
    "/signup",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(limit("signup", 5, 3600))],
)
def signup(body: SignupRequest, db: DbSession):
    """Create a new business with the person signing up as its first admin, and log them in."""
    email = body.email.lower()
    if email_taken(db, email):
        raise HTTPException(status.HTTP_409_CONFLICT, EMAIL_TAKEN)
    business = Business(name=body.business_name)
    user = User(
        business=business,
        name=body.name,
        email=email,
        password_hash=hash_password(body.password),
        role=Role.ADMIN,
    )
    db.add_all([business, user])
    db.commit()
    db.refresh(user)
    return issue_token(user)


@router.get("/me", response_model=MeOut)
def me(user: CurrentUser):
    return user
