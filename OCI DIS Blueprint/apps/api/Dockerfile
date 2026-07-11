# Production API image built from the repository root so the pure calc engine
# is packaged with the application.
FROM python:3.12-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl gosu \
    && rm -rf /var/lib/apt/lists/*

# ---------- runtime dependency builder ----------
FROM base AS runtime-dependency-builder
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*
COPY apps/api/requirements-runtime.txt /tmp/requirements-runtime.txt
RUN pip wheel --no-cache-dir --wheel-dir /tmp/runtime-wheels -r /tmp/requirements-runtime.txt

# ---------- runtime dependencies ----------
FROM base AS runtime-deps
COPY --from=runtime-dependency-builder /tmp/runtime-wheels /tmp/runtime-wheels
RUN pip install --no-cache-dir /tmp/runtime-wheels/* && rm -rf /tmp/runtime-wheels

# ---------- production ----------
FROM runtime-deps AS production
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=production \
    HOME=/tmp/oci-dis-home
RUN addgroup --system --gid 10001 app \
    && adduser --system --uid 10001 --ingroup app app \
    && mkdir -p "$HOME" \
    && chown app:app "$HOME" \
    && chmod 0700 "$HOME"
COPY --chown=app:app apps/api/app ./app
COPY --chown=app:app apps/api/migrations ./migrations
COPY --chown=app:app apps/api/scripts ./scripts
COPY --chown=app:app apps/api/alembic.ini ./alembic.ini
COPY --chown=app:app packages/calc-engine/src/__init__.py /calc-engine/src/__init__.py
COPY --chown=app:app packages/calc-engine/src/engine /calc-engine/src/engine
COPY --chown=app:app docs/api/openapi.yaml /docs/api/openapi.yaml
COPY apps/api/production-entrypoint.sh /usr/local/bin/oci-dis-entrypoint
RUN rm -rf /app/app/tests \
    && mkdir -p /app/uploads /app/generated-reports \
    && chown app:app /app/uploads /app/generated-reports \
    && chmod 0770 /app/uploads /app/generated-reports \
    && chmod 0755 /usr/local/bin/oci-dis-entrypoint
USER app
EXPOSE 8000
ENTRYPOINT ["oci-dis-entrypoint"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

# ---------- quality dependency builder ----------
FROM base AS quality-dependency-builder
COPY apps/api/requirements-quality.txt /tmp/requirements-quality.txt
RUN pip wheel --no-cache-dir --wheel-dir /tmp/quality-wheels -r /tmp/requirements-quality.txt

# ---------- quality gates (never deployed) ----------
FROM production AS quality
USER root
COPY --from=quality-dependency-builder /tmp/quality-wheels /tmp/quality-wheels
RUN pip install --no-cache-dir /tmp/quality-wheels/* && rm -rf /tmp/quality-wheels
COPY --chown=app:app apps/api/app/tests ./app/tests
COPY --chown=app:app packages/calc-engine/src/tests /calc-engine/src/tests
USER app
