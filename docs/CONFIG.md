# Configuration Reference

MOSAIC uses **Pydantic v2** settings with YAML overrides + environment variables.

## File structure

```
mosaic/
├── configs/
│   ├── training/pretrain.yaml   # pre-training pipeline
│   ├── serve/local.yaml         # FastAPI runtime
│   └── eval/release_gates.yaml  # quality thresholds
└── mosaic.yaml                  # top-level project config (optional)
```

## Top-level schema

```yaml
version: "1"
name: "My Project"
description: "..."

model:
  provider: openai          # openai, anthropic, ollama, local
  model: gpt-4o-mini
  api_key: "$OPENAI_API_KEY"  # can reference env

eval:
  prompts: ["{input}"]
  tests:
    - input: "What is 2+2?"
      expected: `
  assertions:
    - type: exact
    - type: llm_judge
      metric: correctness


guard:
  rails: [jailbreak, injection, ..., rate_limit]
  enabled: true

memory:
  scratch_capacity: 512
  episode_capacity: 4096
  archive_capacity: 8192

security:
  rate_limit_max: 100
  rate_limit_window_seconds: 60
```

## Environment variables

- `MOSAIC_OPENAI_API_KEY` — overrides `api_key`
- `MOSAIC_LOG_LEVEL` — INFO, DEBUG, WARNING
- `MOSAIC_REDIS_URL` — rate-limit backend
- `MOSAIC_DEVICE` — `cuda` or `cpu`
- `MOSAIC_DISABLE_GUARDRAILS` — set `true` to bypass all rails

## Pydantic Settings

The `AigisConfig` model (core/schema.py) defines all typed options. Passing a dictionary to `load_config()` returns the validated config object.

```python
from mosaic.core.config import load_config
cfg = load_config("configs/serve/local.yaml")
print(cfg.model.provider, cfg.server.port)
```

### ModelConfig
| Field  | Type | Default |
|--------|------|---------|
| provider | Literal[openai|anthropic|ollama|local] | `"openai"` |
| model | str | `"gpt-4o-mini"` |
| path | Optional[str] | `None` |
| api_key | Optional[str] | from env |

### InferenceMode
`fast`, `deliberate`, `search`, `agent`, `memory` — set per request via CLI flag or API body.

### Guardrail Configuration
Tune per-rail thresholds in `guard:` section:

```yaml
guard:
  rails:
    - jailbreak
    - hallucination
  jailbreak:
    threshold: 0.3
  toxicity:
    enabled: false
```

More advanced settings available via env: `MOSAIC_JAILBREAK_THRESHOLD=0.4`.

## Quick tip: dump-configured

```bash
mosaic validate configs/serve/local.yaml
```

This prints the fully merged config (defaults + yaml + env) without starting the server.
