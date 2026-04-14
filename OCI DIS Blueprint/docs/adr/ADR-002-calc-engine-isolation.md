# ADR-002: Calculation Engine Isolation

**Status:** Accepted
**Date:** 2026-04-13
**Deciders:** Architecture team
**PRD Reference:** PRD-035, PRD-027

---

## Context

Workbook parity requires deterministic, reproducible calculations. Calculation logic historically
lives in Excel formulas (TPL - Volumetría). Embedding this logic in API service code risks:
- Non-determinism from ORM lazy-loading or HTTP side effects
- Difficulty testing individual formulas in isolation
- Breaking parity when API code evolves

## Decision

The calculation engine (`packages/calc-engine/`) is a **pure Python package** with zero external
dependencies (no DB, no HTTP, no Celery). It exposes typed functions that accept explicit inputs
and return `CalcResult` objects containing the computed value, unit, formula string, input snapshot,
and used assumption keys.

The Celery worker calls the engine and persists the result as an immutable `VolumetrySnapshot`.
No calculation logic exists in routers or service files.

## Consequences

- Every formula is independently testable with `pytest`
- Parity tests can run without a database or network connection
- Engine can be called from CLI for ad-hoc benchmarking
- Any assumption change requires an explicit new `AssumptionSet` version — no silent recalculation
- Formulas must be reviewed when workbook assumptions change (service limit updates, billing changes)

## Action Items

- [x] Implement volumetry.py with CalcResult typing
- [x] Implement qa.py with structured QA reasons
- [x] Implement importer.py with inclusion rules
- [x] Write parity tests (test_volumetry.py, test_importer.py)
- [ ] Add CLI entrypoint for benchmark comparison to workbook
