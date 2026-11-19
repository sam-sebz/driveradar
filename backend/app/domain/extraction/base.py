from dataclasses import dataclass
from typing import Protocol

from app.domain.extraction.models import DriveInfo


@dataclass(frozen=True)
class ExtractionResult:
    info: DriveInfo
    # "mock", "anthropic", "openai", "gemini", or "mock_fallback" when an LLM failed.
    provider: str


class Extractor(Protocol):
    def run(self, text: str) -> ExtractionResult: ...
