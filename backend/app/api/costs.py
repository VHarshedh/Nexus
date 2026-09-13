"""
NEXUS — Cost Intelligence & Token Analytics API Router.

Provides endpoints to monitor token consumption and financial expenditure
in Indian Rupees (₹) and USD across all AI features.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.api.schemas import CostSummaryResponse
from app.db import get_db_session
from app.models.user import User
from app.services.cost_tracker import get_cost_summary

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/costs", tags=["costs"])


@router.get("/summary", response_model=CostSummaryResponse)
async def get_user_costs(
    days: int = Query(default=30, ge=1, le=90, description="Time window in days"),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> CostSummaryResponse:
    """Retrieve token usage analytics and spend metrics in INR and USD.
    
    Strictly isolated to the authenticated user's account.
    """
    summary_data = await get_cost_summary(
        session=session,
        user_id=current_user.id,
        days=days,
    )
    return CostSummaryResponse.model_validate(summary_data)
