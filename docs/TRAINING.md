# Training Guide — MOSAIC

## Synthetic Data Generation

MOSAIC supports infinite synthetic instruction-response generation via a teacher model:

```python
from mosaic.train import SyntheticGenerator

gen = SyntheticGenerator(provider="openai", model="gpt-4o-mini")
examples = await gen.batch(100, "qa", topic="Python programming")
```

Built-in templates: `qa`, `summary`, `code`, `math`.

## Supervised Fine-Tuning (SFT)

```python
from mosaic.train import Trainer, TrainerConfig
from mosaic.model.transformer import MosaicTransformer, MosaicConfig

model = MosaicTransformer(MosaicConfig())
cfg = TrainerConfig(epochs=3, batch_size=8, checkpoint_dir="checkpoints/")
trainer = Trainer(model, cfg)
trainer.train(dataloader)   # any torch DataLoader yielding {"input_ids": ..., "labels": ...}
trainer.save_checkpoint()
```

Checkpoints are PyTorch `.pt` files containing model state, optimizer state, and step.

## RLHF (GRPO/PPO)

```python
from mosaic.train import RLTrainer, RLHFConfig
rl = RLTrainer(policy_model=model, cfg=RLHFConfig())
# scaffold — implement reward model & rollout buffer
```

## Export

Checkpoints can be converted to GGUF via `llama.cpp` tools for local inference.
