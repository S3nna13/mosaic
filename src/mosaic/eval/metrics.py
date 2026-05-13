"""Metric primitives — reusable evaluation assertions."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class MetricResult:
    """Outcome of a metric measurement."""

    name: str
    score: float
    threshold: float | None = None
    passed: bool | None = None
    reason: str | None = None
    details: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.passed is None and self.threshold is not None:
            self.passed = self.score >= self.threshold
        elif self.passed is None:
            self.passed = self.score > 0


class Metric(ABC):
    name: str

    @abstractmethod
    async def measure(
        self, input: str, output: str, expected: str | None = None, **kwargs
    ) -> MetricResult:
        """Run the metric on (input, output, expected)."""


class ExactMatch(Metric):
    name = "exact_match"

    async def measure(
        self, input: str, output: str, expected: str | None = None, **kwargs
    ) -> MetricResult:
        score = 1.0 if output.strip() == (expected or "").strip() else 0.0
        return MetricResult(
            name=self.name,
            score=score,
            threshold=1.0,
            reason="Exact match" if score else "Mismatch",
        )


class Contains(Metric):
    name = "contains"

    async def measure(
        self, input: str, output: str, expected: str | None = None, **kwargs
    ) -> MetricResult:
        if expected is None:
            raise ValueError("Contains metric requires 'expected' substring")
        passed = expected in output
        return MetricResult(
            name=self.name,
            score=1.0 if passed else 0.0,
            threshold=1.0,
            reason=f"Expected '{expected[:30]}...' in output",
            passed=passed,
        )


class RegexMatch(Metric):
    name = "regex_match"

    def __init__(self, pattern: str):
        self.pattern = re.compile(pattern)

    async def measure(
        self, input: str, output: str, expected: str | None = None, **kwargs
    ) -> MetricResult:
        score = 1.0 if self.pattern.search(output) else 0.0
        return MetricResult(name=self.name, score=score, threshold=1.0)


# Stubs for LLM-based metrics that need a model adapter
class LLMJudge(Metric):
    name = "llm_judge"

    def __init__(self, model_adapter: Any, criteria: str = "correctness"):
        self.model = model_adapter
        self.criteria = criteria

    async def measure(
        self, input: str, output: str, expected: str | None = None, **kwargs
    ) -> MetricResult:
        # Placeholder: ask the model to score output against expected using the criteria
        return MetricResult(name=self.name, score=0.9, threshold=0.8)


class FactualCheck(Metric):
    name = "factual_check"

    def __init__(self, model_adapter: Any):
        self.model = model_adapter

    async def measure(
        self, input: str, output: str, expected: str | None = None, **kwargs
    ) -> MetricResult:
        # Call out to external fact-checker or call Mosaic model
        return MetricResult(name=self.name, score=0.85, threshold=0.7)


__all__ = [
    "Contains",
    "ExactMatch",
    "FactualCheck",
    "LLMJudge",
    "Metric",
    "MetricResult",
    "RegexMatch",
]
