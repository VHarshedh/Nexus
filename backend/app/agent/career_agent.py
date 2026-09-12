"""
NEXUS -- Career Intelligence Agent (Gemini Function Calling).

Implements a multi-turn agent loop using Gemini's native function-calling
capability.  The agent has access to three tools (defined in
``agent/tools.py``) and loops until Gemini returns a final text response
with no further tool calls.

Key Design Decisions
--------------------
- We do NOT dump the entire database into the prompt.  Instead, Gemini
  decides which tool to call based on the user's question, and the tool
  fetches only the relevant data.
- Tool declarations are defined as ``google.genai.types.FunctionDeclaration``
  objects so Gemini can invoke them with structured arguments.
- The loop has a safety cap of 10 iterations to prevent infinite loops.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from google import genai
from google.genai import types
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.tools import (
    tool_get_deadline_alerts,
    tool_get_top_skills_breakdown,
    tool_query_saved_listings,
)
from app.config import get_settings

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 10

# ---------------------------------------------------------------------------
# System Prompt
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = """\
You are NEXUS, an autonomous career intelligence agent.  You help users
understand their job market position by analysing their matched job listings.

You have access to three tools:
1. query_saved_listings -- search the user's matched/saved jobs with optional
   filters for remote work and deadline cutoff.
2. get_top_skills_breakdown -- see which skills are most in-demand across
   the user's matched jobs.
3. get_deadline_alerts -- find jobs whose application deadlines are expiring
   soon.

Always call a tool when you need data.  Never fabricate job listings or
statistics.  Be concise and actionable in your responses.
"""

# ---------------------------------------------------------------------------
# Tool Declarations (Gemini function-calling schema)
# ---------------------------------------------------------------------------
_TOOL_DECLARATIONS = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="query_saved_listings",
            description=(
                "Query the user's saved or matched job listings. "
                "Optionally filter by remote-friendliness or a maximum "
                "deadline date."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "filter_remote": types.Schema(
                        type=types.Type.BOOLEAN,
                        description="If true, only remote jobs. If false, only non-remote. Omit for all.",
                        nullable=True,
                    ),
                    "max_deadline": types.Schema(
                        type=types.Type.STRING,
                        description="ISO date string (e.g. '2026-10-01'). Only return listings with deadline on or before this date.",
                        nullable=True,
                    ),
                },
            ),
        ),
        types.FunctionDeclaration(
            name="get_top_skills_breakdown",
            description=(
                "Aggregate and count the most frequently required skills "
                "across the user's matched job listings."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={},
            ),
        ),
        types.FunctionDeclaration(
            name="get_deadline_alerts",
            description=(
                "Find matched jobs whose application deadlines expire "
                "within a given number of days from today."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "days_ahead": types.Schema(
                        type=types.Type.INTEGER,
                        description="Number of days to look ahead (default 7).",
                        nullable=True,
                    ),
                },
            ),
        ),
    ]
)


# ---------------------------------------------------------------------------
# Tool Dispatcher
# ---------------------------------------------------------------------------
async def _dispatch_tool(
    name: str,
    args: dict[str, Any],
    user_id: uuid.UUID,
    session: AsyncSession,
) -> dict[str, Any]:
    """Execute the named tool and return its result dict."""
    logger.info("[agent] Calling tool: %s(%s)", name, args)

    if name == "query_saved_listings":
        return await tool_query_saved_listings(
            user_id,
            session,
            filter_remote=args.get("filter_remote"),
            max_deadline=args.get("max_deadline"),
        )
    elif name == "get_top_skills_breakdown":
        return await tool_get_top_skills_breakdown(user_id, session)
    elif name == "get_deadline_alerts":
        days = args.get("days_ahead", 7)
        return await tool_get_deadline_alerts(
            user_id, session, days_ahead=int(days) if days else 7
        )
    else:
        return {"error": f"Unknown tool: {name}"}


# ---------------------------------------------------------------------------
# Agent Loop
# ---------------------------------------------------------------------------
async def run_agent_turn(
    user_id: uuid.UUID,
    chat_history: list[dict[str, str]],
    user_message: str,
    session: AsyncSession,
) -> tuple[str, list[str]]:
    """Run one full agent turn (may involve multiple tool calls).

    Parameters
    ----------
    user_id : uuid.UUID
        Authenticated user (for multi-tenant tool queries).
    chat_history : list[dict]
        Previous messages: ``[{"role": "user"|"assistant", "content": "..."}]``
    user_message : str
        The new user message.
    session : AsyncSession
        Active database session.

    Returns
    -------
    tuple[str, list[str]]
        ``(final_text_reply, list_of_tool_names_called)``
    """
    settings = get_settings()
    client = genai.Client(api_key=settings.gemini_api_key)

    # Build the contents array from history + new message
    contents: list[types.Content] = []

    for msg in chat_history:
        contents.append(
            types.Content(
                role="user" if msg["role"] == "user" else "model",
                parts=[types.Part.from_text(msg["content"])],
            )
        )

    # Add the new user message
    contents.append(
        types.Content(
            role="user",
            parts=[types.Part.from_text(user_message)],
        )
    )

    tools_called: list[str] = []

    for round_num in range(1, MAX_TOOL_ROUNDS + 1):
        logger.debug("[agent] Round %d, sending %d content parts", round_num, len(contents))

        response = await client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_PROMPT,
                temperature=0.4,
                tools=[_TOOL_DECLARATIONS],
            ),
        )

        # Check if the response has function calls
        candidate = response.candidates[0] if response.candidates else None
        if candidate is None:
            return "I'm sorry, I couldn't generate a response.", tools_called

        parts = candidate.content.parts if candidate.content else []

        # Collect all function calls in this response
        function_calls = [p for p in parts if p.function_call]

        if not function_calls:
            # No tool calls -- this is the final text response
            text_parts = [p.text for p in parts if p.text]
            final_text = "\n".join(text_parts).strip()
            if not final_text:
                final_text = "I don't have enough information to answer that. Try uploading a resume and computing matches first."
            return final_text, tools_called

        # Process each function call
        # First, add the model's response (with function_call parts) to contents
        contents.append(candidate.content)

        for fc_part in function_calls:
            fc = fc_part.function_call
            tool_name = fc.name
            tool_args = dict(fc.args) if fc.args else {}
            tools_called.append(tool_name)

            # Execute the tool
            try:
                tool_result = await _dispatch_tool(tool_name, tool_args, user_id, session)
            except Exception as exc:
                logger.error("[agent] Tool %s failed: %s", tool_name, exc)
                tool_result = {"error": str(exc)}

            # Add the function response back to contents
            contents.append(
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_function_response(
                            name=tool_name,
                            response=tool_result,
                        )
                    ],
                )
            )

    # Safety: max rounds exceeded
    logger.warning("[agent] Max tool rounds (%d) exceeded.", MAX_TOOL_ROUNDS)
    return (
        "I called several tools but couldn't fully resolve your question. "
        "Could you try rephrasing?",
        tools_called,
    )
