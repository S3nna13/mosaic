"""PII/secret guardrails (LLM06)."""

from __future__ import annotations

from mosaic.security.privacy import PrivacyFilter

from .engine import Guardrail, GuardrailResult


class PIIDetector(Guardrail):
    name = "pii"
    is_input = True

    async def check(self, text: str, context: str | None = None) -> GuardrailResult:
        pii = PrivacyFilter.detect_pii(text)
        passed = len(pii) == 0
        return GuardrailResult(
            name=self.name,
            passed=passed,
            score=min(1.0, sum(len(v) for v in pii.values()) * 0.1),
            reason=f"PII types: {', '.join(pii.keys())}" if pii else None,
            severity="warning",
        )


class SecretsScanner(Guardrail):
    name = "secrets"
    is_input = True

    async def check(self, text: str, context: str | None = None) -> GuardrailResult:
        secrets = PrivacyFilter.detect_secrets(text)
        passed = len(secrets) == 0
        return GuardrailResult(
            name=self.name,
            passed=passed,
            score=min(1.0, sum(len(v) for v in secrets.values()) * 0.2),
            severity="critical",
        )


__all__ = ["PIIDetector", "SecretsScanner"]
