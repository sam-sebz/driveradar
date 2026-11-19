"""Claude via the official Anthropic SDK, using structured output (output_config.format)."""

from typing import Any

import anthropic

from app.domain.llm.client import LLMError

DEFAULT_MODEL = "claude-opus-5-5"


class AnthropicClient:
    name = "anthropic"

    def __init__(
        self,
        api_key: str,
        model: str | None = None,
        timeout: float = 60.0,
        sdk_client: anthropic.Anthropic | None = None,
    ) -> None:
        self.model = model or DEFAULT_MODEL
        self._client = sdk_client or anthropic.Anthropic(
            api_key=api_key, timeout=timeout, max_retries=2
        )

    def generate_json(self, system: str, user: str, schema: dict[str, Any]) -> str:
        try:
            response = self._client.beta.messages.create(
                model=self.model,
                max_tokens=16000,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_config={"format": {"type": "json_schema", "schema": schema}},
                # If a safety classifier declines, let the API retry on a fallback model.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.APIConnectionError as exc:
            raise LLMError("Could not reach the Anthropic API") from exc
        except anthropic.APIStatusError as exc:
            raise LLMError(f"Anthropic API error {exc.status_code}") from exc

        if response.stop_reason == "refusal":
            raise LLMError("The model declined this request")
        if response.stop_reason == "max_tokens":
            raise LLMError("The model output was cut off (max_tokens)")
        for block in response.content:
            if block.type == "text":
                return block.text
        raise LLMError("The model returned no text")
