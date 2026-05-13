"""Benchmark harness — runs model through diverse scenarios & aggregates scores.

Inspired by HELM (Holistic Evaluation of Language Models) and Aurelius eval patterns.
Scenarios included:
  • TruthfulQA — measures hallucination rate
  • MT-Bench — multi-turn instruction quality
  • HumanEval — code generation pass@k
  • GSM8K — math reasoning accuracy
  • ToxicityPrompts — safety evaluation
  • MMLU — multi-domain multiple choice
  • Custom YAML-defined scenarios

Metrics: accuracy, pass@k, BLEU/ROUGE, toxicity score, refusal rate.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

from mosaic.adapters.base import Message
from mosaic.eval.metrics import JudgeLLM, contains_match, exact_match

logger = structlog.get_logger()


@dataclass
class Scenario:
    name: str
    description: str
    samples: list[dict[str, Any]]
    metric: str  # "exact_match", "contains", "llm_judge", "code_exec"
    answer_key: str = "answer"
    prompt_template: str = "{question}"
    max_tokens: int = 256
    temperature: float = 0.0

    def format_prompt(self, sample: dict[str, Any]) -> str:
        return self.prompt_template.format(**sample)


@dataclass
class ScenarioResult:
    scenario: str
    num_samples: int
    metric: str
    score: float
    details: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario,
            "num_samples": self.num_samples,
            "metric": self.metric,
            "score": round(self.score, 4),
            "details": self.details[:10],  # keep first 10 for brevity
        }


class BenchmarkHarness:
    """Runs a model through a collection of scenarios and aggregates results."""
    def __init__(self, adapter, scenarios_dir: str = "configs/eval/scenarios"):
        self.adapter = adapter
        self.scenarios_dir = Path(scenarios_dir)
        self.scenarios: dict[str, Scenario] = {}
        self.results: list[ScenarioResult] = []

    def load_scenario(self, path: Path) -> Scenario:
        """Load a scenario from a YAML/JSON file."""
        import yaml
        raw = yaml.safe_load(path.read_text())
        return Scenario(**raw)

    def load_all(self) -> None:
        """Load all scenario files from scenarios_dir."""
        for p in self.scenarios_dir.glob("*.yaml") + self.scenarios_dir.glob("*.json"):
            try:
                s = self.load_scenario(p)
                self.scenarios[s.name] = s
                logger.info("scenario_loaded", name=s.name, samples=len(s.samples))
            except Exception as e:
                logger.warning("scenario_load_failed", path=str(p), error=str(e))

    async def run_scenario(self, scenario: Scenario, limit: int | None = None) -> ScenarioResult:
        """Evaluate adapter on a single scenario."""
        samples = scenario.samples if limit is None else scenario.samples[:limit]
        all_scores = []
        details = []

        for sample in samples:
            prompt = scenario.format_prompt(sample)
            messages = [Message(role="user", content=prompt)]
            try:
                resp = await self.adapter.chat(messages, max_tokens=scenario.max_tokens, temperature=scenario.temperature)
                generated = resp.content.strip()
                expected = sample[scenario.answer_key]
            except Exception as e:
                logger.error("generation_failed", scenario=scenario.name, error=str(e))
                generated = ""

            # Compute score using metric function
            if scenario.metric == "exact_match":
                score = exact_match(generated, expected)
            elif scenario.metric == "contains":
                score = contains_match(generated, expected)
            elif scenario.metric == "llm_judge":
                judge = JudgeLLM()
                score = await judge.score(prompt, generated, expected)
            elif scenario.metric == "code_exec":
                score = self._exec_code_score(generated, expected)
            else:
                score = 0.0

            all_scores.append(score)
            details.append({"prompt": prompt[:200], "generated": generated[:300], "expected": str(expected)[:300], "score": score})

        avg_score = statistics.mean(all_scores) if all_scores else 0.0
        return ScenarioResult(scenario.name, len(samples), scenario.metric, avg_score, details)

    async def run_all(self, limit_per: int | None = None) -> dict[str, Any]:
        """Run every loaded scenario and return aggregated results."""
        self.results = []
        for s in self.scenarios.values():
            result = await self.run_scenario(s, limit=limit_per)
            self.results.append(result)
            logger.info("scenario_completed", name=s.name, score=result.score)

        # Aggregate macro-average
        macro_avg = statistics.mean(r.score for r in self.results)
        summary = {
            "num_scenarios": len(self.results),
            "macro_avg": round(macro_avg, 4),
            "scenario_scores": [r.to_dict() for r in self.results],
        }
        return summary

    def _exec_code_score(self, generated: str, expected: str) -> float:
        """Runs generated code in subprocess and compares stdout to expected."""
        import os
        import subprocess
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(generated)
            f.flush()
            try:
                proc = subprocess.run(["python", f.name], capture_output=True, text=True, timeout=5)
                output = proc.stdout.strip()
                score = 1.0 if output == expected.strip() else 0.0
            except Exception:
                score = 0.0
            finally:
                os.unlink(f.name)
        return score


__all__ = ["BenchmarkHarness", "Scenario", "ScenarioResult"]
