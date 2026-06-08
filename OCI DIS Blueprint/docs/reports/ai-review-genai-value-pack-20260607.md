# AI Review GenAI Value Pack — 2026-06-07

## Objective

Improve the existing GenAI/AI Review layer so it creates concrete architecture-review value from governed catalog, topology, import, canvas, QA, volumetry, baseline, and export evidence.

## Implemented

- Decision-grade AI Review output:
  - `decision_brief`
  - `topology_insights`
  - `stress_scenarios`
  - `remediation_plan`
  - reviewer personas, red-team contradictions, confidence signals, and deterministic evidence registry remain intact.
- Provider operations:
  - Provider status endpoint and UI card.
  - Deterministic-only fallback when no LLM key is configured.
  - Daily job quota controls for deterministic and LLM-backed review.
  - Prompt redaction for secrets, tokens, bearer headers, private keys, and password-like values before optional LLM calls.
- Governance and RBAC:
  - Read/run/mutation role gates for AI Review routes.
  - Reviewer/Viewer can read; Analyst can run; Architect/Admin can apply governed mutations.
  - Suggested patches still flow through catalog patch/audit paths.
- Review evolution:
  - Compare endpoint for completed jobs.
  - UI history comparison against the previous completed job in the same scope.
  - Fixed scope filtering so integration/canvas reviews compare only integration jobs for the same integration; map co-pilot compares only project jobs.
- Export:
  - Markdown export endpoint for completed AI Review jobs.
  - Export event is audited.
  - Project brief export now includes AI-derived decision brief, topology intelligence, stress scenarios, and remediation plan sections.
- Import intelligence:
  - Read-only Import Data Quality Assistant endpoint.
  - Import UI shows batch evidence metrics, coverage, excluded-row findings, and next action for selected batches.
- Canvas and topology entry points:
  - Integration Design Canvas exposes "Review canvas with AI".
  - Topology dependency path co-pilot opens the governed review board with graph context.
  - Canvas semantics now use the real governed combinations instead of an empty local list.

## Validation

- Backend tests:
  - `docker compose exec -T api pytest app/tests/test_ai_reviews_api.py app/tests/test_import_service.py app/tests/test_exports_api.py -v`
  - Result: `18 passed in 0.53s`
- Backend lint:
  - `docker compose exec -T api ruff check ...`
  - Result: `All checks passed!`
- Web build:
  - `docker compose build web`
  - Result: Next.js production build passed compile, lint/type validation, and static generation.
- OpenAPI:
  - `docker compose run --rm -v "$PWD:/workspace" -w /workspace -e PYTHONPATH=/workspace/apps/api:/workspace/packages/calc-engine/src api python apps/api/scripts/export_openapi.py --check`
  - Initial result: out of date.
  - Regenerated `docs/api/openapi.yaml`.
  - Final result: OpenAPI artifact is up to date.
- Browser validation against live Docker stack:
  - Dashboard AI Review opened provider/quota, ran a project job, rendered history comparison, and exposed Markdown export.
  - Import selected batch `688346bb-fca9-49f5-be56-a1642d56a16c` rendered Data Quality Assistant metrics for 456 parsed rows, 420 included rows, 36 excluded rows, and source-row table.
  - Integration/canvas review for `55d40a1b-bad5-4426-af01-606074e3b857` ran successfully and compared only same-integration history.
  - Catalog drawer tabs `Overview`, `Canvas`, `Volumetry`, `QA`, and `History` respond through `role="tab"` and render distinct content.
  - Topology map renders the requested workspace-style representation with cluster bands, circular systems, QA/volume edges, compact controls, dependency detail, and map legend.
  - Topology co-pilot ran a project review from selected dependency-path context and compared only project history.
  - Browser console: no errors or warnings captured.
  - API/web logs: no unexpected 4xx/5xx errors; only expected 200/202 requests and healthchecks.

## Production Constraints

- Trigger/source-owned fields remain read-only by design; AI can recommend actions but does not auto-patch immutable source lineage.
- Current local role enforcement uses request headers; production still needs a real identity provider/session integration.
- LLM data retention, tenant policy, and provider SLA controls must be finalized before enabling LLM mode outside governed environments.
