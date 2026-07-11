# Production API image built from the repository root so the pure calc engine
# is packaged with the application.
FROM python:3.12-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl gosu \
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

# ---------- production ----------
FROM deps AS production
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=production \
    HOME=/tmp/oci-dis-home
RUN addgroup --system --gid 10001 app \
    && adduser --system --uid 10001 --ingroup app app \
    && mkdir -p "$HOME" \
    && chown app:app "$HOME" \
    && chmod 0700 "$HOME"
COPY --chown=app:app apps/api .
COPY --chown=app:app packages/calc-engine /calc-engine
COPY --chown=app:app docs/api/openapi.yaml /docs/api/openapi.yaml
COPY apps/api/production-entrypoint.sh /usr/local/bin/oci-dis-entrypoint
RUN mkdir -p /app/uploads \
    && chown app:app /app/uploads \
    && chmod 0770 /app/uploads \
    && chmod 0755 /usr/local/bin/oci-dis-entrypoint
USER app
EXPOSE 8000
ENTRYPOINT ["oci-dis-entrypoint"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
