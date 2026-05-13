# Single-stage build — simple, reliable
FROM python:3.12-slim

LABEL org.opencontainers.image.title="MOSAIC"
LABEL org.opencontainers.image.description="Memory-first, defense-in-depth LLM framework"
LABEL org.opencontainers.image.vendor="MOSAIC Project"
LABEL org.opencontainers.image.licenses="Apache-2.0"

WORKDIR /app

# System deps in one line to avoid continuation issues
RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ make git curl ca-certificates libssl-dev libffi-dev && rm -rf /var/lib/apt/lists/*

# Copy project
COPY . .

# Install package + all extras
RUN pip install --upgrade pip hatchling && pip install -e ".[all]"

# Non-root user
RUN useradd --create-home --uid 1000 mosaic && chown -R mosaic:mosaic /app
USER mosaic

EXPOSE 8000
ENV HOST=0.0.0.0
ENV PORT=8000
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["mosaic", "serve"]
CMD ["--host", "0.0.0.0", "--port", "8000"]
