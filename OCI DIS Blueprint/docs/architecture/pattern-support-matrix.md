# OCI Integration Pattern Support Matrix

**Last updated:** 2026-04-16
**Milestone:** M23 — Pattern Coverage 03–17

## Support levels

| Level | Meaning |
|-------|---------|
| FULLY_SUPPORTED | End to end across capture, QA, volumetry, dashboard, narratives, and exports |
| REFERENCE_ONLY | Pattern exists in the governed library and UI, but parity-ready behavior is not fully operationalized in this phase |

## Support matrix

| ID | Name | Support Level | Notes |
|----|------|---------------|-------|
| #01 | Request-Reply | FULLY_SUPPORTED | Baseline synchronous parity path |
| #02 | Event-Driven / Pub-Sub | FULLY_SUPPORTED | Event-driven parity path with governed Streaming support |
| #03 | API Facade | REFERENCE_ONLY | Rich guidance available; pattern-specific parity remains incomplete |
| #04 | Saga / Compensation | REFERENCE_ONLY | Guidance and QA heuristics exist; full parity path remains incomplete |
| #05 | CDC — Change Data Capture | FULLY_SUPPORTED | CDC parity path documented and operationalized |
| #06 | Strangler Fig Runtime | REFERENCE_ONLY | Migration guidance only in current phase |
| #07 | Scatter-Gather | REFERENCE_ONLY | Fan-out guidance and QA limit checks exist; not full parity-ready sizing |
| #08 | Circuit Breaker | REFERENCE_ONLY | Resilience guidance only in current phase |
| #09 | Transactional Outbox | REFERENCE_ONLY | Guidance only; not a fully differentiated parity path |
| #10 | CQRS + Event Sourcing | REFERENCE_ONLY | Reference architecture only in current phase |
| #11 | BFF — Backend for Frontend | REFERENCE_ONLY | Guidance and Functions limit checks exist; parity remains incomplete |
| #12 | Data Mesh | REFERENCE_ONLY | Architectural library entry only |
| #13 | Zero-Trust Integration | REFERENCE_ONLY | Security architecture entry only |
| #14 | AsyncAPI + Event Catalog | REFERENCE_ONLY | Library guidance only in current phase |
| #15 | AI-Augmented Integration | REFERENCE_ONLY | Guidance and Functions checks exist; parity remains incomplete |
| #16 | Integration Mesh | REFERENCE_ONLY | Kubernetes-oriented reference architecture only |
| #17 | Webhook Fanout | REFERENCE_ONLY | Guidance and streaming/queue heuristics exist; parity remains incomplete |

## Phase 1 parity boundary

Patterns marked `REFERENCE_ONLY` remain intentionally selectable so architects can
document workbook-aligned intent, but the application must keep their support
state explicit. They must not present misleading parity-ready confidence.

Current operational surfaces for reference-only patterns may include:

- governed library metadata and anti-pattern guidance
- pattern detail guidance in the Integration Design Canvas
- QA warnings for specific pattern/tool conflicts
- support badges in the catalog detail workflow

Those surfaces improve honesty and safety, but they do not promote a pattern to
`FULLY_SUPPORTED` unless the full parity path is implemented across sizing,
dashboard, narratives, and exports.
