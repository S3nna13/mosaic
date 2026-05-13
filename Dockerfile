# Multi-stage build — builder stage compiles wheels, final stage runs FastAPI
FROM python:3.12-slim AS builder

WORKDIR /src
COPY . .
RUN apt-get update && apt-get install -y --no-install-recommends build-essential gcc git && rm -rf /var/lib/apt/lists/*
RUN pip install --upgrade pip hatchling
RUN python -m build --wheel --out-dir /dist
# Pre-install deps into a requirements dir for final image (optional optim)


# Runtime stage
FROM python:3.12-slim AS runtime
ARG MOSAIC_EXTRAS=all

LABEL org.opencontainers.image.title="MOSAIC"
LABEL org.opencontainers.image.description="Memory-first, defense-in-depth LLM framework"
LABEL org.opencontainers.image.vendor="MOSAIC Project"
LABEL org.opencontainers.image.licenses="Apache-2.0"

WORKDIR /app
COPY --from=builder /dist/*.whl /wheels/
ARG MOSAIC_EXTRAS=all
RUN pip install --no-cache-dir "/wheels/mosaic-*.whl[${MOSAIC_EXTRAS}]" && rm -rf /wheels

# Non-root user for security
RUN useradd --create-home --uid 1000 mosaic && chown -R mosaic:mosaic /app
USER mosaic

EXPOSE 8000
ENV HOST=0.0.0.0
ENV PORT=8000
ENV PYTHONUNBUFFERED=1

# Default entrypoint runs the API server
ENTRYPOINT ["mosaic", "serve"]
CMD ["--host", "0.0.0.0", "--port", "8000"]
