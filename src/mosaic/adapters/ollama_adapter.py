"""Ollama adapter — local Ollama HTTP server backend."""
from __future__ import annotations

from typing import List, Optional

import httpx

from mosaic.adapters.base import BaseAdapter, Message, ModelResponse


class OllamaAdapter(BaseAdapter):
    name = "ollama"

    def __init__(self, host: str = "http://localhost:11434", model: str = "llama3.2:3b"):
        self.host = host.rstrip("/")
        self.model = model
        self._client = httpx.Client(timeout=60.0)

    def chat(self, messages: List[Message], **kwargs) -> ModelResponse:
        ollama_messages = [{"role": m.role, "content": m.content} for m in messages]
        payload = {
            "model": self.model,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", 0.7),
                "num_predict": kwargs.get("max_tokens", 1024),
                "top_p": kwargs.get("top_p", 0.9),
            },
        }
        resp = self._client.post(f"{self.host}/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return ModelResponse(
            content=data.get("message", {}).get("content", ""),
            model=self.model,
            usage={"prompt_tokens": data.get("prompt_eval_count", 0), "completion_tokens": data.get("eval_count", 0)},
            raw=data,
        )

    def list_models(self) -> List[str]:
        try:
            resp = self._client.get(f"{self.host}/api/tags")
            resp.raise_for_status()
            models = resp.json().get("models", [])
            return [m["name"] for m in models]
        except Exception:
            return []

    def health(self) -> bool:
        try:
            resp = self._client.get(f"{self.host}/api/tags")
            return resp.status_code == 200
        except Exception:
            return False

    def __del__(self):
        self._client.close()
