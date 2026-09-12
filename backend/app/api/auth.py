"""
NEXUS -- Authentication & JWT Token Management.

Provides:
- ``POST /api/auth/register`` -- create a new user account.
- ``POST /api/auth/login``    -- authenticate and receive a JWT.
- ``get_current_user``        -- FastAPI dependency that decodes a JWT
  Bearer token and returns the authenticated ``User`` ORM instance.

Multi-Tenant Isolation
----------------------
Every downstream route receives ``current_user: User`` via ``Depends``.
All queries on user-owned resources (Resume, UserListingMatch, BriefingJob)
MUST filter by ``user_id == current_user.id``.  There is no route parameter
that allows overriding the user identity.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import LoginRequest, RegisterRequest, TokenResponse
from app.config import get_settings
from app.db import get_db_session
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# -- Password hashing --------------------------------------------------------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# -- OAuth2 scheme (tells Swagger UI where to send the token) -----------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------
def create_access_token(user_id: uuid.UUID, email: str) -> str:
    """Sign a JWT containing the user's ID and email."""
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


# ---------------------------------------------------------------------------
# FastAPI dependency: decode JWT -> load User from DB
# ---------------------------------------------------------------------------
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    """Decode the Bearer token and return the authenticated User.

    Raises ``HTTPException(401)`` if the token is invalid, expired, or
    the user no longer exists in the database.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    settings = get_settings()

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id_str: str | None = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
        user_id = uuid.UUID(user_id_str)
    except (JWTError, ValueError):
        raise credentials_exception

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception

    return user


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    session: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    """Create a new user account and return a JWT."""
    # Check for existing email
    existing = await session.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = User(
        email=body.email,
        hashed_password=pwd_context.hash(body.password),
    )
    session.add(user)
    await session.flush()  # populate user.id before commit

    token = create_access_token(user.id, user.email)
    logger.info("User registered: %s", user.email)

    return TokenResponse(
        access_token=token,
        user_id=str(user.id),
        email=user.email,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    """Authenticate with email + password and receive a JWT."""
    result = await session.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user is None or not pwd_context.verify(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    token = create_access_token(user.id, user.email)
    logger.info("User logged in: %s", user.email)

    return TokenResponse(
        access_token=token,
        user_id=str(user.id),
        email=user.email,
    )
