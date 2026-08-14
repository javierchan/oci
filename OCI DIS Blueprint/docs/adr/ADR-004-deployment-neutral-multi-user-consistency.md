# ADR-004 — Deployment-neutral Multi-user Consistency

**Status:** Accepted  
**Date:** 2026-08-14  
**Scope:** Application behavior and local production-mode packaging only

## Context

Local authentication and project membership isolate data, but multiple users and
multiple future replicas also require consistent mutation authorization, stale
write protection, shared runtime state, safe dependency probes, and single-owner
scheduled work. None of those requirements authorizes an OCI deployment or
changes the future OCI IAM decision.

## Decision

1. Every authenticated unsafe HTTP operation is matched against one centralized
   mutation registry. An unregistered unsafe operation fails closed.
2. Authorization is the intersection of App role, live project membership,
   project role, entity-derived project context, and API-token restrictions.
3. Shared human-reviewed records carry an `expected_updated_at` precondition.
   Services lock the row, compare the version, and return typed HTTP 409 evidence
   instead of silently applying a stale update.
4. PostgreSQL, Redis, and S3-compatible Object Storage remain the only shared
   runtime authorities. App Knowledge is version-detected through the object
   store; container-local files are not a publication mechanism.
5. API containers run one Uvicorn process. Database pools are configurable, and
   asynchronous tasks use late acknowledgement, bounded visibility/result
   retention, low prefetch, worker-loss rejection, and Redis leases for scheduled
   ownership.
6. Readiness is read-only and fails closed for migration, Object Storage, Redis,
   or complete provider-embedding knowledge failures. Liveness proves process
   life only.
7. HTTP telemetry contains low-cardinality route data, a request ID, and W3C trace
   correlation. Prompts, responses, user IDs, project IDs, and credentials are not
   telemetry dimensions.

## Consequences

- Two users cannot knowingly overwrite the same reviewed version without a
  visible conflict and reload.
- Adding a mutation route requires an explicit policy and a regression test.
- Replicas can converge on shared App Knowledge without a shared filesystem.
- Scheduler duplication is harmless because only the Redis lease owner executes.
- The OCI observability exporter, IAM verifier, Helm/Terraform packaging, managed
  service selection, and actual failure testing remain M77 work.

## Explicit non-decisions

This ADR does not select or provision an OCI tenancy, Identity Domain, OKE
cluster, database, cache, Object Storage bucket, Vault secret, load balancer, or
observability service. It does not grant permission to authenticate to OCI.

## Validation

Acceptance requires executable negative authorization matrices, stale-write
tests, scheduler lease tests, dependency/readiness tests, shared knowledge
version tests, backend/engine/frontend gates, generated contract drift checks,
and a healthy production-mode local Compose stack.
