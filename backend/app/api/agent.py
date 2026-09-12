"""
NEXUS -- Agent Chat API.

Endpoint:
- ``POST /api/agent/chat`` -- send a message to the career intelligence agent.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.career_agent import run_agent_turn
from app.api.auth import get_current_user
from app.api.schemas import AgentChatRequest, AgentChatResponse
from app.db import get_db_session
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.post("/chat", response_model=AgentChatResponse)
async def agent_chat(
    body: AgentChatRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> AgentChatResponse:
    """Send a message to the NEXUS career intelligence agent.

    The agent may call one or more tools (query_saved_listings,
    get_top_skills_breakdown, get_deadline_alerts) to answer the
    user's question.  The tool-calling loop resolves automatically
    before the final conversational answer is returned.
    """
    history = [
        {"role": msg.role, "content": msg.content}
        for msg in body.messages
    ]

    reply, tools_called = await run_agent_turn(
        user_id=current_user.id,
        chat_history=history,
        user_message=body.message,
        session=session,
    )

    logger.info(
        "[agent] user=%s tools=%s reply_len=%d",
        current_user.email,
        tools_called,
        len(reply),
    )

    return AgentChatResponse(reply=reply, tool_calls_made=tools_called)
