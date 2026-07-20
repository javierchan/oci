# Production API image built from the repository root so the pure calc engine
# is packaged with the application.
FROM python:3.12-alpine AS base

WORKDIR /app

RUN apk upgrade --no-cache \
    && apk add --no-cache curl su-exec

# ---------- runtime dependency builder ----------
FROM base AS runtime-dependency-builder
RUN apk add --no-cache gcc musl-dev postgresql-dev
COPY apps/api/requirements-runtime.txt /tmp/requirements-runtime.txt
RUN pip wheel --no-cache-dir --wheel-dir /tmp/runtime-wheels -r /tmp/requirements-runtime.txt

# ---------- runtime dependencies ----------
FROM base AS runtime-deps
COPY --from=runtime-dependency-builder /tmp/runtime-wheels /tmp/runtime-wheels
RUN pip install --no-cache-dir /tmp/runtime-wheels/* && rm -rf /tmp/runtime-wheels

# ---------- production application ----------
FROM runtime-deps AS production-base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=production \
    HOME=/tmp/oci-dis-home
RUN addgroup -S -g 10001 app \
    && adduser -S -D -H -u 10001 -G app app \
    && mkdir -p "$HOME" \
    && chown app:app "$HOME" \
    && chmod 0700 "$HOME"
COPY --chown=app:app apps/api/app ./app
COPY --chown=app:app apps/api/migrations ./migrations
COPY --chown=app:app apps/api/scripts ./scripts
COPY --chown=app:app apps/api/alembic.ini ./alembic.ini
COPY --chown=app:app packages/calc-engine/src/__init__.py /calc-engine/src/__init__.py
COPY --chown=app:app packages/calc-engine/src/engine /calc-engine/src/engine
COPY --chown=app:app packages/pricing-engine/src/pricing_engine /pricing-engine/src/pricing_engine
COPY --chown=app:app docs/api/openapi.yaml /docs/api/openapi.yaml
COPY apps/api/production-entrypoint.sh /usr/local/bin/oci-dis-entrypoint
RUN rm -rf /app/app/tests \
    && chmod 0755 /usr/local/bin/oci-dis-entrypoint
USER app
EXPOSE 8000
ENTRYPOINT ["oci-dis-entrypoint"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

# The deployed image installs no packages at runtime. Remove the package installer
# and its metadata so build tooling cannot become part of the production surface.
FROM production-base AS production
USER root
RUN python -m pip uninstall --yes pip
USER app

# ---------- quality dependency builder ----------
FROM base AS quality-dependency-builder
COPY apps/api/requirements-quality.txt /tmp/requirements-quality.txt
RUN pip wheel --no-cache-dir --wheel-dir /tmp/quality-wheels -r /tmp/requirements-quality.txt

# ---------- quality gates (never deployed) ----------
FROM production-base AS quality
USER root
COPY --from=quality-dependency-builder /tmp/quality-wheels /tmp/quality-wheels
RUN pip install --no-cache-dir /tmp/quality-wheels/* && rm -rf /tmp/quality-wheels
COPY --chown=app:app apps/api/app/tests ./app/tests
COPY --chown=app:app packages/calc-engine/src/tests /calc-engine/src/tests
COPY --chown=app:app packages/pricing-engine/tests /pricing-engine/tests
COPY --chown=app:app docker-compose.yml package.json /contracts/
COPY --chown=app:app apps/api/Dockerfile apps/api/production-entrypoint.sh /contracts/apps/api/
USER app
