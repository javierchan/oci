# Coverage Roadmap

## Status Snapshot

This section is the working summary of progress.

### Done

- OCI catalog ingestion is working from:
  - `products.json`
  - `metrics.json`
  - `productpresets.json`
- workbook and PDF extraction pipelines exist and are stored in:
  - `data/xls-extract`
  - `data/price-list-extract`
- source pricing documents were centralized in:
  - `data/source-docs/current/`
- runtime containers now package `data/` so workbook-backed and PDF-derived rule artifacts are available inside Docker
- OCI GenAI is integrated through the OCI SDK for:
  - text interpretation
  - image interpretation
- deterministic quotation flow exists in runtime:
  - `server/quotation-engine.js`
  - `server/dependency-resolver.js`
- service registry exists and is exposed through:
  - `/api/coverage`
  - `/api/catalog/search`
- coverage levels `L0-L4` are already modeled
- hybrid flow exists:
  - `GenAI` interprets
  - deterministic engine calculates
- image paste flow exists in the UI
- Excel upload flow exists
- RVTools workbook upload now has VMware-aware migration sizing behavior:
  - detects `vInfo`, `vCPU`, `vMemory`, and `vDisk` sheets as an RVTools export
  - consolidates sizing by VM before quoting
  - skips VMware service/system VMs that should not be migration-priced, such as `vCenter`, `vCLS`, and similar platform appliances
  - converts VMware x86 `vCPU` counts to OCI `OCPU` using `2 VMware vCPUs = 1 OCI OCPU`
  - maps provisioned VMware disk capacity to OCI `Block Storage`
  - surfaces aggregated warnings for skipped service VMs, powered-off VMs, and Windows licensing follow-up needs
- OCI Functions deterministic quoting works for:
  - execution time
  - invocations
- `FastConnect` deterministic quoting works for:
  - port selection by bandwidth
- `Block Volume` deterministic quoting works for:
  - storage
  - performance units
- `BYOL` ambiguity handling now exists:
  - if `BYOL` vs `License Included` is ambiguous, the assistant asks first
  - if the user specifies one mode, the quote is filtered accordingly
- consumption explanation is now live in quote narratives for deterministic services, starting with:
  - `FastConnect`
  - `Block Volume`
  - any other `L4` quote whose SKU metric maps to a known consumption pattern
- OCI GenAI post-quote enrichment is now live as an optional narrative layer on top of deterministic results:
  - assistant quotes now include a short executive summary without changing SKUs, totals, or assumptions
  - Excel and RVTools imports now return a workbook-level summary for migration sizing and next checks
  - RVTools imports now surface migration-oriented narrative about skipped VMware service VMs, powered-off VMs, and Windows follow-up needs
  - deterministic expert summaries now anchor monthly and annual totals, cost drivers, and line-item counts directly to the quoted OCI line items
  - GenAI enrichment is now sanitized so it can add technology-specific considerations and migration notes without redoing arithmetic or contradicting quoted totals
  - workbook enrichment now keeps deterministic counts and totals for both inventory workbooks and RVTools exports, while reserving GenAI only for migration-focused notes
- conversational follow-up handling now preserves product context for:
  - short `BYOL` / `License Included` replies
  - natural follow-ups such as `now do it with license included`
  - short numeric or mode clarifications such as `1.0` and `On demand`
  - short shape-selection replies such as `E4.Flex` after a prior compute clarification
- regression coverage now exists for:
  - catalog listing flows such as `FastConnect` SKU discovery without unnecessary region questions
  - license-mode follow-ups that switch from `BYOL` to `License Included`
  - multistep `Flex` comparison conversations with short clarification answers
  - explicit `Flex + attached Block Storage` prompts so compute and storage are quoted together instead of collapsing to a single domain
  - generic compute clarification flows for `Intel`, `AMD`, and `Arm`
  - hardening cases found during random smoke testing, including:
    - `WAF` prompts that provide generic `instances + requests`
    - `WAF` prompts that append explanation wording without losing the deterministic quote
    - `WAF` prompts where the canonical family request could otherwise lose the richer instance count from the original user text
    - multi-service bundles where some segments need canonical-family rescue inside the composite flow, including:
      - `Exadata Cloud@Customer + Data Safe + Log Analytics`
      - `Base Database Service + Oracle Integration Cloud + Oracle Analytics Cloud`
      - `Generative AI request-volume bundles`
      - `Log Analytics + Monitoring` observability bundles
    - `Exadata Exascale` prompts that must preserve `compute + filesystem storage`
    - `Exadata Dedicated` prompts that must preserve `database compute + base-system infrastructure`
- `Compute Flex` now has:
  - deterministic quoting for `E4`, `E5`, and `A1` flex shapes
  - correct `HOUR_UTILIZED` tier handling for free-tier and overage-based SKUs such as `A1`
  - deterministic `compute + attached block volume` quoting when the prompt already includes an explicit `Flex` shape plus storage sizing
  - deterministic composite workload quoting when compute is combined with attached `Block Storage`, `Object Storage`, and `Flexible Load Balancer` in the same request
  - deterministic generic VM clarification before quoting when the user provides sizing but not the shape
  - vendor-aware generic VM clarification that suggests `E4/E5` for AMD-class x86 prompts and `A1.Flex` for Arm prompts
  - dedicated conversational comparison flow for prompts such as `Compare E4.Flex vs E5.Flex vs A1.Flex ... with and without Capacity Reservation`
  - deterministic comparison output for `On-demand` vs `Capacity Reservation` with user-provided utilization
  - deterministic comparison output for `On-demand` vs `Preemptible` on supported shapes such as `E4` and `A1`
  - deterministic comparison output for `On-demand` vs `Burstable` with user-provided baseline
  - comparison responses now surface modifier-support warnings when a modifier applies only to part of a shape's billable lines
- `Network Firewall` now has:
  - dedicated family metadata
  - required-input clarification behavior
  - deterministic multi-line quote when instance count and processed GB are provided
- `Web Application Firewall` now has:
  - dedicated family metadata
  - required-input clarification behavior
  - deterministic quote when instance/policy count and requests are provided
- `File Storage` now has:
  - dedicated family metadata
  - deterministic quote for storage capacity
  - deterministic quote for high-performance mount target when performance units per GB are provided
- `Object Storage` now has:
  - dedicated family metadata
  - deterministic quote for storage capacity so storage requests resolve to the storage SKU instead of request-only lines
- `Flexible Load Balancer` now has:
  - dedicated family metadata
  - deterministic direct quote for `base + bandwidth`
  - deterministic inclusion inside composite workload requests
- `Data Integration` now has:
  - dedicated family metadata
  - deterministic quote for workspace usage
  - deterministic quote for data processed per hour
  - deterministic quote for execution hours
- `Log Analytics` now has:
  - dedicated family metadata
  - deterministic quote for Active Storage
  - deterministic quote for Archival Storage
  - free-tier handling for the first 10 GB per month
  - storage-unit conversion based on 300 GB per unit with a 1-unit minimum for billable usage
  - explicit note when the archival-storage unit conversion is inferred from the current Oracle price-list references
- transaction-volume services now have broader generic deterministic coverage through the shared `requests` pattern, including:
  - `Networking - DNS`
  - `Notifications - Email Delivery`
  - `Notifications - HTTPS Delivery`
  - `Identity and Access Management - SMS`
  - `Identity and Access Management - Token`
  - `Observability - Monitoring - Ingestion`
  - `Observability - Monitoring - Retrieval`
  - `OCI Generative AI - Large Cohere`
  - `OCI Generative AI - Vector Store Retrieval`
  - `OCI Generative AI - Web Search`
  - `Security - Threat Intelligence`
  - other services whose Oracle catalog metrics are expressed as `queries`, `emails sent`, `SMS messages`, `transactions`, or `tokens`
- request-volume scaling now handles catalog metrics with and without commas, for example:
  - `1000 Requests`
  - `10,000 Transactions`
  - `1,000,000 Tokens`
- dedicated-only GenAI services now fail safer when the prompt asks for a transaction-style quote that the live catalog does not expose directly:
  - `OCI Generative AI - Cohere Rerank - Dedicated` now asks for `cluster-hours` instead of inventing a transaction-based quote
  - `OCI Generative AI - Memory Ingestion` now returns an explicit `quote_unresolved` response when the live catalog does not expose a direct quotable SKU, instead of silently mapping to `Memory Retention`
- direct-consumption time/media metric families now have validated deterministic coverage for:
  - `Vision - Custom Training` billed by `Training Hour`
  - `Speech` billed by `Transcription Hour`
  - `Vision - Stored Video Analysis` billed by `Processed Video Minute`
  - `Media Flow` minute-based output billing, including exact prompt disambiguation for variants such as `HD - Below 30fps`
- direct counted-quantity `Each` metrics now have safer deterministic handling, including:
  - `OCI Batch`
  - `Data Safe for Database Cloud Service - Databases`
  - `Data Safe for On-Premises Databases & Databases on Compute`
  - `OCI Fleet Application Management Service`
  - `OCI Health Checks`
  - other services where the billable quantity is a direct count of databases, devices, stations, jobs, or similar counted resources
- staged smoke testing is now part of hardening:
  - broader `/api/assistant` batches are being run against mixed service families
  - mismatches found in runtime are converted either into deterministic fixes or into narrower clarifications when the live catalog does not expose a direct SKU
- consolidated bundle smoke testing is now part of hardening:
  - common co-estimated workloads are exercised as single prompts, not only as isolated service quotes
  - bundle composition is validated across mixed requests that combine compute, storage, networking, security, database, integration, analytics, and serverless services
  - the current hardened bundle set includes:
    - `3-tier production` workloads
    - `data platform` bundles
    - `secure edge` bundles
    - `integration + analytics` bundles
    - `serverless retrieval` bundles
    - `database modernization` bundles
    - `observability + notifications` bundles with `Monitoring Ingestion`, `Monitoring Retrieval`, `Notifications HTTPS Delivery`, and `Log Analytics`
    - `AI + media` bundles with `Vision`, `Speech`, and `Media Flow`
- registry ranking now ignores low-signal vendor tokens such as `OCI`, `Oracle`, and `Cloud` when scoring service matches, so generic transactional prompts resolve to the actual target service instead of unrelated OCI-branded products
- the assistant now has a narrow deterministic fast-path for simple transactional quotes, so request-volume prompts can bypass weak GenAI reformulations when the raw user text already contains enough information to quote safely
- composite workload normalization now strips narrative prefixes such as `mixed ... stack with` before quoting the first segment, which prevents bundles from drifting into unrelated OCI services
- quote parsing now strips trailing explanation requests such as `Explain how OCI measures...` before SKU resolution, so explanatory wording does not bias the deterministic match for short transactional prompts like `DNS queries`
- technology-aware expert summaries now distinguish:
  - `observability` from `analytics/integration`
  - `AI + media services` from generic OCI pricing
  - storage-heavy bundles from `network/security` bundles even when they include a load balancer
- GenAI quote enrichment now suppresses `Migration Notes` unless the source actually comes from VMware or RVTools context
- mixed `edge-security + DNS` bundles now preserve DNS as its own billable line instead of collapsing that segment into an unrelated OCI family
- observability bundles with `Monitoring Ingestion + Monitoring Retrieval + HTTPS Delivery` now preserve all three billable lines with the correct quantities instead of merging retrieval into notification delivery
- mixed operational-service bundles with `Fleet Application Management + OCI Batch + Notifications Email Delivery` now preserve all three services instead of collapsing to `OCI Batch`
- `Exadata Exascale` direct and bundled quotes now preserve filesystem-storage and smart-storage capacity lines when the prompt specifies the storage model explicitly
- expert-summary profiles now distinguish `operations/platform services` bundles from `observability`, so mixed `Fleet + Batch + Email Delivery` responses no longer present the wrong OCI specialist perspective
- coverage improved materially after this block:
  - `L4`: `797 -> 982`
  - `L1`: `547 -> 362`
  - `deterministicCount`: `838 -> 1023`
  - `explainableCount`: `828 -> 1013`
- `Autonomous AI Transaction Processing` now has:
  - dedicated family metadata
  - mandatory `BYOL` vs `License Included` clarification before quoting
  - deterministic `compute + storage` quote when ECPU and storage inputs are provided
- `Autonomous AI Lakehouse / Autonomous Data Warehouse` now has:
  - dedicated family metadata
  - support for both the current `Autonomous AI Lakehouse` naming and the historical `Autonomous Data Warehouse` naming used in Oracle price references
  - mandatory `BYOL` vs `License Included` clarification before quoting
  - deterministic `compute + storage` quote when ECPU and storage inputs are provided
  - explicit note that the current storage line is mapped to the shared autonomous database storage SKU exposed by the Oracle references used by this repo
- `Base Database Service` now has:
  - dedicated family metadata
  - mandatory `BYOL` vs `License Included` clarification before quoting
  - edition-aware deterministic `compute + storage` quoting for the first modeled VM variants
- `Database Cloud Service` now has:
  - dedicated family metadata
  - mandatory `BYOL` vs `License Included` clarification before quoting
  - deterministic OCPU quote for the first modeled license-included and `BYOL` variants
- `Oracle Integration Cloud Enterprise` now has:
  - dedicated family metadata
  - mandatory `BYOL` vs `License Included` clarification before quoting
  - deterministic enterprise quote for the first modeled instance-based variants
- `Oracle Integration Cloud Standard` now has:
  - dedicated family metadata
  - mandatory `BYOL` vs `License Included` clarification before quoting
  - deterministic standard quote for the first modeled instance-based variants
- `Oracle Analytics Cloud Professional` now has:
  - dedicated family metadata
  - deterministic quote for `named user` pricing without unnecessary license clarification
  - deterministic `OCPU` quote with `BYOL` vs `License Included` clarification when the pricing path is license-sensitive
- `Oracle Analytics Cloud Enterprise` now has:
  - dedicated family metadata
  - mandatory `BYOL` vs `License Included` clarification before quoting
  - deterministic quote for the first modeled `OCPU` and `named user` variants
- `Exadata Exascale Database` now has:
  - dedicated family metadata
  - mandatory `BYOL` vs `License Included` clarification before quoting
  - deterministic `ECPU + storage` quoting for the first modeled storage variants
- `Exadata Dedicated Infrastructure Database` now has:
  - dedicated family metadata
  - mandatory `BYOL` vs `License Included` clarification before quoting
  - deterministic metered database compute quoting
  - deterministic infrastructure line inclusion when the user explicitly sizes supported live-catalog shapes such as `base system` or `quarter rack X9M`
  - explicit warning only when infrastructure is still not sufficiently specified
- `Exadata Cloud@Customer Database` now has:
  - dedicated family metadata
  - mandatory `BYOL` vs `License Included` clarification before quoting
  - deterministic metered database compute quoting
  - deterministic infrastructure line inclusion when the user explicitly sizes supported live-catalog shapes such as `database server X11M`
  - workbook-backed monthly infrastructure fallback for first modeled `X10M` shapes such as `base system`, `database server`, `storage server`, and `expansion rack`
  - explicit warning that installation, activation, and other non-metered prerequisites may still be required

### In Progress

- moving alias handling out of scattered branches and into:
  - `service-families.js`
  - `service-registry.js`
- moving clarification logic to be driven by:
  - `requiredInputs`
  - registry metadata
- using registry matches to override weak or biased GenAI interpretations
- reducing one-off logic in `assistant.js` and `dependency-resolver.js`
- expanding data-driven routing for services outside the first hardened domains
- expanding `Log Analytics` beyond the current Active Storage path and validating broader parity against OCI Calculator or additional Oracle source data
- expanding database support beyond the first modeled families into deployment options, attached services, and prerequisite-heavy variants
- expanding beyond current transaction-volume coverage into other generic metric families such as:
  - remaining `request` and `each`-style metrics whose billable noun is still not covered by the current counted-resource parser
  - additional direct-consumption time/media variants beyond the first validated set of `training hours`, `transcription hours`, and `processed video minutes`
  - ambiguous generative-AI flows where the live Oracle catalog still surfaces adjacent services more clearly than a direct quotable SKU
- expanding compute comparison beyond the first modeled `Flex` comparison flow into broader modifier-aware scenarios such as:
  - reserved pricing outside the current `On-demand` comparison path
  - cleaner treatment of partially supported modifiers where only some billable lines accept the modifier

### Next

- derive more aliases and service groupings from workbook/catalog names
- derive more `requiredInputs` from pricing patterns automatically
- model more license variants beyond current `BYOL` gating
- model prerequisite/dependency-heavy domains
- improve calculator parity workflow using exported JSON fixtures
- add regression fixtures for known OCI Calculator scenarios
- expand regression fixtures beyond the first conversational follow-up flows already covered in automated tests

## Objective

Reach practical coverage for all OCI services represented in the Oracle pricing references used by this repo:

- OCI live catalog JSON
- localizable price list workbook
- global price list PDFs and supplement

This does not mean "recognize the name".

Coverage for a service is complete only when the agent can:

1. identify the correct service or SKU
2. request missing sizing or licensing inputs when necessary
3. resolve dependencies and prerequisites
4. calculate price deterministically
5. explain how OCI measures consumption

## Current Strategy

The repo will scale through:

- data-driven registry expansion
- pattern-based consumption modeling
- deterministic dependency resolution
- targeted ambiguity handling
- validation against OCI Calculator and known examples

## Backlog Structure

### Phase 1: Registry Completeness

Status: `In Progress`

Goal:

- ensure every service from workbook and catalog is represented in the service registry

Tasks:

- normalize duplicate service names
- attach service aliases from workbook/catalog names
- derive `requiredInputs` from pricing metrics
- derive `licenseModes` where `BYOL` variants exist
- expose gaps through `/api/coverage`

Acceptance:

- every workbook service appears in the registry
- duplicate aliases do not fragment the same service

### Phase 2: Pattern Completeness

Status: `In Progress`

Goal:

- cover all major billing patterns used across OCI services

Target patterns include:

- `port-hour`
- `load-balancer-hour`
- `bandwidth-mbps-hour`
- `capacity-gb-month`
- `performance-units-per-gb-month`
- `requests`
- `users-per-month`
- `ocpu-hour`
- `ecpu-hour`
- `memory-gb-hour`
- `generic-hourly`
- `generic-monthly`
- functions-specific patterns

Acceptance:

- services mapped to these patterns can quote from normalized input without service-specific hacks

### Phase 3: Licensing And Ambiguity

Status: `Started`

Goal:

- stop unsafe quotes when pricing depends on licensing mode or service variant

Tasks:

- detect `BYOL` vs `License Included`
- detect mutually exclusive variants
- ask clarification before quoting when variants materially change price

Acceptance:

- mixed `BYOL` and non-`BYOL` quotes are blocked until clarified

### Phase 4: Dependency Modeling

Status: `In Progress`

Goal:

- resolve billable multi-line service compositions correctly

Priority domains:

1. network firewall
2. web application firewall
3. file storage
4. log analytics
5. data integration
6. analytics and integration products with licensing variants
7. databases and attached storage/deployment prerequisites

Acceptance:

- dependent services produce all expected billable lines
- prerequisite services are not silently omitted

### Phase 5: Consumption Explanation

Status: `Started`

Goal:

- explain how OCI measures the selected service

Tasks:

- attach explanation templates by pattern
- include unit transformations in assistant responses
- explain why clarifications are required when they are required

Acceptance:

- for every `L3/L4` service, the agent can explain the billing metric and quantity mapping

### Phase 6: OCI Calculator Parity

Status: `Started`

Goal:

- compare deterministic output against OCI Calculator examples and exports

Tasks:

- parse calculator JSON exports
- compare SKU, quantity, monthly cost, annual cost
- track parity cases as fixtures
- expand automated regression fixtures for:
  - conversational follow-up flows
  - catalog discovery/listing flows
  - calculator-backed quote parity cases

Acceptance:

- known OCI Calculator scenarios can be reproduced or explained when parity is impossible due to missing OCI source data

## What Is Already Reachable

These are examples of areas already working at a meaningful level:

- OCI Functions
- FastConnect
- Block Volume
- File Storage
- Data Integration
- Log Analytics Active Storage
- Autonomous AI Transaction Processing
- Base Database Service
- Database Cloud Service
- Oracle Integration Cloud Enterprise
- Oracle Integration Cloud Standard
- Oracle Analytics Cloud Professional
- Oracle Analytics Cloud Enterprise
- Exadata Exascale Database
- Exadata Dedicated Infrastructure Database
- Exadata Cloud@Customer Database
- consolidated bundles that combine commonly co-estimated OCI services in one deterministic quote
- broader mixed-domain composite bundles now compose deterministically when the parser can rescue each segment through `serviceFamily` metadata, rather than collapsing to a single surviving service
- pasted-image interpretation for supported pricing scenarios
- Excel-based estimation flow
- `BYOL` clarification for ambiguous quotes

These should be treated as reference implementations for expanding other domains.

## What Still Needs To Be Systematized

These are known gaps where catalog presence exists, but interpretation or dependency modeling is still incomplete:

- broader Log Analytics metric coverage beyond current Active Storage and Archival Storage paths
- broader database deployment options and prerequisite-heavy variants
- broader autonomous database variants beyond the current transaction-processing and data-warehouse/lakehouse serverless paths
- deeper Exadata infrastructure sizing beyond current live-catalog and first workbook-backed `X10M` shapes, plus fuller non-metered prerequisite composition
- service families where GenAI wording can still bias the wrong product match
- services with multi-line prerequisite bundles
- services with multiple billing dimensions and unclear default sizing

## Working Rules

When a bug appears:

1. confirm the correct service/SKU from catalog or workbook
2. decide whether the issue is:
   - alias problem
   - required-input problem
   - licensing ambiguity
   - dependency problem
   - pattern problem
3. fix the highest-level reusable abstraction first
4. only add narrow domain logic if reuse is not realistic

## Follow-Up Checklist

Use this checklist when improving any service family:

- registry entry exists
- aliases normalized
- required inputs defined
- licensing variants handled
- dependencies modeled
- deterministic quote verified
- explanation supported
- OCI Calculator parity checked if available

## Immediate Next Domains

Based on current gaps, next priority domains are:

1. databases and attached storage/deployment prerequisites
2. analytics and integration products with licensing variants
3. additional observability/security/storage variants not yet modeled

These already exist in the catalog and registry, so the remaining work is mainly validation, required-input mapping, dependency modeling, and broader licensing coverage.

## Progress Update Rule

When a meaningful change is merged into this repo, update this file in three places:

1. `Status Snapshot`
2. the relevant `Phase` status
3. either `What Is Already Reachable` or `What Still Needs To Be Systematized`

That keeps this file usable as an execution tracker instead of only a planning note.
