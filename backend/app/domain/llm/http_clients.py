"""OpenAI and Gemini providers over their public REST APIs (httpx, no extra SDKs)."""

import json
from typing import Any

import httpx

from app.domain.llm.client import LLMError


def _post(
    client: httpx.Client, url: str, headers: dict[str, str], body: dict[str, Any]
) -> dict[str, Any]:
    try:
        res = client.post(url, headers=headers, json=body)
    except httpx.HTTPError as exc:
        raise LLMError(f"Could not reach {url.split('/')[2]}") from exc
    if res.status_code >= 400:
        raise LLMError(f"Provider returned HTTP {res.status_code}")
    try:
        data: dict[str, Any] = res.json()
    except json.JSONDecodeError as exc:
        raise LLMError("Provider returned invalid JSON") from exc
    return data


class OpenAIClient:
    name = "openai"
    url = "https://api.openai.com/v1/chat/completions"

    def __init__(
        self,
        api_key: str,
        model: str | None = None,
        timeout: float = 60.0,
        http: httpx.Client | None = None,
    ) -> None:
        self.model = model or "gpt-4o-mini"
        self._key = api_key
        self._http = http or httpx.Client(timeout=timeout)

    def generate_json(self, system: str, user: str, schema: dict[str, Any]) -> str:
        data = _post(
            self._http,
            self.url,
            {"Authorization": f"Bearer {self._key}"},
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {"name": "drive_info", "strict": True, "schema": schema},
                },
            },
        )
        try:
            message = data["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("Unexpected OpenAI response shape") from exc
        if message.get("refusal"):
            raise LLMError("The model declined this request")
        content = message.get("content")
        if not isinstance(content, str) or not content:
            raise LLMError("The model returned no text")
        return content


class GeminiClient:
    name = "gemini"

    def __init__(
        self,
        api_key: str,
        model: str | None = None,
        timeout: float = 60.0,
        http: httpx.Client | None = None,
    ) -> None:
        self.model = model or "gemini-2.5-flash"
        self._key = api_key
        self._http = http or httpx.Client(timeout=timeout)

    def generate_json(self, system: str, user: str, schema: dict[str, Any]) -> str:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent"
        )
        data = _post(
            self._http,
            url,
            {"x-goog-api-key": self._key},
            {
                "systemInstruction": {
                    "parts": [{"text": system + "\n\nJSON schema:\n" + json.dumps(schema)}]
                },
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": {"responseMimeType": "application/json"},
            },
        )
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("Unexpected Gemini response shape") from exc
        if not isinstance(text, str) or not text:
            raise LLMError("The model returned no text")
        return text
