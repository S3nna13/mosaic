# Multi-stage build — builder stage compiles wheels, final stage runs FastAPI
FROM python:3.12-slim AS builder

WORKDIR /src
COPY . .

# Install build system only (no project deps here)
RUN apt-get update && apt-get install -y --no-install-recommends \\
    build-essential gcc g++ make git curl ca-certificates \\
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install build backend
RUN pip install --upgrade pip hatchling

# Build wheel WITHOUT installing dependencies (they get installed in runtime stage)
RUN python -m build --wheel --out-dir /dist --no-deps

# Runtime stage
FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.title="MOSAIC"
LABEL org.opencontainers.image.description="Memory-first, defense-in-depth LLM framework"
LABEL org.opencontainers.image.vendor="MOSAIC Project"
LABEL org.opencontainers.image.licenses="Apache-2.0"

WORKDIR /app

# Install runtime system deps (for packages like redis, cryptography, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \\
    libssl-dev libffi-dev gcc g++ \\
    && rm -rf /var/lib/apt/lists/*

# Copy built wheel from builder
COPY --from=builder /dist/*.whl /wheels/

# Install mosaic with chosen extras (default: all)
ARG MOSAIC_EXTRAS=all
RUN pip install --no-cache-dir "/wheels/mosaic-*.whl[${MOSAIC_EXTRAS}]"

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
