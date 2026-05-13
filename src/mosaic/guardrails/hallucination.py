"""HallucinationDetector — compares output with context (LLM05)."""

from __future__ import annotations

from typing import Optional

from .engine import Guardrail, GuardrailResult
from mosaic.adapters.base import ModelAdapter


class HallucinationDetector(Guardrail):
    name = "hallucination"
    is_output = True

    def __init__(self, model: Optional[ModelAdapter] = None, threshold: float = 0.5):
        self.model = model
        self.threshold = threshold

    async def check(self, text: str, context: str | None = None) -> GuardrailResult:
        if not context:
            return GuardrailResult(
                name=self.name,
                passed=True,
                score=0.0,
                reason="No context for fact-check",
            )
        # Simple keyword-based heuristic fallback
        ctx_lower = context.lower()
        out_lower = text.lower()
        unverified = [
            word for word in out_lower.split()
            if word not in ctx_lower and len(word) > 5
        ]
        hallucination_rate = len(unverified) / max(len(out_lower.split()), 1)
        passed = hallucination_rate < self.threshold
        return GuardrailResult(
            name=self.name,
            passed=passed,
            score=hallucination_rate,
            reason=f"Unverified terms: {', '.join(unverified[:5])}..." if unverified else None,
            severity="critical" if not passed else "info",
        )


__all__ = ["HallucinationDetector"]
