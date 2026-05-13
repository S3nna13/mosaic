"""AdaptiveGuardrailTuner — runtime threshold adjustment per rail.

Monitors guardrail decision history (last N decisions) and computes false-positive rate.
If FP rate is significantly above target (e.g. 5%), the threshold is relaxed slightly.
If FP rate is below target (too permissive), threshold is tightened.

This creates a self-tuning safety system that adapts to the actual prompt distribution
without human reconfiguration.

Strategy:
  • Maintain rolling window of the last 100 decisions per rail
  • Track human correction signals: if output guardrail passes but downstream user feedback = BAD, count as FN
  • Simple PID-like adjustment: error = actual_fp - target_fp; adjust += Kp * error
  • Bounds: thresholds stay in [0.05, 0.95] to avoid degenerate settings
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Optional

# Simple proportional controller; could extend to PI or PID
KP = 0.02    # proportional gain
MIN_THRESHOLD = 0.05
MAX_THRESHOLD = 0.95
WINDOW = 100  # decisions to consider


@dataclass
class RailStats:
    name: str
    threshold: float
    decisions: Deque[tuple[bool, bool]] = field(default_factory=lambda: deque(maxlen=WINDOW))
    # decision stored as (passed, was_correct).  was_correct comes from downstream signal:
    #   - If INPUT rail blocks and audit says rightly blocked → True
    #   - If INPUT rail passes and later security incident → False
    #   - For now we treat passes as correct, blocks as correct by default (conservative)

    def record(self, passed: bool, correct: Optional[bool] = None) -> None:
        # If no explicit correctness label, assume passed=correct, blocked=correct (safe default)
        if correct is None:
            correct = passed  # optimistic; conservative would be False for blocks
        self.decisions.append((passed, correct))

    @property
    def fp_rate(self) -> float:
        """False positive rate among blocked decisions (passed=False)."""
        blocked = [c for p, c in self.decisions if not p]
        if not blocked:
            return 0.0
        fps = sum(1 for p, c in blocked if c)
        return fps / len(blocked)

    def adjust(self, target_fp: float = 0.05) -> None:
        """Move threshold in direction that would reduce FP rate."""
        error = self.fp_rate - target_fp
        if abs(error) < 0.01:
            return  # within acceptable band
        adjustment = KP * error
        new_threshold = self.threshold + adjustment
        self.threshold = max(MIN_THRESHOLD, min(MAX_THRESHOLD, new_threshold))


class AdaptiveGuardrailTuner:
    """Registry for all rails; call after each decision to possibly adjust thresholds."""
    def __init__(self):
        self._stats: dict[str, RailStats] = {}

    def register(self, rail_name: str, initial_threshold: float = 0.3) -> None:
        if rail_name not in self._stats:
            self._stats[rail_name] = RailStats(name=rail_name, threshold=initial_threshold)

    def record(self, rail_name: str, passed: bool, correct: Optional[bool] = None) -> None:
        self.register(rail_name)  # ensure exists
        self._stats[rail_name].record(passed, correct)

    def tune(self, target_fp: float = 0.05) -> dict[str, float]:
        """Adjust all thresholds; return dict of {rail: new_threshold}."""
        updates = {}
        for name, stats in self._stats.items():
            old = stats.threshold
            stats.adjust(target_fp)
            if stats.threshold != old:
                updates[name] = stats.threshold
        return updates

    def get_threshold(self, rail_name: str) -> float:
        return self._stats[rail_name].threshold

    def summary(self) -> dict[str, dict]:
        return {
            name: {
                "threshold": stats.threshold,
                "fp_rate": stats.fp_rate,
                "samples": len(stats.decisions),
            }
            for name, stats in self._stats.items()
        }
