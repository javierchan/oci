# Next.js — Docker Desktop (macOS) — all stages containerized.
# Build from the monorepo root so Docker uses the shared workspace lockfile and
# security overrides instead of resolving app dependencies independently.
FROM node:20-alpine AS base
WORKDIR /workspace

# ---------- deps ----------
FROM base AS deps
COPY package.json package-lock.json ./
COPY apps/web/package.json ./apps/web/package.json
RUN npm ci

# ---------- development ----------
FROM deps AS development
COPY apps/web ./apps/web
WORKDIR /workspace/apps/web
EXPOSE 3000
CMD ["npm", "run", "dev"]

# ---------- builder ----------
FROM deps AS builder
COPY apps/web ./apps/web
WORKDIR /workspace/apps/web
RUN npm run build

# ---------- production ----------
FROM base AS production
ENV NODE_ENV=production
RUN addgroup --system --gid 1001 nodejs && adduser --system --uid 1001 nextjs
COPY --from=builder --chown=nextjs:nodejs /workspace/apps/web/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /workspace/apps/web/.next/static ./apps/web/.next/static
COPY --from=builder --chown=nextjs:nodejs /workspace/apps/web/public ./apps/web/public
USER nextjs
EXPOSE 3000
CMD ["node", "apps/web/server.js"]
