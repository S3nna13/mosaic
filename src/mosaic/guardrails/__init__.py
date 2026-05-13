"""Guardrails — 14-rail OWASP LLM Top-10 coverage."""

from __future__ import annotations

from .constitutional import ConstitutionalCritique
from .context import ContextWindowGuard
from .engine import Guardrail, GuardrailPipeline, GuardrailResult
from .factual import FactualConsistency
from .hallucination import HallucinationDetector
from .injection import PromptInjectionDetector
from .jailbreak import JailbreakDetector
from .output import OutputValidator, StructuredOutputValidator
from .pii import PIIDetector
from .rag import RAGPoisoningDetector
from .rate_limit import DoSProtectionGuard
from .pii import SecretsScanner
from .toxicity import ToxicityFilter, ToxicityGuardrail

# Convenience: expose the full set
ALL_RAILS = [
    JailbreakDetector,
    PromptInjectionDetector,
    ToxicityGuardrail,
    ToxicityFilter,
    PIIDetector,
    SecretsScanner,
    ContextWindowGuard,
    RAGPoisoningDetector,
    StructuredOutputValidator,
    ConstitutionalCritique,
    FactualConsistency,
    HallucinationDetector,
    OutputValidator,
    DoSProtectionGuard,
]

__all__ = [
    "ALL_RAILS",
    "ConstitutionalCritique",
    "ContextWindowGuard",
    "DoSProtectionGuard",
    "FactualConsistency",
    "Guardrail",
    "GuardrailPipeline",
    "GuardrailResult",
    "HallucinationDetector",
    "JailbreakDetector",
    "OutputValidator",
    "PIIDetector",
    "PromptInjectionDetector",
    "RAGPoisoningDetector",
    "SecretsScanner",
    "StructuredOutputValidator",
    "ToxicityFilter",
    "ToxicityGuardrail",
]
