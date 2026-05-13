"""FactualConsistency — cross-check assertions against provided context."""

from __future__ import annotations

from .engine import Guardrail, GuardrailResult


class FactualConsistency(Guardrail):
    name = "factual"
    is_output = True

    async def check(self, text: str, context: str | None = None) -> GuardrailResult:
        if not context:
            return GuardrailResult(name=self.name, passed=True, score=0.0)
        # Very simple keyword overlap check
        ctx_words = set(context.lower().split())
        out_words = set(text.lower().split())
        overlap = len(ctx_words & out_words) / max(len(ctx_words), 1)
        passed = overlap >= 0.1
        return GuardrailResult(
            name=self.name,
            passed=passed,
            score=1.0 - overlap,
            reason=f"Context overlap {overlap:.1%}" if not passed else None,
            severity="warning",
        )


__all__ = ["FactualConsistency"]
