"""
NEXUS — Cost & Token Usage Tracking Service.

Tracks LLM token consumption and expenditure in Indian Rupees (₹) and USD.
Prices based on Gemini 3.5 Flash Lite ($0.15/1M input, $1.25/1M output)
and Gemini Embeddings ($0.025/1M tokens) with USD/INR rate = 86.50.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import Date, cast, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.token_usage import TokenUsage

logger = logging.getLogger(__name__)

# Currency conversion
USD_TO_INR_RATE = 86.50

# Pricing per 1,000,000 tokens in USD
MODEL_PRICING: dict[str, dict[str, float]] = {
    # Gemini 3.5 Flash Lite default
    "gemini-3.5-flash-lite": {
        "input_per_1m": 0.15,
        "output_per_1m": 1.25,
    },
    "gemini-2.5-flash": {
        "input_per_1m": 0.15,
        "output_per_1m": 1.25,
    },
    "gemini-1.5-flash": {
        "input_per_1m": 0.15,
        "output_per_1m": 1.25,
    },
    # Embedding model
    "gemini-embedding-2": {
        "input_per_1m": 0.025,
        "output_per_1m": 0.0,
    },
    "text-embedding-004": {
        "input_per_1m": 0.025,
        "output_per_1m": 0.0,
    },
}

DEFAULT_PRICING = {
    "input_per_1m": 0.15,
    "output_per_1m": 1.25,
}

FEATURE_LABELS: dict[str, str] = {
    "career_agent": "AI Career Agent",
    "resume_parsing": "Resume Extraction & Skills",
    "match_justifications": "Match Justifications",
    "video_briefing": "Video & Audio Briefings",
    "job_extraction": "Job Listing Extraction",
    "embeddings": "Vector Embeddings",
}


def calculate_token_cost(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> tuple[float, float]:
    """Calculate (cost_usd, cost_inr) based on token counts and model pricing."""
    pricing = MODEL_PRICING.get(model, DEFAULT_PRICING)
    input_rate = pricing["input_per_1m"] / 1_000_000.0
    output_rate = pricing["output_per_1m"] / 1_000_000.0

    cost_usd = (prompt_tokens * input_rate) + (completion_tokens * output_rate)
    cost_inr = cost_usd * USD_TO_INR_RATE

    return round(cost_usd, 6), round(cost_inr, 4)


async def record_token_usage(
    session: AsyncSession,
    user_id: uuid.UUID | None,
    feature: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    meta: dict[str, Any] | None = None,
) -> TokenUsage | None:
    """Record a token consumption entry in the database.
    
    Guaranteed not to raise exceptions that interrupt caller business logic.
    """
    try:
        total_tokens = prompt_tokens + completion_tokens
        cost_usd, cost_inr = calculate_token_cost(model, prompt_tokens, completion_tokens)

        record = TokenUsage(
            user_id=user_id,
            feature=feature,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
            cost_inr=cost_inr,
            meta=meta,
        )
        session.add(record)
        await session.flush()
        logger.debug(
            "[cost_tracker] Recorded %s for user=%s: %d tokens, ₹%.4f",
            feature, user_id, total_tokens, cost_inr
        )
        return record
    except Exception as exc:
        logger.error("[cost_tracker] Failed to record token usage: %s", exc)
        return None


async def get_cost_summary(
    session: AsyncSession,
    user_id: uuid.UUID,
    days: int = 30,
) -> dict[str, Any]:
    """Fetch aggregated cost intelligence for the given user."""
    now = datetime.now(timezone.utc)
    start_of_today = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    start_of_week = start_of_today - timedelta(days=now.weekday())
    cutoff_date = now - timedelta(days=days)

    # 1. Overall Aggregates for user
    overall_stmt = select(
        func.coalesce(func.sum(TokenUsage.total_tokens), 0),
        func.coalesce(func.sum(TokenUsage.cost_inr), 0.0),
        func.coalesce(func.sum(TokenUsage.cost_usd), 0.0),
        func.count(TokenUsage.id),
    ).where(TokenUsage.user_id == user_id)
    
    overall_res = (await session.execute(overall_stmt)).one()
    total_tokens = int(overall_res[0])
    total_cost_inr = float(overall_res[1])
    total_cost_usd = float(overall_res[2])
    total_calls = int(overall_res[3])

    # 2. Today's Aggregates
    today_stmt = select(
        func.coalesce(func.sum(TokenUsage.total_tokens), 0),
        func.coalesce(func.sum(TokenUsage.cost_inr), 0.0),
    ).where(TokenUsage.user_id == user_id, TokenUsage.created_at >= start_of_today)
    
    today_res = (await session.execute(today_stmt)).one()
    today_tokens = int(today_res[0])
    today_cost_inr = float(today_res[1])

    # 3. This Week's Aggregates
    week_stmt = select(
        func.coalesce(func.sum(TokenUsage.total_tokens), 0),
        func.coalesce(func.sum(TokenUsage.cost_inr), 0.0),
    ).where(TokenUsage.user_id == user_id, TokenUsage.created_at >= start_of_week)
    
    week_res = (await session.execute(week_stmt)).one()
    week_tokens = int(week_res[0])
    week_cost_inr = float(week_res[1])

    # 4. Feature Breakdown
    feature_stmt = select(
        TokenUsage.feature,
        func.coalesce(func.sum(TokenUsage.total_tokens), 0).label("tokens"),
        func.coalesce(func.sum(TokenUsage.cost_inr), 0.0).label("cost_inr"),
        func.coalesce(func.sum(TokenUsage.cost_usd), 0.0).label("cost_usd"),
        func.count(TokenUsage.id).label("call_count"),
    ).where(
        TokenUsage.user_id == user_id
    ).group_by(TokenUsage.feature).order_by(desc("cost_inr"))

    feature_rows = (await session.execute(feature_stmt)).all()
    feature_breakdown = []
    for row in feature_rows:
        feat_name = str(row[0])
        feat_tokens = int(row[1])
        feat_inr = float(row[2])
        feat_usd = float(row[3])
        feat_calls = int(row[4])
        percentage = round((feat_inr / total_cost_inr * 100.0) if total_cost_inr > 0 else 0.0, 1)

        feature_breakdown.append({
            "feature": feat_name,
            "label": FEATURE_LABELS.get(feat_name, feat_name.replace("_", " ").title()),
            "tokens": feat_tokens,
            "cost_inr": round(feat_inr, 4),
            "cost_usd": round(feat_usd, 6),
            "call_count": feat_calls,
            "percentage": percentage,
        })

    # 5. Daily Spending Trends (past 14 days)
    day_col = cast(TokenUsage.created_at, Date)
    daily_stmt = select(
        day_col.label("day"),
        func.coalesce(func.sum(TokenUsage.total_tokens), 0),
        func.coalesce(func.sum(TokenUsage.cost_inr), 0.0),
        func.coalesce(func.sum(TokenUsage.cost_usd), 0.0),
    ).where(
        TokenUsage.user_id == user_id,
        TokenUsage.created_at >= (now - timedelta(days=14)),
    ).group_by(day_col).order_by(day_col)

    daily_rows = (await session.execute(daily_stmt)).all()
    daily_map = {
        (row[0].strftime("%Y-%m-%d") if hasattr(row[0], "strftime") else str(row[0])): (
            int(row[1]), float(row[2]), float(row[3])
        )
        for row in daily_rows if row[0]
    }

    daily_trends = []
    for i in range(13, -1, -1):
        day_date = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        d_tokens, d_inr, d_usd = daily_map.get(day_date, (0, 0.0, 0.0))
        daily_trends.append({
            "date": day_date,
            "tokens": d_tokens,
            "cost_inr": round(d_inr, 4),
            "cost_usd": round(d_usd, 6),
        })

    # 6. Recent Logs (last 30)
    recent_stmt = select(TokenUsage).where(
        TokenUsage.user_id == user_id
    ).order_by(TokenUsage.created_at.desc()).limit(30)

    recent_rows = (await session.execute(recent_stmt)).scalars().all()
    recent_logs = [
        {
            "id": str(r.id),
            "feature": r.feature,
            "label": FEATURE_LABELS.get(r.feature, r.feature.replace("_", " ").title()),
            "model": r.model,
            "prompt_tokens": r.prompt_tokens,
            "completion_tokens": r.completion_tokens,
            "total_tokens": r.total_tokens,
            "cost_inr": round(r.cost_inr, 4),
            "cost_usd": round(r.cost_usd, 6),
            "created_at": r.created_at.isoformat(),
        }
        for r in recent_rows
    ]

    return {
        "total_tokens": total_tokens,
        "total_cost_inr": round(total_cost_inr, 4),
        "total_cost_usd": round(total_cost_usd, 6),
        "total_calls": total_calls,
        "today_tokens": today_tokens,
        "today_cost_inr": round(today_cost_inr, 4),
        "this_week_tokens": week_tokens,
        "this_week_cost_inr": round(week_cost_inr, 4),
        "feature_breakdown": feature_breakdown,
        "daily_trends": daily_trends,
        "recent_logs": recent_logs,
    }
