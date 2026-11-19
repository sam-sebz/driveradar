"""One small interface for every LLM provider. Switching provider is a config change."""

from typing import Any, Protocol


class LLMError(Exception):
    """The provider failed, refused, timed out or returned no usable text."""


class LLMClient(Protocol):
    name: str

    def generate_json(self, system: str, user: str, schema: dict[str, Any]) -> str:
        """Return a JSON string that should match `schema`. Raise LLMError on failure."""
        ...
