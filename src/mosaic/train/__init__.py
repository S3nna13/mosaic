"""Training pipeline — SFT + RLHF scaffolds.

Adapted from Moses Manna engine and Aurelius synthetic data patterns.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F  # noqa: N812

from mosaic.adapters import build_adapter
from mosaic.adapters.base import Message
from mosaic.model.transformer import MosaicTransformer


# ── Synthetic Data Generation ────────────────────────────────────────────────
@dataclass
class SyntheticExample:
    instruction: str
    input: str = ""
    output: str = ""
    metadata: dict | None = None


class SyntheticGenerator:
    """Generates synthetic instruction-response pairs via teacher model."""

    PROMPTS = {  # noqa: RUF012
        "qa": 'Generate a question-answer pair about {topic}. Return ONLY JSON: {"question": "...", "answer": "..."}',
        "summary": "Write a 2-sentence summary of: {text}",
        "code": "Write a Python function that {desc}. Include docstring and type hints. Return code only.",
        "math": "Create a {difficulty} algebra problem. Then show step-by-step solution.",
    }

    def __init__(
        self,
        provider: str = "openai",
        model: str = "gpt-4o-mini",
        api_key: str | None = None,
    ):
        self.adapter = build_adapter(provider=provider, model=model, api_key=api_key)

    async def generate(self, template: str, **kwargs) -> SyntheticExample:
        prompt = self.PROMPTS[template].format(**kwargs)
        messages = [Message(role="user", content=prompt)]
        resp = await self.adapter.chat(messages, temperature=0.8, max_tokens=768)
        try:
            data = json.loads(resp.content)
            return SyntheticExample(
                instruction=prompt, output=resp.content, metadata=data
            )
        except Exception:
            return SyntheticExample(instruction=prompt, output=resp.content)

    async def batch(self, n: int, template: str, **kwargs) -> list[SyntheticExample]:
        return [await self.generate(template, **kwargs) for _ in range(n)]


# ── Trainer ───────────────────────────────────────────────────────────────────
@dataclass
class TrainerConfig:
    epochs: int = 3
    batch_size: int = 8
    gradient_accumulation_steps: int = 4
    learning_rate: float = 3e-4
    weight_decay: float = 0.01
    warmup_steps: int = 100
    checkpoint_dir: str = "checkpoints/"
    device: str = "cuda"


class Trainer:
    """Simple PyTorch trainer with accumulation + checkpointing."""

    def __init__(
        self, model: MosaicTransformer, cfg: TrainerConfig, device: str | None = None
    ):
        self.model = model
        self.cfg = cfg
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
        self.optimizer = torch.optim.AdamW(
            self.model.parameters(),
            lr=cfg.learning_rate,
            weight_decay=cfg.weight_decay,
        )
        self.global_step = 0

    def train_step(self, batch: dict[str, torch.Tensor]) -> float:
        input_ids = batch["input_ids"].to(self.device)
        labels = batch["labels"].to(self.device)
        logits = self.model(input_ids)
        loss = F.cross_entropy(logits.view(-1, logits.size(-1)), labels.view(-1))
        loss.backward()
        if (self.global_step + 1) % self.cfg.gradient_accumulation_steps == 0:
            self.optimizer.step()
            self.optimizer.zero_grad()
        self.global_step += 1
        return loss.item()

    def save_checkpoint(self, path: str | None = None) -> str:
        ckpt_dir = Path(self.cfg.checkpoint_dir)
        ckpt_dir.mkdir(parents=True, exist_ok=True)
        path = path or str(ckpt_dir / f"mosaic_step{self.global_step}.pt")
        torch.save(
            {
                "model": self.model.state_dict(),
                "optimizer": self.optimizer.state_dict(),
                "step": self.global_step,
                "config": self.cfg,
            },
            path,
        )
        return path

    def train(self, dataloader, steps: int | None = None) -> None:
        self.model.train()
        for _epoch in range(self.cfg.epochs):
            for batch in dataloader:
                loss = self.train_step(batch)
                if self.global_step % 50 == 0:
                    print(f"step {self.global_step}  loss={loss:.4f}")
                if steps and self.global_step >= steps:
                    break
            self.save_checkpoint()
        print("Training complete — final checkpoint saved.")


# ── RLHF scaffold (GRPO/PPO) ─────────────────────────────────────────────────
@dataclass
class RLHFConfig:
    reward_model_path: str | None = None
    ppo_epochs: int = 4
    kl_coef: float = 0.02
    gamma: float = 0.99
    lam: float = 0.95


class RLTrainer:
    """Placeholder: GRPO/PPO alignment loop. Real implementation needs ref policy + value net."""

    def __init__(self, policy_model: MosaicTransformer, cfg: RLHFConfig):
        self.policy = policy_model
        self.cfg = cfg
        # Stub: would load/reward model, value net, rollout buffer

    def rollout(self, prompts: list[list[int]]) -> list[dict[str, Any]]:
        # Generate completions, compute reward, return trajectory
        return []

    def update(self, trajectories: list[dict[str, Any]]) -> None:
        # PPO/GRPO update step
        pass


__all__ = [
    "RLHFConfig",
    "RLTrainer",
    "SyntheticExample",
    "SyntheticGenerator",
    "Trainer",
    "TrainerConfig",
]
