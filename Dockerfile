# Multi-stage build — builder creates wheel, runtime installs from PyPI + local wheel
FROM python:3.12-slim AS builder

WORKDIR /src
COPY . .

# Build prerequisites
RUN apt-get update && apt-get install -y --no-install-recommends \\
    build-essential gcc g++ make git curl ca-certificates \\
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip hatchling

# Build wheel without dependency resolution (isolated)
RUN pip wheel --no-deps --wheel-dir /wheels .

# Runtime stage
FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.title="MOSAIC"
LABEL org.opencontainers.image.description="Memory-first, defense-in-depth LLM framework"
LABEL org.opencontainers.image.vendor="MOSAIC Project"
LABEL org.opencontainers.image.licenses="Apache-2.0"

WORKDIR /app

# System libs for cryptography, redis, etc. (kept minimal)
RUN apt-get update && apt-get install -y --no-install-recommends libssl-dev libffi-dev \\
    && rm -rf /var/lib/apt/lists/*

# Copy our wheel
COPY --from=builder /wheels/*.whl /wheels/

# Install mosaic with extras; deps pulled from PyPI (prebuilt wheels)
ARG MOSAIC_EXTRAS=all
RUN pip install --no-cache-dir "/wheels/mosaic-*.whl[${MOSAIC_EXTRAS}]"

# Non-root user
RUN useradd --create-home --uid 1000 mosaic && chown -R mosaic:mosaic /app
USER mosaic

EXPOSE 8000
ENV HOST=0.0.0.0
ENV PORT=8000
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["mosaic", "serve"]
CMD ["--host", "0.0.0.0", "--port", "8000"]
