"""OpenAI adapter — OpenAI SDK (ChatCompletion) backend."""

from __future__ import annotations

import openai
from openai import OpenAI

from mosaic.adapters.base import BaseAdapter, Message, ModelResponse


class OpenAIAdapter(BaseAdapter):
    name = "openai"

    def __init__(
        self, api_key: str, model: str = "gpt-4o-mini", base_url: str | None = None
    ):
        self.model = model
        self.client = OpenAI(
            api_key=api_key, base_url=base_url or "https://api.openai.com/v1"
        )
        self._models_cache: list[str] | None = None

    def chat(self, messages: list[Message], **kwargs) -> ModelResponse:
        oa_messages = []
        for m in messages:
            if m.images:
                content_parts = [{"type": "text", "text": m.content}]
                for img in m.images:
                    content_parts.append(
                        {"type": "image_url", "image_url": {"url": img.source}}
                    )
                oa_messages.append({"role": m.role, "content": content_parts})
            else:
                oa_messages.append({"role": m.role, "content": m.content})
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=oa_messages,
                temperature=kwargs.get("temperature", 0.7),
                max_tokens=kwargs.get("max_tokens", 1024),
                top_p=kwargs.get("top_p", 0.9),
            )
            msg = resp.choices[0].message
            return ModelResponse(
                content=msg.content or "",
                model=resp.model,
                usage={
                    "prompt_tokens": resp.usage.prompt_tokens,
                    "completion_tokens": resp.usage.completion_tokens,
                    "total_tokens": resp.usage.total_tokens,
                },
                raw=resp.model_dump(),
            )
        except openai.RateLimitError as e:
            raise RuntimeError(f"OpenAI rate limited: {e}") from e
        except openai.APIError as e:
            raise RuntimeError(f"OpenAI API error: {e}") from e

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
