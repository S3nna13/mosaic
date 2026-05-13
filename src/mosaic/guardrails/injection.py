"""PromptInjectionDetector — 50+ fragment scanner (LLM01)."""

from __future__ import annotations

import re

from .engine import Guardrail, GuardrailResult


INJECT_FRAGMENTS = [
    "ignore previous",
    "ignore all instructions",
    "disregard previous",
    "disregard all",
    "forget your instructions",
    "forget your rules",
    "you are now",
    "you must now",
    "new instructions",
    "override your",
    "bypass your",
    "ignore your",
    "no restrictions",
    "not bound by",
    "without any rules",
    "free from your",
    "ignore system",
    "system prompt",
    "reveal your system",
    "print your system",
    "repeat your system",
    "  show me your prompt",
    "what are your instructions",
    "what are your rules",
]


class PromptInjectionDetector(Guardrail):
    name = "prompt_injection"
    is_input = True

    def __init__(self, threshold: float = 0.2):
        self.threshold = threshold

    async def check(self, text: str, context: str | None = None) -> GuardrailResult:
        lower = text.lower()
        hits = [f for f in INJECT_FRAGMENTS if f in lower]
        risk = min(1.0, len(hits) * 0.2)
        passed = risk < self.threshold
        return GuardrailResult(
            name=self.name,
            passed=passed,
            score=risk,
            reason=f"Injection fragments: {', '.join(hits)}" if hits else None,
            severity="critical" if not passed else "info",
        )


__all__ = ["PromptInjectionDetector"]
