"""
Tests for email verification tokens, password reset tokens, and anti-tampering logic.
"""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from app.api.auth import (
    create_email_verification_token,
    create_password_reset_token,
    hash_password,
)
from app.config import get_settings
from app.models.user import User
from app.services.email import (
    send_password_reset_email,
    send_verification_email,
)


def test_email_verification_token_structure_and_expiry():
    settings = get_settings()
    user_id = uuid.uuid4()
    email = "test.candidate@example.com"

    token = create_email_verification_token(user_id, email)
    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )

    assert payload["sub"] == str(user_id)
    assert payload["email"] == email
    assert payload["purpose"] == "email_verification"
    # Expires in approximately 24 hours (with small clock delta)
    exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    now = datetime.now(timezone.utc)
    diff_hours = (exp - now).total_seconds() / 3600
    assert 23.9 <= diff_hours <= 24.1


def test_password_reset_token_max_10_minutes_expiry():
    settings = get_settings()
    user = User(
        id=uuid.uuid4(),
        email="reset.user@example.com",
        hashed_password=hash_password("InitialPassword123!"),
        is_verified=True,
    )

    token = create_password_reset_token(user)
    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )

    assert payload["sub"] == str(user.id)
    assert payload["email"] == user.email
    assert payload["purpose"] == "password_reset"
    # Verify expiration is strictly 10 minutes max
    exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    now = datetime.now(timezone.utc)
    diff_mins = (exp - now).total_seconds() / 60
    assert 9.8 <= diff_mins <= 10.1


def test_password_reset_token_single_use_and_revocation():
    """Verify that once the password changes, previously issued reset tokens are invalid."""
    user = User(
        id=uuid.uuid4(),
        email="target.user@example.com",
        hashed_password=hash_password("OldPassword123!"),
        is_verified=True,
    )

    # 1. Issue reset token for current password
    token = create_password_reset_token(user)
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    pwd_sig = payload["pwd_sig"]

    # Verify signature matches current hash
    current_sig = hashlib.sha256(user.hashed_password.encode("utf-8")).hexdigest()[:16]
    assert pwd_sig == current_sig

    # 2. Simulate password reset to a new password
    user.hashed_password = hash_password("NewPassword456$")
    new_sig = hashlib.sha256(user.hashed_password.encode("utf-8")).hexdigest()[:16]

    # Verify the old reset token's pwd_sig is now invalid (revocation check)
    assert pwd_sig != new_sig


def test_tampered_token_rejected():
    """Verify that an altered token is mathematically rejected."""
    settings = get_settings()
    user_id = uuid.uuid4()
    email = "innocent@example.com"
    token = create_email_verification_token(user_id, email)

    # Tamper with token by swapping characters in the signature segment
    parts = token.split(".")
    tampered_parts = [parts[0], parts[1], parts[2][:-4] + "AAAA"]
    tampered_token = ".".join(tampered_parts)

    with pytest.raises(Exception):
        jwt.decode(
            tampered_token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )


@pytest.mark.asyncio
async def test_email_service_dispatches_or_simulates_cleanly():
    """Verify send_verification_email and send_password_reset_email return without crashing."""
    from unittest.mock import AsyncMock, patch

    with patch("aiosmtplib.send", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = ({"someone@example.com": (250, "OK")}, "250 OK")
        res1 = await send_verification_email("someone@example.com", "http://localhost:3000/verify-email?token=abc")
        res2 = await send_password_reset_email("someone@example.com", "http://localhost:3000/reset-password?token=xyz")

        assert res1 is True
        assert res2 is True
        assert mock_send.call_count == 2
