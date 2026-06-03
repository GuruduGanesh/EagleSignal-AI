# EagleSignal AI — container image for Docker Desktop
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src \
    TZ=America/New_York

WORKDIR /app

# System deps (curl for healthcheck; build tools only if a wheel is missing)
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY src/ ./src/
COPY config/ ./config/
COPY README.md SKILLS.md WORKFLOW.md ARCHITECTURE.md ./

# Reports + data volumes are created at runtime
RUN mkdir -p reports data

# Non-root user
RUN useradd -m -u 10001 eagle && chown -R eagle:eagle /app
USER eagle

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

# Default: serve the API + dashboard. Override CMD to run the CLI batch instead.
CMD ["uvicorn", "eaglesignal.api:app", "--host", "0.0.0.0", "--port", "8000"]
