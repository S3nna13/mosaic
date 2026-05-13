"""Guardrail base types + pipeline orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field

# Optional MITRE mapper — guardrails work without it
try:
    from mosaic.tools.attack_mapper import MITREMapper

    _mitre = MITREMapper()
except Exception:  # pragma: no cover
    _mitre = None


@dataclass
class GuardrailResult:
    name: str
    passed: bool
    score: float  # 0=pass, 1=fail  (or continuous risk score)
    reason: str | None = None
    severity: str = "info"  # info | warning | critical
    redacted: str | None = None
    mitre_techniques: list[str] = field(default_factory=list)  # mapped ATT&CK IDs


class Guardrail:
    name: str

    async def check(self, text: str, context: str | None = None) -> GuardrailResult:
        raise NotImplementedError


class GuardrailPipeline:
    """Sequential orchestration of multiple guardrails."""

    def __init__(self, rails: list[type[Guardrail]]):
        instances = []
        for r in rails:
            if isinstance(r, type):
                instances.append(r())
            else:
                instances.append(r)
        self._instances = instances

    async def check_input(self, text: str) -> list[GuardrailResult]:
        results = [
            await r.check(text)
            for r in self._instances
            if getattr(r, "is_input", False)
        ]
        # Enrich with MITRE mapping
        if _mitre is not None:
            for r in results:
                if not r.passed:
                    techs = _mitre.map_finding(
                        {"reason": r.reason or "", "type": r.name}
                    )
                    r.mitre_techniques = [t.id for t in techs]
        return results

    async def check_output(
        self, text: str, context: str | None = None
    ) -> list[GuardrailResult]:
        results = [
            await r.check(text, context)
            for r in self._instances
            if getattr(r, "is_output", False)
        ]
        if _mitre is not None:
            for r in results:
                if not r.passed:
                    techs = _mitre.map_finding(
                        {"reason": r.reason or "", "type": r.name}
                    )
                    r.mitre_techniques = [t.id for t in techs]
        return results

    # Convenience helpers
    @staticmethod
    def default_input() -> GuardrailPipeline:
        from .context import ContextWindowGuard
        from .injection import PromptInjectionDetector
        from .jailbreak import JailbreakDetector
        from .pii import PIIDetector, SecretsScanner
        from .toxicity import ToxicityGuardrail

        return GuardrailPipeline(
            [
                JailbreakDetector,
                PromptInjectionDetector,
                ToxicityGuardrail,
                PIIDetector,
                SecretsScanner,
                ContextWindowGuard,
            ]
        )

    @staticmethod
    def default_output() -> GuardrailPipeline:
        from .factual import FactualConsistency
        from .hallucination import HallucinationDetector
        from .output import OutputValidator, StructuredOutputValidator
        from .rate_limit import DoSProtectionGuard

        return GuardrailPipeline(
            [
                HallucinationDetector,
                FactualConsistency,
                OutputValidator,
                StructuredOutputValidator,
                DoSProtectionGuard,
            ]
        )


__all__ = [
    "Guardrail",
    "GuardrailPipeline",
    "GuardrailResult",
]
