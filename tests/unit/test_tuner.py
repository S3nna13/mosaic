"""Adaptive guardrail tuner — threshold adjustment based on false-positive rate."""
from __future__ import annotations

import pytest
from mosaic.guardrails.tuner import GuardrailTuner, TunerConfig


def test_tuner_increases_threshold_on_high_fp_rate():
    tuner = GuardrailTuner(
        config=TunerConfig(
            rail_name="pii",
            target_fp_rate=0.1,     # want ≤10% false positives
            adjustment_step=0.05,
            min_threshold=0.1,
            max_threshold=0.9,
        )
    )
    # Historical FP rate = 0.4 (40% of non-PII texts flagged → too sensitive)
    history = [{"passed": False, "was_false_positive": True} for _ in range(40)] + \
              [{"passed": True}] * 60  # 40% FP, 60% TN
    new_threshold = tuner.compute_new_threshold(history)
    # Too many FPs → threshold should go up (reduce sensitivity)
    assert new_threshold > tuner.config.initial_threshold


def test_tuner_decreases_threshold_on_low_fp_rate():
    tuner = GuardrailTuner(
        config=TunerConfig(
            rail_name="jailbreak",
            target_fp_rate=0.1,
            adjustment_step=0.05,
            min_threshold=0.1,
            max_threshold=0.9,
        )
    )
    # Low FP rate = 2% → could be more sensitive to catch more true positives
    history = [{"passed": False, "was_false_positive": True} for _ in range(2)] + \
              [{"passed": True}] * 98
    new_threshold = tuner.compute_new_threshold(history)
    # Low FP → threshold should go down (more sensitive)
    assert new_threshold < tuner.config.initial_threshold


def test_tuner_respects_bounds():
    tuner = GuardrailTuner(
        config=TunerConfig(
            rail_name="test",
            target_fp_rate=0.1,
            adjustment_step=0.2,
            min_threshold=0.2,
            max_threshold=0.8,
        )
    )
    # Extreme FP rate → adjustment hits bounds
    history = [{"passed": False, "was_false_positive": True}] * 200  # 100% FP
    new = tuner.compute_new_threshold(history)
    assert new <= 0.8
    assert new >= 0.2


def test_history_insufficient_defaults_to_pass_through():
    tuner = GuardrailTuner(config=TunerConfig(rail_name="x"))
    # Empty or tiny sample size → no change
    new = tuner.compute_new_threshold([])
    assert new == tuner.config.initial_threshold
    new = tuner.compute_new_threshold([{"passed": True}] * 3)
    assert new == tuner.config.initial_threshold
