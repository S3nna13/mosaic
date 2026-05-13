"""ConstitutionalCritique — LLM-based principle review (Anthropic-style)."""

from __future__ import annotations

from typing import Optional

from .engine import Guardrail, GuardrailResult
from mosaic.model.transformer import MosaicTransformer  # full model used for self-critique  # local model for critique


PRINCIPLES = [
    (
        "Helpful and Harmless",
        ["bomb", "explosive", "weapon", "kill", "murder", "rape", 
         "assault", "abuse", "terrorist", "trafficking","harmful","dangerous"],
    ),
    ("Truthful", ["hallucinated", "fabricated", "made up", "false claim"]),
    ("Fair", ["discriminat", "racist", "sexist", "bigot"]),
]


class ConstitutionalCritique(Guardrail):
    name = "constitutional"
    is_output = True

    def __init__(self, critic: Optional[MosaicForCausalLM] = None):
        self.critic = critic

    async def check(self, text: str, context: str | None = None) -> GuardrailResult:
        if self.critic is None:
            # Fallback: simple keyword scan
            violations = []
            for principle, keywords in PRINCIPLES:
                for kw in keywords:
                    if kw in text.lower():
                        violations.append(f"{principle}: {kw}")
                        break
            passed = len(violations) == 0
            return GuardrailResult(
                name=self.name,
                passed=passed,
                score=min(1.0, len(violations) * 0.3),
                reason="; ".join(violations) if violations else None,
                severity="warning",
            )
        # Future: run critic model to produce score
        return GuardrailResult(name=self.name, passed=True, score=0.0)


__all__ = ["ConstitutionalCritique"]
