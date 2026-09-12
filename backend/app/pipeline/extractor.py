"""
NEXUS — LLM Structured Extraction & Validation.

Feeds raw scraped listing text into **Google Gemini** and parses the response
into a validated Pydantic schema.  Implements:

* **Extraction caching** — SHA-256 of the raw text is checked against an
  in-memory cache.  If a previous extraction exists, the cached result is
  returned immediately without calling Gemini.
* **Retry with repair** — up to ``MAX_RETRIES`` attempts.  On a Pydantic
  ``ValidationError`` the error context is sent back to Gemini in a "repair"
  prompt so it can fix its own output.
* **Graceful rejection** — if all retries fail the listing is skipped and
  logged; the pipeline **never crashes**.

Usage::

    extractor = ListingExtractor()
    result = await extractor.extract(raw_text)
    if result is not None:
        print(result.title, result.company)
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from google import genai
from google.genai import types
from pydantic import BaseModel, Field, ValidationError

from app.config import get_settings

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


# ─── Pydantic Schema for Extracted Listings ──────────────────────────────────
class ExtractedListing(BaseModel):
    """
    Validated schema for a job listing extracted by the LLM.

    Every field is nullable or has a default so that partial extractions
    don't crash the pipeline.
    """

    title: str = Field(..., description="Job title")
    company: str = Field(..., description="Company or organisation name")
    location: str | None = Field(None, description="City / region / 'Remote'")
    remote_ok: bool = Field(False, description="Whether the role is remote-friendly")
    stipend: str | None = Field(None, description="Salary, stipend, or compensation info")
    required_skills: list[str] = Field(
        default_factory=list,
        description="List of required skills, technologies, or qualifications",
    )
    experience_level: str | None = Field(
        None, description="e.g. 'intern', 'junior', 'mid', 'senior', 'lead'"
    )
    deadline: str | None = Field(None, description="Application deadline if mentioned")


# ─── System Prompt ───────────────────────────────────────────────────────────
_SYSTEM_PROMPT = """\
You are a precise data-extraction assistant.  Given a raw job listing text,
extract structured information and return it as a JSON object matching this
exact schema:

{
  "title": "<string>",
  "company": "<string>",
  "location": "<string or null>",
  "remote_ok": <true|false>,
  "stipend": "<string or null>",
  "required_skills": ["<skill1>", "<skill2>", ...],
  "experience_level": "<string or null>",
  "deadline": "<string or null>"
}

Rules:
- Return ONLY the JSON object, no markdown fences, no commentary.
- If a field is not mentioned in the text, use null (or false for booleans,
  or [] for lists).
- For "required_skills", list individual technologies / languages / tools.
- For "experience_level", normalise to one of: intern, junior, mid, senior,
  lead, or manager.  If unclear, use null.
- "stipend" should include the original currency and range if given.
"""

_REPAIR_PROMPT_TEMPLATE = """\
Your previous JSON response could not be parsed.  The validation error was:

{error}

Please fix the JSON and return a corrected version matching the schema.
Return ONLY the corrected JSON object.
"""


# ─── Extractor Class ─────────────────────────────────────────────────────────
class ListingExtractor:
    """
    Stateful extractor with an in-memory cache keyed by raw-text SHA-256.
    """

    def __init__(self) -> None:
        # Construct the SDK client only when it is actually needed.  This
        # allows the scraper/orchestrator to start in degraded mode when a
        # deployment has no Gemini key, and lets extract() turn that into a
        # normal failed record instead of a process-startup exception.
        self._client: genai.Client | None = None
        self._model = "gemini-2.0-flash"
        self._cache: dict[str, ExtractedListing] = {}

    @staticmethod
    def _text_hash(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    async def extract(self, raw_text: str) -> ExtractedListing | None:
        """
        Extract structured listing data from *raw_text*.

        Returns ``None`` if extraction fails after all retries.
        """
        # Do not send empty input to the provider.  Besides avoiding a paid
        # request, this makes malformed scraper output a harmless skip.
        if not raw_text or not raw_text.strip():
            logger.warning("[extractor] Empty raw listing; skipping extraction.")
            return None

        text_hash = self._text_hash(raw_text)

        # ── Cache hit ────────────────────────────────────────────────────
        if text_hash in self._cache:
            logger.debug("Extraction cache hit for %s…", text_hash[:12])
            return self._cache[text_hash]

        # ── Initial extraction call ──────────────────────────────────────
        messages: list[types.Content] = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(
                    text=f"Extract structured job data from this listing:\n\n{raw_text}"
                )],
            )
        ]

        last_error: str = ""
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                if self._client is None:
                    settings = get_settings()
                    self._client = genai.Client(api_key=settings.gemini_api_key)
                if attempt > 1 and last_error:
                    # Repair prompt — feed the error back
                    messages.append(
                        types.Content(
                            role="user",
                            parts=[types.Part.from_text(
                                text=_REPAIR_PROMPT_TEMPLATE.format(error=last_error)
                            )],
                        )
                    )

                response = await self._client.aio.models.generate_content(
                    model=self._model,
                    contents=messages,
                    config=types.GenerateContentConfig(
                        system_instruction=_SYSTEM_PROMPT,
                        temperature=0.1,
                        max_output_tokens=1024,
                    ),
                )

                response_text = response.text.strip() if response.text else ""
                if not response_text:
                    last_error = "Empty response from model."
                    logger.warning(
                        "[extractor] Attempt %d/%d: empty response.",
                        attempt, MAX_RETRIES,
                    )
                    continue

                # Strip markdown code fences if the model wraps the JSON
                if response_text.startswith("```"):
                    lines = response_text.splitlines()
                    # Remove first and last lines (``` markers)
                    lines = [
                        l for l in lines
                        if not l.strip().startswith("```")
                    ]
                    response_text = "\n".join(lines).strip()

                # ── Parse JSON ───────────────────────────────────────────
                parsed: dict[str, Any] = json.loads(response_text)

                # ── Validate with Pydantic ───────────────────────────────
                result = ExtractedListing.model_validate(parsed)

                # ── Cache and return ─────────────────────────────────────
                self._cache[text_hash] = result
                logger.info(
                    "[extractor] Extracted: %s @ %s (attempt %d)",
                    result.title, result.company, attempt,
                )
                return result

            except json.JSONDecodeError as exc:
                last_error = f"JSON decode error: {exc}"
                logger.warning(
                    "[extractor] Attempt %d/%d: %s",
                    attempt, MAX_RETRIES, last_error,
                )
            except ValidationError as exc:
                last_error = str(exc)
                logger.warning(
                    "[extractor] Attempt %d/%d: Pydantic validation error: %s",
                    attempt, MAX_RETRIES, last_error,
                )
            except Exception as exc:
                last_error = f"Unexpected error: {exc}"
                logger.error(
                    "[extractor] Attempt %d/%d: %s",
                    attempt, MAX_RETRIES, last_error,
                )

        # ── All retries exhausted ────────────────────────────────────────
        logger.error(
            "[extractor] Failed to extract after %d attempts. "
            "Skipping listing (hash=%s…). Last error: %s",
            MAX_RETRIES, text_hash[:12], last_error,
        )
        return None
