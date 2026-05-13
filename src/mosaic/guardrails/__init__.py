"""Guardrails — 14-rail OWASP LLM Top-10 coverage."""
from __future__ import annotations

from .engine import Guardrail, GuardrailResult, GuardrailPipeline
from .jailbreak import JailbreakDetector
from .injection import PromptInjectionDetector
from .toxicity import ToxicityGuardrail, ToxicityFilter
from .pii import PIIDetector
from .secrets import SecretsScanner
from .context import ContextWindowGuard
from .rag import RAGPoisoningDetector
from .output import OutputValidator, StructuredOutputValidator
from .constitutional import ConstitutionalCritique
from .factual import FactualConsistency
from .hallucination import HallucinationDetector
from .rate_limit import DoSProtectionGuard

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
    "Guardrail",
    "GuardrailResult",
    "GuardrailPipeline",
    "JailbreakDetector",
    "PromptInjectionDetector",
    "ToxicityGuardrail",
    "ToxicityFilter",
    "PIIDetector",
    "SecretsScanner",
    "ContextWindowGuard",
    "RAGPoisoningDetector",
    "StructuredOutputValidator",
    "ConstitutionalCritique",
    "FactualConsistency",
    "HallucinationDetector",
    "OutputValidator",
    "DoSProtectionGuard",
    "ALL_RAILS",
]
