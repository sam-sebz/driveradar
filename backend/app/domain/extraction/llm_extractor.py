"""LLM extraction: JSON schema output, Pydantic validation, one retry, then rule fallback."""

import logging
import time

from pydantic import ValidationError

from app.domain.extraction.base import ExtractionResult
from app.domain.extraction.models import DriveInfo, llm_json_schema
from app.domain.extraction.rules import RuleBasedExtractor
from app.domain.llm.client import LLMClient, LLMError

logger = logging.getLogger("driveradar.extraction")

MAX_NOTICE_CHARS = 60_000

SYSTEM_PROMPT = """You extract facts from Indian campus placement notices into JSON.
Rules:
- Use only what the notice states. If a value is not stated, use null. Never guess.
- Money: CTC in lakhs per annum (6,00,000 INR = 6.0). Stipend and penalties in INR.
- Dates are Indian Standard Time. Deadline as ISO 8601 with +05:30. If no time is given,
  use 23:59.
- "No active backlogs" or "no standing arrears" means max_active_backlogs = 0.
- "No bond" means bond_years = 0.
- If the notice gives a UG percentage instead of CGPA, fill min_ug_percent, not min_cgpa.
- Only describe the single role in the text you are given."""


class LLMExtractor:
    def __init__(self, client: LLMClient, fallback: RuleBasedExtractor | None = None) -> None:
        self.client = client
        self.fallback = fallback or RuleBasedExtractor()

    def run(self, text: str) -> ExtractionResult:
        if len(text) > MAX_NOTICE_CHARS:
            logger.warning("notice_too_long_for_llm", extra={"chars": len(text)})
            return ExtractionResult(self.fallback.extract(text), "mock_fallback")

        schema = llm_json_schema()
        base_prompt = f"Placement notice:\n<notice>\n{text}\n</notice>"
        prompt = base_prompt
        for attempt in (1, 2):
            started = time.perf_counter()
            try:
                raw = self.client.generate_json(SYSTEM_PROMPT, prompt, schema)
            except LLMError as exc:
                logger.warning(
                    "llm_failed",
                    extra={"provider": self.client.name, "attempt": attempt, "error": str(exc)},
                )
                break
            try:
                info = DriveInfo.model_validate_json(raw)
            except ValidationError as exc:
                logger.info(
                    "llm_invalid_output",
                    extra={
                        "provider": self.client.name,
                        "attempt": attempt,
                        "errors": exc.error_count(),
                    },
                )
                prompt = (
                    f"{base_prompt}\n\nYour previous JSON failed validation:\n"
                    f"{exc}\nReturn corrected JSON only."
                )
                continue
            logger.info(
                "llm_extracted",
                extra={
                    "provider": self.client.name,
                    "attempt": attempt,
                    "latency_ms": round((time.perf_counter() - started) * 1000),
                },
            )
            return ExtractionResult(info, self.client.name)
        return ExtractionResult(self.fallback.extract(text), "mock_fallback")
