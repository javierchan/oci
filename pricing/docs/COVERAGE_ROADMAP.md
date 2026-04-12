# Coverage Roadmap

## Purpose

This document is the operational roadmap for the `pricing` agent.

Use it to answer:

- what is already implemented
- what is covered deterministically today
- what is still pending
- what the next production-grade milestones are

This file is intentionally shorter and more actionable than a running changelog.

## Current Snapshot

Reference artifacts:

- [coverage_matrix.json](/Users/javierchan/Documents/GitHub/oci/pricing/data/rule-registry/coverage_matrix.json)
- [service_family_rules.json](/Users/javierchan/Documents/GitHub/oci/pricing/data/rule-registry/service_family_rules.json)
- [vm_shape_rules.json](/Users/javierchan/Documents/GitHub/oci/pricing/data/rule-registry/vm_shape_rules.json)

Current generated snapshot:

- workbook services: `1004`
- pdf billing rules: `364`
- pdf prerequisite rules: `60`
- VM shapes in registry: `23`
- service families in registry artifact: `9`
- compute residual uncovered count: `0`

Runtime coverage snapshot:

- `L4`: `525`
- `L3`: `31`
- `L2`: `9`
- `L1`: `439`

Interpretation of the current state:

- the most critical `compute residual` block that had been producing misroutes is closed
- the agent is now materially stronger in deterministic quoting than it was at the beginning of this project
- the remaining gaps are mostly:
  - broader parity coverage
  - more declarative metadata
  - more backend follow-up coverage
  - production hardening

## Implemented In Codebase

### Catalog And Source Ingestion

Implemented:

- startup retrieval of all four live OCI catalog feeds
- retry policy for catalog retrieval
- filesystem snapshots in `pricing/data/catalog-cache/current/`
- merged catalog view that includes `products-apex`

Reference:

- [index.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/index.js)
- [catalog.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/catalog.js)

### Sessions And Frontend Persistence

Implemented:

- server-authoritative sessions
- session isolation by `x-client-id`
- persisted:
  - messages
  - session context
  - workbook context
  - event log
- workbook and RVTools follow-ups handled from backend state
- quote export from persisted session quote

Reference:

- [session-store.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/session-store.js)
- [index.html](/Users/javierchan/Documents/GitHub/oci/pricing/app/index.html)
- [index.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/index.js)

### GenAI Routing And Structured Context

Implemented:

- `route + quotePlan` extraction
- structured product context for discovery and explanation
- discovery questions routed away from quote generation
- conceptual prerequisite and quote-composition questions now stay in discovery or answer mode even when the controller over-predicts a quote path
- active-quote conceptual follow-ups now answer without mutating the persisted quote source for covered SKU/component and compute-composition questions
- discovery and explanation prompts with quotable numeric inputs now stay in answer/discovery mode instead of being auto-promoted into deterministic quotes by registry fallback matching
- route normalization now also overrides explicit `quote_request` outputs for clearly explanatory pricing-dimension prompts with measurable inputs
- safer unsupported-service replies when deterministic pricing should not run

Reference:

- [intent-extractor.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/intent-extractor.js)
- [normalizer.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/normalizer.js)
- [context-packs.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/context-packs.js)
- [assistant.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/assistant.js)

### Deterministic Pricing

Implemented:

- deterministic line-item resolution
- metric-aware quantity calculation
- tier-aware pricing
- annual/monthly rollups
- quote export paths

Reference:

- [quotation-engine.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/quotation-engine.js)
- [dependency-resolver.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/dependency-resolver.js)
- [consumption-model.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/consumption-model.js)
- [quote-export.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/quote-export.js)

### VM Shape Coverage

Implemented:

- calculator-aligned VM shape registry
- fixed vs flex handling
- Intel, AMD, and Ampere VM shape coverage
- fixed bare metal legacy coverage in registry
- last major residual compute mismatches closed

Current registry snapshot:

- total shapes: `23`
- flex: `11`
- fixed: `12`

Reference:

- [vm_shape_rules.json](/Users/javierchan/Documents/GitHub/oci/pricing/data/rule-registry/vm_shape_rules.json)
- [vm-shapes.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/vm-shapes.js)

### Workbook And RVTools

Implemented:

- workbook guided quoting
- RVTools detection and VMware-aware sizing
- `vCPU -> OCPU` conversion for VMware x86
- block volume sizing and `VPU` overrides
- persisted workbook follow-ups within a session
- workbook-derived compute requests now also have regression coverage when composed with shared edge and observability services such as load balancer, DNS, FastConnect, monitoring retrieval, and health checks
- workbook-derived requests now also have regression coverage for shared connectivity plus observability combinations, including `FastConnect + Monitoring Retrieval`, across both RVTools single-request paths and guided inventory aggregates
- workbook-derived aggregate totals now also have regression coverage for shared `Load Balancer + DNS` bundles across both guided inventory and RVTools migration flows
- workbook-derived aggregate totals now also have regression coverage for shared `Load Balancer + Monitoring Retrieval` bundles on guided inventory flows
- RVTools-derived aggregate totals now also have regression coverage for shared `FastConnect + Health Checks` bundles
- RVTools-derived aggregate totals now also have regression coverage for shared `Load Balancer + Monitoring Retrieval` bundles
- guided inventory aggregate totals now also have regression coverage for shared `FastConnect + Health Checks` bundles
- workbook-focused aggregate fixtures now also use reusable builders for AMD inventory and RVTools migration books, reducing duplication as the guided-bundle regression surface grows
- workbook-origin and RVTools-origin follow-ups now also have regression coverage when shape, VPU, or capacity-reservation changes must preserve shared `FastConnect + Monitoring Retrieval` services in the persisted quote source
- workbook-origin and RVTools-origin follow-ups now also have regression coverage when shape, VPU, or capacity-reservation changes must preserve shared `Load Balancer + DNS` services in the persisted quote source
- workbook-origin and RVTools-origin mixed follow-ups now also have regression coverage when shared `FastConnect` or `Monitoring Retrieval` components are explicitly removed from the persisted quote source
- workbook-origin and RVTools-origin mixed follow-ups now also have regression coverage for safe shared-service replacements such as `FastConnect -> DNS`, `Monitoring Retrieval -> Health Checks`, `DNS -> Health Checks`, and `Health Checks -> DNS`
- workbook-origin and RVTools-origin mixed follow-ups now also have regression coverage for parameter-only mutations on persisted shared services, including `FastConnect bandwidth`, `DNS query volume`, and `Health Checks endpoint count`
- workbook-origin and RVTools-origin mixed follow-ups now also have symmetric regression coverage for shared `FastConnect + Monitoring Retrieval` bundles when:
  - `Monitoring Retrieval` is removed
  - `FastConnect` is replaced by `DNS`
  - `Monitoring Retrieval` is replaced by `Health Checks`
- workbook-origin and RVTools-origin mixed follow-ups now also have symmetric parameter-only regression coverage for shared `FastConnect + Monitoring Retrieval` bundles when:
  - workbook-origin `Monitoring Retrieval` datapoint changes preserve `FastConnect`
  - RVTools-origin `Monitoring Retrieval` datapoint changes preserve `FastConnect`
  - RVTools-origin `FastConnect` bandwidth changes preserve `Monitoring Retrieval`
- workbook-origin and RVTools-origin mixed follow-ups now also have symmetric regression coverage for shared `FastConnect + Health Checks` bundles when:
  - `Health Checks` endpoint count changes preserve `FastConnect`
  - `Health Checks` is removed
  - `Health Checks` is replaced by `DNS`
- workbook-origin and RVTools-origin mixed follow-ups now also have regression coverage for observability bundles that swap `Health Checks -> DNS` while preserving neighboring `Monitoring Retrieval`
- workbook-origin and RVTools-origin mixed follow-ups now also have regression coverage for shared `Monitoring Retrieval + DNS` bundles when `DNS` query-volume changes preserve neighboring `Monitoring Retrieval`
- workbook-origin and RVTools-origin mixed follow-ups now also have regression coverage for shared `Monitoring Retrieval + DNS` bundles when `DNS` is removed and neighboring `Monitoring Retrieval` must be preserved
- workbook-origin and RVTools-origin mixed follow-ups now also have regression coverage for shared `Monitoring Retrieval + DNS` bundles when `Monitoring Retrieval` datapoint changes preserve neighboring `DNS`
- workbook-origin and RVTools-origin mixed follow-ups now also have symmetric regression coverage for shared `FastConnect + DNS` bundles when:
  - `DNS` is removed
  - `FastConnect` is removed
  - `DNS` is replaced by `Health Checks`
- workbook-origin and RVTools-origin mixed follow-ups now also have regression coverage for shared `FastConnect + DNS` bundles when `DNS` query-volume changes preserve neighboring `FastConnect`
- workbook-origin and RVTools-origin mixed follow-ups now also have regression coverage for shared `Load Balancer + Monitoring Retrieval` bundles when:
  - workbook-origin shape plus `VPU` changes preserve both services
  - RVTools-origin shape plus `capacity reservation` changes preserve both services
  - workbook-origin `Load Balancer` bandwidth changes preserve `Monitoring Retrieval`
  - RVTools-origin `Load Balancer` bandwidth changes preserve `Monitoring Retrieval`
  - `Monitoring Retrieval` datapoint changes preserve `Flexible Load Balancer`
- workbook-origin and RVTools-origin mixed follow-ups now also have symmetric regression coverage for shared `Load Balancer + Monitoring Retrieval` bundles when:
  - `Monitoring Retrieval` is removed
  - `Load Balancer` is removed
  - `Monitoring Retrieval` is replaced by `Health Checks`
- workbook-origin and RVTools-origin mixed follow-ups now also have regression coverage for shared `Load Balancer + DNS` bundles when:
  - `DNS` query-volume changes preserve neighboring `Flexible Load Balancer`
  - `DNS` is replaced by `Health Checks`
  - `DNS` is removed
  - `Load Balancer` is removed
- workbook-origin and RVTools-origin mixed follow-ups now also have regression coverage for shared `Load Balancer + Health Checks` bundles when:
  - `Load Balancer` is removed across workbook-origin and RVTools-origin sources
  - `Health Checks` is removed across workbook-origin and RVTools-origin sources
  - `Health Checks` is replaced by `DNS`
- workbook-origin and RVTools-origin mixed follow-ups now also have regression coverage for shared `Monitoring Retrieval + Health Checks` bundles when:
  - `Monitoring Retrieval` is removed
  - `Health Checks` is removed
  - `Monitoring Retrieval` is replaced by `Monitoring Ingestion`
  - `Monitoring Retrieval` datapoint changes preserve `Health Checks`
  - `Health Checks` endpoint count changes preserve `Monitoring Retrieval`
  - `Health Checks` is replaced by `DNS`

Reference:

- [excel.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/excel.js)
- [index.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/index.js)

### OCI Calculator Parity

Implemented:

- parity suite exists and is actively used
- parity coverage includes major families already exercised in runtime:
  - compute
  - block volume
  - load balancer
  - WAF
  - fastconnect
  - DNS
  - API Gateway
  - Email Delivery
  - File/Object Storage
  - OIC
  - OAC
  - Base Database Service
  - Database Cloud Service
  - Data Safe
  - Network Firewall
- several observability/platform services
- parity already includes mixed database, integration, storage, and edge bundles instead of only isolated family cases
- parity now also exercises larger enterprise bundles that mix analytics/integration with file storage and Exadata platform lines
- parity now also covers enterprise database and Exadata bundles that mix observability and security primitives such as monitoring, health checks, firewall, and log analytics
- parity now also covers Base Database, Database Cloud Service, and Exadata Cloud@Customer combinations that mix Data Safe, monitoring, health checks, notifications, and log analytics in the same deterministic request
- parity now also covers Autonomous AI Lakehouse and Autonomous AI Transaction Processing bundles that mix Data Integration, firewall, load balancer, DNS, monitoring, notifications, and health checks
- parity now also covers an analytics/integration transport bundle that combines Oracle Integration Cloud, Oracle Analytics Cloud, OCI Data Integration workspace usage, FastConnect, and Log Analytics archival storage
- parity now also covers a Base Database platform bundle that combines Base Database Service, Oracle Integration Cloud, Oracle Analytics Cloud, Data Safe, and monitoring ingestion in one deterministic request
- parity now also covers an autonomous storage bundle that combines Autonomous AI Lakehouse, autonomous database storage, Object Storage, Log Analytics archival storage, and Notifications HTTPS delivery
- parity now also covers a serverless edge/security bundle that combines load balancer, WAF, API Gateway, DNS, health checks, and Notifications HTTPS delivery
- parity now also covers a mixed observability stack that combines monitoring ingestion, monitoring retrieval, notifications HTTPS delivery, and log analytics archival storage
- parity now also covers a larger enterprise operations/security bundle that combines monitoring, log analytics active + archival, notifications HTTPS delivery, DNS, health checks, and network firewall
- parity now also covers a larger global customer platform bundle that combines mixed compute, storage, edge, integration, analytics, database, and log analytics services in one deterministic request
- active-quote licensing parity now explicitly covers `Base Database Service` and `Oracle Analytics Cloud` OCPU license flips, not only OIC and autonomous database families
- follow-up capability evaluation now treats `null` extracted inputs as missing, which prevents false `license optional` decisions while preserving the intentional no-license path for OAC named-user quotes
- active-quote quantity parity now also covers metadata-driven OCPU/storage replacement for `Base Database Service` and OAC OCPU families, reducing the risk of duplicated sizing tokens in follow-up prompts
- active-quote quantity parity now also covers `Database Cloud Service` OCPU replacement and `Exadata Exascale` ECPU/storage/model replacement, expanding deterministic follow-up support across licensing-sensitive database families
- active-quote follow-up detection now also recognizes edition-only database changes and Exadata infrastructure-only changes as valid quote mutations
- active-quote quantity and variant parity now also covers:
  - `Base Database Service` edition replacement
  - `Base Database Service` OCPU-to-ECPU replacement
  - `Base Database Service` ECPU license flips
  - `Base Database Service` ECPU edition replacement
  - `Database Cloud Service` edition replacement
  - `Database Cloud Service` edition-sensitive license flips
  - `Database Cloud Service` standard and extreme-performance edition transitions
  - `Exadata Dedicated Infrastructure` ECPU replacement
  - `Exadata Dedicated Infrastructure` X11M infrastructure replacement
  - `Exadata Cloud@Customer` ECPU replacement
  - `Exadata Cloud@Customer` X10M infrastructure replacement
- composite active-quote removal parity now also covers safe service removal inside mixed persisted bundles for:
  - `OCI Data Safe`
  - `OCI Log Analytics`
  - `Oracle Integration Cloud Standard`
  - `Oracle Analytics Cloud Professional`
- explicit composite-removal follow-ups now suppress later family-level replacement passes, which prevents accidental mutations such as `sin OIC Standard` rewriting `Base Database Service Enterprise` into `Standard`
- composite active-quote replacement parity now also covers safe sibling-service swaps inside mixed persisted bundles for:
  - `Oracle Integration Cloud Standard -> Oracle Integration Cloud Enterprise`
  - `Oracle Analytics Cloud Professional -> Oracle Analytics Cloud Enterprise`
- composite active-quote replacement parity now also covers the reverse sibling-service swaps inside mixed persisted bundles for:
  - `Oracle Integration Cloud Enterprise -> Oracle Integration Cloud Standard`
  - `Oracle Analytics Cloud Enterprise -> Oracle Analytics Cloud Professional`
- explicit composite-replacement follow-ups now suppress later family-level replacement passes, which prevents accidental mutations such as `cambia OIC Standard por OIC Enterprise ...` rewriting `Base Database Service Enterprise` into `Standard`
- active-quote variant parity now also covers family-owned variant swaps for:
  - `OCI Data Safe` (`Database Cloud Service <-> On-Premises Databases`)
  - `OCI Log Analytics` (`Active Storage <-> Archival Storage`)
- those same family-owned variant swaps are now covered inside mixed persisted database bundles, preserving neighboring `Exadata Cloud@Customer`, `Data Safe`, and `Log Analytics` segments while only the intended family changes
- the `OCI Data Safe` and `OCI Log Analytics` variant-swaps are now covered in both directions on direct active quotes and mixed persisted bundles, so this family-owned follow-up slice is symmetric rather than one-way
- focused `service-families` unit coverage now also validates the follow-up capability matrix itself for the recently hardened families, including:
  - composite replacement flags on `OIC` / `OAC` sibling families
  - family-owned replacement rules on `Data Safe` and `Log Analytics`
  - composite-removal registry entries for `Data Safe` and `Log Analytics`
- the rule-registry artifact suite now also guards `security_waf` inside `followup_capability_matrix.json`, including its canonical service name, composite remove/replace flags, and active-quote rule presence
- mixed persisted workbook and RVTools follow-up coverage now also proves that `Monitoring Retrieval -> Monitoring Ingestion` preserves composite quote context not only with `FastConnect` and neighboring `Flexible Load Balancer` services, but also with neighboring `Health Checks`
- `service-families.js` now also exports a reusable follow-up capability matrix view, so this metadata can be inspected directly by tests and future tooling instead of only through assistant regressions
- the same follow-up capability matrix is now emitted as a machine-readable rule artifact in `pricing/data/rule-registry/followup_capability_matrix.json`, aligning this metadata with the existing `coverage_matrix.json` and `service_family_rules.json` artifacts

Reference:

- [calculator-parity.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/calculator-parity.test.js)

### Current Test Baseline

Current test baseline:

- assistant follow-up regression suite: `148 pass / 0 fail`
- service-families metadata suite: `15 pass / 0 fail`
- rule-registry artifact suite: `3 pass / 0 fail`
- session follow-up helper suite: `9 pass / 0 fail`
- workbook-focused suite: `40 pass / 0 fail`
- parity suite: `154 pass / 0 fail`
- quote export endpoint suite: `3 pass / 0 fail`
- full server suite in sandbox: `760 pass / 0 fail`

This is the operational baseline at the time of this documentation update.

Most recently closed conservative slices:

- workbook-origin and RVTools-origin follow-up coverage now also includes shared `FastConnect + Monitoring Retrieval + DNS` bundles where `DNS` query-volume changes mutate only the `DNS` segment while preserving neighboring `FastConnect`, neighboring `Monitoring Retrieval`, and the surrounding compute/storage quote context
- workbook-origin and RVTools-origin follow-up coverage now also includes shared `FastConnect + Health Checks + DNS` bundles where `DNS` query-volume changes mutate only the `DNS` segment while preserving neighboring `FastConnect`, neighboring `Health Checks`, and the surrounding compute/storage quote context
- workbook-origin and RVTools-origin follow-up coverage now also includes shared `FastConnect + Health Checks + DNS` bundles where `DNS` removal preserves neighboring `FastConnect`, neighboring `Health Checks`, and the surrounding compute/storage quote context
- workbook-origin and RVTools-origin follow-up coverage now also includes shared `Load Balancer + DNS` bundles where `DNS` query-volume changes mutate only the `DNS` segment while preserving neighboring `Flexible Load Balancer` and the surrounding compute/storage quote context
- workbook-origin and RVTools-origin follow-up coverage now also includes shared `Load Balancer + Monitoring Retrieval` bundles where `Load Balancer` bandwidth changes mutate only the `Load Balancer` segment while preserving neighboring `Monitoring Retrieval` and the surrounding compute/storage quote context
- workbook-origin and RVTools-origin follow-up coverage now also includes shared `Load Balancer + Health Checks` bundles where removing `Load Balancer` preserves neighboring `Health Checks` and the surrounding compute/storage quote context
- workbook-origin and RVTools-origin follow-up coverage now also includes shared `Load Balancer + Health Checks` bundles where removing `Health Checks` preserves neighboring `Flexible Load Balancer` and the surrounding compute/storage quote context

## What Is Explicitly Closed

These blocks should now be treated as closed unless a regression reopens them:

### 1. Server-Authoritative Session Model

Closed:

- frontend is no longer the source of truth for active session state
- workbook follow-up detection is backend-owned
- session events and contexts are persisted server-side

### 2. Critical VM Shape Misclassification

Closed:

- `VM.Standard3.Flex` and related VM-family gaps that were causing severe misroutes
- `computeVariantAudit.uncoveredServiceCount = 0`

### 3. Copy/Export Based On Persisted Quotes

Closed at baseline level:

- `Copy Quote`
- `Export CSV`
- `Export XLSX`

These now operate from persisted quote state rather than depending purely on transient DOM state.

### 4. Safe Failure Policy

Closed at baseline level:

- unsupported pricing scenarios should return safe guidance or clarification
- the agent should not invent deterministic quotes for unsupported families

## What Is Still Pending

### 1. Broader OCI Calculator Parity

Pending:

- more multi-service golden cases
- more database combinations
- more analytics/integration combinations
- more workbook/RVTools parity cases
- more mixed networking/security architectures

Recently advanced:

- added deterministic parity for an `OIC + OAC + OCI Data Integration workspace + FastConnect + Log Analytics archival storage` bundle
- added deterministic parity for a `Base Database + OIC + OAC + Data Safe + Monitoring Ingestion` bundle
- added deterministic parity for an `Autonomous AI Lakehouse + Object Storage + Log Analytics archival + Notifications` bundle
- added deterministic parity for a `Database Cloud Service + OIC Standard BYOL + OAC Professional + Monitoring Retrieval + Monitoring Ingestion` bundle
- added deterministic parity for a `Base Database BYOL + File Storage + Archive Storage + Infrequent Access retrieval + Monitoring Ingestion` bundle
- added deterministic parity for a `Load Balancer + WAF + API Gateway + DNS + Health Checks + Notifications` serverless edge/security bundle
- added deterministic parity for a `Base Database BYOL + OIC Standard BYOL + OAC Professional BYOL OCPU + FastConnect` transport-platform bundle
- added deterministic parity for a `Database Cloud Service BYOL + OIC Enterprise BYOL + OAC Professional BYOL OCPU + Object Storage` platform bundle
- added deterministic parity for an `Exadata Dedicated + OIC Standard + OAC Enterprise + File Storage + FastConnect` storage-heavy platform bundle
- added workbook aggregate regression coverage for `RVTools-derived compute + FastConnect + Monitoring Retrieval`
- added workbook aggregate regression coverage for `guided inventory AMD workloads + Flexible Load Balancer + Health Checks`

Why this matters:

- parity is the strongest evidence that the deterministic engine is production-safe

### 2. More Declarative Family Coverage

Pending:

- move more behavior from `assistant.js` into:
  - `service-families`
  - `context-packs`
  - generated registries
- continue moving non-follow-up family policy out of `assistant.js`
- extend the declarative capability matrix beyond the currently hardened active-quote replacement categories

Recently advanced:

- extracted WAF and Data Safe extracted-input aliasing into declarative family metadata
- extracted composite replacement ownership for `OCI Data Safe` and `OCI Log Analytics` into declarative family metadata and the emitted follow-up capability artifact
- added dedicated regression coverage for family-level input normalization
- moved the structured discovery fallback builder into `context-packs.js` so family discovery responses no longer depend on a local assistant-only formatter
- moved discovery and billing-question classification rules into a dedicated reusable module instead of keeping them embedded in `assistant.js`
- moved lightweight heuristic intent construction and discovery-route override logic into a dedicated helper module
- moved analyzed-intent reconciliation and fallback merge logic into a dedicated helper module
- moved quote-followup route forcing and modify-quote intent override logic into a dedicated helper module
- moved contextual follow-up request shaping and post-intent Flex-comparison preparation into a dedicated helper module
- workbook aggregate coverage now also includes the shared `FastConnect + Load Balancer` bundle and an explicit `Monitoring Retrieval + Health Checks` workbook-path regression
- guided inventory aggregate coverage now also includes the shared `FastConnect + Load Balancer` bundle, closing the source-path mirror against the already-covered RVTools aggregate scenario
- mixed persisted follow-up coverage now also includes the `RVTools` mirror for `Load Balancer + Health Checks -> DNS`, closing that replacement symmetry across both workbook and RVTools source paths
- `OCI Monitoring` now also owns declarative active-quote replacement rules for `Ingestion <-> Retrieval` plus datapoint mutations, and those capabilities are locked by both runtime follow-up regressions and the emitted follow-up capability matrix artifact
- parity now also includes smaller observability-edge anchor cases for `Monitoring Ingestion + Health Checks` and `Monitoring Retrieval + Health Checks`, giving us faster failure isolation than the larger mixed observability bundles alone
- moved Flex-comparison clarification prompts and deterministic comparison reply shaping into a dedicated helper module so the same policy is reused across pre-intent and post-intent paths
- moved greeting and FastConnect-specific early deterministic replies into a dedicated helper module and added focused regression coverage for those entry points
- moved generic compute-shape clarification detection into a dedicated helper module and added focused unit coverage for Intel, AMD, and non-VM guardrails
- moved license-choice detection and clarification-decision logic into a dedicated helper module and added focused unit coverage for BYOL, License Included, and skip-input guardrails
- moved BYOL ambiguity detection and quote filtering into the same license helper module and added unit coverage for mixed-license quotes that keep shared non-license lines
- moved mixed-license ambiguity clarification formatting into the same helper module so the remaining BYOL confirmation branch is no longer assistant-owned
- moved quote-unresolved payload shaping into a dedicated helper so unresolved deterministic quote replies no longer depend on inline assistant formatting
- moved canonical family request shaping and preflight quote selection into `quote-request-shaping.js` so active-quote parsing, canonical rewrite preference, and modifier preservation no longer remain embedded in `assistant.js`
- added focused unit coverage for canonical rewrite safety, including the guardrail that rejects family rewrites which would drop family-owned replacement signals from the active quote source
- moved quote entry preparation into `quote-entry-preparation.js` so route-driven quote-follow-up reuse, unsupported-compute discovery fallback, and deterministic top-service promotion no longer remain inline in `assistant.js`
- added focused unit coverage for quote entry preparation and revalidated the helper with assistant regressions for legacy fixed-VM fallback and workbook-style route follow-ups
- moved the early deterministic direct-quote branches into `direct-quote-fast-paths.js` so composite quote resolution and simple transactional quote resolution no longer remain embedded in `assistant.js`
- added focused unit coverage for the new direct-quote helper and revalidated it with assistant composite-bundle regressions plus calculator parity coverage for compute-and-storage entry paths
- moved the remaining pre-intent early exits into `early-assistant-routing.js` so greeting responses, generic VM shape clarification, and flex-comparison early routing no longer remain embedded in `assistant.js`
- added focused unit coverage for the new early-routing helper and revalidated it with the existing early-reply and flex-comparison suites plus assistant regressions for pre-intent and composite scenarios
- moved mid-flow discovery routing into `discovery-routing.js` so registry query construction, catalog discovery replies, and structured discovery fallback handling no longer remain embedded in `assistant.js`
- added focused unit coverage for the new discovery-routing helper and revalidated it with context-pack fallback coverage plus broad assistant discovery regressions for billing guidance, prerequisite questions, SKU-composition prompts, and safe unavailability behavior
- consolidated the remaining quote-entry transition into `quote-entry-preparation.js` so unsupported-compute discovery fallback payloads and deterministic `topService` promotion no longer remain embedded in `assistant.js`
- expanded focused unit coverage for quote-entry preparation and revalidated it with assistant regressions for legacy fixed-VM fallback, discovery-versus-quote guardrails, deterministic HPC quotes, and Autonomous AI Lakehouse quote entry
- extended `quote-entry-preparation.js` into a quote-ready state contract so family resolution, request shaping, and preflight quote selection now cross into clarification through an explicit helper return value instead of more assistant-owned inline state
- added focused unit coverage for quote-ready state preparation and revalidated it with assistant regressions for deterministic service entry, license-choice routing, active quote follow-ups, and quote narrative preservation
- moved the post-clarification response phase into `post-clarification-routing.js` so license-choice prompts, final clarification replies, deterministic quote execution, unresolved quote fallback, and generic answer fallback no longer remain embedded in `assistant.js`
- added focused unit coverage for the new post-clarification helper and revalidated it with assistant regressions for license-choice scenarios, unresolved quote handling, clarification guardrails, and deterministic quote narrative behavior
- moved the remaining intent bridge into `intent-pipeline.js` so GenAI fallback handling, quote-followup override ordering, post-intent follow-up reconciliation, and post-intent flex replies no longer remain embedded in `assistant.js`
- added focused unit coverage for the new intent bridge and revalidated it with helper suites plus assistant regressions for discovery fallback, quote-followup reuse, and flex-comparison behavior
- moved final answer-mode fallback payload shaping into a dedicated helper so the last generic guidance branch is no longer assistant-owned
- moved post-reformulation quote clarification state handling into a dedicated helper so missing-input gating and pre-quote clarification no longer depend on inline assistant branching
- moved active-quote clarification and license-follow-up heuristics into `clarification-followup.js` so short contextual replies, prior-product recovery, license directive extraction, session quote reuse, and inline shape selection no longer remain embedded in `assistant.js`
- added focused unit coverage in `clarification-followup.test.js` for contextual clarification merges, license-mode directive normalization, session quote follow-up reuse, and inline shape replacement guardrails
- revalidated the extraction with a green `11 pass / 0 fail` helper suite and kept the sandbox full-suite baseline green at `675 pass / 0 fail`
- moved active-quote session mutation orchestration into `session-quote-followup.js` so composite removal/replacement flows, license-mode rewrites, currency changes, modifier persistence, active-family inference, and route-driven quote-followup merges no longer remain embedded in `assistant.js`
- added focused unit coverage in `session-quote-followup.test.js` for Flex shape switching, composite removal and sibling replacement behavior, route-driven follow-up reuse, metered modifier preservation, and short prefixed-answer normalization
- revalidated that extraction with a green `19 pass / 0 fail` focused helper run and kept the sandbox full-suite baseline green at `675 pass / 0 fail`
- completed a full green pass of `pricing/server/test/*.test.js` after the refactor wave, giving us confidence to prioritize broader deterministic coverage and parity expansion instead of continuing smaller orchestration extractions by default
- added focused regression coverage for active-quote license flips in `Base Database Service` and OAC OCPU families, plus a metadata-unit guard that keeps OAC named-user quotes intentionally non-licensable
- fixed a capability-evaluation bug where `null` extracted inputs were being treated as present values, which had incorrectly disabled OAC OCPU license flips during active-quote parsing
- extended family metadata so active quote follow-ups can replace Base Database OCPU/storage sizing and OAC OCPU sizing directly, instead of relying on prompt concatenation
- revalidated that broader assistant, parity, and workbook coverage stayed green after the metadata change
- extended the same metadata-driven follow-up replacement pattern to `Database Cloud Service` and `Exadata Exascale`, including a storage-model switch path for filesystem versus smart database storage
- revalidated that the broader assistant and full server suites stayed green after the new database-family replacement rules
- extended the follow-up gate so edition-only prompts and Exadata infrastructure-only prompts are treated as active-quote mutations instead of falling back to clarification
- added deterministic regressions for `Database Cloud Service` edition changes plus `Exadata Dedicated Infrastructure` and `Exadata Cloud@Customer` ECPU and infrastructure-shape swaps
- extended `Base Database Service` metadata to replace the active edition token declaratively and added deterministic follow-up coverage for edition swaps plus `OCPU -> ECPU` compute-mode changes
- added deterministic coverage for edition-sensitive `Database Cloud Service` license flips on `Extreme Performance`
- added deterministic coverage for `Base Database Service` ECPU license flips and ECPU edition swaps, plus `Database Cloud Service` standard/extreme-performance edition transitions under both `License Included` and `BYOL`
- revalidated with a green `275 / 0` assistant follow-up suite and a green `625 / 0` full server suite

Why this matters:

- lowers long-term maintenance cost
- reduces one-off prompt handling
- gives us a stable baseline for expanding follow-up capabilities and mixed-bundle coverage with less regression risk

### 3. Stronger Quote Follow-Ups Across More Families

Pending:

- more complete backend quote-followup support for:
  - licensing changes
  - component add/remove
  - currency/modifier updates
  - conceptual active-quote questions that should answer instead of mutate
  - family-specific modifications outside the currently hardened set

### 4. Observability And Production Telemetry

Pending:

- better per-turn structured logs for:
  - route
  - quotePlan
  - context pack summary
  - quote source
  - warnings
- stronger startup and health diagnostics

### 5. Concurrency And Multiuser Hardening

Pending:

- more explicit tests for concurrent session mutation
- more verification of session isolation at scale
- more browser rehydration and race-condition tests

### 5A. Parallel Execution Readiness

Recently advanced:

- formalized a conservative `5 effective agents` operating ceiling for the current stage
- documented explicit single-writer hotspots for:
  - `assistant.js`
  - `service-families.js`
  - shared plan and roadmap docs
- defined lane-based ownership for:
  - follow-up metadata
  - assistant regression partitioning
  - calculator/parity expansion
  - workbook/RVTools hardening
  - docs and registry alignment
- extracted stable assistant regression domains into dedicated suites so parallel work no longer has to collide on one monolithic file
- introduced a shared assistant regression harness in:
  - [assistant-test-helpers.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/assistant-test-helpers.js)
- the first extracted suites are now:
  - [assistant-followup-compute-composite-regressions.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/assistant-followup-compute-composite-regressions.test.js)
  - [assistant-deterministic-service-bundles-regressions.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/assistant-deterministic-service-bundles-regressions.test.js)
  - [assistant-expert-summary.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/assistant-expert-summary.test.js)
  - [assistant-sanitization.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/assistant-sanitization.test.js)
- the second extracted follow-up lane is now:
  - [assistant-followup-platform-database-regressions.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/assistant-followup-platform-database-regressions.test.js)
- the third extracted routing lane is now:
  - [assistant-routing-discovery-regressions.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/assistant-routing-discovery-regressions.test.js)
- the fourth extracted compute lane is now:
  - [assistant-deterministic-compute-regressions.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/assistant-deterministic-compute-regressions.test.js)
- the fifth extracted canonical-request lane is now:
  - [assistant-request-shaping-regressions.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/assistant-request-shaping-regressions.test.js)
- the sixth extracted residual direct-quote lane is now:
  - [assistant-direct-quote-unit-conversions.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/assistant-direct-quote-unit-conversions.test.js)
- the seventh extracted residual deterministic-quote lane is now:
  - [assistant-residual-deterministic-quotes.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/assistant-residual-deterministic-quotes.test.js)
- the eighth extracted comparison lane is now:
  - [assistant-flex-comparison-regressions.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/assistant-flex-comparison-regressions.test.js)
- the former monolith [assistant-regressions.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/assistant-regressions.test.js) has now been retired after its remaining coverage was redistributed into focused suites
- assistant regression coverage now lives in dedicated suites backed by:
  - [assistant-test-helpers.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/assistant-test-helpers.js)
- the next maintenance rule is to add future assistant regressions to the appropriate focused suite instead of recreating a shared sink file

Reference:

- [PARALLEL_EXECUTION_LANES.md](/Users/javierchan/Documents/GitHub/oci/pricing/docs/PARALLEL_EXECUTION_LANES.md)

Why this matters:

- lets us use sub-agents for real throughput gains without turning hotspots into merge bottlenecks
- creates a safer path to future larger-scale parallelism once current chokepoints are reduced

### 6. Structured Discovery Knowledge Layer

Pending:

- introduce service-level `composition blueprints` so discovery answers can explain:
  - which SKUs or pricing components usually participate in a quote
  - which inputs are mandatory before quoting
  - how each family is billed
  - how licensing and variants affect the composition
- introduce a small declarative set of response types such as:
  - `sku_composition`
  - `billing_explanation`
  - `required_inputs`
  - `variant_comparison`
- improve retrieval so discovery answers are driven by family blueprints and context packs rather than by prompt-specific assistant rules
- pilot the blueprint approach on:
  - `compute_vm_generic`
  - `integration_oic`
  - `storage_block`
  - `database_base_db`
  - `network_load_balancer`
- convert a curated manual prompt set into a fixed capability regression for conceptual discovery quality

Why this matters:

- reduces pressure to keep adding one-off rules in `assistant.js`
- improves consistency across GenAI model changes
- strengthens SKU-composition and prerequisite answers, which are currently more fragile than deterministic quote paths

## Not In Scope For “Done”

These are intentionally not required for considering the current roadmap materially successful:

- quoting every OCI service in existence
- removing GenAI entirely from the system
- perfect zero-maintenance parity for all future Oracle catalog changes

The target is a production-grade pricing agent for the practical OCI quoting perimeter, not infinite scope.

## Next Recommended Work Order

### Priority 1

- widen OCI Calculator parity with more family-level and bundled scenarios

### Priority 2

- keep moving family and discovery logic out of `assistant.js` into registries and context packs

### Priority 3

- expand backend quote-followup handling across more complex families

### Priority 4

- strengthen observability, startup checks, and multiuser concurrency coverage

## Update Rule For This Document

When this roadmap is updated:

1. refresh values from generated artifacts instead of editing counts by memory
2. move work from `Pending` to `Implemented` only after code + tests are green
3. treat one-off fixes as incomplete unless they improve metadata, parity, or deterministic runtime behavior

This file should remain a reference document, not a historical dump of every incremental change.
