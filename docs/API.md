# MOSAIC HTTP API Reference

## Base URL

`http://localhost:8000` (default serve port).

## Endpoints

### POST /load
Initialize the decoder with a provider + model.

```json
{
  "provider": "openai",
  "model": "gpt-4o-mini",
  "api_key": "sk-…"
}
```

### POST /chat
Generate a completion.

```json
{
  "messages": [{"role": "user", "content": "Hello"}],
  "mode": "fast",
  "max_tokens": 512,
  "temperature": 0.7,
  "guardrails": true
}
```

Response:
```json
{
  "content": "Hi there!",
  "model": "mosaic",
  "mode_used": "fast",
  "stability": 0.92,
  "request_id": "uuid…",
  "ts": "2026-05-13T00:20:12.345Z",
  "guardrail_report": [...],
  "usage": {"prompt_tokens": 10, "completion_tokens": 3}
}
```

### GET /status
Service health + uptime.

### GET /metrics
Prometheus-style key/value metrics.

### GET /dashboard
JSON snapshot of memory, guardrail stats, recent audit.

### POST /guard
Run guardrail pipeline on ad-hoc text.

`POST /guard?text=…&mode=input`

### GET /audit/tail?n=20
Recent ArkLedger entries.

### POST /reset
Clear session memory.

## Error model

HTTP 4xx for client errors (blocked by guardrails → 403), 5xx for internal failures.

## CORS

Enabled for all origins by default (restrict in prod via `MOSAIC_CORS_ORIGINS`).
