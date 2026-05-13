"""ToxicityGuardrail + ToxicityFilter (LLM02)."""

from __future__ import annotations

from typing import ClassVar

from .engine import Guardrail, GuardrailResult

TOXIC_KEYWORDS = [
    "hate",
    "kill yourself",
    "murder",
    "bomb",
    "terrorist",
    "racist",
    "sexist",
    "bigot",
    "fuck you",
    "die",
    "worthless",
]


class ToxicityGuardrail(Guardrail):
    name = "toxicity"
    is_input = True

    def __init__(self, threshold: float = 0.25):
        self.threshold = threshold

    async def check(self, text: str, context: str | None = None) -> GuardrailResult:
        lower = text.lower()
        hits = [w for w in TOXIC_KEYWORDS if w in lower]
        risk = min(1.0, len(hits) * 0.2)
        return GuardrailResult(
            name=self.name,
            passed=risk < self.threshold,
            score=risk,
            reason=f"Toxic terms: {', '.join(hits)}" if hits else None,
            severity="warning",
        )


class ToxicityFilter(Guardrail):
    name = "toxicity_filter"
    is_output = True  # sanitize outputs

    TOXIC_MAP: ClassVar = {
        "fuck": "f***",
        "shit": "s***",
        "damn": "d***",
    }

    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    async def check(self, text: str, context: str | None = None) -> GuardrailResult:
        if not self.enabled:
            return GuardrailResult(name=self.name, passed=True, score=0.0)
        filtered = text
        for bad, good in self.TOXIC_MAP.items():
            filtered = filtered.replace(bad, good)
        return GuardrailResult(
            name=self.name,
            passed=True,
            score=0.0,
            redacted=filtered if filtered != text else None,
        )


__all__ = ["ToxicityFilter", "ToxicityGuardrail"]
