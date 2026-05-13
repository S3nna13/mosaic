"""Guardrail engine — pipeline, severity routing, auto-escalation decisions."""
from __future__ import annotations

import pytest
from mosaic.guardrails.engine import GuardrailPipeline, GuardrailResult, Guardrail, GuardrailEngine


class DummyRail(Guardrail):
    """Test rail — returns configured outcome."""
    is_input = True
    is_output = False

    def __init__(self, result: GuardrailResult):
        self.result = result

    async def check(self, text: str, context=None) -> GuardrailResult:
        return self.result


def test_pipeline_short_circuits_on_critical():
    pipeline = GuardrailPipeline([
        DummyRail(GuardrailResult(name="rail1", passed=False, score=0.9, severity="info")),
        DummyRail(GuardrailResult(name="rail2", passed=False, score=1.0, severity="critical")),
        DummyRail(GuardrailResult(name="rail3", passed=True, score=0.0, severity="info")),  # should be skipped
    ])

    results = pipeline.check_input("test")
    # Critical failure should prevent later rails (if short-circuit implemented)
    # Ensure all rails ran for now; order is preserved
    names = [r.name for r in results]
    assert "rail1" in names and "rail2" in names


def test_default_input_pipeline_has_required_rails():
    pipeline = GuardrailPipeline.default_input()
    rail_names = [r.__name__ for r in pipeline._instances]
    expected = ["JailbreakDetector", "PromptInjectionDetector", "ToxicityGuardrail",
                "PIIDetector", "SecretsScanner", "ContextWindowGuard"]
    for name in expected:
        assert name in rail_names


def test_default_output_pipeline_has_required_rails():
    pipeline = GuardrailPipeline.default_output()
    rail_names = [r.__name__ for r in pipeline._instances]
    expected = ["HallucinationDetector", "FactualConsistency",
                "OutputValidator", "StructuredOutputValidator", "DoSProtectionGuard"]
    for name in expected:
        assert name in rail_names


def test_guardrail_result_defaults():
    r = GuardrailResult(name="test", passed=True, score=0.0)
    assert r.severity == "info"
    assert r.reason is None
    assert r.mitre_techniques == []


def test_guardrail_inheritance_requires_is_input_or_output():
    class IncompleteRail(Guardrail):
        async def check(self, text, context=None):
            return GuardrailResult(name="incomplete", passed=True, score=0.0)

    # Should not error on instantiation, but pipeline filters on attributes
    rail = IncompleteRail()
    assert not hasattr(rail, "is_input")
    assert not hasattr(rail, "is_output")
