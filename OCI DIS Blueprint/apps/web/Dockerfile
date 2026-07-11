# Next.js — Docker Desktop (macOS) — all stages containerized.
# Build from the monorepo root so Docker uses the shared workspace lockfile and
# security overrides instead of resolving app dependencies independently.
FROM node:26.0.0-alpine AS base
WORKDIR /workspace

# ---------- deps ----------
FROM base AS deps
COPY package.json package-lock.json ./
COPY apps/web/package.json ./apps/web/package.json
RUN npm ci

# ---------- quality gates ----------
FROM deps AS test
COPY apps/web ./apps/web
WORKDIR /workspace/apps/web
RUN npm test

FROM deps AS lint
COPY apps/web ./apps/web
WORKDIR /workspace/apps/web
RUN npm run type-check && npm run lint

# ---------- builder ----------
FROM deps AS builder
COPY apps/web ./apps/web
WORKDIR /workspace/apps/web
RUN npm run build

# ---------- production ----------
FROM base AS production
ENV NODE_ENV=production
RUN apk upgrade --no-cache \
    && rm -rf /usr/local/lib/node_modules/npm /usr/local/bin/npm /usr/local/bin/npx \
    && addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 nextjs
COPY --from=builder --chown=nextjs:nodejs /workspace/apps/web/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /workspace/apps/web/.next/static ./apps/web/.next/static
COPY --from=builder --chown=nextjs:nodejs /workspace/apps/web/public ./apps/web/public
USER nextjs
EXPOSE 3000
CMD ["node", "apps/web/server.js"]
