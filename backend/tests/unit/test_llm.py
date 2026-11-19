import json
from pathlib import Path
from typing import Any

import anthropic
import httpx
import httpx2
import pytest

from app.core.config import Settings
from app.domain.extraction.llm_extractor import MAX_NOTICE_CHARS, LLMExtractor
from app.domain.extraction.models import llm_json_schema
from app.domain.extraction.rules import RuleBasedExtractor
from app.domain.llm.anthropic_client import AnthropicClient
from app.domain.llm.client import LLMError
from app.domain.llm.http_clients import GeminiClient, OpenAIClient
from app.services.extractor_factory import build_extractor, build_llm_client
from tests.conftest import make_settings


class FakeClient:
    name = "fake"

    def __init__(self, replies: list[str | Exception]) -> None:
        self.replies = replies
        self.prompts: list[str] = []

    def generate_json(self, system: str, user: str, schema: dict[str, Any]) -> str:
        self.prompts.append(user)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


GOOD = json.dumps({"company": "Foo", "ctc_lpa_min": 5, "ctc_lpa_max": 6})
BAD = json.dumps({"company": "Foo", "ctc_lpa_min": 9, "ctc_lpa_max": 6})


def test_llm_success_first_try() -> None:
    result = LLMExtractor(FakeClient([GOOD])).run("CTC: 5-6 LPA")
    assert result.provider == "fake"
    assert result.info.company == "Foo"


def test_llm_retries_once_with_validation_error() -> None:
    client = FakeClient([BAD, GOOD])
    result = LLMExtractor(client).run("notice")
    assert result.provider == "fake"
    assert "failed validation" in client.prompts[1]


def test_llm_falls_back_to_rules_after_two_invalid_answers() -> None:
    result = LLMExtractor(FakeClient([BAD, "not json"])).run("CTC: 4 LPA")
    assert result.provider == "mock_fallback"
    assert result.info.ctc_lpa_min == 4.0


def test_llm_falls_back_on_provider_error() -> None:
    result = LLMExtractor(FakeClient([LLMError("down")])).run("CTC: 4 LPA")
    assert result.provider == "mock_fallback"


def test_llm_skips_overlong_notice() -> None:
    client = FakeClient([GOOD])
    result = LLMExtractor(client).run("x" * (MAX_NOTICE_CHARS + 1))
    assert result.provider == "mock_fallback"
    assert client.prompts == []


def test_schema_is_strict_and_complete() -> None:
    schema = llm_json_schema()
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])


# ---- providers with mocked HTTP --------------------------------------------------------


def _http(handler: Any) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_openai_client_parses_content() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        assert body["response_format"]["json_schema"]["strict"] is True
        assert req.headers["authorization"] == "Bearer k"
        return httpx.Response(200, json={"choices": [{"message": {"content": GOOD}}]})

    assert OpenAIClient("k", http=_http(handler)).generate_json("s", "u", {}) == GOOD


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500, json={}),
        httpx.Response(200, json={"choices": []}),
        httpx.Response(200, json={"choices": [{"message": {"refusal": "no"}}]}),
        httpx.Response(200, json={"choices": [{"message": {"content": ""}}]}),
        httpx.Response(200, text="<html>"),
    ],
)
def test_openai_client_errors(response: httpx.Response) -> None:
    with pytest.raises(LLMError):
        OpenAIClient("k", http=_http(lambda r: response)).generate_json("s", "u", {})


def test_network_error_becomes_llm_error() -> None:
    def boom(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    with pytest.raises(LLMError, match="Could not reach"):
        GeminiClient("k", http=_http(boom)).generate_json("s", "u", {})


def test_gemini_client_parses_text() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.headers["x-goog-api-key"] == "k"
        assert "key=" not in str(req.url)  # key must not leak into URLs / logs
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": GOOD}]}}]})

    assert GeminiClient("k", http=_http(handler)).generate_json("s", "u", {}) == GOOD
    with pytest.raises(LLMError):
        GeminiClient("k", http=_http(lambda r: httpx.Response(200, json={}))).generate_json(
            "s", "u", {}
        )


def _anthropic(handler: Any) -> AnthropicClient:
    # The anthropic SDK 2.x is built on httpx2, so it needs an httpx2 mock transport.
    http = httpx2.Client(transport=httpx2.MockTransport(handler))
    sdk = anthropic.Anthropic(api_key="k", http_client=http, max_retries=0)
    return AnthropicClient("k", sdk_client=sdk)


def _message(stop_reason: str, text: str | None = GOOD) -> dict[str, Any]:
    content = [{"type": "text", "text": text}] if text is not None else []
    return {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": "claude-opus-5-5",
        "content": content,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 10},
    }


def test_anthropic_client_sends_structured_output_request() -> None:
    seen: dict[str, Any] = {}

    def handler(req: httpx2.Request) -> httpx2.Response:
        seen.update(json.loads(req.content))
        seen["beta"] = req.headers.get("anthropic-beta", "")
        return httpx2.Response(200, json=_message("end_turn"))

    assert _anthropic(handler).generate_json("sys", "user", llm_json_schema()) == GOOD
    assert seen["model"] == "claude-opus-5-5"
    assert seen["output_config"]["format"]["type"] == "json_schema"
    assert seen["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in seen["beta"]


@pytest.mark.parametrize(
    "payload",
    [_message("refusal"), _message("max_tokens"), _message("end_turn", text=None)],
)
def test_anthropic_client_unusable_responses(payload: dict[str, Any]) -> None:
    with pytest.raises(LLMError):
        _anthropic(lambda r: httpx2.Response(200, json=payload)).generate_json("s", "u", {})


def test_anthropic_client_http_errors() -> None:
    with pytest.raises(LLMError, match="529"):
        _anthropic(lambda r: httpx2.Response(529, json={"type": "error"})).generate_json(
            "s", "u", {}
        )

    def boom(req: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("no route")

    with pytest.raises(LLMError, match="reach"):
        _anthropic(boom).generate_json("s", "u", {})


# ---- provider selection ------------------------------------------------------------------


def test_factory_defaults_to_mock(tmp_path: Path) -> None:
    assert isinstance(build_extractor(make_settings(tmp_path)), RuleBasedExtractor)


def test_factory_without_key_uses_mock(tmp_path: Path) -> None:
    s: Settings = make_settings(tmp_path, llm_provider="openai")
    assert build_llm_client(s) is None


@pytest.mark.parametrize(
    ("provider", "key_field", "cls"),
    [
        ("openai", "openai_api_key", OpenAIClient),
        ("gemini", "gemini_api_key", GeminiClient),
        ("anthropic", "anthropic_api_key", AnthropicClient),
    ],
)
def test_factory_builds_real_provider(
    tmp_path: Path, provider: str, key_field: str, cls: type
) -> None:
    s = make_settings(tmp_path, llm_provider=provider, **{key_field: "test-key"})
    assert isinstance(build_llm_client(s), cls)
    assert isinstance(build_extractor(s), LLMExtractor)
