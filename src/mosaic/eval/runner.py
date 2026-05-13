"""Eval runner — executes a YAML config and aggregates results."""

from __future__ import annotations

from pathlib import Path

from mosaic.adapters.base import BaseAdapter
from mosaic.core.config import load_config
from mosaic.eval.metrics import Metric, MetricResult


class EvalContext:
    def __init__(self, config_path: str | Path, model: BaseAdapter | None = None):
        from mosaic.core.config import load_config
        self.config = load_config(config_path)
        self.model = model

    def get_prompts(self) -> list[str]:
        return [p["template"] for p in (self.config.get("eval", {}).get("prompts", []) or [])]

    def get_tests(self) -> list[dict]:
        return self.config.get("eval", {}).get("tests", []) or []

    def get_metrics(self) -> list[Metric]:
        from mosaic.eval.metrics import Contains, ExactMatch
        metrics = []
        for a in self.config.get("eval", {}).get("assertions", []) or []:
            t = a.get("type")
            if t == "exact":
                metrics.append(ExactMatch())
            elif t == "contains":
                metrics.append(Contains())
            else:
                metrics.append(ExactMatch())
        return metrics


def _build_metric(assertion: dict, model: BaseAdapter | None = None) -> Metric:
    from mosaic.eval.metrics import Contains, ExactMatch, LLMJudge, RegexMatch
    t = assertion.get("type", "exact")
    if t == "exact":
        return ExactMatch()
    if t == "contains":
        val = assertion.get("value", "")
        return Contains(expected=val)
    if t == "regex":
        return RegexMatch(pattern=str(assertion.get("value", ".*")))
    if t in ("llm_judge", "factual"):
        return LLMJudge(model_adapter=model, criteria=assertion.get("metric", "correctness"))
    return ExactMatch()


async def run_eval(config: str | Path | dict, model_override: BaseAdapter | None = None):

    config_obj = load_config(str(config)) if isinstance(config, (str, Path)) else config

    # Select model from config or override
    if model_override:
        model = model_override
    else:
        mc = config_obj.get("model", {})
        provider = mc.get("provider")
        if provider == "openai":
            from ..adapters.openai_adapter import OpenAIAdapter
            model = OpenAIAdapter(
                model=mc.get("model", "gpt-4o-mini"),
                api_key=mc.get("api_key"),
            )
        elif provider == "local":
            from ..adapters.local_adapter import LocalAdapter
            model = LocalAdapter(model_path=mc.get("path", "mosaic-ai/cerberus-1.6b"))
        else:
            raise ValueError(f"Unknown provider: {provider}")

    metrics_cfg = config_obj.get("eval", {}).get("assertions", [])
    metrics = [_build_metric(a, model) for a in metrics_cfg]

    tests = config_obj.get("eval", {}).get("tests", [])
    results: list[MetricResult] = []

    for test in tests:
        inp = test.get("input", "")
        # Compile prompt from template + variables
        prompt_template = test.get("prompt", "{input}")
        prompt = prompt_template.format(input=inp)

        # Run model
        from ..adapters.base import Message
        messages = [Message(role="user", content=prompt)]
        resp = await model.generate(messages)
        output = resp.content

        expected = test.get("expected")
        for m in metrics:
            result = await m.measure(input=inp, output=output, expected=expected)
            results.append(result)

    return results


__all__ = [
    "EvalContext",
    "run_eval",
]
