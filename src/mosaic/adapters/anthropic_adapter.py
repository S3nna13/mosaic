"""Anthropic adapter — Claude API backend."""

from __future__ import annotations

from anthropic import Anthropic, APIError, RateLimitError

from mosaic.adapters.base import BaseAdapter, Message, ModelResponse


class AnthropicAdapter(BaseAdapter):
    name = "anthropic"

    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022"):
        self.model = model
        self.client = Anthropic(api_key=api_key)
        self._models_cache: list[str] | None = None

    def chat(self, messages: list[Message], **kwargs) -> ModelResponse:
        system_msg = ""
        formatted: list[dict] = []
        for m in messages:
            if m.role == "system":
                system_msg = m.content
            else:
                if m.images:
                    blocks = []
                    for img in m.images:
                        blocks.append(
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": img.mime_type,
                                    "data": "...",
                                },  # base64 requires conversion
                            }
                        )
                    blocks.append({"type": "text", "text": m.content})
                    formatted.append({"role": m.role, "content": blocks})
                else:
                    formatted.append({"role": m.role, "content": m.content})

        try:
            resp = self.client.messages.create(
                model=self.model,
                system=system_msg or None,
                messages=formatted,
                max_tokens=kwargs.get("max_tokens", 1024),
                temperature=kwargs.get("temperature", 0.7),
                top_p=kwargs.get("top_p", 0.9),
            )
            text = resp.content[0].text if resp.content else ""
            return ModelResponse(
                content=text,
                model=resp.model,
                usage={
                    "input_tokens": resp.usage.input_tokens,
                    "output_tokens": resp.usage.output_tokens,
                },
                raw=resp.model_dump(),
            )
        except RateLimitError as e:
            raise RuntimeError(f"Anthropic rate limited: {e}") from e
        except APIError as e:
            raise RuntimeError(f"Anthropic API error: {e}") from e

    def list_models(self) -> list[str]:
        if self._models_cache is None:
            try:
                models = self.client.models.list()
                self._models_cache = [m.id for m in models.data]
            except Exception:
                self._models_cache = []
        return self._models_cache

    def health(self) -> bool:
        try:
            self.client.models.list()
            return True
        except Exception:
            return False
