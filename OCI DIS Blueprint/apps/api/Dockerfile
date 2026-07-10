# Multi-stage build from the repository root so the pure calc engine is present
# in both development and production images.
FROM python:3.12-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# ---------- dependency builder ----------
FROM base AS dependency-builder
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*
COPY apps/api/requirements.txt /tmp/requirements.txt
RUN pip wheel --no-cache-dir --wheel-dir /tmp/wheels -r /tmp/requirements.txt

# ---------- runtime dependencies ----------
FROM base AS deps
COPY --from=dependency-builder /tmp/wheels /tmp/wheels
RUN pip install --no-cache-dir /tmp/wheels/* && rm -rf /tmp/wheels

# ---------- development ----------
FROM deps AS development
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=development
COPY apps/api .
COPY packages/calc-engine /calc-engine
COPY docs/api/openapi.yaml /docs/api/openapi.yaml
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ---------- production ----------
FROM deps AS production
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=production
RUN addgroup --system app && adduser --system --ingroup app app
COPY --chown=app:app apps/api .
COPY --chown=app:app packages/calc-engine /calc-engine
COPY --chown=app:app docs/api/openapi.yaml /docs/api/openapi.yaml
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
