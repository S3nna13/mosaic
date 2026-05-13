# Deployment Guide — MOSAIC

## Docker (single-node)

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install -e '.[all]'
CMD ["uvicorn", "mosaic.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build & run:
```bash
docker build -t mosaic .
docker run -p 8000:8000 mosaic
```

## Kubernetes

Helm charts live under `deploy/helm/` (not yet written).  Core resources:

  • StatefulSet for the API server (replicas ≥ 2)
  • ConfigMap with `configs/serve/local.yaml`
  • PersistentVolumeClaim for ArkLedger logs
  • Service + Ingress with TLS

Environment variables:

| Name                     | Purpose                         |
|--------------------------|---------------------------------|
| MOSAIC_OPENAI_API_KEY    | OpenAI credentials              |
| MOSAIC_REDIS_URL         | Redis for rate limiting         |
| MOSAIC_LOG_LEVEL         | DEBUG / INFO / WARNING          |
| MOSAIC_CORS_ORIGINS      | Comma-separated allowed origins |

## Serverless (Cloud Run / Lambda)

Package as a container image and deploy to any FaaS platform that supports custom runtimes.  Ensure 4 GB memory for local models.

## Observability

OpenTelemetry tracing is auto-initialized; export via `OTEL_EXPORTER_OTLP_ENDPOINT`.  Prometheus scrape `/metrics`.

## Security hardening

- Set `MOSAIC_DISABLE_GUARDRAILS=false`
- Use a web application firewall in front
- Rotate API keys via your secret manager
- Enable audit logging to a SIEM
