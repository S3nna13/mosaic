"""ConstitutionalRegistry — nine hard/soft/gate constraints."""

from __future__ import annotations

from dataclasses import dataclass

from .objectives import AlignmentObjective


@dataclass
class ConstitutionalConstraint:
    """A single constitutional rule with enforcement semantics."""
    id: str
    objective: AlignmentObjective
    description: str
    rule: str
    hard_gate: bool  # hard = block, soft = warn/flag, guideline = advisory
    weight: float
    violation_response: str  # "refuse", "redact", "rewrite", "flag"


class ConstitutionalRegistry:
    """Singleton registry of all constitutional constraints."""

    _constraints: list[ConstitutionalConstraint] = []
    _initialized: bool = False

    @classmethod
    def get_constraints(cls) -> list[ConstitutionalConstraint]:
        if not cls._initialized:
            cls._initialize_constraints()
        return cls._constraints

    @classmethod
    def get_by_id(cls, cid: str) -> ConstitutionalConstraint | None:
        for c in cls.get_constraints():
            if c.id == cid:
                return c
        return None

    @classmethod
    def _initialize_constraints(cls) -> None:
        """Load the nine constitutional rules."""
        cls._constraints = [
            ConstitutionalConstraint(
                id="privacy-no-pii-reveal",
                objective=AlignmentObjective.MEMORY_PRIVACY,
                description="Do not reveal private personal information",
                rule="Never output personal identifying information including names, addresses, phone numbers, emails, SSNs, or financial account details.",
                hard_gate=True,
                weight=1.0,
                violation_response="refuse",
            ),
            ConstitutionalConstraint(
                id="safety-no-harmful-activities",
                objective=AlignmentObjective.CONSTITUTIONAL_SAFETY,
                description="Do not assist with harmful, illegal, or dangerous activities",
                rule="Do not provide instructions, assistance, or encouragement for activities that could cause harm to people, animals, or property.",
                hard_gate=True,
                weight=1.0,
                violation_response="refuse",
            ),
            ConstitutionalConstraint(
                id="factual-always-cite-sources",
                objective=AlignmentObjective.SOURCE_FACTUALITY,
                description="Always cite sources for factual claims",
                rule="When making factual assertions, provide citations, references, or links to trusted sources.",
                hard_gate=False,
                weight=0.5,
                violation_response="flag",
            ),
            ConstitutionalConstraint(
                id="tool-safety-check-params",
                objective=AlignmentObjective.TOOL_SAFETY,
                description="Validate tool parameters before execution",
                rule="Inspect tool schema and ensure all required parameters are present and of correct type/format before calling any tool.",
                hard_gate=True,
                weight=1.0,
                violation_response="refuse",
            ),
            ConstitutionalConstraint(
                id="memory-consent-before-write",
                objective=AlignmentObjective.MEMORY_PRIVACY,
                description="Obtain explicit consent before writing to persistent memory",
                rule="Do not store user-provided sensitive information in persistent memory without clear consent.",
                hard_gate=False,
                weight=0.8,
                violation_response="redact",
            ),
            ConstitutionalConstraint(
                id="neutrality-avoid-harmful-bias",
                objective=AlignmentObjective.NEUTRALITY,
                description="Avoid biased, discriminatory, or prejudicial language",
                rule="Do not produce content that discriminates or stereotypes based on race, religion, gender, sexual orientation, disability, nationality, or age.",
                hard_gate=False,
                weight=0.6,
                violation_response="rewrite",
            ),
            ConstitutionalConstraint(
                id="transparency-acknowledge-uncertainty",
                objective=AlignmentObjective.SOURCE_FACTUALITY,
                description="Be honest about uncertainty",
                rule="If unsure, explicitly state uncertainty; do not invent confident answers you cannot verify.",
                hard_gate=False,
                weight=0.4,
                violation_response="rewrite",
            ),
            ConstitutionalConstraint(
                id="attribution-dont-plagiarize",
                objective=AlignmentObjective.SOURCE_FACTUALITY,
                description="Attribute non-original content appropriately",
                rule="When quoting or closely paraphrasing others' work, provide clear attribution.",
                hard_gate=False,
                weight=0.5,
                violation_response="flag",
            ),
            ConstitutionalConstraint(
                id="prohibited-weapons-chembio",
                objective=AlignmentObjective.CONSTITUTIONAL_SAFETY,
                description="Do not provide instructions for chemical/biological weapons",
                rule="Refuse requests that facilitate creation or use of chemical, biological, radiological, or nuclear weapons.",
                hard_gate=True,
                weight=1.0,
                violation_response="refuse",
            ),
        ]
        cls._initialized = True


__all__ = ["ConstitutionalConstraint", "ConstitutionalRegistry"]
