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

import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    TokenResponse,
    VerifyEmailRequest,
    UserPreferencesUpdateRequest,
    UserProfileResponse,
    ChangePasswordRequest,
)
from app.config import get_settings
from app.db import get_db_session
from app.models.user import User
from app.services.email import send_password_reset_email, send_verification_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# -- Password hashing (Direct bcrypt + SHA-256 pre-hashing) ------------------
# Pre-hashing with SHA-256 compresses arbitrary-length passwords into a 32-byte
# digest, completely avoiding bcrypt's 72-byte restriction while retaining full entropy.
def hash_password(password: str) -> str:
    """Hash password using SHA-256 pre-hashing + bcrypt."""
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(digest, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against bcrypt hash with SHA-256 and fallback for raw."""
    try:
        hashed_bytes = hashed_password.encode("utf-8")
        # 1. Primary check: SHA-256 pre-hash
        digest = hashlib.sha256(plain_password.encode("utf-8")).digest()
        if bcrypt.checkpw(digest, hashed_bytes):
            return True

        # 2. Backwards-compatibility fallback: raw password if <= 72 bytes
        raw_bytes = plain_password.encode("utf-8")
        if len(raw_bytes) <= 72 and bcrypt.checkpw(raw_bytes, hashed_bytes):
            return True
    except Exception:
        return False
    return False

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


def create_email_verification_token(user_id: uuid.UUID, email: str) -> str:
    """Sign a single-use JWT for email verification (24 hr expiry)."""
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.email_verification_expire_minutes)
    payload = {
        "sub": str(user_id),
        "email": email,
        "purpose": "email_verification",
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_password_reset_token(user: User) -> str:
    """Sign a single-use JWT for password reset (10 min expiry max).

    Incorporates a 16-character SHA-256 signature of the user's current hashed_password.
    Once the password changes, any previously issued token becomes immediately invalid.
    """
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.password_reset_expire_minutes)
    pwd_sig = hashlib.sha256(user.hashed_password.encode("utf-8")).hexdigest()[:16]
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "pwd_sig": pwd_sig,
        "purpose": "password_reset",
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
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    """Create a new user account, send confirmation email via Gmail SMTP, and return JWT."""
    existing = await session.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        is_verified=False,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    settings = get_settings()
    verify_token = create_email_verification_token(user.id, user.email)
    verify_url = f"{settings.frontend_url}/verify-email?token={verify_token}"
    background_tasks.add_task(send_verification_email, user.email, verify_url)

    token = create_access_token(user.id, user.email)
    logger.info("User registered (unverified): %s", user.email)

    return TokenResponse(
        access_token=token,
        user_id=str(user.id),
        email=user.email,
        is_verified=False,
        onboarded=user.onboarded,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    """Authenticate with email + password and receive a JWT."""
    result = await session.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email address before signing in.",
        )

    token = create_access_token(user.id, user.email)
    logger.info("User logged in: %s", user.email)

    return TokenResponse(
        access_token=token,
        user_id=str(user.id),
        email=user.email,
        is_verified=True,
        onboarded=user.onboarded,
    )


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(
    body: VerifyEmailRequest,
    session: AsyncSession = Depends(get_db_session),
) -> MessageResponse:
    """Verify a user's account using the token dispatched to their email."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            body.token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        if payload.get("purpose") != "email_verification":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid email verification token.",
            )
        user_id_str: str | None = payload.get("sub")
        if not user_id_str:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid email verification token.",
            )
        user_id = uuid.UUID(user_id_str)
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification link is invalid or has expired.",
        )

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account not found.",
        )

    if not user.is_verified:
        user.is_verified = True
        await session.flush()
        logger.info("User email successfully verified: %s", user.email)

    return MessageResponse(
        message="Your email address has been verified successfully. You may now sign in."
    )


@router.post("/resend-verification", response_model=MessageResponse)
async def resend_verification(
    body: ResendVerificationRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session),
) -> MessageResponse:
    """Resend verification email to an unverified user account."""
    result = await session.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user and not user.is_verified:
        settings = get_settings()
        verify_token = create_email_verification_token(user.id, user.email)
        verify_url = f"{settings.frontend_url}/verify-email?token={verify_token}"
        background_tasks.add_task(send_verification_email, user.email, verify_url)
        logger.info("Resent verification email for: %s", user.email)

    # Return constant message to prevent email enumeration
    return MessageResponse(
        message="If an unverified account exists with this email, a new confirmation link has been sent."
    )


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    body: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session),
) -> MessageResponse:
    """Request a password reset link. Dispatches email via Gmail SMTP (10 min expiry)."""
    result = await session.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user and user.is_verified:
        settings = get_settings()
        reset_token = create_password_reset_token(user)
        reset_url = f"{settings.frontend_url}/reset-password?token={reset_token}"
        background_tasks.add_task(send_password_reset_email, user.email, reset_url)
        logger.info("Dispatched password reset email for: %s", user.email)
    elif user and not user.is_verified:
        # Prompt user to verify account if they haven't verified yet
        logger.info("Forgot password requested for unverified user %s; dispatching verification email", user.email)
        settings = get_settings()
        verify_token = create_email_verification_token(user.id, user.email)
        verify_url = f"{settings.frontend_url}/verify-email?token={verify_token}"
        background_tasks.add_task(send_verification_email, user.email, verify_url)

    # Constant generic message to avoid email enumeration
    return MessageResponse(
        message="If an account exists with this email, instructions to reset your password have been sent."
    )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    body: ResetPasswordRequest,
    session: AsyncSession = Depends(get_db_session),
) -> MessageResponse:
    """Reset user password using single-use signed token (max 10 min expiry)."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            body.token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        if payload.get("purpose") != "password_reset":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid password reset token.",
            )
        user_id_str: str | None = payload.get("sub")
        pwd_sig: str | None = payload.get("pwd_sig")
        if not user_id_str or not pwd_sig:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid password reset token.",
            )
        user_id = uuid.UUID(user_id_str)
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password reset link is invalid or has expired (10-minute limit).",
        )

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account not found.",
        )

    # Single-use guarantee: verify token was created for the current password hash
    current_sig = hashlib.sha256(user.hashed_password.encode("utf-8")).hexdigest()[:16]
    if current_sig != pwd_sig:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password reset link has already been used or invalidated. Please request a new one.",
        )

    user.hashed_password = hash_password(body.new_password)
    user.is_verified = True  # Verified by virtue of email-token possession
    await session.flush()
    logger.info("Password successfully reset for: %s", user.email)

    return MessageResponse(
        message="Your password has been reset successfully. You may now sign in with your new password."
    )


@router.patch("/preferences", response_model=MessageResponse)
async def update_preferences(
    body: UserPreferencesUpdateRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> MessageResponse:
    """Update the user's onboarding preferences."""
    current_user.preferences = body.preferences.model_dump()
    current_user.onboarded = True
    await session.commit()
    logger.info("Preferences updated and onboarded for user: %s", current_user.email)
    
    return MessageResponse(
        message="Preferences saved successfully."
    )


@router.get("/me", response_model=UserProfileResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
) -> UserProfileResponse:
    """Get the current user's profile and preferences."""
    return UserProfileResponse(
        user_id=str(current_user.id),
        email=current_user.email,
        is_verified=current_user.is_verified,
        onboarded=current_user.onboarded,
        preferences=current_user.preferences,
    )


@router.put("/password", response_model=MessageResponse)
async def change_password(
    body: ChangePasswordRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> MessageResponse:
    """Change the current user's password."""
    # Verify current password
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect current password.",
        )
    
    # Save new password
    current_user.hashed_password = hash_password(body.new_password)
    await session.commit()
    logger.info("Password changed by user: %s", current_user.email)

    return MessageResponse(message="Password successfully updated.")


@router.delete("/me", response_model=MessageResponse)
async def delete_my_account(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> MessageResponse:
    """Permanently delete the user account and all associated data."""
    email = current_user.email
    await session.delete(current_user)
    await session.commit()
    logger.warning("Account deleted permanently: %s", email)

    return MessageResponse(message="Account successfully deleted.")

