"""OutputValidator + StructuredOutputValidator (LLM07)."""

from __future__ import annotations

import json
import re

from .engine import Guardrail, GuardrailResult


class OutputValidator(Guardrail):
    name = "output_safety"
    is_output = True

    SAFE_PATTERNS = (
        (r"I cannot", 1.0),
        (r"I'm unable", 1.0)
    )

    async def check(self, text: str, context: str | None = None) -> GuardrailResult:
        # Basic keyword-based output filtering
        for pattern, _penalty in self.SAFE_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return GuardrailResult(
                    name=self.name,
                    passed=True,
                    score=0.0,
                    reason="Output contains safe refusal phrase",
                )
        return GuardrailResult(name=self.name, passed=True, score=0.0)


class StructuredOutputValidator(Guardrail):
    name = "structured_output"
    is_output = True

    def __init__(self, schema: dict | None = None, threshold: float = 0.3):
        self.schema = schema
        self.threshold = threshold

    async def check(self, text: str, context: str | None = None) -> GuardrailResult:
        if not self.schema:
            return GuardrailResult(name=self.name, passed=True, score=0.0)
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return GuardrailResult(
                name=self.name,
                passed=False,
                score=1.0,
                reason="Response is not valid JSON",
                severity="warning",
            )
        # Required field check
        required = set(self.schema.get("required", []))
        present = set(data.keys())
        missing = required - present
        passed = len(missing) == 0
        return GuardrailResult(
            name=self.name,
            passed=passed,
            score=len(missing) / max(len(required), 1),
            reason=f"Missing required fields: {', '.join(missing)}" if missing else None,
            severity="warning",
        )


__all__ = ["OutputValidator", "StructuredOutputValidator"]
