# Quickstart — MOSAIC in 5 Minutes

## 1. Install
```bash
git clone <your-mosaic-repo>
cd mosaic
python -m venv .venv
source .venv/bin/activate
pip install -e '.[all]'
```

## 2. Configure
Set your API keys (environment variables):
```bash
export MOSAIC_OPENAI_API_KEY="sk-..."
export MOSAIC_ANTHROPIC_API_KEY="sk-ant-..."
```

Or create a YAML config at `configs/serve/local.yaml`:
```yaml
adapter: openai
model: gpt-4o-mini
openai_api_key: ${MOSAIC_OPENAI_API_KEY}
guard:
  enabled: true
  strict: false
```

Validate it:
```bash
mosaic config configs/serve/local.yaml
```

## 3. Start the server
```bash
mosaic serve --reload
```
Server starts at http://localhost:8000

## 4. Try the CLI
In another terminal:
```bash
mosaic chat --prompt "What is 2 + 2?" --adapter openai
```

You'll see:
- Guardrail pre-check (jailbreak, toxicity, etc.)
- Generation via GPT-4o-mini
- Verifier score and stability
- Audit log entry created

## 5. Open the dashboard
Visit http://localhost:8000/dashboard — live request-rate, guardrail hit-rate, latency, stability score.

## 6. Run a benchmark
```bash
mosaic eval --benchmark --limit 5
```

## 7. Generate synthetic training data
```bash
mosaic train synthetic --template code --n 10 --topic "Python decorators"
```

## Next steps
- Explore the docs: [docs/](docs/)
- Write a custom tool: [docs/TOOLS.md](docs/TOOLS.md)
- Train your own model: [docs/TRAINING.md](docs/TRAINING.md)
- Add vision support: [docs/MULTIMODAL.md](docs/MULTIMODAL.md)

