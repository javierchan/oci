# Governed Integration Pattern Certification

**Certification version:** 1.0.0  
**Applies to:** governed system patterns `#01` through `#21`

## Purpose

OCI DIS Architect certifies the **use of a pattern inside the App**. This is an
internal, versioned governance contract; it is not an Oracle product
certification. A pattern definition is certified only when the App owns its
required evidence, approved tool composition, sizing strategy, commercial
service coverage, validation controls, QA behavior, narratives, dashboard
projection, and exports.

Selecting a certified pattern does not automatically certify an integration.
The integration must also provide the required evidence and use an approved
core-tool and overlay composition. Missing evidence or a noncompliant canvas
keeps that integration in architect review with stable reason codes.

## Certification Matrix

| ID | Pattern | Sizing strategy | Required evidence | Governed implementation boundary |
|---|---|---|---|---|
| #01 | Request-Reply | request/response | Target latency | OIC or Functions; API edge when used |
| #02 | Event-Driven / Pub-Sub | event backbone | Idempotency | Streaming, Queue, or OIC + Functions |
| #03 | API Facade | API edge | Latency, data classification | API Gateway with OIC or Functions |
| #04 | Saga / Compensation | stateful orchestration | Criticality, retry, idempotency | OIC with durable recovery controls |
| #05 | CDC | data movement | Window, data classification | GoldenGate, Data Integration, or ODI |
| #06 | Strangler Fig Runtime | migration coexistence | Criticality, latency | API Gateway and OIC migration route |
| #07 | Scatter-Gather | parallel fan-out | Fan-out, latency | OIC parallel branches |
| #08 | Circuit Breaker | resilient delivery | Retry, latency | OIC or Queue with observable recovery |
| #09 | Transactional Outbox | transactional event | Idempotency, retention | GoldenGate or Streaming relay |
| #10 | CQRS + Event Sourcing | event projection | Idempotency, retention, classification | Streaming + Functions with archive |
| #11 | BFF | experience API | Latency, classification | API Gateway with OIC or Functions |
| #12 | Data Mesh | governed data product | Criticality, retention, classification | Data processing plus catalog and storage |
| #13 | Zero-Trust Integration | zero-trust policy | Classification, latency | API Gateway, IAM, and workload route |
| #14 | AsyncAPI + Event Catalog | event contract | Classification, retention | Broker plus governed event catalog |
| #15 | AI-Augmented Integration | AI inference | Classification, latency | Integration route plus declared model capacity |
| #16 | Integration Mesh | service mesh | Criticality, classification, latency | Governed route plus external OKE/Istio capacity |
| #17 | Webhook Fanout | webhook fan-out | Fan-out, retry, idempotency | API edge, buffer, and isolated subscribers |
| #18 | Scheduled Batch / File Transfer | scheduled batch | Processing window | OIC, Data Integration, or ODI with staging |
| #19 | Async Request-Reply | async correlation | Latency, retry, idempotency | Queue-backed correlated exchange |
| #20 | Claim Check | claim check | Retention, classification | Object Storage plus reference transport |
| #21 | DLQ / Retry with Backoff | retry/DLQ | Retry, idempotency | Queue and observable replay controls |

## Runtime Enforcement

- `packages/calc-engine/src/engine/pattern_certification.py` is the pure,
  deterministic certification registry.
- QA evaluates required evidence and canvas composition on every import, capture,
  patch, and recalculation.
- The canvas exposes approved core tools and overlays from the same contract.
- Recalculation persists certification version, sizing strategy, composition
  compliance, and reason codes in immutable snapshot evidence.
- AI Review may explain or prioritize deterministic findings, but cannot certify
  a pattern or integration independently.
- XLSX, JSON, PDF, brief, Dashboard, and offline-template exports preserve the
  same certification status and provenance.

Unknown custom pattern IDs remain selectable for documentation but are
`unverified`; they cannot produce certified sizing or architecture-readiness
evidence until a reviewed certification profile and regression fixtures are
added.
