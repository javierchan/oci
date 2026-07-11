"""Seed reference data for patterns, dictionary options, and assumptions."""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.db import get_sync_database_url
from app.models import (
    AssumptionSet,
    AuditEvent,
    DictionaryOption,
    PatternDefinition,
    PromptTemplateVersion,
    ServiceCapabilityProfile,
    ServiceEvidenceSource,
    ServiceInteroperabilityRule,
    ServiceLimit,
    ServiceProductVersion,
)
from app.migrations.reference_seed_data import DICTIONARY_OPTIONS

PATTERNS: list[dict[str, str]] = [
    {
        "pattern_id": "#01",
        "name": "Request-Reply",
        "category": "SYNCHRONOUS",
        "description": "One system asks, another responds — synchronous, bounded-latency contracts.",
        "oci_components": "OIC Gen3 (REST/SOAP adapter) | OCI API Gateway | OCI APM",
        "when_to_use": (
            "- Operations that complete in under 30 seconds.\n"
            "- Real-time lookups: price checks, stock availability, identity validation.\n"
            "- Transactions requiring immediate confirmation before the caller proceeds.\n"
            "- Integrations where the source system cannot continue without the response."
        ),
        "when_not_to_use": (
            "Do NOT use for operations that may exceed 30 seconds — the caller will time out "
            "and the integration will appear to fail even if it completes. "
            "Use an asynchronous pattern (#02 or #04) and return a correlation ID instead."
        ),
        "technical_flow": (
            "1. Source system calls OIC REST/SOAP trigger endpoint.\n"
            "2. OIC validates schema, headers, and authentication.\n"
            "3. OIC invokes downstream adapter (REST, SOAP, DB, or ERP).\n"
            "4. Response payload is mapped and returned synchronously to the caller.\n"
            "5. OCI APM records latency, status code, and payload size per execution."
        ),
        "business_value": (
            "Simplest pattern — zero queue overhead, predictable latency, and straightforward "
            "debugging via OCI APM traces. Ideal for read-heavy, low-latency integration paths."
        ),
    },
    {
        "pattern_id": "#02",
        "name": "Event-Driven / Pub-Sub",
        "category": "ASYNCHRONOUS",
        "description": "Events flow; subscribers react — decouple producers from consumers permanently.",
        "oci_components": "OCI Streaming (Kafka-compatible) | OIC Kafka Adapter | OCI Functions (consumer) | OCI Monitoring",
        "when_to_use": (
            "- High-volume event streams where multiple independent consumers react to the same event.\n"
            "- Source and target must remain fully decoupled (different teams, different SLAs).\n"
            "- Events must be replayed or audited after the fact.\n"
            "- Fan-out to N consumers from a single producer."
        ),
        "when_not_to_use": (
            "OCI Streaming guarantees at-least-once delivery, NOT exactly-once. "
            "Every consumer MUST be idempotent. "
            "Do not use when strict message ordering is required across partitions — "
            "ordering is only guaranteed within a single partition."
        ),
        "technical_flow": (
            "1. Producer publishes event to an OCI Streaming topic (Kafka-compatible API).\n"
            "2. OIC Kafka Adapter or OCI Functions consumer subscribes to the topic.\n"
            "3. Consumer processes the event and applies business logic.\n"
            "4. Consumer commits offsets after successful processing.\n"
            "5. Failed messages are routed to a Dead Letter Queue (DLQ) for reprocessing."
        ),
        "business_value": (
            "Elastic fan-out with zero coupling between producer and consumers. "
            "Consumers can be added or removed without touching the producer. "
            "Survives consumer downtime via offset replay. "
            "Enables real-time analytics pipelines alongside transactional consumers."
        ),
    },
    {
        "pattern_id": "#03",
        "name": "API Facade",
        "category": "SECURITY / PERFORMANCE",
        "description": "One stable API hides the chaos behind — simplify, secure, and throttle at the edge.",
        "oci_components": "OCI Functions | OCI API Gateway (rate limit + auth policies) | OCI WAF (optional) | OCI Vault",
        "when_to_use": (
            "- Exposing internal services to external partners or third parties.\n"
            "- Consolidating multiple backend calls under one stable public endpoint.\n"
            "- Applying JWT / OAuth2 security, rate limiting, or IP allowlisting centrally.\n"
            "- Versioning an API contract independently from its backend implementation."
        ),
        "when_not_to_use": (
            "Do NOT implement complex orchestration or business logic inside the OCI Function. "
            "Functions in this pattern should transform and route only. "
            "Multi-step orchestration with error handling and compensation belongs in OIC (#04 Saga)."
        ),
        "technical_flow": (
            "1. Client request arrives at OCI API Gateway (rate limit and auth policy evaluated).\n"
            "2. Gateway invokes the OCI Function facade.\n"
            "3. Function routes to one or more backend services, applying schema transformation.\n"
            "4. Aggregated response is normalized and returned to the client.\n"
            "5. OCI Vault manages all backend credentials — no secrets in Function code."
        ),
        "business_value": (
            "Decouples the public API contract from backend implementation details. "
            "Enables API versioning, blue-green backend migrations, and centralized security policy "
            "without touching client code."
        ),
    },
    {
        "pattern_id": "#04",
        "name": "Saga / Compensation",
        "category": "RESILIENCE",
        "description": "Distribute transactions across services — each step compensates if a later step fails.",
        "oci_components": "OIC Process Automation | OIC Integration (orchestration) | OCI Queue (async compensation buffer)",
        "when_to_use": (
            "- Multi-system transactions that cannot use two-phase commit (e.g., ERP + WMS + payment gateway).\n"
            "- Long-running business processes exceeding 30 seconds.\n"
            "- When partial failure must be reversed cleanly without leaving inconsistent state across systems."
        ),
        "when_not_to_use": (
            "Every step in the saga MUST be idempotent. "
            "Non-idempotent compensation steps will corrupt state on retry. "
            "Do not model sagas with more than 10 steps — the compensation graph becomes unmanageable "
            "and debugging failures becomes intractable."
        ),
        "technical_flow": (
            "1. OIC Process Automation starts the saga and checkpoints initial state.\n"
            "2. Steps execute sequentially; each step records a compensation action.\n"
            "3. Step N fails — compensation chain is triggered in reverse order.\n"
            "4. Each compensation action undoes its corresponding forward step.\n"
            "5. Process terminates with FAILED status and a complete audit trail of all forward and compensation calls."
        ),
        "business_value": (
            "Achieves distributed consistency across heterogeneous systems without distributed locks "
            "or two-phase commit. Enables long-running business workflows (order fulfillment, "
            "multi-brand price updates) that span systems with different reliability profiles."
        ),
    },
    {
        "pattern_id": "#05",
        "name": "CDC — Change Data Capture",
        "category": "DATA",
        "description": "Stream every database mutation as an event — real-time data integration without polling.",
        "oci_components": "Oracle GoldenGate (CDC engine) | OCI Streaming | OCI Data Integration (optional transformation layer)",
        "when_to_use": (
            "- Real-time replication from an Oracle DB to a data warehouse, data lake, or another OLTP system.\n"
            "- Replacing polling-based DB sync jobs that cause load spikes.\n"
            "- Capturing inserts, updates, and deletes with full before/after row images."
        ),
        "when_not_to_use": (
            "Requires a separate Oracle GoldenGate license — validate licensing cost before adopting. "
            "Not cost-effective for tables with infrequent changes where a scheduled batch would suffice. "
            "CDC consumers MUST process events idempotently — GoldenGate guarantees at-least-once delivery."
        ),
        "technical_flow": (
            "1. GoldenGate captures redo log entries on the source Oracle DB (extract process).\n"
            "2. Trail file is published as events to an OCI Streaming topic.\n"
            "3. OCI Data Integration or OIC consumes the stream and applies transformations.\n"
            "4. Transformed records are written to the target system.\n"
            "5. GoldenGate trail checkpoints ensure no events are skipped on restart."
        ),
        "business_value": (
            "Near-zero latency replication with no impact on source system query load. "
            "Eliminates bulk ETL batch windows. "
            "Enables event-driven data products downstream of the DB without application code changes."
        ),
    },
    {
        "pattern_id": "#06",
        "name": "Strangler Fig Runtime",
        "category": "MIGRATION",
        "description": "Route traffic selectively — migrate legacy systems incrementally without big-bang cutovers.",
        "oci_components": "OCI API Gateway (routing table) | OIC Gen3 (translation layer) | OCI Monitoring (traffic split visibility)",
        "when_to_use": (
            "- Legacy system modernization where full cutover is too risky.\n"
            "- When new and old systems must coexist during a multi-month migration window.\n"
            "- When new system functionality is delivered incrementally and needs real traffic to validate."
        ),
        "when_not_to_use": (
            "This is a MIGRATION pattern, not a permanent architecture. "
            "Operating the Strangler Fig routing layer indefinitely creates permanent dual-maintenance burden "
            "on two systems. Define explicit completion criteria and a deadline to remove the routing layer "
            "once migration is complete."
        ),
        "technical_flow": (
            "1. API Gateway receives 100% of traffic for the integration endpoint.\n"
            "2. Routing policy sends X% to legacy system, (100-X)% to new system.\n"
            "3. OIC translation layer adapts data model differences where schemas diverge.\n"
            "4. OCI Monitoring tracks error rates, latency, and response parity per route.\n"
            "5. Traffic weight is shifted incrementally (10% → 50% → 100% new) until migration is complete."
        ),
        "business_value": (
            "Zero-downtime migration with rollback capability at any traffic split percentage. "
            "Reduces big-bang cutover risk by validating the new system against real production traffic "
            "before full commitment."
        ),
    },
    {
        "pattern_id": "#07",
        "name": "Scatter-Gather",
        "category": "SYNCHRONOUS",
        "description": "Fan out a single request to multiple services, aggregate responses — parallel orchestration.",
        "oci_components": "OIC Gen3 (Parallel Flow action) | OCI Functions (optional per-branch callout) | OCI APM",
        "when_to_use": (
            "- Aggregating responses from multiple independent systems in a single user-facing request.\n"
            "- Operations where parallel execution reduces total latency vs. sequential calls.\n"
            "- Price aggregation across N suppliers, availability checks across N warehouses."
        ),
        "when_not_to_use": (
            "MUST handle partial failures explicitly. "
            "If 1 of 5 branches fails, the integration must decide: fail-all, best-effort with partial results, "
            "or return a degraded response with an error flag. "
            "Silent partial failure — returning a result without indicating that a branch failed — "
            "is a critical correctness defect."
        ),
        "technical_flow": (
            "1. OIC receives a single inbound request.\n"
            "2. Parallel Flow action forks N concurrent branches, one per target system.\n"
            "3. Each branch executes its callout independently.\n"
            "4. Gather step waits for all branches to complete (with a configurable timeout).\n"
            "5. Results are aggregated, mapped to the response schema, and returned to the caller."
        ),
        "business_value": (
            "Reduces latency of multi-system reads from O(N) sequential to O(1) parallel. "
            "Enables real-time dashboards and aggregation APIs that would be too slow if called sequentially."
        ),
    },
    {
        "pattern_id": "#08",
        "name": "Circuit Breaker",
        "category": "RESILIENCE",
        "description": "Stop calling a failing service — protect the system from cascade failure.",
        "oci_components": "OIC Error Handling (retry + fault scope) | OCI Monitoring (threshold alerts) | OCI Notifications",
        "when_to_use": (
            "- When a downstream service has intermittent failures or latency spikes.\n"
            "- When failure of one service must not cascade to its callers.\n"
            "- Any integration that calls an external system with variable availability."
        ),
        "when_not_to_use": (
            "Do NOT confuse Circuit Breaker with Retry. "
            "Retry retries immediately on failure. "
            "Circuit Breaker STOPS calling after N consecutive failures and waits a recovery window before probing. "
            "Both are complementary — use Retry for transient errors, Circuit Breaker for sustained outages."
        ),
        "technical_flow": (
            "1. OIC calls downstream service normally (circuit CLOSED).\n"
            "2. Failure counter increments on each error response or timeout.\n"
            "3. Counter exceeds threshold — circuit transitions to OPEN (no calls sent to downstream).\n"
            "4. After a configured recovery timeout, circuit transitions to HALF-OPEN (one probe sent).\n"
            "5. Probe succeeds → circuit CLOSED; probe fails → circuit returns to OPEN with reset timer."
        ),
        "business_value": (
            "Prevents cascading failures from propagating upstream. "
            "Enables graceful degradation (serve cached or default response while circuit is open). "
            "Reduces load on a recovering downstream system — giving it space to heal."
        ),
    },
    {
        "pattern_id": "#09",
        "name": "Transactional Outbox",
        "category": "DATA / DELIVERY GUARANTEES",
        "description": "Write to DB and event log in the same transaction — guaranteed delivery without two-phase commit.",
        "oci_components": "Oracle DB (outbox table) | Oracle GoldenGate (CDC on outbox table) | OCI Streaming",
        "when_to_use": (
            "- When a DB write and a message publish MUST succeed or fail atomically.\n"
            "- Order creation that must also publish an order event — both or neither.\n"
            "- Any integration where 'event was lost' is unacceptable and dual-write race conditions are a risk."
        ),
        "when_not_to_use": (
            "Consumers of the outbox stream MUST be idempotent. "
            "The Transactional Outbox guarantees at-least-once delivery to the stream — "
            "a message may be delivered more than once during recovery. "
            "Consumers that cannot handle duplicates will produce incorrect business results."
        ),
        "technical_flow": (
            "1. Application writes the business record AND an outbox event row in a single DB transaction.\n"
            "2. GoldenGate CDC detects the new outbox row via redo log capture.\n"
            "3. GoldenGate publishes the event to OCI Streaming.\n"
            "4. Consumer reads from the stream and processes the event.\n"
            "5. Outbox row is marked as published (or deleted) after confirmed delivery."
        ),
        "business_value": (
            "Eliminates the dual-write race condition — the most common cause of 'event was lost' defects "
            "in distributed systems. "
            "No distributed transaction coordinator required. "
            "Business record and event are always consistent by construction."
        ),
    },
    {
        "pattern_id": "#10",
        "name": "CQRS + Event Sourcing",
        "category": "DATA / ADVANCED",
        "description": "Commands mutate state via events; queries read from projections — separate write and read models.",
        "oci_components": "OCI Streaming (event store) | OCI Functions (projector) | Oracle ATP (read model) | OCI Object Storage (event archive)",
        "when_to_use": (
            "- A complete, immutable audit trail of every state change is required.\n"
            "- Read and write load patterns are dramatically different and must scale independently.\n"
            "- Event replay is needed for debugging, reprocessing, or rebuilding projections."
        ),
        "when_not_to_use": (
            "OVERKILL for simple CRUD applications. "
            "The event sourcing overhead — managing projections, handling schema evolution, "
            "implementing replay — costs significantly more than it saves unless the auditability "
            "or replay requirement genuinely exists. "
            "Default to Request-Reply (#01) or CDC (#05) first."
        ),
        "technical_flow": (
            "1. Command is validated and a domain event is emitted to OCI Streaming.\n"
            "2. Event is persisted as an immutable record (append-only event store).\n"
            "3. Projector Function reads the stream and updates the read model in Oracle ATP.\n"
            "4. Read model (projection) reflects the current state derived from all events.\n"
            "5. Queries are served exclusively from the ATP read model — never from the event store directly."
        ),
        "business_value": (
            "Complete, immutable audit trail. "
            "Temporal queries: reconstruct system state at any point in time by replaying events. "
            "Independent scaling of read and write paths. "
            "Debugging by replaying the exact event sequence that led to a defect."
        ),
    },
    {
        "pattern_id": "#11",
        "name": "BFF — Backend for Frontend",
        "category": "API DESIGN",
        "description": "One backend per client type — tailor the API contract to each consumer without compromise.",
        "oci_components": "OCI Functions (one Function per BFF) | OCI API Gateway (per-client routing) | OIC Gen3 (shared backend orchestration)",
        "when_to_use": (
            "- Mobile, web, and partner clients have fundamentally different data needs from the same backend.\n"
            "- A single generic API produces over-fetching (too much data) or under-fetching (multiple round trips).\n"
            "- Client-specific caching, authentication, or payload shaping is required."
        ),
        "when_not_to_use": (
            "Do NOT duplicate business logic in each BFF. "
            "BFF Functions should transform and aggregate only — "
            "they are an adaptation layer, not a business tier. "
            "Business rules belong in backend services. "
            "BFF proliferation with shared business logic is harder to maintain than a single generic API."
        ),
        "technical_flow": (
            "1. API Gateway identifies client type (mobile / web / partner) from the request path or header.\n"
            "2. Request is routed to the appropriate BFF Function.\n"
            "3. BFF calls shared backend services via OIC orchestration.\n"
            "4. Response is shaped (filtered, aggregated, formatted) for the specific client type.\n"
            "5. Client-specific caching headers and payload compression applied independently per BFF."
        ),
        "business_value": (
            "Eliminates over-fetching and under-fetching per client type. "
            "Each BFF can evolve independently of other clients. "
            "Mobile clients receive compact payloads; web clients receive richer responses. "
            "Partner API contracts are versioned and isolated from internal changes."
        ),
    },
    {
        "pattern_id": "#12",
        "name": "Data Mesh",
        "category": "ARCHITECTURE / DATA",
        "description": "Federate data ownership to domains — treat data products as first-class citizens.",
        "oci_components": "Oracle Data Catalog | OCI Object Storage (data product storage) | OCI Data Integration | OCI IAM (domain-scoped access policies)",
        "when_to_use": (
            "- Enterprise-scale data platforms with multiple autonomous data-producing domains.\n"
            "- The central data team is a delivery bottleneck for data consumers.\n"
            "- Each domain has the organizational maturity to own, publish, and SLA-commit to its data products."
        ),
        "when_not_to_use": (
            "Data Mesh requires ORGANIZATIONAL change, not just technology deployment. "
            "Deploying the tooling (Data Catalog, Object Storage, Data Integration) "
            "without domain ownership, per-product SLAs, and federated governance "
            "produces a more expensive, less governable data swamp. "
            "Technology without organizational change does not deliver Data Mesh outcomes."
        ),
        "technical_flow": (
            "1. Domain team owns, builds, and publishes its data product to OCI Object Storage.\n"
            "2. Schema and metadata are registered in Oracle Data Catalog.\n"
            "3. OCI Data Integration applies quality checks and format standardization.\n"
            "4. Consumers discover available data products via the Catalog.\n"
            "5. OCI IAM enforces domain-scoped access — consumers request access per product."
        ),
        "business_value": (
            "Scales data delivery beyond central team capacity. "
            "Reduces time-to-data for consumers by eliminating central pipeline queues. "
            "Enforces accountability at domain level — the producing team owns quality and availability."
        ),
    },
    {
        "pattern_id": "#13",
        "name": "Zero-Trust Integration",
        "category": "SECURITY",
        "description": "Never trust, always verify — mutual TLS, fine-grained authz, and observable access at every hop.",
        "oci_components": "OCI IAM (IDCS / IAM policies) | OCI API Gateway (mTLS + JWT validation) | OCI Vault (certificate management) | OCI Audit",
        "when_to_use": (
            "- External partner integrations crossing organizational trust boundaries.\n"
            "- Regulated workloads requiring demonstrable access controls (PCI-equivalent, HIPAA-equivalent).\n"
            "- Any integration where lateral movement from a compromised service must be contained."
        ),
        "when_not_to_use": (
            "Do NOT attempt to implement Zero-Trust across the entire integration estate simultaneously. "
            "Prioritize by data sensitivity classification. "
            "A phased rollout (highest sensitivity first) delivers security value immediately "
            "and avoids the operational paralysis of trying to secure everything at once."
        ),
        "technical_flow": (
            "1. Every service-to-service call presents a certificate or short-lived token.\n"
            "2. OCI API Gateway validates JWT claims and mTLS client certificate.\n"
            "3. OCI IAM policy is evaluated per request (not per session).\n"
            "4. OCI Vault rotates all credentials automatically on a defined schedule.\n"
            "5. Every access decision is logged to OCI Audit for compliance evidence."
        ),
        "business_value": (
            "Eliminates implicit trust within the network perimeter. "
            "Reduces blast radius of any single credential compromise. "
            "Produces audit evidence required by compliance frameworks without manual logging."
        ),
    },
    {
        "pattern_id": "#14",
        "name": "AsyncAPI + Event Catalog",
        "category": "API DESIGN / ASYNCHRONOUS",
        "description": "Document your events as contracts — an undocumented event stream is technical debt by default.",
        "oci_components": "OCI Streaming | OCI Schema Registry (Glue-compatible) | OIC Kafka Adapter",
        "when_to_use": (
            "- Any event-driven integration with more than one producer or consumer.\n"
            "- When contracts between teams must be enforced formally to prevent silent breaking changes.\n"
            "- When an event inventory is required for compliance, auditing, or developer onboarding."
        ),
        "when_not_to_use": (
            "A stale event specification is WORSE than no specification — "
            "it creates false confidence and misleads consumers about the actual schema in production. "
            "Only adopt this pattern if the team commits to keeping specifications current "
            "as part of the definition of done for every schema change."
        ),
        "technical_flow": (
            "1. Producer team defines the AsyncAPI schema and registers it in the Schema Registry.\n"
            "2. Schema version is published and assigned a unique identifier.\n"
            "3. Consumers validate inbound messages against the registered schema before processing.\n"
            "4. Breaking schema changes require a version bump — consumers choose their supported version.\n"
            "5. The Catalog is surfaced as a discoverable API inventory for all developers."
        ),
        "business_value": (
            "Prevents silent contract breakage between producer and consumer teams. "
            "Enables event discovery — new consumers find and subscribe to existing streams without tribal knowledge. "
            "Provides governance evidence: what events exist, who produces them, and who consumes them."
        ),
    },
    {
        "pattern_id": "#15",
        "name": "AI-Augmented Integration",
        "category": "AI",
        "description": "Enrich integration flows with AI inference — classify, extract, and route with intelligence.",
        "oci_components": "OIC Gen3 AI Agents | OCI Language (NLP service) | OCI Data Science (custom models) | OCI Functions (inference wrapper)",
        "when_to_use": (
            "- Document classification: routing invoices, orders, or emails by inferred category.\n"
            "- Sentiment or intent extraction from unstructured text payloads in transit.\n"
            "- Intelligent routing decisions based on payload content that cannot be rule-encoded."
        ),
        "when_not_to_use": (
            "Do NOT use AI for deterministic business rules. "
            "If the rule is 'amount > 1000 → route to approval queue', use a simple condition in OIC — "
            "not an AI model. "
            "AI is appropriate for probabilistic classification of ambiguous or unstructured content. "
            "Using AI for deterministic logic adds latency, cost, and non-determinism without benefit."
        ),
        "technical_flow": (
            "1. Integration receives a payload containing unstructured or semi-structured content.\n"
            "2. OCI Language or a custom OCI Data Science model is invoked via an OCI Function.\n"
            "3. Inference result (classification label, extracted entities, confidence score) is returned.\n"
            "4. OIC routes the integration flow based on the AI output.\n"
            "5. Low-confidence results (below threshold) are routed to a human-review queue rather than automated."
        ),
        "business_value": (
            "Automates previously manual classification and triage tasks at integration speed. "
            "Scales document processing without headcount. "
            "Reduces integration routing errors caused by inconsistent human tagging of inbound payloads."
        ),
    },
    {
        "pattern_id": "#16",
        "name": "Integration Mesh",
        "category": "ARCHITECTURE",
        "description": "Service mesh for integrations — centralize policy enforcement, observability, and traffic control.",
        "oci_components": "Istio on OKE (service mesh) | OCI API Gateway (north-south ingress) | OCI APM (distributed tracing) | OCI Monitoring",
        "when_to_use": (
            "- Large Kubernetes-based microservices estates where per-integration OIC flows are operationally unmanageable.\n"
            "- When uniform mTLS, retry, circuit break, and rate-limit policy must be applied across all services without code changes.\n"
            "- When distributed tracing across all service-to-service calls is required."
        ),
        "when_not_to_use": (
            "Requires significant Kubernetes and Istio operational maturity. "
            "Adopting this pattern without an experienced platform engineering team "
            "creates a more complex and less observable system than the one it replaces. "
            "Do not adopt Integration Mesh as a shortcut to avoid OIC licensing — "
            "the operational cost of running Istio correctly exceeds OIC licensing for most mid-market workloads."
        ),
        "technical_flow": (
            "1. All service-to-service traffic is routed through Istio sidecar proxies automatically.\n"
            "2. mTLS is enforced mesh-wide without application code changes.\n"
            "3. Traffic policies (rate limit, retry, circuit break) are applied via Istio VirtualService manifests.\n"
            "4. OCI APM receives distributed traces from all Envoy sidecars.\n"
            "5. OCI API Gateway handles north-south ingress from external callers into the mesh."
        ),
        "business_value": (
            "Centralized policy enforcement with zero application code changes. "
            "Automatic observability for all service-to-service calls. "
            "Zero-trust by default across the mesh — mTLS with no per-service configuration."
        ),
    },
    {
        "pattern_id": "#17",
        "name": "Webhook Fanout",
        "category": "ASYNCHRONOUS / API",
        "description": "Receive one webhook, fan out to N subscribers — decouple external event producers from internal consumers.",
        "oci_components": "OCI API Gateway (HMAC signature verification) | OIC Gen3 (fanout orchestration) | OCI Queue (delivery buffer)",
        "when_to_use": (
            "- Third-party systems that emit webhooks (payment gateways, SaaS platforms, marketplaces).\n"
            "- When multiple internal systems must react to the same external event independently.\n"
            "- When a single inbound endpoint must serve N registered subscriber systems."
        ),
        "when_not_to_use": (
            "No built-in rate control at the webhook source — for high-frequency webhook sources "
            "(more than 100 events per minute), buffer with OCI Queue before fanout. "
            "Direct fanout without a queue buffer will overwhelm downstream subscribers during traffic spikes "
            "and cause cascading failures across all N consumers simultaneously."
        ),
        "technical_flow": (
            "1. External system posts an event to the OCI API Gateway webhook endpoint.\n"
            "2. API Gateway verifies the HMAC signature — rejects unauthenticated requests.\n"
            "3. Validated event is handed to OIC for fanout orchestration.\n"
            "4. If volume is high, OCI Queue buffers events to provide backpressure.\n"
            "5. OIC fans out the event to N registered subscriber integrations in parallel."
        ),
        "business_value": (
            "Single inbound webhook endpoint serves N consumers with no changes at the source. "
            "HMAC verification prevents webhook spoofing attacks. "
            "OCI Queue provides backpressure for traffic spikes — "
            "subscribers are never overwhelmed regardless of inbound event rate."
        ),
    },
]

ASSUMPTION_SET = {
    "version": "1.0.0",
    "label": "Client workload assumptions v1",
    "is_default": True,
    "assumptions": {
        "month_days": 31,
        "streaming_default_partitions": 200,
        "functions_default_duration_ms": 2000,
        "functions_default_memory_mb": 256,
        "functions_default_concurrency": 1,
        "functions_batch_size_records": 500,
        "queue_throughput_soft_limit_msgs_per_second": 10,
        "business_metadata": {
            "salesforce_batch_limit_millions": 8,
            "file_server_concurrent_connections": 50,
            "default_record_size_bytes": 250,
            "hours_per_month": 744,
        },
    },
    "notes": "Client-provided or planning assumptions only. Oracle service limits are governed by Service Product Library.",
}

SERVICE_PROFILES: list[dict[str, object]] = [
    {
        "service_id": "API_GATEWAY",
        "name": "OCI API Gateway",
        "category": "API_INGRESS",
        "sla_uptime_pct": 99.95,
        "pricing_model": "Per 1 million API calls/month",
        "limits": {
            "max_request_body_kb": 20480,
            "max_function_backend_body_kb": 6144,
            "max_stock_response_body_kb": 20480,
            "max_cached_response_kb": 51200,
            "max_routes_per_deployment": 50,
            "max_deployments_per_gateway": 20,
            "max_gateways_monthly_universal_credits": 50,
            "max_gateways_payg": 5,
            "max_concurrent_https_per_ip": 1000,
            "backend_connect_timeout_max_s": 75,
            "backend_read_send_timeout_max_s": 300,
            "label": "documented",
        },
        "architectural_fit": (
            "API facade and north-south ingress. Policy enforcement (OAuth2/OIDC/JWT, "
            "mTLS, rate limiting, request/response transformation, caching) in front of "
            "OIC, Functions, ORDS, OKE workloads, or custom HTTP backends. "
            "Best used as a thin policy edge — not as a transformation-heavy ESB."
        ),
        "anti_patterns": (
            "NOT suitable for very large synchronous payloads (20 MB hard limit). "
            "NOT suitable for coarse-grained 'mega APIs' with unbounded route counts. "
            "NOT a replacement for OIC orchestration. "
            "Functions backend is limited to 6 MB — large payload mediation must use OIC instead. "
            "Default CA bundle is NOT used for client-certificate verification — "
            "custom CA bundles must be provided for mTLS."
        ),
        "interoperability_notes": (
            "Integrates natively with OCI Functions, general HTTP/HTTPS backends, ORDS, "
            "OKE ingress, and OIC endpoints. "
            "Supports OAuth2/OIDC token validation via Remote JWKS or static keys. "
            "Authorizer Functions enable custom authentication logic."
        ),
        "oracle_docs_urls": (
            "https://docs.oracle.com/en-us/iaas/Content/APIGateway/home.htm|"
            "https://docs.oracle.com/en-us/iaas/Content/APIGateway/Reference/apigatewaylimits.htm|"
            "https://docs.oracle.com/en-us/iaas/Content/APIGateway/Tasks/apigatewayusingjwttokens.htm|"
            "https://docs.oracle.com/en-us/iaas/Content/APIGateway/Tasks/apigatewayaddingmtlssupport.htm|"
            "https://www.oracle.com/cloud/cloud-native/api-management/pricing/"
        ),
    },
    {
        "service_id": "OIC3",
        "name": "Oracle Integration 3 (OIC Gen3)",
        "category": "ORCHESTRATION",
        "sla_uptime_pct": 99.9,
        "pricing_model": "Message pack (5,000 billing msgs/hr new license; 20,000 BYOL). Payloads >50 KB increment billing messages in 50 KB steps.",
        "limits": {
            "max_active_integrations": 800,
            "max_invocation_depth": 16,
            "sync_flow_max_duration_s": 300,
            "async_scheduled_flow_max_duration_s": 21600,
            "max_message_size_kb": 10240,
            "max_parallel_branches": 5,
            "billing_threshold_kb": 50,
            "pack_size_msgs_per_hour_new_license": 5000,
            "pack_size_msgs_per_hour_byol": 20000,
            "sync_concurrency_per_pack_new": 100,
            "sync_concurrency_per_pack_byol": 400,
            "async_concurrency_per_pack_new": 50,
            "async_concurrency_per_pack_byol": 200,
            "adapter_catalog_count": 133,
            "api_observability_instances_per_request": 50,
            "label": "documented",
            "note": "Parallel branches consume synchronous concurrency quota.",
        },
        "architectural_fit": (
            "Primary platform for application integration, workflow orchestration, "
            "saga-like business processes, and hybrid SaaS/on-prem integration. "
            "133 adapter catalog covers Oracle SaaS, third-party SaaS, databases, Kafka, "
            "OCI Streaming, REST, SOAP, and private resources. "
            "Connectivity agent enables hybrid/on-prem access without public IP. "
            "MCP server support allows integrations to be discovered as tools by AI agent frameworks. "
            "Best for adapter-heavy mediation and orchestration with error handling and compensation."
        ),
        "anti_patterns": (
            "NOT the right backbone for very high-rate event streams (>5,000 msgs/hr per pack) — "
            "use OCI Streaming/Queue in front of bursty work and keep OIC for orchestration. "
            "Synchronous flows hard-limited to 5 minutes — long-running work must be async. "
            "10 MB message size limit means large file/data transfers must use Object Storage or FTP. "
            "Parallel branches are capped at 5 — Scatter-Gather patterns with >5 targets need decomposition."
        ),
        "interoperability_notes": (
            "Private endpoints for VCN resources; connectivity agent for on-prem/FastConnect/VPN. "
            "Integrates with Oracle SaaS, Salesforce, SAP, and 130+ other adapters. "
            "Kafka adapter connects to OCI Streaming (Kafka-compatible). "
            "Rapid Adapter Builder for custom REST-based adapters without code. "
            "MCP: expose integration flows as tools for OCI AI Agents and compatible frameworks."
        ),
        "oracle_docs_urls": (
            "https://docs.oracle.com/en-us/iaas/application-integration/index.html|"
            "https://docs.oracle.com/en/cloud/paas/application-integration/oracle-integration-oci/service-limits.html|"
            "https://docs.oracle.com/en/cloud/paas/application-integration/oracle-integration-oci/message-pack-usage-synchronous-requests.html|"
            "https://docs.oracle.com/en/cloud/paas/application-integration/find-adapters.html|"
            "https://docs.oracle.com/en/cloud/paas/application-integration/aiagents/enable-mcp-project.html|"
            "https://www.oracle.com/integration/pricing/"
        ),
    },
    {
        "service_id": "STREAMING",
        "name": "OCI Streaming",
        "category": "EVENT_BACKBONE",
        "sla_uptime_pct": 99.9,
        "pricing_model": "GB-hour of storage + GB of PUT/GET data transferred. Minimum expected usage billed when exceeding default partition limits.",
        "limits": {
            "max_message_size_kb": 1024,
            "max_request_size_kb": 1024,
            "write_throughput_mb_s_per_partition": 1.0,
            "get_requests_per_s_per_consumer_group_per_partition": 5,
            "max_partitions_monthly_universal_credits": 200,
            "max_partitions_payg": 50,
            "max_consumer_groups_per_stream": 50,
            "retention_min_h": 24,
            "retention_max_d": 7,
            "partition_count_immutable_after_creation": True,
            "retention_immutable_after_creation": True,
            "label": "documented",
            "note": (
                "Partition count and retention period CANNOT be changed after stream creation. "
                "Size partitions slightly above maximum expected throughput to absorb spikes. "
                "OCI also offers 'Streaming with Apache Kafka' — a managed Kafka cluster service "
                "distinct from OCI Streaming. Choose consciously: Kafka-API compatibility ≠ full Kafka semantics."
            ),
        },
        "architectural_fit": (
            "Asynchronous event backbone for ordered partitioned log streams: telemetry, "
            "fan-out, CDC consumers, decoupled microservices event distribution, "
            "event sourcing append store. Kafka-compatible API allows existing producers/consumers "
            "to connect without self-managing ZooKeeper/Kafka infrastructure. "
            "Integrates natively with GoldenGate, Service Connector Hub, and OIC Kafka Adapter."
        ),
        "anti_patterns": (
            "NOT suitable for transactional work queues (use OCI Queue instead). "
            "1 MB hard message size limit — large event payloads must be externalized to Object Storage "
            "with only a reference pointer in the stream. "
            "Partition key design is critical: poor cardinality hotspots a single partition and "
            "collapses throughput to 1 MB/s total instead of N × 1 MB/s. "
            "Classic OCI Streaming is NOT a drop-in for every Kafka cluster feature — "
            "use managed Kafka service when true Kafka-cluster semantics (ACLs, SASL/SCRAM) are required."
        ),
        "interoperability_notes": (
            "Direct integration: Service Connector Hub (as source/target), "
            "GoldenGate (as source/target for CDC pipelines), OIC Kafka Adapter. "
            "Connector Hub can route Streaming events to Functions, Log Analytics, "
            "Object Storage, and back to Streaming."
        ),
        "oracle_docs_urls": (
            "https://docs.oracle.com/en-us/iaas/Content/Streaming/home.htm|"
            "https://docs.oracle.com/en-us/iaas/Content/Streaming/Concepts/streamingoverview_topic-Limits_on_Streaming_Resources.htm|"
            "https://docs.oracle.com/en-us/iaas/Content/Streaming/Concepts/partitioningastream.htm|"
            "https://docs.oracle.com/en-us/iaas/Content/Streaming/Tasks/kafkacompatibility.htm|"
            "https://docs.oracle.com/en-us/iaas/Content/kafka/home.htm|"
            "https://www.oracle.com/cloud/streaming/pricing/"
        ),
    },
    {
        "service_id": "QUEUE",
        "name": "OCI Queue",
        "category": "WORK_QUEUE",
        "sla_uptime_pct": 99.9,
        "pricing_model": "Per 1 million requests (first 1M/month free). A request = 64 KB; larger messages count as multiple requests.",
        "limits": {
            "max_message_size_kb": 256,
            "max_queues_per_tenancy_per_region": 10,
            "max_channels_per_queue": 256,
            "max_consumer_groups_per_queue": 10,
            "max_inflight_messages_per_queue": 100000,
            "ingress_throughput_mb_s_per_queue": 10,
            "egress_throughput_mb_s_per_queue": 10,
            "max_concurrent_get_rps": 1000,
            "max_message_ops_per_s_per_api_per_queue": 1000,
            "max_storage_per_queue_gb": 2,
            "max_storage_per_tenancy_gb": 20,
            "retention_min_s": 10,
            "retention_max_d": 7,
            "visibility_timeout_max_h": 12,
            "put_message_max_count_per_request": 20,
            "get_message_max_count_per_request": 20,
            "label": "documented",
            "note": "Transparently autoscales based on throughput within documented limits. Channels inherit queue permissions and limits.",
        },
        "architectural_fit": (
            "Durable asynchronous work queue for: transactional decoupling, retry buffering, "
            "saga step handoff, compensation handler invocation, and fan-out to N consumers. "
            "STOMP and REST/OpenAPI interfaces enable polyglot clients without Oracle-specific SDKs. "
            "DLQ semantics: messages exceeding max delivery attempts are moved to a dead-letter channel "
            "for inspection and reprocessing. Visibility timeout ensures at-most-one-in-flight per consumer."
        ),
        "anti_patterns": (
            "NOT a high-retention event log (max 7 days, max 2 GB/queue) — use OCI Streaming for replay. "
            "NOT for high-throughput event backbones (use Streaming). "
            "256 KB max message size — large payloads must be stored in Object Storage with a queue reference. "
            "10 queues per tenancy per region is a hard limit — design queue topology carefully; "
            "use channels (max 256 per queue) to subdivide a single queue for multiple consumers. "
            "Exactly-once processing is NOT guaranteed by service semantics — consumers must be idempotent."
        ),
        "interoperability_notes": (
            "Integrates with Service Connector Hub (Queue as source → Functions, Notifications, "
            "Object Storage, Streaming). STOMP interface enables legacy JMS-style clients. "
            "REST/OpenAPI spec available — any HTTP client can produce/consume without Oracle SDK."
        ),
        "oracle_docs_urls": (
            "https://docs.oracle.com/en-us/iaas/Content/queue/home.htm|"
            "https://docs.oracle.com/en-us/iaas/Content/queue/overview.htm|"
            "https://docs.oracle.com/en-us/iaas/Content/queue/messages-stomp.htm|"
            "https://docs.oracle.com/en-us/iaas/Content/queue/deadletterqueues.htm|"
            "https://www.oracle.com/cloud/queue/pricing/"
        ),
    },
    {
        "service_id": "FUNCTIONS",
        "name": "OCI Functions",
        "category": "SERVERLESS_COMPUTE",
        "sla_uptime_pct": 99.5,
        "pricing_model": "Per invocation + GB-memory-seconds. First 2M invocations/month and 400K GB-memory-seconds/month free. Provisioned concurrency charged at 25% when idle.",
        "limits": {
            "max_invoke_body_kb": 6144,
            "free_invocations_per_month": 2000000,
            "free_gb_memory_seconds_per_month": 400000,
            "provisioned_concurrency_idle_cost_pct": 25,
            "label": "documented",
            "sla_note": (
                "SLA is 99.5% — LOWER than API Gateway (99.95%), OIC (99.9%), and Queue (99.9%). "
                "Do not treat Functions as a zero-consideration control plane for mission-critical "
                "synchronous APIs without accounting for the lower SLA floor."
            ),
        },
        "architectural_fit": (
            "Lightweight stateless compute for: custom API Gateway policy logic (authorizer functions), "
            "event workers triggered by Queue/Streaming/Connector Hub, "
            "narrow transformation steps, and compensation handlers in saga flows. "
            "Fn Project-based development. Provisioned concurrency reduces cold-start latency "
            "at the cost of reserved capacity (charged at 25% idle rate). "
            "APM distributed tracing integration available."
        ),
        "anti_patterns": (
            "NOT suitable for large payload mediation (6 MB hard limit — same as API Gateway→Functions limit). "
            "NOT suitable for long-running orchestration — move durable state to Queue, Streaming, or OIC. "
            "NOT a substitute for OIC orchestration and adapter-heavy mediation. "
            "The 99.5% SLA is the lowest in the OCI integration portfolio — "
            "architect accordingly when Functions is in the synchronous critical path."
        ),
        "interoperability_notes": (
            "Native: API Gateway (backend target), Connector Hub (function task), "
            "APM (distributed tracing), OCI Registry (image deployment), IAM (resource principal). "
            "Can be invoked from CLI/SDK/API and triggered by Streaming, Queue, or Connector Hub events."
        ),
        "oracle_docs_urls": (
            "https://docs.oracle.com/en-us/iaas/Content/Functions/Concepts/functionsoverview.htm|"
            "https://docs.oracle.com/en-us/iaas/Content/Functions/Concepts/functionsavailability.htm|"
            "https://docs.oracle.com/en-us/iaas/Content/Functions/Tasks/functionsusingprovisionedconcurrency.htm|"
            "https://docs.oracle.com/en-us/iaas/Content/Functions/Tasks/functionsviewinglimits.htm|"
            "https://www.oracle.com/cloud/price-list/"
        ),
    },
    {
        "service_id": "CONNECTOR_HUB",
        "name": "OCI Connector Hub",
        "category": "OCI_DATA_MOVER",
        "sla_uptime_pct": None,
        "pricing_model": "No charge for Connector Hub itself. Pay standard rates for source/target services (Logging, Object Storage, Streaming, Functions, Notifications).",
        "limits": {
            "connector_structure": "source → optional task → target (sequential, not parallel)",
            "sources": ["Logging", "Monitoring", "Queue", "Streaming"],
            "targets_from_queue": ["Functions", "Notifications", "Object Storage", "Streaming"],
            "targets_from_streaming": ["Functions", "Log Analytics", "Object Storage", "Streaming"],
            "targets_from_monitoring": ["Functions", "Object Storage", "Streaming"],
            "targets_from_logging": ["Functions", "Log Analytics", "Notifications", "Object Storage", "Streaming"],
            "task_types": ["function_task", "log_filter_task"],
            "throughput_note": "Speed depends on connector configuration and limits of attached source/target services; operations are sequential; aggregation/buffering can delay delivery.",
            "label": "documented",
            "warning": "Oracle can automatically deactivate connectors that are not validated and observed to work as expected.",
        },
        "architectural_fit": (
            "OCI-native managed data mover for routing/enrichment/archival between OCI services. "
            "Ideal for: shipping service logs to Object Storage, routing Queue/Streaming events to "
            "Functions for processing, forwarding Monitoring alarms to Notifications, "
            "archiving events to Log Analytics. Zero-cost orchestration for OCI-internal flows."
        ),
        "anti_patterns": (
            "NOT an ESB or general-purpose workflow engine. "
            "NOT suitable for cross-SaaS or on-prem integration — external connectivity is indirect via targets. "
            "NOT for rich stateful orchestration with compensation or error handling. "
            "Sequential operations mean it cannot fan-out in parallel; "
            "use OIC or Functions-orchestrated parallel patterns for fan-out."
        ),
        "interoperability_notes": (
            "OCI-centric: Logging, Monitoring, Queue, Streaming as sources. "
            "Targets: Functions, Notifications, Object Storage, Log Analytics, Streaming. "
            "Private endpoints supported for stream source/target access inside VCN."
        ),
        "oracle_docs_urls": (
            "https://docs.oracle.com/en-us/iaas/Content/connector-hub/home.htm|"
            "https://docs.oracle.com/en-us/iaas/Content/service-connector-hub/overview.htm|"
            "https://docs.oracle.com/en-us/iaas/Content/connector-hub/metrics-reference.htm|"
            "https://www.oracle.com/application-development/connector-hub/pricing/"
        ),
    },
    {
        "service_id": "OBJECT_STORAGE",
        "name": "OCI Object Storage",
        "category": "STORAGE",
        "sla_uptime_pct": 99.9,
        "pricing_model": "GB stored per month + request and data transfer charges by storage tier.",
        "limits": {
            "single_part_upload_max_gb": 50,
            "multipart_upload_required_above_gb": 50,
            "object_versioning_supported": True,
            "pre_authenticated_requests_supported": True,
            "lifecycle_policy_supported": True,
            "label": "documented",
            "note": (
                "Use Object Storage as payload externalization for OIC, Streaming, Queue, "
                "API Gateway, and Functions when messages exceed service payload limits."
            ),
        },
        "architectural_fit": (
            "Durable payload staging, file exchange, event archive, data lake landing zone, "
            "and large-object externalization. Fits batch ingestion, CDC archive, "
            "large-event pointer patterns, and export storage."
        ),
        "anti_patterns": (
            "NOT an orchestration layer or message broker. "
            "Do not pass large binary payloads inline through OIC/Streaming/Queue when an "
            "Object Storage reference would preserve service limits and reduce retries."
        ),
        "interoperability_notes": (
            "Used by Data Integration, Connector Hub, Functions, GoldenGate, Streaming reference "
            "patterns, OIC file patterns, and export workflows. IAM policies and bucket lifecycle "
            "rules must be governed as part of architecture."
        ),
        "oracle_docs_urls": (
            "https://docs.oracle.com/en-us/iaas/Content/Object/home.htm|"
            "https://docs.oracle.com/en-us/iaas/Content/Object/Tasks/usingmultipartuploads.htm|"
            "https://docs.oracle.com/en-us/iaas/Content/Object/Tasks/usingpreauthenticatedrequests.htm|"
            "https://www.oracle.com/cloud/storage/pricing/"
        ),
    },
    {
        "service_id": "GOLDENGATE",
        "name": "OCI GoldenGate",
        "category": "CDC_REPLICATION",
        "sla_uptime_pct": 99.95,
        "pricing_model": "OCPU per hour (replication) + separate OCPU/hour for Stream Analytics. BYOL rate available.",
        "limits": {
            "scaling_axis": "OCPU-based (right-size replication and analytics OCPUs separately)",
            "stream_analytics_starting_ocpus_recommended": 3,
            "ocpu_utilization_note": "Near-100% OCPU utilization degrades management-console responsiveness; size with headroom.",
            "data_streams_availability": "Data Streams (AsyncAPI pub/sub) requires Oracle GoldenGate 23ai deployments only",
            "data_streams_output_format": "JSON (documented preferred format)",
            "label": "documented",
        },
        "architectural_fit": (
            "Real-time CDC and cross-database replication. Captures redo log changes on Oracle DB "
            "and propagates them to downstream systems (OCI Streaming, target databases, data lakes). "
            "GoldenGate Data Streams (23ai only) adds AsyncAPI pub/sub semantics for event consumption. "
            "Stream Analytics provides real-time analysis of event streams. "
            "Requires separate GoldenGate license (not bundled with OCI)."
        ),
        "anti_patterns": (
            "NOT a substitute for business orchestration, API mediation, or generic ETL design. "
            "Data Streams is NOT available on pre-23ai GoldenGate deployments. "
            "NOT cost-effective for tables with infrequent changes — "
            "scheduled batch (Data Integration) is cheaper for low-change-rate sources. "
            "Requires private networking and Vault/Secrets permissions configured correctly — "
            "public endpoint access is not the expected deployment pattern."
        ),
        "interoperability_notes": (
            "Connects to: Oracle databases (source/target), OCI Streaming (source/target), "
            "Object Storage, and external/on-prem data management systems. "
            "Private endpoints, dedicated connections, and Vault/Secrets for credential management. "
            "GoldenGate trail → OCI Streaming is the canonical CDC→event-backbone handoff pattern."
        ),
        "oracle_docs_urls": (
            "https://docs.oracle.com/en-us/iaas/goldengate/index.html|"
            "https://docs.oracle.com/en-us/iaas/goldengate/doc/add-data-streams.html|"
            "https://docs.oracle.com/en-us/iaas/goldengate/doc/stream-analytics.html|"
            "https://docs.oracle.com/en-us/iaas/goldengate/doc/ocpu-management-and-billing.html|"
            "https://docs.oracle.com/en-us/iaas/goldengate/doc/connect-oci-streaming.html|"
            "https://www.oracle.com/integration/goldengate/pricing/"
        ),
    },
    {
        "service_id": "ORDS",
        "name": "Oracle REST Data Services (ORDS)",
        "category": "DATABASE_REST",
        "sla_uptime_pct": None,
        "pricing_model": "Bundled with host platform (Autonomous Database, Compute/WebLogic/Tomcat). No standalone OCI managed service pricing.",
        "limits": {
            "throughput_note": "Scaling depends on hosting topology, JVM sizing, connection pools, and DB tier. No standalone OCI quota model.",
            "autorest_note": "AutoREST has documented drawbacks/limitations — preferred for simple table/view/PLSQL exposure only.",
            "openapi_support": "Retrieves OpenAPI v3 document from running instance for all available ORDS DB APIs.",
            "label": "documented",
            "sla_note": "No standalone ORDS SLA — availability governed by host service SLA (e.g., Autonomous Database).",
        },
        "architectural_fit": (
            "Database-native API facade when Oracle Database is the system of record and a "
            "separate application layer is undesirable. "
            "AutoREST for tables/views/PL/SQL objects; manual REST services with SQL and JavaScript. "
            "JWT bearer token auth with OAuth2-compliant IdPs. OpenAPI v3 output for API catalog. "
            "Multi-database routing and deployment in standalone, Tomcat, WebLogic, or OCI contexts."
        ),
        "anti_patterns": (
            "NOT a substitute for OIC workflow orchestration or cross-SaaS mediation. "
            "NOT an event backbone — ORDS is request/response only. "
            "Should NOT be exposed directly to external clients without API Gateway in front "
            "(for centralized rate limiting, policy enforcement, and external auth)."
        ),
        "interoperability_notes": (
            "Exposes Oracle Database to standard HTTP clients. "
            "Can sit behind API Gateway, be called from OIC REST adapters, or act as "
            "OKE service backend. JWT integration with OCI IAM-issued tokens supported."
        ),
        "oracle_docs_urls": (
            "https://docs.oracle.com/en/database/oracle/oracle-rest-data-services/|"
            "https://docs.oracle.com/en/database/oracle/oracle-rest-data-services/25.2/orddg/developing-REST-applications.html|"
            "https://docs.oracle.com/en/database/oracle/oracle-rest-data-services/24.4/orrst/index.html"
        ),
    },
    {
        "service_id": "DATA_INTEGRATION",
        "name": "OCI Data Integration",
        "category": "BATCH_ETL",
        "sla_uptime_pct": None,
        "pricing_model": "Workspace usage per hour + GB data processed + pipeline operator execution per hour.",
        "limits": {
            "default_concurrent_task_runs_per_workspace": 4,
            "pipeline_latency_note": "Pipelines are NOT designed for low-latency tasks — documented architectural boundary.",
            "scale_out_path": "OCI Data Flow (Spark) for heavier/larger-volume transformations",
            "label": "documented",
        },
        "architectural_fit": (
            "Batch/ELT/ETL and scheduled data movement for data engineering pipelines. "
            "Workspaces, projects, tasks, pipelines, data flows, SQL tasks, REST tasks. "
            "Lineage generation into Oracle Data Catalog. "
            "OCI Data Flow integration for scalable Spark-based processing. "
            "Right fit for scheduled/micro-batch data movement and transformations."
        ),
        "anti_patterns": (
            "NOT a real-time operational mediation layer — "
            "pipelines have documented latency constraints and default 4 concurrent task runs. "
            "NOT a replacement for GoldenGate (real-time CDC) or OIC (application integration). "
            "Cost is tied to workspace uptime — idle workspaces still incur hourly charges. "
            "Low-latency or event-driven needs belong in Streaming/Queue/OIC."
        ),
        "interoperability_notes": (
            "Integrates with OCI Data Flow, Oracle Data Catalog (lineage), Object Storage, "
            "OCI APIs via REST tasks and resource principals. "
            "Data Flow private endpoints for private resource access in scale-out execution path."
        ),
        "oracle_docs_urls": (
            "https://docs.oracle.com/en-us/iaas/data-integration/home.htm|"
            "https://docs.oracle.com/en-us/iaas/data-integration/using/overview.htm|"
            "https://docs.oracle.com/en-us/iaas/Content/data-integration/using/task-runs.htm|"
            "https://docs.oracle.com/en-us/iaas/Content/data-integration/using/rest-tasks.htm|"
            "https://www.oracle.com/integration/pricing/"
        ),
    },
    {
        "service_id": "DATA_FLOW",
        "name": "OCI Data Flow",
        "category": "SPARK_PROCESSING",
        "sla_uptime_pct": None,
        "pricing_model": "Serverless Spark runtime consumption. Review OCI price list and tenancy-specific service limits before sizing.",
        "limits": {
            "execution_model": "Serverless Apache Spark applications and runs",
            "api_driven": True,
            "supported_languages": ["SQL", "Python", "Java", "Scala", "spark-submit"],
            "free_trial_simple_experiment_instances": 2,
            "limits_are_tenancy_specific": True,
            "label": "documented",
            "note": (
                "Oracle documents Data Flow as serverless Spark. Quotas must be checked in "
                "Limits, Quotas and Usage because practical concurrency and capacity depend "
                "on tenancy subscription and requested increases."
            ),
        },
        "architectural_fit": (
            "Serverless Apache Spark processing for large data transformations, data lake processing, "
            "and advanced batch analytics jobs. Fits when OCI Data Integration needs Spark scale-out "
            "or when engineers want reusable Spark applications without managing clusters."
        ),
        "anti_patterns": (
            "NOT an operational API mediation layer or low-latency event processor. "
            "Do not use it for small request/response transformations better served by OIC, "
            "Functions, or database-native SQL. Spark driver bottlenecks and data skew must be "
            "designed for explicitly."
        ),
        "interoperability_notes": (
            "Used by OCI Data Integration for scale-out tasks. Reads and writes data in Object Storage "
            "and other Spark-accessible data sources. Can use Data Catalog metastore for shared metadata. "
            "IAM policies, private endpoints, and Object Storage layout drive successful use."
        ),
        "oracle_docs_urls": (
            "https://docs.oracle.com/en-us/iaas/data-flow/using/home.htm|"
            "https://docs.oracle.com/en-us/iaas/data-flow/using/dfs_service_overview.htm|"
            "https://docs.oracle.com/en-us/iaas/Content/data-flow/using/dfs_administer_data_flow.htm|"
            "https://docs.oracle.com/en-us/iaas/Content/General/service-limits/default.htm"
        ),
    },
    {
        "service_id": "DATA_CATALOG",
        "name": "OCI Data Catalog",
        "category": "DATA_GOVERNANCE",
        "sla_uptime_pct": None,
        "pricing_model": "Review OCI price list and tenancy limits. Costs and quotas depend on catalog resources and usage.",
        "limits": {
            "catalog_instances_per_region": 2,
            "harvest_jobs_supported": True,
            "business_glossary_supported": True,
            "private_endpoint_supported": True,
            "metastore_for_data_flow_supported": True,
            "label": "documented",
            "note": (
                "Data Catalog is a metadata management and governance service. It is not a data movement "
                "engine; it harvests and enriches metadata for discovery, lineage, glossary, and governance."
            ),
        },
        "architectural_fit": (
            "Metadata discovery and governance for data integration estates. Helps data engineers, "
            "stewards, analysts, and scientists discover assets, harvest technical metadata, manage "
            "business glossary terms, enrich objects, and support Data Flow metastore usage."
        ),
        "anti_patterns": (
            "NOT an ETL/ELT runtime, CDC engine, message broker, or transformation engine. "
            "Do not treat catalog coverage as proof of data quality or data freshness. Harvesting "
            "schedules and glossary ownership must be governed."
        ),
        "interoperability_notes": (
            "Integrates with Data Integration lineage, Object Storage assets, databases, private endpoints, "
            "IAM, Events, Search, Monitoring, and Data Flow metastore. Use it to provide evidence and "
            "metadata context around integration recommendations."
        ),
        "oracle_docs_urls": (
            "https://docs.oracle.com/en-us/iaas/Content/data-catalog/home.htm|"
            "https://docs.oracle.com/en-us/iaas/Content/data-catalog/using/overview.htm|"
            "https://docs.oracle.com/en-us/iaas/Content/General/service-limits/default.htm"
        ),
    },
    {
        "service_id": "GOLDENGATE_DATA_TRANSFORMS",
        "name": "OCI GoldenGate Data Transforms",
        "category": "DATA_TRANSFORMATION",
        "sla_uptime_pct": None,
        "pricing_model": "Delivered through OCI GoldenGate deployment patterns; review GoldenGate pricing and deployment sizing.",
        "limits": {
            "graphical_data_flows_supported": True,
            "graphical_workflows_supported": True,
            "requires_goldengate_deployment": True,
            "generic_connections_required": True,
            "label": "documented",
            "note": (
                "Data Transforms provides graphical data flows and workflows inside OCI GoldenGate "
                "Data Transforms deployments. It is related to ODI concepts but operated through "
                "the GoldenGate deployment experience."
            ),
        },
        "architectural_fit": (
            "Graphical data transformation and workflow design for loading and transforming data "
            "between systems when the estate is already using OCI GoldenGate. Useful for database "
            "and warehouse transformation flows adjacent to replication."
        ),
        "anti_patterns": (
            "NOT a replacement for real-time CDC replication, event streaming, or application "
            "orchestration. Do not use it as the universal integration hub when OCI Data Integration, "
            "ODI, or OIC is the better runtime fit."
        ),
        "interoperability_notes": (
            "Pairs with OCI GoldenGate data replication deployments and Generic connections. "
            "Commonly works with Autonomous Database, Object Storage, and Oracle database targets. "
            "Credential, network, and connection assignment governance is required before launch."
        ),
        "oracle_docs_urls": (
            "https://docs.oracle.com/en-us/iaas/goldengate/doc/data-transforms.html|"
            "https://docs.oracle.com/en-us/iaas/goldengate/doc/data-transforms-quickstart.html|"
            "https://docs.oracle.com/en/database/data-integration/data-transforms/using/using-oracle-data-transforms.pdf"
        ),
    },
    {
        "service_id": "ODI",
        "name": "Oracle Data Integrator",
        "category": "ENTERPRISE_ETL",
        "sla_uptime_pct": None,
        "pricing_model": "Licensed Oracle middleware product; deployment and infrastructure costs depend on chosen platform.",
        "limits": {
            "elt_architecture": True,
            "batch_integration_supported": True,
            "event_based_integration_supported": True,
            "service_based_integration_supported": True,
            "big_data_support": True,
            "label": "documented",
            "note": (
                "ODI is Oracle's enterprise data integration platform for ELT/ETL, data movement, "
                "synchronization, quality, management, and data services. It is not a managed OCI "
                "service profile by default, so operational limits depend on deployment topology."
            ),
        },
        "architectural_fit": (
            "Enterprise data integration platform for high-volume batch loads, event-driven or "
            "trickle-feed integration, data-centric architectures, and SOA-enabled data services. "
            "Appropriate where clients already standardize on ODI or require declarative ELT close "
            "to Oracle database and warehouse platforms."
        ),
        "anti_patterns": (
            "NOT the simplest choice for lightweight SaaS/API orchestration or cloud-native event "
            "buffering. Avoid introducing ODI just to replace governed OCI managed services when "
            "no client standard or workload requirement calls for it."
        ),
        "interoperability_notes": (
            "Can be used with Oracle GoldenGate and Enterprise Data Quality in broader Oracle Data "
            "Integration estates. Deployment architecture controls scalability, scheduling, security, "
            "repository design, and runtime availability."
        ),
        "oracle_docs_urls": (
            "https://www.oracle.com/middleware/technologies/data-integrator.html|"
            "https://www.oracle.com/middleware/technologies/data-integration.html|"
            "https://docs.oracle.com/en/middleware/fusion-middleware/data-integrator/12.2.1.3/odiun/overview-oracle-data-integrator.html|"
            "https://docs.oracle.com/en/database/data-integration/index.html"
        ),
    },
    {
        "service_id": "STREAM_ANALYTICS",
        "name": "Oracle Stream Analytics",
        "category": "STREAM_ANALYTICS",
        "sla_uptime_pct": None,
        "pricing_model": "Review Oracle Integration/Stream Analytics deployment and subscription model before sizing.",
        "limits": {
            "spark_based_pipelines": True,
            "continuous_query_language": True,
            "goldengate_integration_supported": True,
            "oracle_integration_workflow_trigger_supported": True,
            "managed_service_and_on_premises_options": True,
            "label": "documented",
            "note": (
                "Stream Analytics creates Spark-based streaming analytics pipelines. It analyzes "
                "events in motion and can trigger workflows or feed analytics outputs."
            ),
        },
        "architectural_fit": (
            "Real-time analytics and complex event processing over event streams. Fits operational "
            "dashboards, temporal analytics, pattern detection, and GoldenGate/Kafka stream analysis "
            "where decisions must be made while data is still in motion."
        ),
        "anti_patterns": (
            "NOT an event broker, CDC replication engine, ETL batch runtime, or generic business "
            "orchestration engine. It should consume streams produced by GoldenGate, Kafka, or "
            "Streaming rather than replace those services."
        ),
        "interoperability_notes": (
            "Can analyze transaction event streams pushed by GoldenGate to Kafka. Processed outcomes "
            "can trigger Oracle Integration workflows or feed data lake/analytics surfaces."
        ),
        "oracle_docs_urls": (
            "https://docs.oracle.com/en/cloud/paas/integration-cloud/user-stream-analytics/overview-oracle-streaming-analytics.html|"
            "https://docs.oracle.com/en/database/data-integration/index.html"
        ),
    },
    {
        "service_id": "ENTERPRISE_DATA_QUALITY",
        "name": "Oracle Enterprise Data Quality",
        "category": "DATA_QUALITY",
        "sla_uptime_pct": None,
        "pricing_model": "Licensed Oracle middleware product; OCI Marketplace deployment still requires appropriate EDQ licenses.",
        "limits": {
            "data_quality_management": True,
            "data_profiling_supported": True,
            "data_matching_supported": True,
            "data_cleansing_supported": True,
            "marketplace_deployment_available": True,
            "label": "documented",
            "note": (
                "EDQ governs, measures, improves, and manages data quality. OCI deployment is possible "
                "through Marketplace, but licensing and repository database design remain client-specific."
            ),
        },
        "architectural_fit": (
            "Data quality management for migration, MDM, BI, data integration, and CRM quality use cases. "
            "Use when the architecture needs profiling, cleansing, standardization, matching, or quality "
            "governance before or after integration flows."
        ),
        "anti_patterns": (
            "NOT a transport, ETL scheduler, API gateway, or streaming platform. Do not use EDQ to "
            "mask missing data ownership, data stewardship, or upstream quality accountability."
        ),
        "interoperability_notes": (
            "Complements ODI, GoldenGate, and broader Oracle Data Integration estates. Can be deployed "
            "on OCI Marketplace with Tomcat or WebLogic and requires an Oracle Database repository."
        ),
        "oracle_docs_urls": (
            "https://www.oracle.com/middleware/technologies/data-integration.html|"
            "https://www.oracle.com/middleware/technologies/enterprise-data-quality.html|"
            "https://docs.oracle.com/middleware/12211/edq/docs.htm|"
            "https://docs.oracle.com/en/database/data-integration/index.html"
        ),
    },
    {
        "service_id": "OBSERVABILITY",
        "name": "OCI Monitoring, APM, Logging, and Log Analytics",
        "category": "OBSERVABILITY",
        "sla_uptime_pct": 99.9,
        "pricing_model": "APM: tracing events/hr + synthetic runs/hr + stack monitoring resources/hr. Logging: GB log storage/month (first 10 GB free). Monitoring: separate price list.",
        "limits": {
            "apm_free_tier": "Always Free floor for tracing and synthetic usage",
            "logging_free_gb_per_month": 10,
            "alarm_interval_note": "Alarm intervals must match metric emission frequency — documented best practice.",
            "log_analytics_rename_note": "Service was renamed from 'Logging Analytics' to 'Oracle Log Analytics' — update architecture docs accordingly.",
            "label": "documented",
        },
        "architectural_fit": (
            "Control plane for OIC/API Gateway/Functions/event-platform observability. "
            "Monitoring: metrics/alarms for all OCI services and custom apps. "
            "APM: distributed tracing (OpenTelemetry-compatible), service topology, synthetic monitoring. "
            "Logging: managed log collection and search. "
            "Log Analytics: enriched analysis, aggregation, AI/ML-oriented correlation. "
            "Connector Hub can route Monitoring and Logging data into other OCI services. "
            "Must be designed as first-class architecture, not added after go-live — "
            "debugging async/CDC/saga systems without observability is extremely expensive."
        ),
        "anti_patterns": (
            "Observability should NOT be treated as optional adjunct. "
            "Alarm intervals that do not match metric emission frequency produce false positives/negatives. "
            "Log retention and search choices directly drive cost — "
            "log everything by default is expensive; tier by sensitivity and SLA."
        ),
        "interoperability_notes": (
            "Logging integrates with Connector Hub, Monitoring alarms, service logs across all OCI resources. "
            "APM: distributed tracing from OpenTelemetry sources and OCI services including Functions. "
            "Monitoring alarms can trigger Notifications or Connector Hub automation."
        ),
        "oracle_docs_urls": (
            "https://docs.oracle.com/en-us/iaas/Content/Monitoring/Concepts/monitoringoverview.htm|"
            "https://docs.oracle.com/en-us/iaas/application-performance-monitoring/home.htm|"
            "https://docs.oracle.com/en-us/iaas/Content/Logging/home.htm|"
            "https://docs.oracle.com/en-us/iaas/logging-analytics/index.html|"
            "https://www.oracle.com/manageability/pricing/"
        ),
    },
    {
        "service_id": "IAM",
        "name": "OCI IAM with Identity Domains + Security Services",
        "category": "IDENTITY_SECURITY",
        "sla_uptime_pct": 99.95,
        "pricing_model": "IAM base is included. Billable add-ons: SMS MFA per message, KMS private vault/HSM, external key management. Vault keys and Cloud Guard are separately priced.",
        "limits": {
            "mfa_mandate": "MFA is mandatory for users accessing Oracle Cloud Services including OCI console (March 2026 Pillar Document)",
            "vault_private_hsm": "KMS private vaults with HSM isolation are separately priced",
            "cloud_guard_note": "Cloud Guard provides detective → preventive remediation when combined with Security Zones",
            "policy_note": "Policy inheritance, domain design, least privilege, and DR/replication must be designed up front — not retrofitted",
            "label": "documented",
        },
        "architectural_fit": (
            "Identity, SSO, OAuth/SAML, lifecycle, and access-control plane for OCI and connected apps. "
            "Control plane for: human/admin access, app-to-app trust (resource principals, dynamic groups), "
            "policy enforcement, MFA, and identity federation. "
            "Vault/KMS: centralized key management, auto-rotation, HSM isolation option. "
            "Cloud Guard: problem detection and automated remediation. "
            "Security Zones: preventive guardrails that block policy violations before they happen. "
            "MFA is mandatory — design enrollment flow and break-glass procedures from day one."
        ),
        "anti_patterns": (
            "Over-broad IAM policies are the most common OCI security failure — "
            "not missing features. Least privilege is non-negotiable. "
            "Ungoverned secret distribution (hardcoded credentials, shared service accounts) "
            "defeats all other security controls. Use Vault and resource principals. "
            "Do not skip compartment and domain design — retrofitting is painful and risky. "
            "Do not implement Zero-Trust controls all at once — phase by data sensitivity."
        ),
        "interoperability_notes": (
            "API Gateway: OAuth2/OIDC/JWT token validation and mTLS. "
            "OIC, Queue, Functions, Connector Hub, Data Integration, GoldenGate: all rely on IAM policies. "
            "GoldenGate and Data Integration REST tasks use Vault for secret/key management. "
            "Resource principals and dynamic groups enable service-to-service auth without credentials. "
            "Security Zones integrate with Cloud Guard for preventive + detective posture."
        ),
        "oracle_docs_urls": (
            "https://docs.oracle.com/en-us/iaas/Content/Identity/home.htm|"
            "https://docs.oracle.com/en-us/iaas/Content/Identity/domains/overview.htm|"
            "https://docs.oracle.com/en-us/iaas/Content/Resources/Assets/whitepapers/best-practices-for-iam-on-oci.pdf|"
            "https://docs.oracle.com/en-us/iaas/Content/KeyManagement/home.htm|"
            "https://docs.oracle.com/en-us/iaas/cloud-guard/using/index.htm|"
            "https://docs.oracle.com/en-us/iaas/security-zone/using/security-zones.htm|"
            "https://www.oracle.com/contracts/docs/paas_iaas_pub_cld_srvs_pillar_4021422.pdf"
        ),
    },
]

SERVICE_INTEROPERABILITY_RULES: list[dict[str, object]] = [
    {
        "source_service_id": "API_GATEWAY",
        "target_service_id": "OIC3",
        "relationship_type": "http_backend",
        "patterns": ["#01", "#03", "#11", "#13"],
        "required_components": ["JWT/OAuth policy", "deployment route", "OIC endpoint"],
        "constraints": {"payload_limit_source": "API Gateway request limit and OIC message-size limit both apply"},
        "risk_notes": "Keep API Gateway as policy edge; transformation-heavy logic belongs in OIC or backend services.",
    },
    {
        "source_service_id": "API_GATEWAY",
        "target_service_id": "FUNCTIONS",
        "relationship_type": "function_backend",
        "patterns": ["#01", "#03", "#08", "#13"],
        "required_components": ["authorizer or backend function", "IAM policy"],
        "constraints": {"payload_limit_source": "Functions invoke body limit applies"},
        "risk_notes": "Use only for narrow stateless compute; avoid large payload mediation.",
    },
    {
        "source_service_id": "API_GATEWAY",
        "target_service_id": "ORDS",
        "relationship_type": "database_api_backend",
        "patterns": ["#01", "#03", "#11", "#13"],
        "required_components": ["ORDS endpoint", "JWT/OAuth or mTLS policy"],
        "constraints": {"availability_source": "ORDS availability follows host platform"},
        "risk_notes": "Do not expose ORDS directly for external clients without gateway policy enforcement.",
    },
    {
        "source_service_id": "OIC3",
        "target_service_id": "STREAMING",
        "relationship_type": "kafka_adapter",
        "patterns": ["#02", "#07", "#09", "#10", "#14", "#17"],
        "required_components": ["OIC Kafka adapter", "stream pool", "partition key strategy"],
        "constraints": {"message_size": "Streaming 1 MB record limit; OIC message-size limit also applies"},
        "risk_notes": "Use Streaming for event backbone; keep OIC focused on orchestration and adapter mediation.",
    },
    {
        "source_service_id": "STREAMING",
        "target_service_id": "FUNCTIONS",
        "relationship_type": "event_consumer",
        "patterns": ["#02", "#09", "#10", "#14"],
        "required_components": ["consumer function", "idempotency key", "offset handling"],
        "constraints": {"throughput": "Partition throughput and Functions concurrency both apply"},
        "risk_notes": "Consumers must be idempotent because event delivery is at least once.",
    },
    {
        "source_service_id": "QUEUE",
        "target_service_id": "FUNCTIONS",
        "relationship_type": "work_item_consumer",
        "patterns": ["#04", "#07", "#08", "#09"],
        "required_components": ["queue", "consumer function", "dead-letter channel"],
        "constraints": {"message_size": "Queue message-size and Functions invoke limits both apply"},
        "risk_notes": "Use Queue for work dispatch, not replayable event log semantics.",
    },
    {
        "source_service_id": "CONNECTOR_HUB",
        "target_service_id": "OBJECT_STORAGE",
        "relationship_type": "managed_route_target",
        "patterns": ["#02", "#05", "#09", "#12", "#14"],
        "required_components": ["connector", "source service", "bucket target"],
        "constraints": {"execution_model": "Connector Hub operations are sequential source-task-target routes"},
        "risk_notes": "Good for archive and telemetry movement; not a general workflow engine.",
    },
    {
        "source_service_id": "CONNECTOR_HUB",
        "target_service_id": "FUNCTIONS",
        "relationship_type": "managed_route_task",
        "patterns": ["#02", "#08", "#09", "#14"],
        "required_components": ["connector", "function task", "IAM policy"],
        "constraints": {"execution_model": "Connector Hub function tasks run inside a source-task-target route"},
        "risk_notes": "Keep processing bounded; complex orchestration belongs in OIC or explicit workflow design.",
    },
    {
        "source_service_id": "GOLDENGATE",
        "target_service_id": "STREAMING",
        "relationship_type": "cdc_event_handoff",
        "patterns": ["#02", "#05", "#09", "#10", "#14"],
        "required_components": ["GoldenGate deployment", "stream target", "schema governance"],
        "constraints": {"deployment": "GoldenGate/Data Streams capabilities depend on deployment version"},
        "risk_notes": "Best fit for database CDC to event backbone; not generic API mediation.",
    },
    {
        "source_service_id": "DATA_INTEGRATION",
        "target_service_id": "OBJECT_STORAGE",
        "relationship_type": "batch_storage_target",
        "patterns": ["#05", "#06", "#12"],
        "required_components": ["workspace", "bucket", "data asset", "task"],
        "constraints": {"latency": "Data Integration pipelines are not designed for low-latency tasks"},
        "risk_notes": "Use for governed batch/ELT, not operational real-time mediation.",
    },
    {
        "source_service_id": "DATA_INTEGRATION",
        "target_service_id": "DATA_FLOW",
        "relationship_type": "spark_task_execution",
        "patterns": ["#05", "#06", "#12", "#17"],
        "required_components": ["Data Integration task", "Data Flow application", "Object Storage staging"],
        "constraints": {"runtime": "Spark job capacity and tenancy Data Flow quotas apply"},
        "risk_notes": "Use for scale-out transformations; avoid for low-latency operational mediation.",
    },
    {
        "source_service_id": "DATA_INTEGRATION",
        "target_service_id": "DATA_CATALOG",
        "relationship_type": "lineage_metadata_publication",
        "patterns": ["#05", "#06", "#12"],
        "required_components": ["workspace", "lineage metadata", "catalog governance process"],
        "constraints": {"governance": "Catalog harvest and lineage freshness depend on configured schedules"},
        "risk_notes": "Catalog evidence is metadata, not proof of payload quality or runtime freshness.",
    },
    {
        "source_service_id": "DATA_FLOW",
        "target_service_id": "OBJECT_STORAGE",
        "relationship_type": "spark_data_lake_processing",
        "patterns": ["#05", "#06", "#12", "#17"],
        "required_components": ["Spark application", "bucket layout", "IAM policy"],
        "constraints": {"performance": "Partitioning, skew, driver sizing, and file layout drive practical throughput"},
        "risk_notes": "Poor Object Storage partitioning can dominate Spark runtime regardless of service capacity.",
    },
    {
        "source_service_id": "DATA_CATALOG",
        "target_service_id": "DATA_FLOW",
        "relationship_type": "metastore_metadata",
        "patterns": ["#05", "#06", "#12"],
        "required_components": ["Data Catalog metastore", "Data Flow application", "IAM policy"],
        "constraints": {"governance": "Metastore access must align with data domain ownership"},
        "risk_notes": "Do not treat metastore registration as data access authorization by itself.",
    },
    {
        "source_service_id": "GOLDENGATE",
        "target_service_id": "GOLDENGATE_DATA_TRANSFORMS",
        "relationship_type": "replication_transform_pair",
        "patterns": ["#05", "#06", "#10", "#12", "#14"],
        "required_components": ["GoldenGate deployment", "Data Transforms deployment", "Generic connections"],
        "constraints": {"deployment": "Data Transforms is configured through OCI GoldenGate deployment patterns"},
        "risk_notes": "Keep CDC replication and transformation responsibilities explicit to avoid hidden dual-write semantics.",
    },
    {
        "source_service_id": "GOLDENGATE_DATA_TRANSFORMS",
        "target_service_id": "OBJECT_STORAGE",
        "relationship_type": "transformed_dataset_target",
        "patterns": ["#05", "#06", "#12"],
        "required_components": ["data flow", "workflow", "bucket target"],
        "constraints": {"staging": "Object Storage lifecycle, file naming, and replay strategy must be governed"},
        "risk_notes": "Avoid unmanaged data lake drops without catalog, lineage, and retention rules.",
    },
    {
        "source_service_id": "ODI",
        "target_service_id": "GOLDENGATE",
        "relationship_type": "batch_cdc_hybrid",
        "patterns": ["#05", "#06", "#10", "#12", "#14"],
        "required_components": ["ODI repositories", "GoldenGate deployment", "monitoring policy"],
        "constraints": {"runtime": "ODI availability and throughput depend on customer-managed deployment topology"},
        "risk_notes": "Use only when client ODI standardization or workload shape justifies a non-managed runtime.",
    },
    {
        "source_service_id": "ENTERPRISE_DATA_QUALITY",
        "target_service_id": "ODI",
        "relationship_type": "quality_gate",
        "patterns": ["#05", "#06", "#12", "#16"],
        "required_components": ["quality rules", "profiling output", "ODI load process"],
        "constraints": {"ownership": "Quality thresholds and remediation ownership must be defined outside the tool"},
        "risk_notes": "Quality tooling cannot replace data stewardship or source-system accountability.",
    },
    {
        "source_service_id": "GOLDENGATE",
        "target_service_id": "STREAM_ANALYTICS",
        "relationship_type": "cdc_stream_analytics",
        "patterns": ["#02", "#09", "#10", "#14"],
        "required_components": ["GoldenGate stream", "Kafka-compatible topic", "Stream Analytics pipeline"],
        "constraints": {"streaming": "Pipeline semantics depend on event-time windows, checkpointing, and source ordering"},
        "risk_notes": "Use for event analytics; do not route transactional command processing through analytics pipelines.",
    },
    {
        "source_service_id": "STREAM_ANALYTICS",
        "target_service_id": "OIC3",
        "relationship_type": "event_insight_workflow_trigger",
        "patterns": ["#02", "#08", "#09", "#14"],
        "required_components": ["published pipeline", "alert action", "OIC workflow endpoint"],
        "constraints": {"latency": "Analytics detection and workflow invocation are separate reliability domains"},
        "risk_notes": "Make alert deduplication and workflow idempotency explicit.",
    },
    {
        "source_service_id": "OBJECT_STORAGE",
        "target_service_id": "DATA_INTEGRATION",
        "relationship_type": "batch_storage_source",
        "patterns": ["#05", "#06", "#12"],
        "required_components": ["bucket", "data asset", "workspace"],
        "constraints": {"latency": "Batch windows and workspace usage assumptions apply"},
        "risk_notes": "Make lifecycle and retention assumptions explicit before sizing.",
    },
    {
        "source_service_id": "OIC3",
        "target_service_id": "OBJECT_STORAGE",
        "relationship_type": "large_payload_reference",
        "patterns": ["#03", "#05", "#06", "#07", "#17"],
        "required_components": ["bucket", "object key reference", "OIC file/object adapter"],
        "constraints": {"payload": "Use references when inline message payload limits would be exceeded"},
        "risk_notes": "Avoid passing large binary/file payloads through orchestration inline.",
    },
]

PROMPT_TEMPLATE: dict[str, Any] = {
    "version": "1.0.0",
    "name": "Deterministic Justification Template",
    "is_default": True,
    "template_config": {
        "summary": (
            "The integration {interface_name} connects {source_system} to {destination_system} "
            "and currently has QA status {qa_status}."
        ),
        "blocks": [
            {
                "title": "Context",
                "body": (
                    "Interface {interface_id} supports brand {brand} within business process {business_process}. "
                    "It runs at frequency {frequency} with {payload_text}."
                ),
            },
            {
                "title": "Pattern",
                "body": (
                    "Documented pattern: {pattern_label}. Rationale: {pattern_rationale}."
                ),
            },
            {
                "title": "Implementation",
                "body": (
                    "Type {type}, trigger {trigger_type}, and core tools {core_tools}. "
                    "Retry policy: {retry_policy}."
                ),
            },
            {
                "title": "QA Governance",
                "body": "QA status {qa_status}. Observations: {qa_reasons}.",
            },
        ],
    },
    "notes": "Seeded default template for deterministic methodology narratives.",
}


def _audit(session: Session, event_type: str, entity_type: str, entity_id: str, new_value: dict[str, object]) -> None:
    session.add(
        AuditEvent(
            project_id=None,
            actor_id="system-seed",
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            old_value=None,
            new_value=new_value,
        )
    )


def _pattern_lines(value: str | None) -> list[str]:
    """Normalize multiline workbook guidance into structured seed values."""

    if not value:
        return []
    return [line.lstrip("-• 0123456789.").strip() for line in value.splitlines() if line.strip()]


def _pattern_capture_guidance(pattern_data: dict[str, str]) -> tuple[list[str], list[str], list[str]]:
    """Derive novice-friendly selection aids from the governed pattern narrative."""

    examples = _pattern_lines(pattern_data.get("when_to_use"))[:3]
    first_example = examples[0] if examples else f"The scenario matches {pattern_data['name']}"
    questions = [
        f"Does the scenario satisfy this condition: {first_example}?",
        "Have failure handling, retries, idempotency, and relevant limits been documented?",
        "Do the selected services match the route designed in Canvas?",
    ]
    required_inputs = ["Source and destination", "Frequency", "Payload per execution", "Trigger type"]
    category = pattern_data["category"].upper()
    if "ASYN" in category or "DATA" in category:
        required_inputs.extend(["Retention or processing window", "Idempotency and retry/DLQ"])
    if pattern_data["pattern_id"] in {"#02", "#07", "#17"}:
        required_inputs.append("Fan-out and destination count")
    return examples, questions, required_inputs


def seed_patterns(session: Session) -> int:
    count = 0
    for pattern_data in PATTERNS:
        applicability_examples, selection_questions, required_inputs = _pattern_capture_guidance(pattern_data)
        existing = session.scalar(
            select(PatternDefinition).where(PatternDefinition.pattern_id == pattern_data["pattern_id"])
        )
        if existing is None:
            existing = PatternDefinition(
                **pattern_data,
                applicability_examples=applicability_examples,
                selection_questions=selection_questions,
                required_inputs=required_inputs,
            )
            session.add(existing)
            session.flush()
            if hasattr(existing, "is_system"):
                existing.is_system = True
            _audit(session, "seed_insert", "pattern_definition", existing.id, cast(dict[str, object], pattern_data))
            count += 1
        else:
            existing.name = pattern_data["name"]
            existing.category = pattern_data["category"]
            existing.description = cast(str | None, pattern_data.get("description"))
            existing.oci_components = cast(str | None, pattern_data.get("oci_components"))
            existing.when_to_use = cast(str | None, pattern_data.get("when_to_use"))
            existing.when_not_to_use = cast(str | None, pattern_data.get("when_not_to_use"))
            existing.technical_flow = cast(str | None, pattern_data.get("technical_flow"))
            existing.business_value = cast(str | None, pattern_data.get("business_value"))
            existing.applicability_examples = applicability_examples
            existing.selection_questions = selection_questions
            existing.required_inputs = required_inputs
            if hasattr(existing, "is_system"):
                existing.is_system = True
            existing.version = "1.0.0"
            continue
        existing.description = cast(str | None, pattern_data.get("description"))
        existing.oci_components = cast(str | None, pattern_data.get("oci_components"))
        existing.when_to_use = cast(str | None, pattern_data.get("when_to_use"))
        existing.when_not_to_use = cast(str | None, pattern_data.get("when_not_to_use"))
        existing.technical_flow = cast(str | None, pattern_data.get("technical_flow"))
        existing.business_value = cast(str | None, pattern_data.get("business_value"))
        existing.applicability_examples = applicability_examples
        existing.selection_questions = selection_questions
        existing.required_inputs = required_inputs
        existing.version = "1.0.0"
    return count


def seed_dictionary_options(session: Session) -> int:
    count = 0
    for option_data in DICTIONARY_OPTIONS:
        existing = session.scalar(
            select(DictionaryOption).where(
                DictionaryOption.category == option_data["category"],
                DictionaryOption.value == option_data["value"],
            )
        )
        if existing is None:
            existing = DictionaryOption(
                category=str(option_data["category"]),
                code=cast(str | None, option_data.get("code")),
                value=str(option_data["value"]),
                description=cast(str | None, option_data.get("description")),
                executions_per_day=cast(float | None, option_data.get("executions_per_day")),
                is_volumetric=cast(bool | None, option_data.get("is_volumetric")),
                sort_order=int(cast(int, option_data["sort_order"])),
                is_active=bool(option_data.get("is_active", True)),
                version=cast(str, option_data.get("version", "1.0.0")),
            )
            session.add(existing)
            session.flush()
            _audit(session, "seed_insert", "dictionary_option", existing.id, option_data)
            count += 1
        else:
            existing.code = cast(str | None, option_data.get("code"))
            existing.description = cast(str | None, option_data.get("description"))
            existing.executions_per_day = cast(float | None, option_data.get("executions_per_day"))
            existing.is_volumetric = cast(bool | None, option_data.get("is_volumetric"))
            existing.sort_order = int(cast(int, option_data["sort_order"]))
            existing.is_active = bool(option_data.get("is_active", True))
            existing.version = cast(str, option_data.get("version", "1.0.0"))
    return count


def seed_assumption_set(session: Session) -> int:
    existing = session.scalar(
        select(AssumptionSet).where(AssumptionSet.version == ASSUMPTION_SET["version"])
    )
    if existing is None:
        existing = AssumptionSet(**ASSUMPTION_SET)
        session.add(existing)
        session.flush()
        _audit(
            session,
            "seed_insert",
            "assumption_set",
            existing.id,
            {"version": ASSUMPTION_SET["version"]},
        )
        return 1
    existing.label = str(ASSUMPTION_SET["label"])
    existing.is_default = bool(ASSUMPTION_SET["is_default"])
    existing.assumptions = cast(dict[str, Any], dict(cast(dict[str, Any], ASSUMPTION_SET["assumptions"])))
    existing.notes = cast(str | None, ASSUMPTION_SET["notes"])
    return 0


def seed_service_profiles(session: Session) -> int:
    count = 0
    for profile_data in SERVICE_PROFILES:
        existing = session.scalar(
            select(ServiceCapabilityProfile).where(
                ServiceCapabilityProfile.service_id == profile_data["service_id"]
            )
        )
        if existing is None:
            existing = ServiceCapabilityProfile(**profile_data)
            session.add(existing)
            session.flush()
            _audit(
                session,
                "seed_insert",
                "service_capability_profile",
                existing.id,
                {"service_id": cast(str, profile_data["service_id"])},
            )
            count += 1
        else:
            existing.name = cast(str, profile_data["name"])
            existing.category = cast(str, profile_data["category"])
            existing.sla_uptime_pct = cast(float | None, profile_data.get("sla_uptime_pct"))
            existing.pricing_model = cast(str | None, profile_data.get("pricing_model"))
            existing.limits = cast(dict[str, object], profile_data["limits"])
            existing.architectural_fit = cast(str | None, profile_data.get("architectural_fit"))
            existing.anti_patterns = cast(str | None, profile_data.get("anti_patterns"))
            existing.interoperability_notes = cast(
                str | None,
                profile_data.get("interoperability_notes"),
            )
            existing.oracle_docs_urls = cast(str | None, profile_data.get("oracle_docs_urls"))
            existing.is_active = True
            existing.version = "1.0.0"
    return count


def _split_oracle_docs_urls(value: str | None) -> list[str]:
    if not value:
        return []
    return [url.strip() for url in value.split("|") if url.strip()]


def _humanize_limit_key(key: str) -> str:
    return key.replace("_", " ").strip().title()


def _infer_limit_unit(key: str, value: object) -> str | None:
    if key.endswith("_kb"):
        return "KB"
    if key.endswith("_mb") or "_mb_" in key:
        return "MB"
    if key.endswith("_gb") or "_gb_" in key:
        return "GB"
    if key.endswith("_s") or "_s_" in key:
        return "seconds"
    if key.endswith("_h") or "_h_" in key:
        return "hours"
    if key.endswith("_d") or "_d_" in key:
        return "days"
    if key.endswith("_pct"):
        return "percent"
    if key.endswith("_per_month"):
        return "per month"
    if isinstance(value, bool):
        return "boolean"
    return None


def _infer_limit_type(key: str) -> str:
    normalized = key.lower()
    if "payload" in normalized or "message_size" in normalized or "body" in normalized:
        return "payload"
    if "throughput" in normalized or "concurrency" in normalized or "rps" in normalized:
        return "performance"
    if "retention" in normalized:
        return "retention"
    if "max_" in normalized or normalized.startswith("max"):
        return "quota"
    if "billing" in normalized or "pricing" in normalized or "free_" in normalized:
        return "quota"
    return "operational"


def _can_request_limit_increase(key: str) -> bool:
    normalized = key.lower()
    if "payload" in normalized or "message_size" in normalized or "body" in normalized:
        return False
    return "max_" in normalized or "partition" in normalized or "gateway" in normalized


def seed_service_product_library(session: Session) -> int:
    """Seed normalized service-product versions, limits, evidence, and matrix rules."""

    changed = 0
    profiles = {
        profile.service_id: profile
        for profile in session.scalars(select(ServiceCapabilityProfile)).all()
    }

    for profile in profiles.values():
        first_source_url = _split_oracle_docs_urls(profile.oracle_docs_urls)[0] if profile.oracle_docs_urls else None
        version = session.scalar(
            select(ServiceProductVersion).where(
                ServiceProductVersion.service_profile_id == profile.id,
                ServiceProductVersion.version_label == profile.version,
            )
        )
        version_payload: dict[str, object] = {
            "service_id": profile.service_id,
            "source_profile_version": profile.version,
            "pricing_model": profile.pricing_model,
            "sla_uptime_pct": profile.sla_uptime_pct,
        }
        if version is None:
            version = ServiceProductVersion(
                service_profile_id=profile.id,
                version_label=profile.version,
                description=profile.architectural_fit,
                capabilities=cast(dict[str, object], dict(profile.limits)),
                use_cases=[profile.architectural_fit] if profile.architectural_fit else [],
                anti_patterns=[profile.anti_patterns] if profile.anti_patterns else [],
                commercial_notes=profile.pricing_model,
                product_metadata=version_payload,
                created_by="system-seed",
            )
            session.add(version)
            session.flush()
            _audit(
                session,
                "seed_insert",
                "service_product_version",
                version.id,
                {"service_id": profile.service_id, "version": profile.version},
            )
            changed += 1
        else:
            version.description = profile.architectural_fit
            version.capabilities = cast(dict[str, object], dict(profile.limits))
            version.use_cases = [profile.architectural_fit] if profile.architectural_fit else []
            version.anti_patterns = [profile.anti_patterns] if profile.anti_patterns else []
            version.commercial_notes = profile.pricing_model
            version.product_metadata = version_payload

        for key, value in cast(dict[str, object], profile.limits).items():
            if key == "label":
                continue
            existing_limit = session.scalar(
                select(ServiceLimit).where(
                    ServiceLimit.service_profile_id == profile.id,
                    ServiceLimit.limit_key == key,
                )
            )
            if existing_limit is None:
                existing_limit = ServiceLimit(
                    service_profile_id=profile.id,
                    limit_key=key,
                    label=_humanize_limit_key(key),
                    scope="service",
                    limit_type=_infer_limit_type(key),
                    value=value,
                    unit=_infer_limit_unit(key, value),
                    can_request_increase=_can_request_limit_increase(key),
                    source_url=first_source_url,
                    confidence=0.9 if first_source_url else 0.75,
                    notes=None,
                )
                session.add(existing_limit)
                session.flush()
                _audit(
                    session,
                    "seed_insert",
                    "service_limit",
                    existing_limit.id,
                    {"service_id": profile.service_id, "limit_key": key},
                )
                changed += 1
            else:
                # Normalized limits are the runtime source of truth. Re-seeding must
                # never overwrite an architect-reviewed or verification-agent value.
                continue

        for index, url in enumerate(_split_oracle_docs_urls(profile.oracle_docs_urls), start=1):
            existing_source = session.scalar(
                select(ServiceEvidenceSource).where(
                    ServiceEvidenceSource.service_profile_id == profile.id,
                    ServiceEvidenceSource.url == url,
                )
            )
            title = f"{profile.name} evidence source {index}"
            if "service-limits" in url or "limits" in url:
                title = f"{profile.name} service limits"
            elif "pricing" in url or "price-list" in url:
                title = f"{profile.name} pricing"
            if existing_source is None:
                existing_source = ServiceEvidenceSource(
                    service_profile_id=profile.id,
                    source_type="official_docs" if "docs.oracle.com" in url else "official_pricing",
                    url=url,
                    title=title,
                    publisher="Oracle",
                    trust_tier="tier_1_official_docs" if "docs.oracle.com" in url else "tier_2_official_commercial",
                    retrieval_strategy="http_fetch",
                    expected_update_frequency_days=90,
                    status="seeded_pending_verification",
                )
                session.add(existing_source)
                session.flush()
                _audit(
                    session,
                    "seed_insert",
                    "service_evidence_source",
                    existing_source.id,
                    {"service_id": profile.service_id, "url": url},
                )
                changed += 1
            else:
                existing_source.title = title
                existing_source.publisher = "Oracle"
                existing_source.retrieval_strategy = "http_fetch"
                existing_source.expected_update_frequency_days = 90
                if existing_source.status == "pending_verification":
                    existing_source.status = "seeded_pending_verification"

    for rule_data in SERVICE_INTEROPERABILITY_RULES:
        source = profiles.get(cast(str, rule_data["source_service_id"]))
        target = profiles.get(cast(str, rule_data["target_service_id"]))
        if source is None or target is None:
            continue
        relationship_type = cast(str, rule_data["relationship_type"])
        existing_rule = session.scalar(
            select(ServiceInteroperabilityRule).where(
                ServiceInteroperabilityRule.source_service_profile_id == source.id,
                ServiceInteroperabilityRule.target_service_profile_id == target.id,
                ServiceInteroperabilityRule.relationship_type == relationship_type,
            )
        )
        source_url = _split_oracle_docs_urls(source.oracle_docs_urls)[0] if source.oracle_docs_urls else None
        if existing_rule is None:
            existing_rule = ServiceInteroperabilityRule(
                source_service_profile_id=source.id,
                target_service_profile_id=target.id,
                relationship_type=relationship_type,
                supported=True,
                directionality="source_to_target",
                patterns=cast(list[object], rule_data.get("patterns", [])),
                required_components=cast(list[object], rule_data.get("required_components", [])),
                constraints=cast(dict[str, object], rule_data.get("constraints", {})),
                risk_notes=cast(str | None, rule_data.get("risk_notes")),
                source_url=source_url,
                confidence=0.85,
            )
            session.add(existing_rule)
            session.flush()
            _audit(
                session,
                "seed_insert",
                "service_interoperability_rule",
                existing_rule.id,
                {
                    "source_service_id": source.service_id,
                    "target_service_id": target.service_id,
                    "relationship_type": relationship_type,
                },
            )
            changed += 1
        else:
            existing_rule.supported = True
            existing_rule.patterns = cast(list[object], rule_data.get("patterns", []))
            existing_rule.required_components = cast(list[object], rule_data.get("required_components", []))
            existing_rule.constraints = cast(dict[str, object], rule_data.get("constraints", {}))
            existing_rule.risk_notes = cast(str | None, rule_data.get("risk_notes"))
            existing_rule.source_url = source_url
            existing_rule.confidence = 0.85
            existing_rule.is_active = True

    return changed


def seed_prompt_template(session: Session) -> int:
    existing = session.scalar(
        select(PromptTemplateVersion).where(PromptTemplateVersion.version == PROMPT_TEMPLATE["version"])
    )
    if existing is None:
        existing = PromptTemplateVersion(**PROMPT_TEMPLATE)
        session.add(existing)
        session.flush()
        _audit(
            session,
            "seed_insert",
            "prompt_template_version",
            existing.id,
            {"version": PROMPT_TEMPLATE["version"]},
        )
        return 1
    existing.name = str(PROMPT_TEMPLATE["name"])
    existing.is_default = bool(PROMPT_TEMPLATE["is_default"])
    existing.template_config = cast(dict[str, Any], dict(PROMPT_TEMPLATE["template_config"]))
    existing.notes = cast(str | None, PROMPT_TEMPLATE["notes"])
    return 0


def main() -> None:
    engine = create_engine(get_sync_database_url())
    with Session(engine) as session:
        patterns = seed_patterns(session)
        assumptions = seed_assumption_set(session)
        dictionary_options = seed_dictionary_options(session)
        prompt_templates = seed_prompt_template(session)
        service_profiles = seed_service_profiles(session)
        service_product_library = seed_service_product_library(session)
        session.commit()
        print(
            "Seed complete: "
            f"patterns={patterns}, assumptions={assumptions}, "
            f"dictionary_options={dictionary_options}, prompt_templates={prompt_templates}, "
            f"service_profiles={service_profiles}, service_product_library={service_product_library}"
        )


if __name__ == "__main__":
    main()
