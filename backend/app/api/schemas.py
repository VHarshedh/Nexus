"""
NEXUS -- Pydantic Request / Response Schemas.

Defines every DTO used across the REST API.  Keeps validation logic
separate from ORM models and route handlers.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        """Enforce password rules:
        - Any number of characters allowed (no arbitrary length limits).
        - Must include alphanumeric characters (both letters and numbers) and at least one symbol.
        """
        if not v or not v.strip():
            raise ValueError("Password cannot be empty.")
        if not any(c.isalpha() for c in v):
            raise ValueError("Password must include at least one letter.")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must include at least one number.")
        if not any(not c.isalnum() and not c.isspace() for c in v):
            raise ValueError("Password must include at least one symbol (e.g. !@#$%^&*).")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str


# ---------------------------------------------------------------------------
# Resume
# ---------------------------------------------------------------------------
class ResumeResponse(BaseModel):
    id: uuid.UUID
    raw_text: str
    file_path: str | None
    uploaded_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Matches
# ---------------------------------------------------------------------------
class MatchListingDetail(BaseModel):
    """Embedded listing snapshot inside a match response."""
    id: uuid.UUID
    title: str | None
    company: str | None
    location: str | None
    remote_ok: bool
    stipend: str | None
    required_skills: list[str] | None
    experience_level: str | None
    deadline: str | None
    source_url: str

    model_config = {"from_attributes": True}


class MatchResponse(BaseModel):
    id: uuid.UUID
    listing_id: uuid.UUID
    match_score: float
    justification: str | None
    saved: bool
    status: str
    created_at: datetime
    listing: MatchListingDetail | None = None

    model_config = {"from_attributes": True}


class MatchComputeResponse(BaseModel):
    computed: int
    matches: list[MatchResponse]


# ---------------------------------------------------------------------------
# Briefing
# ---------------------------------------------------------------------------
class BriefingJobResponse(BaseModel):
    id: uuid.UUID
    status: str
    script: str | None
    media_url: str | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class BriefingCreateResponse(BaseModel):
    job_id: uuid.UUID
    status: str
    message: str


# ---------------------------------------------------------------------------
# Agent Chat
# ---------------------------------------------------------------------------
class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class AgentChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(default_factory=list)
    message: str


class AgentChatResponse(BaseModel):
    reply: str
    tool_calls_made: list[str] = Field(default_factory=list)
