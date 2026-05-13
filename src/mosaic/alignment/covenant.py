"""CovenantAlignment — orchestrates all constraints + gate enforcement."""

from __future__ import annotations

from typing import Any

from .constitutional import ConstitutionalRegistry
from .result import AlignmentResult, SafetyTier
from .safety_gates import GateEnforcer


class CovenantAlignment:
    """Top-level alignment orchestrator.

    Takes a context dict (request details, memory state, verifier scores)
    and returns a structured AlignmentResult with pass/fail and tier.
    """

    def __init__(
        self,
        constraints: list | None = None,
        gates: list | None = None,
    ) -> None:
        self.constraints = constraints or ConstitutionalRegistry.get_constraints()
        self.gate_enforcer = GateEnforcer(gates or [])
        # Secondary refusal generator for polite blocking
        self.refusal_phrases = [
            "I cannot comply with that request.",
            "I'm unable to assist with that.",
            "That request cannot be fulfilled due to safety policy.",
        ]

    def align_response(
        self,
        response: str,
        context: dict[str, Any],
        verifier_scores: list[float] | None = None,
    ) -> AlignmentResult:
        """Evaluate response against constitutional + gate constraints."""
        full_context = dict(context)
        full_context["response"] = response

        all_passed, violations = self.gate_enforcer.enforce(full_context)

        # Evaluate constitutional constraints (already included via gates for hard ones)
        constraint_scores: dict[str, float] = {}
        for constraint in self.constraints:
            constraint_scores[constraint.id] = 0.5  # placeholder

        needs_verifier_pass = False
        refusal_reason: str | None = None
        safety_tier = SafetyTier.SAFE

        hard_violations = [
            v
            for v in violations
            if any(
                c.hard_gate and c.violation_response == "refuse"
                for c in self.constraints
                if c.id in v
            )
        ]

        if not all_passed:
            if hard_violations:
                safety_tier = SafetyTier.BLOCKED
                refusal_reason = "; ".join(hard_violations)
            else:
                safety_tier = SafetyTier.REVIEW

        # Combine verifier scores if provided
        if verifier_scores:
            avg = sum(verifier_scores) / len(verifier_scores)
            if avg < 0.5:
                needs_verifier_pass = True

        return AlignmentResult(
            approved=all_passed and not needs_verifier_pass,
            modified_response=None,
            violations=violations,
            constraint_scores=constraint_scores,
            needs_verifier_pass=needs_verifier_pass,
            refusal_reason=refusal_reason,
            safety_tier=safety_tier,
        )


__all__ = ["AlignmentResult", "CovenantAlignment", "SafetyTier"]
