"""RAGPoisoningDetector — detects malicious context in RAG inputs (LLM03)."""

from __future__ import annotations

from .engine import Guardrail, GuardrailResult


class RAGPoisoningDetector(Guardrail):
    name = "rag_poisoning"
    is_input = True

    SUSPICIOUS_PATTERNS = (
        "ignore all previous",
        "disregard the following",
        "override with these",
        "instead of that, use",
    )

    def __init__(self, threshold: float = 0.3):
        self.threshold = threshold

    async def check(self, text: str, context: str | None = None) -> GuardrailResult:
        if not context:
            # No retrieved context → skip
            return GuardrailResult(name=self.name, passed=True, score=0.0)
        hits = sum(1 for p in self.SUSPICIOUS_PATTERNS if p in text.lower())
        score = min(1.0, hits * 0.25)
        return GuardrailResult(
            name=self.name,
            passed=score < self.threshold,
            score=score,
            reason="Suspicious instruction injected into context" if hits else None,
            severity="warning",
        )


__all__ = ["RAGPoisoningDetector"]
