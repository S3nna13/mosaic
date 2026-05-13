"""AlignmentResult + SafetyTier dataclasses."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class SafetyTier(StrEnum):
    SAFE = "safe"
    REVIEW = "review"  # flagged but not blocked
    BLOCKED = "blocked"


@dataclass
class AlignmentResult:
    """Structured alignment gate outcome."""

    approved: bool
    modified_response: str | None
    violations: list[str]
    constraint_scores: dict[str, float]
    needs_verifier_pass: bool = False
    refusal_reason: str | None = None
    safety_tier: SafetyTier = SafetyTier.SAFE

    def to_dict(self) -> dict[str, Any]:
        return {
            "approved": self.approved,
            "safety_tier": self.safety_tier,
            "violations": self.violations,
            "needs_verifier": self.needs_verifier_pass,
        }


__all__ = ["AlignmentResult", "SafetyTier"]
