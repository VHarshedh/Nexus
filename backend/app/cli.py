"""
NEXUS — CLI Commands.

Provides a Click-based CLI for running the scraping pipeline and managing
the database.

Usage::

    python -m app.cli scrape                  # Scrape all sources
    python -m app.cli scrape --source remoteok # Single source
    python -m app.cli scrape --skip-embeddings # Skip embedding generation
    python -m app.cli db init                  # Create tables + pgvector
    python -m app.cli db stats                 # Show row counts
"""

from __future__ import annotations

import asyncio
import logging
import sys

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from app.config import get_settings

console = Console()


def _setup_logging() -> None:
    """Configure structured logging with Rich."""
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


# ─── Top-Level CLI Group ─────────────────────────────────────────────────────
@click.group()
def cli() -> None:
    """NEXUS -- Autonomous Career Intelligence Agent CLI."""
    _setup_logging()


# ─── Scrape Command ──────────────────────────────────────────────────────────
@cli.command()
@click.option(
    "--source", "-s",
    multiple=True,
    help="Scraper name(s) to run. Omit to run all. (remoteok, github, weworkremotely, arbeitnow, remotive)",
)
@click.option(
    "--skip-embeddings",
    is_flag=True,
    default=False,
    help="Skip embedding generation (useful for testing without Gemini key).",
)
def scrape(source: tuple[str, ...], skip_embeddings: bool) -> None:
    """Run the scrape -> extract -> embed -> store pipeline."""
    from app.pipeline.orchestrator import run_scrape_pipeline

    sources = list(source) if source else None
    console.print(
        f"\n[bold cyan]>> Starting NEXUS scrape pipeline[/bold cyan]"
        f"\n   Sources: {sources or 'ALL'}"
        f"\n   Embeddings: {'SKIP' if skip_embeddings else 'ON'}\n"
    )

    stats = asyncio.run(
        run_scrape_pipeline(sources, skip_embeddings=skip_embeddings)
    )

    # Pretty-print results
    table = Table(title="Pipeline Results", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", justify="right", style="green")
    for key, value in stats.items():
        table.add_row(key.capitalize(), str(value))
    console.print(table)


# ─── Database Commands ───────────────────────────────────────────────────────
@cli.group()
def db() -> None:
    """Database management commands."""
    pass


@db.command()
def init() -> None:
    """Create the pgvector extension and all tables."""
    from app.db import init_db

    console.print("[bold cyan]Initialising database...[/bold cyan]")
    asyncio.run(init_db())
    console.print("[bold green]Database initialised successfully.[/bold green]")


@db.command()
@click.option("--yes", is_flag=True, help="Skip confirmation prompt.")
def drop(yes: bool) -> None:
    """Drop all database tables."""
    from app.db import drop_db

    if not yes and not click.confirm("Are you sure you want to drop all tables? This cannot be undone."):
        console.print("[yellow]Aborted.[/yellow]")
        return
    console.print("[bold red]Dropping database tables...[/bold red]")
    asyncio.run(drop_db())
    console.print("[bold green]All tables dropped successfully.[/bold green]")


@db.command()
@click.option("--yes", is_flag=True, help="Skip confirmation prompt.")
def reset(yes: bool) -> None:
    """Drop all tables and recreate them cleanly."""
    from app.db import drop_db, init_db

    if not yes and not click.confirm("Are you sure you want to reset the database? All data will be lost."):
        console.print("[yellow]Aborted.[/yellow]")
        return

    async def _do_reset() -> None:
        console.print("[bold red]Dropping database tables...[/bold red]")
        await drop_db()
        console.print("[bold cyan]Re-initialising database tables...[/bold cyan]")
        await init_db()

    asyncio.run(_do_reset())
    console.print("[bold green]Database reset completed successfully.[/bold green]")


@db.command()
def stats() -> None:
    """Show row counts for all tables."""
    from sqlalchemy import func, select, text

    from app.db import get_session
    from app.models import (
        BriefingJob,
        JobListing,
        Resume,
        User,
        UserListingMatch,
    )

    async def _stats() -> None:
        table = Table(title="NEXUS Database Stats", show_header=True, header_style="bold magenta")
        table.add_column("Table", style="cyan")
        table.add_column("Rows", justify="right", style="green")

        models = [
            ("users", User),
            ("job_listings", JobListing),
            ("resumes", Resume),
            ("user_listing_matches", UserListingMatch),
            ("briefing_jobs", BriefingJob),
        ]
        async with get_session() as session:
            for name, model in models:
                result = await session.execute(select(func.count()).select_from(model))
                count = result.scalar() or 0
                table.add_row(name, str(count))

        console.print(table)

    asyncio.run(_stats())


# ─── Semantic Search Test Command ────────────────────────────────────────────
@cli.command()
@click.argument("resume_text")
@click.option("--top-k", "-k", default=10, help="Number of results.")
def search(resume_text: str, top_k: int) -> None:
    """Test semantic search: find listings similar to RESUME_TEXT."""
    from app.db import get_session
    from app.pipeline.embeddings import find_similar_listings, generate_embedding

    async def _search() -> None:
        console.print(f"[cyan]Generating embedding for query text...[/cyan]")
        embedding = await generate_embedding(resume_text)
        if embedding is None:
            console.print("[red]Failed to generate embedding.[/red]")
            return

        async with get_session() as session:
            results = await find_similar_listings(embedding, session, top_k=top_k)

        if not results:
            console.print("[yellow]No matching listings found.[/yellow]")
            return

        table = Table(title=f"Top {top_k} Matches", show_header=True, header_style="bold magenta")
        table.add_column("#", style="dim", width=4)
        table.add_column("Title", style="cyan")
        table.add_column("Company", style="green")
        table.add_column("Distance", justify="right", style="yellow")

        for i, (listing, dist) in enumerate(results, 1):
            table.add_row(str(i), listing.title or "?", listing.company or "?", f"{dist:.4f}")

        console.print(table)

    asyncio.run(_search())


# ─── Entry Point ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    cli()
