"""
NEXUS — System Status, Live Command Center & Backend Frontend Interface.

Serves:
- ``GET /``: A responsive dark-mode Command Center dashboard that displays
  real-time backend metrics, scraper source breakdowns, database health, and
  an interactive live job listings explorer.
- ``GET /api/stats``: JSON telemetry endpoint reporting real-time database
  counts, source breakdowns, and recently ingested opportunities.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.briefing_job import BriefingJob
from app.models.job_listing import JobListing
from app.models.resume import Resume
from app.models.user import User
from app.models.user_listing_match import UserListingMatch

router = APIRouter(tags=["system"])

EXCHANGE_RATES_TO_USD: dict[str, float] = {
    "usd": 1.0,
    "$": 1.0,
    "inr": 1.0 / 85.0,
    "₹": 1.0 / 85.0,
    "rs": 1.0 / 85.0,
    "rupee": 1.0 / 85.0,
    "rupees": 1.0 / 85.0,
    "eur": 1.08,
    "€": 1.08,
    "gbp": 1.28,
    "£": 1.28,
    "cad": 0.74,
    "c$": 0.74,
    "aud": 0.66,
    "a$": 0.66,
    "chf": 1.12,
    "jpy": 1.0 / 150.0,
    "¥": 1.0 / 150.0,
}


def parse_stipend_to_usd(text: str | None) -> float | None:
    """Parse a stipend/salary string into its highest value normalized to USD."""
    if not text:
        return None
    raw = text.strip()
    if not raw or raw.lower() in ("not specified", "unlisted", "competitive", "undisclosed"):
        return None

    cleaned = raw.lower().replace(",", "")

    # 1. Determine currency rate
    rate = 1.0
    if any(sym in cleaned for sym in ("inr", "₹", "rs", "rupee", "rupees", "lpa", "lakh")):
        rate = EXCHANGE_RATES_TO_USD["inr"]
    elif any(sym in cleaned for sym in ("eur", "€")):
        rate = EXCHANGE_RATES_TO_USD["eur"]
    elif any(sym in cleaned for sym in ("gbp", "£")):
        rate = EXCHANGE_RATES_TO_USD["gbp"]
    elif any(sym in cleaned for sym in ("cad", "c$")):
        rate = EXCHANGE_RATES_TO_USD["cad"]
    elif any(sym in cleaned for sym in ("aud", "a$")):
        rate = EXCHANGE_RATES_TO_USD["aud"]
    elif "chf" in cleaned:
        rate = EXCHANGE_RATES_TO_USD["chf"]
    elif any(sym in cleaned for sym in ("jpy", "¥", "yen")):
        rate = EXCHANGE_RATES_TO_USD["jpy"]
    elif "$" in cleaned or "usd" in cleaned:
        rate = 1.0

    # 2. Check for Indian LPA / Lakh (e.g., "12 LPA", "8.5 Lakh")
    lpa_matches = re.findall(r"(\d+(?:\.\d+)?)\s*(?:lpa|lakh|lac)", cleaned)
    if lpa_matches:
        lpa_vals = [float(v) * 100000 * EXCHANGE_RATES_TO_USD["inr"] for v in lpa_matches]
        return max(lpa_vals)

    # 3. Match numeric amounts with optional 'k' or 'm' multiplier
    matches = re.findall(r"(\d+(?:\.\d+)?)\s*([km])?", cleaned)
    if not matches:
        return None

    amounts: list[float] = []
    has_k = "k" in cleaned
    for num_str, suffix in matches:
        try:
            val = float(num_str)
            if suffix == "k":
                val *= 1000
            elif suffix == "m":
                val *= 1000000
            elif val < 1000 and has_k and "/hr" not in cleaned and "/hour" not in cleaned:
                val *= 1000
            amounts.append(val * rate)
        except ValueError:
            continue

    return max(amounts) if amounts else None


def matches_min_stipend(listing_stipend: str | None, filter_input: str | None) -> bool:
    """Check if listing stipend is greater than or equal to searched amount, with currency conversion."""
    if not filter_input or not filter_input.strip():
        return True
    query = filter_input.strip()
    cleaned_query = re.sub(r"^[>\s=min]+", "", query, flags=re.IGNORECASE).rstrip("+").strip()
    min_usd = parse_stipend_to_usd(cleaned_query)

    if min_usd is not None:
        listing_usd = parse_stipend_to_usd(listing_stipend)
        if listing_usd is not None:
            return listing_usd >= min_usd
        return False

    return query.lower() in (listing_stipend or "").lower()


@router.get("/api/stats")
async def get_system_stats(
    db: AsyncSession = Depends(get_db),
    source: str | None = None,
    search: str | None = None,
    company: str | None = None,
    location: str | None = None,
    remote_ok: bool | None = None,
    has_stipend: bool | None = None,
    min_stipend: str | None = None,
    stipend: str | None = None,
    has_embedding: bool | None = None,
    limit: int = 1000,
) -> dict[str, Any]:
    """Return live system telemetry, listing metrics, and all ingested opportunities."""
    # 1. Overall counts
    total_listings = (await db.execute(select(func.count(JobListing.id)))).scalar() or 0
    vectorized_listings = (
        await db.execute(select(func.count(JobListing.id)).where(JobListing.embedding.is_not(None)))
    ).scalar() or 0
    total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0
    total_resumes = (await db.execute(select(func.count(Resume.id)))).scalar() or 0
    total_matches = (await db.execute(select(func.count(UserListingMatch.id)))).scalar() or 0
    total_briefings = (await db.execute(select(func.count(BriefingJob.id)))).scalar() or 0

    # 2. Group by source
    source_counts_query = (
        select(JobListing.source_name, func.count(JobListing.id))
        .group_by(JobListing.source_name)
    )
    source_rows = (await db.execute(source_counts_query)).all()
    source_breakdown = {name: count for name, count in source_rows}

    # 3. All recent listings (lightweight projection without raw_text or heavy vectors)
    query = (
        select(
            JobListing.id,
            JobListing.title,
            JobListing.company,
            JobListing.location,
            JobListing.remote_ok,
            JobListing.stipend,
            JobListing.required_skills,
            JobListing.source_name,
            JobListing.source_url,
            JobListing.scraped_at,
            (JobListing.embedding.is_not(None)).label("has_embedding"),
        )
        .order_by(desc(JobListing.scraped_at))
    )

    if source and source.lower() != "all":
        if source.lower() in ("github", "hn_who_is_hiring", "hiring"):
            query = query.where(
                or_(
                    JobListing.source_name.ilike("%github%"),
                    JobListing.source_name.ilike("%hiring%"),
                )
            )
        else:
            query = query.where(JobListing.source_name.ilike(f"%{source}%"))

    if search:
        query = query.where(
            or_(
                JobListing.title.ilike(f"%{search}%"),
                JobListing.company.ilike(f"%{search}%"),
            )
        )

    if company:
        query = query.where(JobListing.company.ilike(f"%{company}%"))

    if location:
        query = query.where(JobListing.location.ilike(f"%{location}%"))

    if remote_ok is not None:
        query = query.where(JobListing.remote_ok == remote_ok)

    if has_stipend is True:
        query = query.where(
            JobListing.stipend.is_not(None),
            JobListing.stipend != "",
            JobListing.stipend != "Not specified",
        )

    if has_embedding is True:
        query = query.where(JobListing.embedding.is_not(None))
    elif has_embedding is False:
        query = query.where(JobListing.embedding.is_(None))

    query = query.limit(limit)
    rows = (await db.execute(query)).all()

    recent_listings = [
        {
            "id": str(r.id),
            "title": r.title or "Untitled Role",
            "company": r.company or "Undisclosed",
            "location": r.location or "Remote",
            "remote_ok": r.remote_ok,
            "stipend": r.stipend or "Not specified",
            "skills": r.required_skills or [],
            "source_name": r.source_name,
            "source_url": r.source_url,
            "scraped_at": r.scraped_at.isoformat() if r.scraped_at else None,
            "has_embedding": bool(r.has_embedding),
        }
        for r in rows
    ]

    active_min_stipend = min_stipend or stipend
    if active_min_stipend:
        recent_listings = [
            item for item in recent_listings if matches_min_stipend(item["stipend"], active_min_stipend)
        ]

    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "counts": {
            "total_listings": total_listings,
            "vectorized_listings": vectorized_listings,
            "vector_percentage": round((vectorized_listings / total_listings * 100), 1) if total_listings > 0 else 0.0,
            "total_users": total_users,
            "total_resumes": total_resumes,
            "total_matches": total_matches,
            "total_briefings": total_briefings,
        },
        "sources": source_breakdown,
        "recent_listings": recent_listings,
    }


@router.get("/", response_class=HTMLResponse)
async def live_command_center(db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    """Serve the NEXUS Live Command Center frontend interface."""
    stats = await get_system_stats(db=db)
    stats_json = json.dumps(stats)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NEXUS — Live Mission Control & Pipeline Monitor</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800&family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg: #07090E;
            --surface: #0E131F;
            --surface-card: #131A2B;
            --surface-hover: #1A243B;
            --border: rgba(255, 255, 255, 0.08);
            --border-highlight: rgba(99, 102, 241, 0.3);
            --primary: #6366F1;
            --primary-glow: rgba(99, 102, 241, 0.25);
            --cyan: #06B6D4;
            --cyan-glow: rgba(6, 182, 212, 0.25);
            --emerald: #10B981;
            --emerald-glow: rgba(16, 185, 129, 0.2);
            --purple: #8B5CF6;
            --amber: #F59E0B;
            --text: #F8FAFC;
            --text-muted: #94A3B8;
            --text-faint: #64748B;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background-color: var(--bg);
            color: var(--text);
            line-height: 1.5;
            min-height: 100vh;
            background-image: 
                radial-gradient(circle at 15% 10%, rgba(99, 102, 241, 0.12) 0%, transparent 35%),
                radial-gradient(circle at 85% 20%, rgba(6, 182, 212, 0.10) 0%, transparent 30%),
                radial-gradient(circle at 50% 80%, rgba(139, 92, 246, 0.08) 0%, transparent 40%);
            background-attachment: fixed;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 24px 32px;
        }}

        /* Header */
        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 24px;
            border-bottom: 1px solid var(--border);
            margin-bottom: 32px;
        }}

        .brand {{
            display: flex;
            align-items: center;
            gap: 16px;
        }}

        .logo-box {{
            width: 44px;
            height: 44px;
            border-radius: 12px;
            background: linear-gradient(135deg, var(--primary), var(--cyan));
            display: flex;
            align-items: center;
            justify-content: center;
            font-family: 'Outfit', sans-serif;
            font-weight: 800;
            font-size: 22px;
            color: white;
            box-shadow: 0 0 20px var(--primary-glow);
        }}

        .brand-text h1 {{
            font-family: 'Outfit', sans-serif;
            font-size: 22px;
            font-weight: 700;
            letter-spacing: -0.02em;
            background: linear-gradient(to right, #FFFFFF, #CBD5E1);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}

        .brand-text p {{
            font-size: 13px;
            color: var(--text-muted);
        }}

        .header-actions {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}

        .badge-live {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 6px 14px;
            border-radius: 9999px;
            background: rgba(16, 185, 129, 0.12);
            border: 1px solid rgba(16, 185, 129, 0.3);
            color: var(--emerald);
            font-size: 13px;
            font-weight: 600;
            box-shadow: 0 0 14px var(--emerald-glow);
        }}

        .pulse-dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background-color: var(--emerald);
            animation: pulse 1.8s infinite;
        }}

        @keyframes pulse {{
            0% {{ box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }}
            70% {{ box-shadow: 0 0 0 8px rgba(16, 185, 129, 0); }}
            100% {{ box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }}
        }}

        .btn {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 8px 16px;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 600;
            text-decoration: none;
            transition: all 0.2s ease;
            cursor: pointer;
            border: 1px solid transparent;
        }}

        .btn-primary {{
            background: linear-gradient(135deg, var(--primary), var(--purple));
            color: white;
            box-shadow: 0 4px 14px var(--primary-glow);
        }}

        .btn-primary:hover {{
            transform: translateY(-1px);
            box-shadow: 0 6px 20px var(--primary-glow);
        }}

        .btn-outline {{
            background: rgba(255, 255, 255, 0.04);
            border-color: var(--border);
            color: var(--text);
        }}

        .btn-outline:hover {{
            background: rgba(255, 255, 255, 0.08);
            border-color: var(--border-highlight);
        }}

        /* Metrics Grid */
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 20px;
            margin-bottom: 32px;
        }}

        .metric-card {{
            background: var(--surface-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 22px 24px;
            position: relative;
            overflow: hidden;
            transition: transform 0.2s ease, border-color 0.2s ease;
        }}

        .metric-card:hover {{
            transform: translateY(-2px);
            border-color: var(--border-highlight);
        }}

        .metric-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, var(--card-color, var(--primary)), transparent);
        }}

        .metric-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }}

        .metric-title {{
            font-size: 13px;
            font-weight: 500;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .metric-icon {{
            font-size: 18px;
            opacity: 0.8;
        }}

        .metric-value {{
            font-family: 'Outfit', sans-serif;
            font-size: 36px;
            font-weight: 700;
            line-height: 1;
            margin-bottom: 6px;
            color: #FFFFFF;
        }}

        .metric-subtext {{
            font-size: 12px;
            color: var(--text-faint);
            display: flex;
            align-items: center;
            gap: 6px;
        }}

        /* Sources Section */
        .section-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
        }}

        .section-title {{
            font-family: 'Outfit', sans-serif;
            font-size: 18px;
            font-weight: 700;
            color: var(--text);
            display: flex;
            align-items: center;
            gap: 10px;
        }}

        .sources-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
            margin-bottom: 36px;
        }}

        .source-pill-card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 16px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            transition: all 0.2s ease;
        }}

        .source-pill-card:hover {{
            background: var(--surface-hover);
            border-color: var(--border-highlight);
        }}

        .source-name {{
            font-weight: 600;
            font-size: 14px;
            color: var(--text);
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .source-dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--cyan);
        }}

        .source-badge {{
            background: rgba(99, 102, 241, 0.15);
            border: 1px solid rgba(99, 102, 241, 0.3);
            color: #A5B4FC;
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            font-weight: 600;
            padding: 4px 10px;
            border-radius: 6px;
        }}

        /* Table Card */
        .table-card {{
            background: var(--surface-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            overflow: hidden;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
        }}

        .table-toolbar {{
            padding: 18px 24px;
            background: var(--surface);
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 16px;
            flex-wrap: wrap;
        }}

        .search-box {{
            flex: 1;
            min-width: 260px;
            position: relative;
        }}

        .search-box input {{
            width: 100%;
            padding: 10px 16px 10px 38px;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border);
            border-radius: 8px;
            color: var(--text);
            font-size: 13px;
            outline: none;
            transition: border-color 0.2s ease;
        }}

        .search-box input:focus {{
            border-color: var(--primary);
            background: rgba(255, 255, 255, 0.08);
        }}

        .search-icon {{
            position: absolute;
            left: 12px;
            top: 50%;
            transform: translateY(-50%);
            color: var(--text-faint);
            font-size: 14px;
        }}

        .filter-group {{
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }}

        .filter-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 12px;
            width: 100%;
            margin-bottom: 12px;
        }}

        .input-group {{
            display: flex;
            flex-direction: column;
            gap: 6px;
        }}

        .input-group label {{
            font-size: 11px;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            display: flex;
            align-items: center;
            gap: 5px;
        }}

        .input-group input, .input-group select {{
            width: 100%;
            padding: 9px 12px;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border);
            border-radius: 8px;
            color: var(--text);
            font-size: 13px;
            outline: none;
            transition: border-color 0.2s ease, background 0.2s ease;
        }}

        .input-group input:focus, .input-group select:focus {{
            border-color: var(--primary);
            background: rgba(255, 255, 255, 0.08);
            box-shadow: 0 0 0 1px var(--primary-glow);
        }}

        .input-group select option {{
            background: var(--surface-card);
            color: var(--text);
        }}

        .count-badge {{
            font-size: 11px;
            font-weight: 500;
            color: #A5B4FC;
            background: rgba(99, 102, 241, 0.12);
            border: 1px solid rgba(99, 102, 241, 0.25);
            border-radius: 9999px;
            padding: 2px 10px;
            margin-left: 10px;
            letter-spacing: 0;
            text-transform: none;
        }}

        .filter-btn {{
            padding: 6px 12px;
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid var(--border);
            border-radius: 6px;
            color: var(--text-muted);
            font-size: 12px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
        }}

        .filter-btn.active, .filter-btn:hover {{
            background: var(--primary);
            border-color: var(--primary);
            color: white;
        }}

        /* Table */
        .table-responsive {{
            overflow-x: auto;
            max-height: 640px;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 13px;
        }}

        thead {{
            background: rgba(15, 23, 42, 0.8);
            position: sticky;
            top: 0;
            z-index: 10;
            backdrop-filter: blur(8px);
        }}

        th {{
            padding: 14px 20px;
            font-size: 11px;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.06em;
            border-bottom: 1px solid var(--border);
        }}

        td {{
            padding: 16px 20px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.04);
            color: var(--text);
            vertical-align: middle;
        }}

        tr:hover td {{
            background: rgba(255, 255, 255, 0.02);
        }}

        .job-title-cell {{
            font-weight: 600;
            color: #FFFFFF;
            font-size: 14px;
        }}

        .job-company {{
            font-size: 12px;
            color: var(--cyan);
            margin-top: 2px;
        }}

        .tag-pill {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 500;
            background: rgba(255, 255, 255, 0.06);
            color: var(--text-muted);
            margin: 2px;
        }}

        .vector-badge {{
            display: inline-flex;
            align-items: center;
            gap: 5px;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            font-family: 'JetBrains Mono', monospace;
            background: rgba(16, 185, 129, 0.1);
            color: var(--emerald);
            border: 1px solid rgba(16, 185, 129, 0.25);
        }}

        .source-tag {{
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }}

        .source-remoteok {{ background: rgba(6, 182, 212, 0.15); color: #22D3EE; }}
        .source-levels_fyi {{ background: rgba(16, 185, 129, 0.2); color: #34D399; font-weight: 700; border: 1px solid rgba(16, 185, 129, 0.35); }}
        .source-adzuna {{ background: rgba(245, 158, 11, 0.2); color: #FBBF24; }}
        .source-weworkremotely {{ background: rgba(239, 68, 68, 0.15); color: #FCA5A5; }}
        .source-arbeitnow {{ background: rgba(139, 92, 246, 0.15); color: #C4B5FD; }}
        .source-remotive {{ background: rgba(245, 158, 11, 0.15); color: #FCD34D; }}
        .source-github_hiring {{ background: rgba(16, 185, 129, 0.15); color: #6EE7B7; }}

        .action-link {{
            color: var(--cyan);
            text-decoration: none;
            font-weight: 600;
            font-size: 12px;
            transition: color 0.15s ease;
        }}

        .action-link:hover {{
            color: #67E8F9;
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <header>
            <div class="brand">
                <div class="logo-box">N</div>
                <div class="brand-text">
                    <h1>NEXUS Mission Control</h1>
                    <p>Autonomous Career Intelligence Agent & Scraper Telemetry</p>
                </div>
            </div>
            <div class="header-actions">
                <div class="badge-live">
                    <span class="pulse-dot"></span>
                    <span>PIPELINE ONLINE</span>
                </div>
                <a href="http://localhost:3000" target="_blank" class="btn btn-primary">Launch Next.js App ↗</a>
                <a href="/docs" target="_blank" class="btn btn-outline">Swagger API Docs</a>
            </div>
        </header>

        <!-- Metric Grid -->
        <div class="metrics-grid">
            <div class="metric-card" style="--card-color: var(--cyan);">
                <div class="metric-header">
                    <span class="metric-title">Live Ingested Listings</span>
                    <span class="metric-icon">💼</span>
                </div>
                <div class="metric-value" id="metric-total">{stats['counts']['total_listings']}</div>
                <div class="metric-subtext">
                    <span>Active in PostgreSQL pgvector</span>
                </div>
            </div>

            <div class="metric-card" style="--card-color: var(--emerald);">
                <div class="metric-header">
                    <span class="metric-title">AI Vectorization</span>
                    <span class="metric-icon">🧠</span>
                </div>
                <div class="metric-value" id="metric-vectors">{stats['counts']['vectorized_listings']}</div>
                <div class="metric-subtext">
                    <span style="color: var(--emerald); font-weight: 600;">{stats['counts']['vector_percentage']}%</span>
                    <span>vectorized (gemini-embedding-2)</span>
                </div>
            </div>

            <div class="metric-card" style="--card-color: var(--purple);">
                <div class="metric-header">
                    <span class="metric-title">Active Ingestion Sources</span>
                    <span class="metric-icon">🛡️</span>
                </div>
                <div class="metric-value">{len(stats['sources'])} Sources</div>
                <div class="metric-subtext">
                    <span>Multi-channel scraping & APIs</span>
                </div>
            </div>

            <div class="metric-card" style="--card-color: var(--primary);">
                <div class="metric-header">
                    <span class="metric-title">Vector Match Engine</span>
                    <span class="metric-icon">⚡</span>
                </div>
                <div class="metric-value">768-dim</div>
                <div class="metric-subtext">
                    <span>Sub-50ms cosine similarity index</span>
                </div>
            </div>
        </div>

        <!-- Sources Breakdown Section -->
        <div class="section-header">
            <div class="section-title">
                <span>📡</span> Ingestion Source Breakdown
            </div>
            <span style="font-size: 13px; color: var(--text-muted);" id="last-updated">Auto-refreshed live</span>
        </div>
        <div class="sources-grid" id="sources-container">
            <!-- Dynamic Source Cards -->
        </div>

        <!-- Recent Jobs Explorer -->
        <div class="section-header">
            <div class="section-title">
                <span>⚡</span> Real-Time Job Opportunity Feed
                <span id="feed-count-badge" class="count-badge">Showing opportunities</span>
            </div>
            <button id="resetFiltersBtn" class="btn btn-outline" style="display: none; padding: 6px 14px; font-size: 12px; color: #FCA5A5; border-color: rgba(239, 68, 68, 0.35); background: rgba(239, 68, 68, 0.08);">
                ✕ Reset All Filters
            </button>
        </div>
        <div class="table-card">
            <div class="table-toolbar" style="flex-direction: column; align-items: stretch; gap: 14px;">
                <!-- Primary Search Box -->
                <div class="search-box" style="width: 100%;">
                    <span class="search-icon">🔍</span>
                    <input type="text" id="searchInput" placeholder="Search role title (e.g. Senior Backend) or technical skills (FastAPI, React, PyTorch)...">
                </div>

                <!-- 4 Multi-Attribute Controls: Company, Location, Stipend, Sort -->
                <div class="filter-grid">
                    <div class="input-group">
                        <label for="companyInput">🏢 Company Name</label>
                        <input type="text" id="companyInput" placeholder="e.g. Stripe, OpenAI...">
                    </div>
                    <div class="input-group">
                        <label for="locationInput">📍 Location / Region</label>
                        <input type="text" id="locationInput" placeholder="e.g. Remote, San Francisco...">
                    </div>
                    <div class="input-group">
                        <label for="stipendInput">💰 Min Stipend (≥)</label>
                        <input type="text" id="stipendInput" placeholder="e.g. > $800, 80000 rupees, 100k...">
                    </div>
                    <div class="input-group">
                        <label for="sortSelector">⇅ Sort Order</label>
                        <select id="sortSelector">
                            <option value="newest">Newest Scraped First</option>
                            <option value="company">Company (A-Z)</option>
                            <option value="title">Role Title (A-Z)</option>
                            <option value="stipend">Disclosed Stipend First</option>
                        </select>
                    </div>
                </div>

                <!-- Quick Filter Pills & Toggles -->
                <div style="display: flex; justify-content: space-between; align-items: center; width: 100%; flex-wrap: wrap; gap: 10px; padding-top: 4px; border-top: 1px solid var(--border);">
                    <div class="filter-group" id="filterGroup">
                        <button class="filter-btn active" data-filter="all">All Sources</button>
                        <button class="filter-btn" data-filter="levels_fyi">Levels.fyi 💰</button>
                        <button class="filter-btn" data-filter="remoteok">RemoteOK</button>
                        <button class="filter-btn" data-filter="remotive">Remotive</button>
                        <button class="filter-btn" data-filter="weworkremotely">WWR</button>
                        <button class="filter-btn" data-filter="arbeitnow">Arbeitnow</button>
                        <button class="filter-btn" data-filter="github">HN Hiring</button>
                    </div>
                    <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                        <button class="filter-btn" id="stipendToggleBtn" style="border-color: rgba(16, 185, 129, 0.4); color: #34D399;">💰 Disclosed Stipend Only</button>
                        <button class="filter-btn" id="remoteToggleBtn" style="border-color: rgba(6, 182, 212, 0.4); color: #22D3EE;">🌐 Remote Only</button>
                        <button class="filter-btn" id="vectorToggleBtn" style="border-color: rgba(139, 92, 246, 0.4); color: #C4B5FD;">🧠 768-dim Vectorized Only</button>
                    </div>
                </div>
            </div>
            <div class="table-responsive">
                <table>
                    <thead>
                        <tr>
                            <th>Opportunity</th>
                            <th>Location</th>
                            <th>Skills & Tags</th>
                            <th>Stipend</th>
                            <th>Source</th>
                            <th>AI Vector</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody id="jobsTableBody">
                        <!-- Populated by JavaScript -->
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        const initialData = {stats_json};
        let currentFilter = 'all';
        let searchQuery = '';
        let companyQuery = '';
        let locationQuery = '';
        let stipendQuery = '';
        let onlyWithStipend = false;
        let onlyRemote = false;
        let onlyVectorized = false;
        let sortBy = 'newest';

        function countActiveFilters() {{
            let count = 0;
            if (currentFilter !== 'all') count++;
            if (searchQuery) count++;
            if (companyQuery) count++;
            if (locationQuery) count++;
            if (stipendQuery) count++;
            if (onlyWithStipend) count++;
            if (onlyRemote) count++;
            if (onlyVectorized) count++;
            if (sortBy !== 'newest') count++;
            return count;
        }}

        function updateToggleStyles() {{
            const stipendBtn = document.getElementById('stipendToggleBtn');
            if (stipendBtn) {{
                if (onlyWithStipend) {{
                    stipendBtn.style.background = '#10B981';
                    stipendBtn.style.color = '#FFFFFF';
                    stipendBtn.style.borderColor = '#10B981';
                }} else {{
                    stipendBtn.style.background = 'rgba(255, 255, 255, 0.04)';
                    stipendBtn.style.color = '#34D399';
                    stipendBtn.style.borderColor = 'rgba(16, 185, 129, 0.4)';
                }}
            }}

            const remoteBtn = document.getElementById('remoteToggleBtn');
            if (remoteBtn) {{
                if (onlyRemote) {{
                    remoteBtn.style.background = '#06B6D4';
                    remoteBtn.style.color = '#FFFFFF';
                    remoteBtn.style.borderColor = '#06B6D4';
                }} else {{
                    remoteBtn.style.background = 'rgba(255, 255, 255, 0.04)';
                    remoteBtn.style.color = '#22D3EE';
                    remoteBtn.style.borderColor = 'rgba(6, 182, 212, 0.4)';
                }}
            }}

            const vectorBtn = document.getElementById('vectorToggleBtn');
            if (vectorBtn) {{
                if (onlyVectorized) {{
                    vectorBtn.style.background = '#8B5CF6';
                    vectorBtn.style.color = '#FFFFFF';
                    vectorBtn.style.borderColor = '#8B5CF6';
                }} else {{
                    vectorBtn.style.background = 'rgba(255, 255, 255, 0.04)';
                    vectorBtn.style.color = '#C4B5FD';
                    vectorBtn.style.borderColor = 'rgba(139, 92, 246, 0.4)';
                }}
            }}
        }}

        function resetAllFilters() {{
            currentFilter = 'all';
            searchQuery = '';
            companyQuery = '';
            locationQuery = '';
            stipendQuery = '';
            onlyWithStipend = false;
            onlyRemote = false;
            onlyVectorized = false;
            sortBy = 'newest';

            document.getElementById('searchInput').value = '';
            document.getElementById('companyInput').value = '';
            document.getElementById('locationInput').value = '';
            document.getElementById('stipendInput').value = '';
            document.getElementById('sortSelector').value = 'newest';

            document.querySelectorAll('#filterGroup .filter-btn').forEach(b => {{
                b.classList.toggle('active', b.dataset.filter === 'all');
            }});

            updateToggleStyles();
            renderTable(initialData.recent_listings);
        }}

        function renderSources(sources) {{
            const container = document.getElementById('sources-container');
            container.innerHTML = '';
            const sourceDisplayNames = {{
                'levels_fyi': 'Levels.fyi 💰',
                'remoteok': 'RemoteOK API',
                'remotive': 'Remotive Software',
                'weworkremotely': 'We Work Remotely',
                'arbeitnow': 'Arbeitnow Tech',
                'hn_who_is_hiring': 'HN Who is Hiring',
                'github': 'HN Who is Hiring',
                'adzuna': 'Adzuna API'
            }};

            for (const [key, count] of Object.entries(sources)) {{
                const name = sourceDisplayNames[key] || key;
                const card = document.createElement('div');
                card.className = 'source-pill-card';
                card.innerHTML = `
                    <div class="source-name">
                        <span class="source-dot"></span>
                        <span>${{name}}</span>
                    </div>
                    <div class="source-badge">${{count}} jobs</div>
                `;
                container.appendChild(card);
            }}
        }}

        const EXCHANGE_RATES_TO_USD = {{
            'usd': 1.0,
            '$': 1.0,
            'inr': 1.0 / 85.0,
            '₹': 1.0 / 85.0,
            'rs': 1.0 / 85.0,
            'rupee': 1.0 / 85.0,
            'rupees': 1.0 / 85.0,
            'eur': 1.08,
            '€': 1.08,
            'gbp': 1.28,
            '£': 1.28,
            'cad': 0.74,
            'c$': 0.74,
            'aud': 0.66,
            'a$': 0.66,
            'chf': 1.12,
            'jpy': 1.0 / 150.0,
            '¥': 1.0 / 150.0
        }};

        function parseStipendToUsd(text) {{
            if (!text) return null;
            const raw = text.trim();
            if (!raw || /^(not specified|unlisted|competitive|undisclosed)$/i.test(raw)) {{
                return null;
            }}

            const cleaned = raw.toLowerCase().replace(/,/g, '');

            let rate = 1.0;
            if (['inr', '₹', 'rs', 'rupee', 'rupees', 'lpa', 'lakh'].some(sym => cleaned.includes(sym))) {{
                rate = EXCHANGE_RATES_TO_USD['inr'];
            }} else if (['eur', '€'].some(sym => cleaned.includes(sym))) {{
                rate = EXCHANGE_RATES_TO_USD['eur'];
            }} else if (['gbp', '£'].some(sym => cleaned.includes(sym))) {{
                rate = EXCHANGE_RATES_TO_USD['gbp'];
            }} else if (['cad', 'c$'].some(sym => cleaned.includes(sym))) {{
                rate = EXCHANGE_RATES_TO_USD['cad'];
            }} else if (['aud', 'a$'].some(sym => cleaned.includes(sym))) {{
                rate = EXCHANGE_RATES_TO_USD['aud'];
            }} else if (cleaned.includes('chf')) {{
                rate = EXCHANGE_RATES_TO_USD['chf'];
            }} else if (['jpy', '¥', 'yen'].some(sym => cleaned.includes(sym))) {{
                rate = EXCHANGE_RATES_TO_USD['jpy'];
            }} else if (cleaned.includes('$') || cleaned.includes('usd')) {{
                rate = 1.0;
            }}

            const lpaMatches = cleaned.match(/(\d+(?:\.\d+)?)\s*(?:lpa|lakh|lac)/g);
            if (lpaMatches) {{
                const lpaVals = lpaMatches
                    .map(m => parseFloat(m.replace(/[^0-9.]/g, '')) * 100000 * EXCHANGE_RATES_TO_USD['inr'])
                    .filter(v => !isNaN(v));
                if (lpaVals.length > 0) return Math.max(...lpaVals);
            }}

            const regex = /(\d+(?:\.\d+)?)\s*([km])?/gi;
            const amounts = [];
            const hasK = cleaned.includes('k');
            let match;
            while ((match = regex.exec(cleaned)) !== null) {{
                const num = parseFloat(match[1]);
                if (isNaN(num)) continue;
                const suffix = (match[2] || '').toLowerCase();
                let val = num;
                if (suffix === 'k') val *= 1000;
                else if (suffix === 'm') val *= 1000000;
                else if (val < 1000 && hasK && !cleaned.includes('/hr') && !cleaned.includes('/hour')) val *= 1000;
                amounts.push(val * rate);
            }}

            return amounts.length > 0 ? Math.max(...amounts) : null;
        }}

        function matchesMinStipend(listingStipend, filterInput) {{
            if (!filterInput || !filterInput.trim()) return true;
            const query = filterInput.trim();
            const cleanedQuery = query.replace(/^[>\s=min]+/i, '').replace(/\+$/, '').trim();
            const minUsd = parseStipendToUsd(cleanedQuery);

            if (minUsd !== null) {{
                const listingUsd = parseStipendToUsd(listingStipend);
                if (listingUsd !== null) {{
                    return listingUsd >= minUsd;
                }}
                return false;
            }}

            return (listingStipend || '').toLowerCase().includes(query.toLowerCase());
        }}

        function renderTable(listings) {{
            const tbody = document.getElementById('jobsTableBody');
            tbody.innerHTML = '';

            const filtered = listings.filter(item => {{
                // 1. Source filter
                const sName = (item.source_name || '').toLowerCase();
                const matchesFilter = currentFilter === 'all' || 
                    sName.includes(currentFilter.toLowerCase()) ||
                    (currentFilter === 'github' && (sName.includes('hiring') || sName.includes('github') || sName.includes('hn')));

                // 2. Search query (title + skills)
                const textSearch = (item.title + ' ' + item.company + ' ' + (item.skills || []).join(' ')).toLowerCase();
                const matchesSearch = !searchQuery || textSearch.includes(searchQuery.toLowerCase());

                // 3. Company filter
                const matchesCompany = !companyQuery || (item.company || '').toLowerCase().includes(companyQuery.toLowerCase());

                // 4. Location filter
                const matchesLocation = !locationQuery || 
                    (item.location || '').toLowerCase().includes(locationQuery.toLowerCase()) ||
                    (locationQuery.toLowerCase() === 'remote' && item.remote_ok);

                // 5. Stipend filter (greater than or equal to searched amount with currency conversion)
                const matchesStipendText = !stipendQuery || matchesMinStipend(item.stipend, stipendQuery);

                // 6. Explicit stipend toggle
                const hasStipend = item.stipend && item.stipend.toLowerCase() !== 'not specified' && item.stipend.trim() !== '';
                const matchesOnlyStipend = !onlyWithStipend || hasStipend;

                // 7. Remote only toggle
                const matchesRemote = !onlyRemote || item.remote_ok;

                // 8. Vectorized only toggle
                const matchesVectorized = !onlyVectorized || item.has_embedding;

                return matchesFilter && matchesSearch && matchesCompany && matchesLocation && matchesStipendText && matchesOnlyStipend && matchesRemote && matchesVectorized;
            }});

            // Sorting
            filtered.sort((a, b) => {{
                if (sortBy === 'company') {{
                    return (a.company || '').localeCompare(b.company || '');
                }}
                if (sortBy === 'title') {{
                    return (a.title || '').localeCompare(b.title || '');
                }}
                if (sortBy === 'stipend') {{
                    const aHas = a.stipend && a.stipend.toLowerCase() !== 'not specified' ? 1 : 0;
                    const bHas = b.stipend && b.stipend.toLowerCase() !== 'not specified' ? 1 : 0;
                    return bHas - aHas;
                }}
                // default: newest
                const aTime = a.scraped_at ? new Date(a.scraped_at).getTime() : 0;
                const bTime = b.scraped_at ? new Date(b.scraped_at).getTime() : 0;
                return bTime - aTime;
            }});

            const activeCount = countActiveFilters();
            const badge = document.getElementById('feed-count-badge');
            if (badge) {{
                badge.textContent = `Showing ${{filtered.length}} of ${{listings.length}} opportunities in database` +
                    (activeCount > 0 ? ` • ${{activeCount}} filter${{activeCount > 1 ? 's' : ''}} active` : '');
            }}

            const resetBtn = document.getElementById('resetFiltersBtn');
            if (resetBtn) {{
                resetBtn.style.display = activeCount > 0 ? 'inline-flex' : 'none';
            }}

            if (filtered.length === 0) {{
                tbody.innerHTML = `
                    <tr>
                        <td colspan="7" style="text-align: center; padding: 48px; color: var(--text-muted);">
                            <div style="font-size: 26px; margin-bottom: 8px;">🔍</div>
                            <div style="font-size: 15px; font-weight: 600; color: #FFFFFF; margin-bottom: 6px;">No opportunities match your filter criteria</div>
                            <div style="font-size: 12px; color: var(--text-faint); max-width: 440px; margin: 0 auto 16px;">
                                None of the listings in the database matched the selected company, location, stipend, vector status, or search query.
                            </div>
                            <button onclick="resetAllFilters()" class="btn btn-primary" style="font-size: 12px; padding: 6px 14px;">Clear All Filters</button>
                        </td>
                    </tr>
                `;
                return;
            }}

            for (const item of filtered) {{
                const tr = document.createElement('tr');
                const skillsHtml = (item.skills || []).slice(0, 4).map(s => `<span class="tag-pill">${{s}}</span>`).join('') +
                    ((item.skills || []).length > 4 ? `<span class="tag-pill">+${{item.skills.length - 4}}</span>` : '');

                const sourceClass = 'source-' + (item.source_name || 'custom').replace(/[^a-z0-9]/gi, '_');

                const hasExplicitStipend = item.stipend && item.stipend.toLowerCase() !== 'not specified' && item.stipend.trim() !== '';
                const stipendBadge = hasExplicitStipend
                    ? `<span style="font-family: 'JetBrains Mono', monospace; font-size: 12px; font-weight: 600; color: #34D399; background: rgba(16,185,129,0.12); border: 1px solid rgba(16,185,129,0.3); padding: 3px 8px; border-radius: 4px;">💰 ${{item.stipend}}</span>`
                    : `<span style="font-family: 'JetBrains Mono', monospace; font-size: 11px; color: var(--text-faint);">Not specified</span>`;

                tr.innerHTML = `
                    <td>
                        <div class="job-title-cell">${{item.title}}</div>
                        <div class="job-company">${{item.company}}</div>
                    </td>
                    <td>
                        <span style="color: var(--text-muted); font-size: 12px;">${{item.location}}</span>
                        ${{item.remote_ok ? '<span class="tag-pill" style="color: var(--emerald); background: rgba(16,185,129,0.1);">Remote</span>' : ''}}
                    </td>
                    <td>${{skillsHtml || '<span style="color: var(--text-faint);">—</span>'}}</td>
                    <td>${{stipendBadge}}</td>
                    <td><span class="source-tag ${{sourceClass}}">${{item.source_name}}</span></td>
                    <td>
                        ${{item.has_embedding 
                            ? '<span class="vector-badge">✓ 768-dim</span>' 
                            : '<span style="color: var(--text-faint); font-size: 11px;">Pending</span>'}}
                    </td>
                    <td>
                        <a href="${{item.source_url}}" target="_blank" rel="noopener noreferrer" class="action-link">View Listing ↗</a>
                    </td>
                `;
                tbody.appendChild(tr);
            }}
        }}

        // Initialize with server-rendered data
        renderSources(initialData.sources);
        renderTable(initialData.recent_listings);

        // Input Listeners
        document.getElementById('searchInput').addEventListener('input', (e) => {{
            searchQuery = e.target.value.trim();
            renderTable(initialData.recent_listings);
        }});

        document.getElementById('companyInput').addEventListener('input', (e) => {{
            companyQuery = e.target.value.trim();
            renderTable(initialData.recent_listings);
        }});

        document.getElementById('locationInput').addEventListener('input', (e) => {{
            locationQuery = e.target.value.trim();
            renderTable(initialData.recent_listings);
        }});

        document.getElementById('stipendInput').addEventListener('input', (e) => {{
            stipendQuery = e.target.value.trim();
            renderTable(initialData.recent_listings);
        }});

        document.getElementById('sortSelector').addEventListener('change', (e) => {{
            sortBy = e.target.value;
            renderTable(initialData.recent_listings);
        }});

        // Source Filter Buttons
        document.querySelectorAll('#filterGroup .filter-btn').forEach(btn => {{
            btn.addEventListener('click', () => {{
                document.querySelectorAll('#filterGroup .filter-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                currentFilter = btn.dataset.filter;
                renderTable(initialData.recent_listings);
            }});
        }});

        // Toggle Buttons
        document.getElementById('stipendToggleBtn').addEventListener('click', () => {{
            onlyWithStipend = !onlyWithStipend;
            updateToggleStyles();
            renderTable(initialData.recent_listings);
        }});

        document.getElementById('remoteToggleBtn').addEventListener('click', () => {{
            onlyRemote = !onlyRemote;
            updateToggleStyles();
            renderTable(initialData.recent_listings);
        }});

        document.getElementById('vectorToggleBtn').addEventListener('click', () => {{
            onlyVectorized = !onlyVectorized;
            updateToggleStyles();
            renderTable(initialData.recent_listings);
        }});

        // Reset Button
        document.getElementById('resetFiltersBtn').addEventListener('click', resetAllFilters);

        // Auto-refresh telemetry every 15 seconds
        setInterval(async () => {{
            try {{
                const res = await fetch('/api/stats');
                if (res.ok) {{
                    const data = await res.json();
                    document.getElementById('metric-total').textContent = data.counts.total_listings;
                    document.getElementById('metric-vectors').textContent = data.counts.vectorized_listings;
                    renderSources(data.sources);
                    initialData.recent_listings = data.recent_listings;
                    renderTable(initialData.recent_listings);
                    document.getElementById('last-updated').textContent = 'Refreshed ' + new Date().toLocaleTimeString();
                }}
            }} catch (err) {{
                console.debug('Telemetry poll error', err);
            }}
        }}, 15000);
    </script>
</body>
</html>
"""
    return HTMLResponse(content=html_content)
