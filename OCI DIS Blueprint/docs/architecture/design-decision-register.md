# Design Decision Register

This register explains the architectural choices visible in the current
repository. An accepted decision is implemented and validated; a planned
decision describes the approved direction but cannot be presented as current
runtime behavior. ADR references are immutable. Entries marked “ADR required”
must receive a dedicated record before production deployment.

| ID | Status | Decision | Why | Consequence and evidence | ADR |
| --- | --- | --- | --- | --- | --- |
| DD-01 | Accepted | Use a Next.js, FastAPI, PostgreSQL, Redis/Celery, and S3-compatible modular monorepo. | Separates UI, typed API, durable state, asynchronous work, and artifacts while retaining Python engines. | Two application runtimes are maintained; the root CI contract validates both. | [ADR-001](../adr/ADR-001-stack-selection.md) |
| DD-02 | Accepted | Keep calculation and pricing engines pure and free of database, HTTP, or Celery dependencies. | Workbook parity and commercial totals must be deterministic and independently reproducible. | Services assemble explicit inputs; immutable outputs preserve formulas and provenance. | [ADR-002](../adr/ADR-002-calc-engine-isolation.md) |
| DD-03 | Accepted | Preserve source evidence separately from governed working records. | Correction must never erase what the client supplied. | Immutable source rows and original artifacts coexist with human-authorized catalog values and audit. | ADR required |
| DD-04 | Accepted | Put business transactions in services and keep routers thin. | HTTP concerns should not become domain authority, and workers must reuse the same rules. | Routers validate contracts; services own mutations and audit. | ADR required |
| DD-05 | Accepted | Normalize OCI service limits and interoperability rules as runtime authority. | Versioned service facts must be consistent across canvas, sizing, review, and export. | Client assumptions cannot silently override OCI service facts. | ADR required |
| DD-06 | Accepted | Model deployment scenarios separately from the logical integration catalog. | DEV, QA, and PRD rollout timing changes consumption, not the integration definition. | Monthly BOM projections retain environment and phase provenance without duplicating integrations. | ADR required |
| DD-07 | Accepted | Use immutable snapshots and Decimal commercial calculations. | Technical and commercial results must be explainable and comparable after rules or prices change. | Recalculation creates new evidence; it does not rewrite a prior published result. | ADR required |
| DD-08 | Accepted | Use one S3-compatible artifact boundary. | Local MinIO and future OCI Object Storage need the same object-key contract. | Persistent artifacts cannot depend on container disks; legacy local paths are read-compatible only. | ADR required |
| DD-09 | Accepted | Separate deterministic and agent Celery consumers. | Model latency and provider failures must not starve import, recalculation, or pricing jobs. | `agent-worker` consumes the `agents` queue; delivery hardening is still required for OKE. | ADR required |
| DD-10 | Accepted | Treat Generative AI as advisory and expose only typed, allowlisted App tools. | Models must not become authority for quantities, prices, governed mutations, or arbitrary infrastructure access. | Deterministic evidence remains authoritative; approval and execution are separate audited commands. | ADR required |
| DD-11 | Accepted | Use OCI Responses first and Chat only as endpoint compatibility for the same provider. | OCI model endpoints have differing OpenAI-compatible capabilities. | “Chat fallback” is not a local answer fallback or alternate model. | ADR required |
| DD-12 | Accepted | Require provider embeddings for a configured production App Assistant. | Mixing vector spaces or silently using weaker retrieval made answers erratic and hid outages. | Loss of provider vectors or query embedding fails the answer closed. Local vectors remain test/build evidence only. | ADR required |
| DD-13 | Accepted | Let the App Knowledge Governance Agent regenerate and validate embeddings automatically. | The knowledge derives from executable App contracts and curated App guidance; routine human approval adds delay without a new source of truth. | Publication is atomic only after model, dimensions, hash, coverage, and drift checks pass; shared storage is still planned. | ADR required |
| DD-14 | Accepted | Keep inferred conversation context internal and explicit contexts user-visible and persistent. | The assistant needs continuity without showing internal memory mechanics or losing user-selected evidence. | Only `Add context` attachments are visible/removable; prior model answers are never authoritative evidence. | ADR required |
| DD-15 | Accepted | Use an AI-led Import Correction Agent inside deterministic invariants and human promotion. | Import deviations cannot be enumerated exhaustively, but provenance, formula rejection, supported schema, and authorization cannot be probabilistic. | The agent reasons per line and proposes corrections; the App enforces invariants; the human authorizes or rejects. | ADR required |
| DD-16 | Accepted | Keep one canonical repository-root CI workflow. | Duplicate workflows had drifted and created false confidence. | API, engines, frontend, OpenAPI, migrations, images, and browser gates share one release contract. | ADR required |
| DD-17 | Planned | Deploy the primary platform in `mx-queretaro-1` and spread stateless replicas across three Fault Domains. | Queretaro is the required data and operational region; the region has one Availability Domain. | Fault-Domain spread and disruption budgets are mandatory; this is not a regional disaster-recovery solution. | ADR required before OCI creation |
| DD-18 | Planned | Keep OCI GenAI in `us-chicago-1` as a monitored remote dependency with no assistant answer fallback. | Required models and Guardrails are remote; distance does not justify moving the primary platform. | Cross-region latency, egress, quota, and failure alarms are part of release evidence. | ADR required before OCI creation |
| DD-19 | Planned | Derive identity and roles from OCI IAM tokens and reject caller-supplied identity headers. | Current role checks trust unverified client headers. | Production ingress and API authorization must bind actor identity to a verified subject. | ADR required |
| DD-20 | Planned | Publish App Knowledge as an immutable Object Storage artifact with a transactional active-version pointer. | Per-container `/tmp` publication diverges across replicas. | A replica serves only a complete active hash and readiness fails if that version is unavailable. | ADR required |
| DD-21 | Planned | Use OCI-native observability with OpenTelemetry correlation. | Local logs and bounded GenAI counters cannot support a distributed OKE service. | Metrics and traces exclude customer content, prompts, credentials, and high-cardinality identities. | ADR required |

## Decision principles

1. **Evidence before synthesis.** A model can explain only evidence the App can
   retrieve and label.
2. **Correction without source destruction.** Raw evidence is immutable; every
   promoted interpretation is traceable.
3. **Approval is not execution.** Human acceptance authorizes a governed
   proposal; idempotent domain actions produce actual state.
4. **One authority per fact.** Service facts, workload assumptions, commercial
   terms, and conversation continuity have different owners.
5. **Failure must be visible.** A failed provider, embedding, safety, or
   grounding stage is not converted into a successful assistant answer.
6. **Deployment claims require runtime evidence.** Container compatibility is
   not Kubernetes readiness, and a plan is not a provisioned OCI service.

## ADR backlog order

Before OCI provisioning, create dedicated ADRs in this order:

1. Production identity and role derivation (`DD-19`).
2. Shared App Knowledge publication (`DD-20`).
3. OKE topology, database connection budget, and queue semantics (`DD-17`).
4. Queretaro-to-Chicago dependency and regional recovery (`DD-18`).
5. Observability data policy and platform (`DD-21`).
6. Source/correction governance and agent authority (`DD-03`, `DD-10`,
   `DD-12`, `DD-15`).

Historical decisions must not be rewritten to match future behavior. Superseding
an accepted decision requires a new ADR that links to the old record and
explains the migration and rollback consequences.
