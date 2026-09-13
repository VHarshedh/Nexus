"""
NEXUS — Extraction Evaluation Suite.

Evaluates the accuracy of the Gemini-powered ``ListingExtractor`` against
a curated benchmark of hand-labelled job listings and negative/noisy samples.

Calculates:
- Field-level accuracy for Title, Company, Location, Remote Detection, and Experience Level
- Token-level Precision, Recall, and F1-Score for Required Skills
- Specificity (rejection rate) on non-job conversational chatter
- Composite Pipeline Extraction Accuracy score

Usage::

    # Run against live Gemini API
    python -m evals.eval_extraction

    # Run in deterministic offline mock mode (for fast CI checks)
    python -m evals.eval_extraction --mock
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from app.config import get_settings
from app.pipeline.extractor import ExtractedListing, ListingExtractor

console = Console()
DATASET_PATH = Path(__file__).parent / "dataset.json"


# ─── Metric Helpers ──────────────────────────────────────────────────────────
def normalize_text(text: str | None) -> str:
    """Strip punctuation, whitespace, and lowercase text."""
    if not text:
        return ""
    return re.sub(r"[^\w\s]", "", text).strip().lower()


def string_similarity(pred: str | None, exp: str | None) -> float:
    """Compute string similarity ratio between predicted and expected."""
    if pred is None and exp is None:
        return 1.0
    if pred is None or exp is None:
        return 0.0
    norm_p = normalize_text(pred)
    norm_e = normalize_text(exp)
    if norm_p == norm_e:
        return 1.0
    if norm_e in norm_p or norm_p in norm_e:
        return 0.9
    return SequenceMatcher(None, norm_p, norm_e).ratio()


def calculate_skills_f1(pred_skills: list[str], exp_skills: list[str]) -> tuple[float, float, float]:
    """Calculate token-normalized Precision, Recall, and F1-Score for skills."""
    if not pred_skills and not exp_skills:
        return 1.0, 1.0, 1.0
    if not pred_skills or not exp_skills:
        return 0.0, 0.0, 0.0

    norm_pred = {normalize_text(s) for s in pred_skills if normalize_text(s)}
    norm_exp = {normalize_text(s) for s in exp_skills if normalize_text(s)}

    # Fuzzy intersection
    true_positives = 0
    for p in norm_pred:
        if any(p == e or p in e or e in p for e in norm_exp):
            true_positives += 1

    precision = true_positives / len(norm_pred) if norm_pred else 0.0
    recall = true_positives / len(norm_exp) if norm_exp else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    return precision, recall, f1


EXPERIENCE_SYNONYMS = {
    "lead": {"lead", "staff", "principal", "architect", "head", "senior"},
    "senior": {"senior", "sr", "staff", "lead"},
    "mid": {"mid", "intermediate", "experienced"},
    "junior": {"junior", "jr", "entry", "associate"},
    "intern": {"intern", "internship", "coop", "co-op", "trainee"},
}


def experience_level_match(pred: str | None, exp: str | None) -> float:
    """Evaluate experience level with synonym tolerance (e.g. staff/lead/senior)."""
    if pred is None and exp is None:
        return 1.0
    if pred is None or exp is None:
        return 0.0
    norm_p = normalize_text(pred)
    norm_e = normalize_text(exp)
    if norm_p == norm_e:
        return 1.0
    for level, synonyms in EXPERIENCE_SYNONYMS.items():
        if (norm_p in synonyms or norm_p == level) and (norm_e in synonyms or norm_e == level):
            return 1.0
    return 0.0


# ─── Sample Evaluation Result ────────────────────────────────────────────────
@dataclass
class SampleScore:
    sample_id: str
    source: str
    title_score: float
    company_score: float
    remote_score: float
    experience_score: float
    skills_f1: float
    overall_sample_score: float
    predicted: ExtractedListing | None
    expected: dict[str, Any]
    error: str | None = None


# ─── Mock Fixtures for Fast / Offline Verification ───────────────────────────
MOCK_RESPONSES = {
    "hn_infra_senior": {
        "title": "Senior Infrastructure Engineer",
        "company": "Stripe",
        "location": "US, Canada (Remote)",
        "remote_ok": True,
        "stipend": "$185k - $240k + equity",
        "required_skills": ["Go", "Kubernetes", "AWS", "Terraform", "Kafka", "Envoy", "Linux"],
        "experience_level": "senior",
        "deadline": None,
    },
    "wwr_backend_staff": {
        "title": "Staff Backend Engineer (Verify)",
        "company": "GitLab",
        "location": "EMEA (Remote)",
        "remote_ok": True,
        "stipend": "EUR 95,000 - 125,000",
        "required_skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "Redis"],
        "experience_level": "lead",
        "deadline": "October 30, 2026",
    },
    "remoteok_ml_lead": {
        "title": "Lead ML Research Engineer",
        "company": "Anthropic",
        "location": "San Francisco, CA",
        "remote_ok": True,
        "stipend": "$280,000 - $360,000",
        "required_skills": ["PyTorch", "JAX", "CUDA", "Megatron-LM", "DeepSpeed"],
        "experience_level": "lead",
        "deadline": None,
    },
    "arbeitnow_junior_frontend": {
        "title": "Junior Frontend Developer",
        "company": "Acme Health",
        "location": "New York, NY",
        "remote_ok": True,
        "stipend": "$70,000 - $85,000",
        "required_skills": ["TypeScript", "React", "Next.js", "Tailwind CSS", "Git"],
        "experience_level": "junior",
        "deadline": None,
    },
    "intern_swe_datadog": {
        "title": "Software Engineering Intern",
        "company": "Datadog",
        "location": "Boston, MA",
        "remote_ok": False,
        "stipend": "$55/hr",
        "required_skills": ["Java", "Go", "Python", "Algorithms", "Data Structures"],
        "experience_level": "intern",
        "deadline": None,
    },
    "negative_forum_chatter": {
        "title": None,
        "company": None,
        "location": None,
        "remote_ok": False,
        "stipend": None,
        "required_skills": [],
        "experience_level": None,
        "deadline": None,
    },
    "candidate_seeking_work": {
        "title": None,
        "company": None,
        "location": None,
        "remote_ok": False,
        "stipend": None,
        "required_skills": [],
        "experience_level": None,
        "deadline": None,
    },
    "scif_strict_onsite_no_remote": {
        "title": "Deployment Strategist",
        "company": "Palantir Technologies",
        "location": "Washington, DC",
        "remote_ok": False,
        "stipend": "$140,000 - $185,000",
        "required_skills": ["Python", "Bash", "Kubernetes", "Linux", "AWS GovCloud"],
        "experience_level": "mid",
        "deadline": None,
    },
    "recruitment_agency_stealth_client": {
        "title": "Principal Security Architect",
        "company": "Apex Talent Partners",
        "location": "London, UK",
        "remote_ok": False,
        "stipend": "£140,000 - £175,000",
        "required_skills": ["C", "C++", "Rust", "eBPF", "Linux", "HSM"],
        "experience_level": "lead",
        "deadline": None,
    },
    "contract_day_rate_multi_position": {
        "title": "Senior Platform Reliability Engineer",
        "company": "Monzo Bank",
        "location": "UK",
        "remote_ok": True,
        "stipend": "£650 - £750 / day",
        "required_skills": ["Go", "Kubernetes", "Terraform", "AWS", "Prometheus", "Envoy", "CockroachDB"],
        "experience_level": "senior",
        "deadline": None,
    },
}


def _extract_text_from_contents(contents: Any) -> str:
    if isinstance(contents, str):
        return contents
    if isinstance(contents, list) and contents:
        first = contents[0]
        if hasattr(first, "parts") and first.parts:
            return getattr(first.parts[0], "text", str(first.parts[0]))
    return str(contents)


class MockModelClient:
    """Mock Gemini client returning deterministic mock responses."""
    def __init__(self, responses_by_id: dict[str, dict[str, Any]]):
        self.responses_by_id = responses_by_id

    async def generate_content(self, contents: Any, **_kwargs) -> Any:
        text = _extract_text_from_contents(contents)
        for sample_id, resp in self.responses_by_id.items():
            company = resp.get("company")
            title = resp.get("title")
            if f"[ID:{sample_id}]" in text or sample_id in text:
                return SimpleNamespace(text=json.dumps(resp))
            if company and company.lower() in text.lower():
                return SimpleNamespace(text=json.dumps(resp))
            if title and title.lower() in text.lower():
                return SimpleNamespace(text=json.dumps(resp))

        # Check negative sample indicator
        if "pycon" in text.lower() or "yc batch" in text.lower():
            return SimpleNamespace(text=json.dumps(self.responses_by_id["negative_forum_chatter"]))

        return SimpleNamespace(text='{"title": null, "company": null, "remote_ok": false, "required_skills": []}')


# ─── Evaluation Runner ───────────────────────────────────────────────────────
async def run_evaluation(mock_mode: bool = False) -> tuple[float, list[SampleScore]]:
    """Execute evaluation benchmark across all dataset samples."""
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    settings = get_settings()
    is_live = bool(settings.gemini_api_key and not mock_mode)

    mode_color = "green" if is_live else "yellow"
    mode_text = "LIVE (Gemini 3.5 Flash Lite)" if is_live else "OFFLINE MOCK (Deterministic)"
    console.print(
        Panel.fit(
            f"[bold cyan]NEXUS LLM Extraction Evaluation Suite[/bold cyan]\n"
            f"Dataset: [white]{len(dataset)} hand-labelled ground-truth samples[/white]\n"
            f"Execution Mode: [{mode_color}]{mode_text}[/{mode_color}]",
            box=box.ROUNDED,
        )
    )

    extractor = ListingExtractor()
    if not is_live:
        # Patch client with mock responses for fast deterministic run
        fake_model = MockModelClient(MOCK_RESPONSES)
        extractor._client = SimpleNamespace(aio=SimpleNamespace(models=fake_model))
        from app.pipeline import extractor as ext_mod
        async def _noop(): pass
        ext_mod._extractor_limiter.acquire = _noop

    scores: list[SampleScore] = []

    with console.status("[bold blue]Running extraction benchmarks...", spinner="dots"):
        for item in dataset:
            sample_id = item["id"]
            source = item.get("source", "Unknown")
            raw_text = item["raw_text"]
            expected = item["expected"]

            # If mock mode, embed sample_id in raw_text header so mock model identifies it
            eval_input = f"[ID:{sample_id}]\n{raw_text}" if not is_live else raw_text

            try:
                pred = await extractor.extract(eval_input)
            except Exception as exc:
                scores.append(
                    SampleScore(
                        sample_id=sample_id,
                        source=source,
                        title_score=0.0,
                        company_score=0.0,
                        remote_score=0.0,
                        experience_score=0.0,
                        skills_f1=0.0,
                        overall_sample_score=0.0,
                        predicted=None,
                        expected=expected,
                        error=str(exc),
                    )
                )
                continue

            # Field-level scoring
            if expected.get("is_job_listing") is False:
                # Negative sample: must reject (title and company null)
                t_score = 1.0 if (pred is None or pred.title is None) else 0.0
                c_score = 1.0 if (pred is None or pred.company is None) else 0.0
                rem_score = 1.0 if (pred is None or not pred.remote_ok) else 0.0
                exp_score = 1.0 if (pred is None or pred.experience_level is None) else 0.0
                s_f1 = 1.0 if (pred is None or not pred.required_skills) else 0.0
            else:
                if pred is None:
                    t_score = c_score = rem_score = exp_score = s_f1 = 0.0
                else:
                    t_score = string_similarity(pred.title, expected["title"])
                    c_score = string_similarity(pred.company, expected["company"])
                    rem_score = 1.0 if pred.remote_ok == expected["remote_ok"] else 0.0
                    exp_score = experience_level_match(pred.experience_level, expected["experience_level"])
                    _, _, s_f1 = calculate_skills_f1(pred.required_skills, expected["required_skills"])

            # Weighted overall score for this sample
            # Title (25%), Company (25%), Skills (25%), Remote (15%), Experience (10%)
            overall = (
                0.25 * t_score
                + 0.25 * c_score
                + 0.25 * s_f1
                + 0.15 * rem_score
                + 0.10 * exp_score
            )

            scores.append(
                SampleScore(
                    sample_id=sample_id,
                    source=source,
                    title_score=t_score,
                    company_score=c_score,
                    remote_score=rem_score,
                    experience_score=exp_score,
                    skills_f1=s_f1,
                    overall_sample_score=overall,
                    predicted=pred,
                    expected=expected,
                )
            )

    # ─── Render Results Tables ───────────────────────────────────────────────
    details_table = Table(
        title="Sample-by-Sample Extraction Performance",
        box=box.SIMPLE_HEAVY,
        header_style="bold magenta",
        show_lines=True,
    )
    details_table.add_column("Sample ID", style="cyan", no_wrap=True)
    details_table.add_column("Source", style="dim")
    details_table.add_column("Title Match", justify="center")
    details_table.add_column("Company Match", justify="center")
    details_table.add_column("Remote OK", justify="center")
    details_table.add_column("Exp Level", justify="center")
    details_table.add_column("Skills F1", justify="center")
    details_table.add_column("Accuracy", justify="right", style="bold")

    def fmt_pct(val: float) -> str:
        color = "green" if val >= 0.85 else "yellow" if val >= 0.60 else "red"
        return f"[{color}]{val * 100:.1f}%[/{color}]"

    for s in scores:
        details_table.add_row(
            s.sample_id,
            s.source,
            fmt_pct(s.title_score),
            fmt_pct(s.company_score),
            fmt_pct(s.remote_score),
            fmt_pct(s.experience_score),
            fmt_pct(s.skills_f1),
            fmt_pct(s.overall_sample_score),
        )

    console.print("\n")
    console.print(details_table)

    # Aggregate Metrics
    avg_title = sum(s.title_score for s in scores) / len(scores)
    avg_company = sum(s.company_score for s in scores) / len(scores)
    avg_remote = sum(s.remote_score for s in scores) / len(scores)
    avg_exp = sum(s.experience_score for s in scores) / len(scores)
    avg_skills = sum(s.skills_f1 for s in scores) / len(scores)
    composite_accuracy = sum(s.overall_sample_score for s in scores) / len(scores)

    summary_table = Table(
        title="Aggregated Evaluation Metrics",
        box=box.ROUNDED,
        header_style="bold green",
    )
    summary_table.add_column("Evaluated Metric Dimension", style="white")
    summary_table.add_column("Target Threshold", justify="center", style="dim")
    summary_table.add_column("Achieved Score", justify="right", style="bold")
    summary_table.add_column("Status", justify="center")

    def add_metric_row(name: str, score: float, target: float = 0.80):
        passed = score >= target
        status = "[bold green]PASS[/bold green]" if passed else "[bold red]FAIL[/bold red]"
        summary_table.add_row(name, f"{target * 100:.0f}%", fmt_pct(score), status)

    add_metric_row("Job Title Extraction Accuracy", avg_title, target=0.85)
    add_metric_row("Company Name Extraction Accuracy", avg_company, target=0.85)
    add_metric_row("Remote Classification Accuracy", avg_remote, target=0.85)
    add_metric_row("Experience Level Mapping Accuracy", avg_exp, target=0.80)
    add_metric_row("Skills Token Overlap (Mean F1-Score)", avg_skills, target=0.75)
    add_metric_row("Overall Composite Accuracy", composite_accuracy, target=0.80)

    console.print(summary_table)

    color = "bold green" if composite_accuracy >= 0.80 else "bold red"
    console.print(
        f"\n[{color}]Overall Extraction Benchmark Score: {composite_accuracy * 100:.2f}%[/{color}]\n"
    )

    return composite_accuracy, scores


# ─── Standalone CLI Entry Point ──────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NEXUS Extraction Evaluation Suite")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run in deterministic offline mock mode (skips Gemini API calls)",
    )
    args = parser.parse_args()

    accuracy, _ = asyncio.run(run_evaluation(mock_mode=args.mock))
    if accuracy < 0.80:
        raise SystemExit(1)
    raise SystemExit(0)
