"""ContextWindowGuard — DoS via context overflow (LLM04)."""

from __future__ import annotations

from .engine import Guardrail, GuardrailResult


class ContextWindowGuard(Guardrail):
    name = "context_length"
    is_input = True

    def __init__(self, max_tokens: int = 32_768, threshold: float = 0.8):
        self.max_tokens = max_tokens
        self.threshold = threshold

    async def check(self, text: str, context: str | None = None) -> GuardrailResult:
        toks = len(text.split())  # rough approximation
        ratio = toks / self.max_tokens
        passed = ratio < self.threshold
        return GuardrailResult(
            name=self.name,
            passed=passed,
            score=ratio,
            reason=f"Context uses {toks} tokens (capacity {self.max_tokens})",
            severity="warning" if ratio < 1.0 else "critical",
        )


__all__ = ["ContextWindowGuard"]
