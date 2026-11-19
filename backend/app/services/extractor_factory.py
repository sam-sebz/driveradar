import logging

from app.core.config import Settings
from app.domain.extraction.base import Extractor
from app.domain.extraction.llm_extractor import LLMExtractor
from app.domain.extraction.rules import RuleBasedExtractor
from app.domain.llm.client import LLMClient

logger = logging.getLogger("driveradar.llm")


def build_llm_client(settings: Settings) -> LLMClient | None:
    """None means "use the offline rule-based extractor" (LLM_PROVIDER=mock or no key)."""
    provider = settings.llm_provider
    if provider == "mock":
        return None
    key_setting = {
        "openai": settings.openai_api_key,
        "anthropic": settings.anthropic_api_key,
        "gemini": settings.gemini_api_key,
    }[provider]
    if key_setting is None or not key_setting.get_secret_value():
        logger.warning("llm_key_missing", extra={"provider": provider, "using": "mock"})
        return None
    key = key_setting.get_secret_value()
    timeout = settings.llm_timeout_seconds
    if provider == "anthropic":
        from app.domain.llm.anthropic_client import AnthropicClient

        return AnthropicClient(key, settings.llm_model, timeout)
    from app.domain.llm.http_clients import GeminiClient, OpenAIClient

    if provider == "openai":
        return OpenAIClient(key, settings.llm_model, timeout)
    return GeminiClient(key, settings.llm_model, timeout)


def build_extractor(settings: Settings) -> Extractor:
    client = build_llm_client(settings)
    rules = RuleBasedExtractor()
    return rules if client is None else LLMExtractor(client, rules)
