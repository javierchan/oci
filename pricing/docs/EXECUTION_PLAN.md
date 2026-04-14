# Execution Plan

## Purpose

This document turns the current `pricing` roadmap into an executable work plan.

Document role:

- this file is the source of truth for tactical sequencing, active priorities, and exit criteria
- architecture intent lives in [Architecture](/Users/javierchan/Documents/GitHub/oci/pricing/docs/ARCHITECTURE.md)
- validated runtime coverage state lives in [Coverage Roadmap](/Users/javierchan/Documents/GitHub/oci/pricing/docs/COVERAGE_ROADMAP.md)
- the full docs map lives in [Docs Guide](/Users/javierchan/Documents/GitHub/oci/pricing/docs/README.md)

Use it to answer:

- what to do next
- in what order to do it
- which files are most likely to change
- how to know when a workstream is actually complete

This plan is intentionally tactical. It complements:

- [Coverage Roadmap](/Users/javierchan/Documents/GitHub/oci/pricing/docs/COVERAGE_ROADMAP.md)
- [Architecture](/Users/javierchan/Documents/GitHub/oci/pricing/docs/ARCHITECTURE.md)

## How To Use This Plan

- use `Next Concrete Tasks`, status headings, and exit criteria as the primary navigation points
- treat long completed-slice sections as execution traceability, not as the fastest way to find the next step
- if a detail is already covered as validated runtime state, prefer [Coverage Roadmap](/Users/javierchan/Documents/GitHub/oci/pricing/docs/COVERAGE_ROADMAP.md) instead of duplicating the same interpretation here

## Current Working Read

The codebase already has strong foundations:

- deterministic pricing is the core contract
- `GenAI` is used for interpretation and explanation, not final arithmetic
- session state is server-authoritative
- calculator parity and regression tests already cover a large OCI perimeter

The main imbalance today is structural:

- `assistant.js` still carries too much product logic
- parity coverage is broad but still thinner than the desired production proof level for mixed scenarios
- follow-up handling is useful but still uneven across families
- operational hardening is behind functional coverage

## Current Status

Completed in the current execution wave:

- parity coverage expanded for composite compute bundles:
  - `E4.Flex` + Load Balancer + Block Volume + Object Storage
  - `E5.Flex` + Load Balancer + Block Volume
- parity coverage now also includes mixed edge and networking/security bundles:
  - Load Balancer + WAF + DNS + Health Checks
  - Network Firewall + Monitoring Retrieval + Notifications HTTPS Delivery + Health Checks
  - Network Firewall + WAF + Load Balancer + DNS + Health Checks
- workbook parsing now recognizes more guided selections:
  - `vSphere` and `ESXi` as VMware
  - `AHV` as another hypervisor
- workbook tests now cover guided AMD `E5.Flex` and Ampere `A2.Flex` target-shape flows
- RVTools tests now also cover guided AMD `E5.Flex` and Ampere `A2.Flex` target-shape flows with VMware sizing preserved
- `assistant.js` follow-up prompt mutation logic was reduced into declarative rule sets for:
  - component removal from composite quotes
  - quantity and sizing replacements
  - currency changes
  - compute modifier updates
- active quote follow-ups can now switch license mode cleanly for covered families instead of appending ambiguous `BYOL` / `License Included` tokens
- license-mode follow-ups now consult family metadata before mutating the active quote source
- active quote license-flip coverage now also explicitly includes the reverse `BYOL -> License Included` path for `Oracle Integration Cloud Standard`, so the family can now round-trip license mode changes symmetrically on persisted quotes
- active quote license-flip coverage now explicitly includes:
  - `Base Database Service` OCPU + storage quotes
  - `Oracle Analytics Cloud Professional` OCPU quotes
  - `Oracle Analytics Cloud Enterprise` OCPU quotes
- active quote quantity-replacement coverage now also explicitly includes:
  - `Base Database Service` OCPU changes
  - `Base Database Service` storage changes
  - `Oracle Analytics Cloud Professional` OCPU changes
  - `Oracle Analytics Cloud Enterprise` OCPU changes
- active quote quantity/variant replacement coverage now also explicitly includes:
  - `Base Database Service` edition changes
  - `Base Database Service` OCPU-to-ECPU changes
  - `Base Database Service` ECPU license flips
  - `Base Database Service` ECPU edition changes
  - `Database Cloud Service` OCPU changes
  - `Database Cloud Service` edition changes
  - `Database Cloud Service` license flips for edition-sensitive variants
  - `Database Cloud Service` standard and extreme-performance edition transitions
  - `Exadata Dedicated Infrastructure` ECPU changes
  - `Exadata Dedicated Infrastructure` X11M infrastructure changes
  - `Exadata Cloud@Customer` ECPU changes
  - `Exadata Cloud@Customer` X10M infrastructure changes
  - `Exadata Exascale` ECPU changes
  - `Exadata Exascale` storage-size changes
  - `Exadata Exascale` storage-model changes
- active quote follow-up detection now also treats edition-only changes and Exadata infrastructure-only changes as valid quote mutations, instead of dropping into unnecessary clarification mode
- `Oracle Analytics Cloud` named-user quotes remain intentionally protected from license-mode follow-ups because the user-based path does not depend on `BYOL` versus `License Included`
- fixed a metadata-capability edge case where `null` extracted inputs could be treated as present values, which was incorrectly suppressing OAC OCPU license flips on active quotes
- unsupported license follow-ups are ignored for non-licensable families instead of contaminating the active prompt
- composite component-removal follow-ups for `WAF`, `DNS`, `Load Balancer`, `Health Checks`, and `API Gateway` now originate from family metadata instead of a hardcoded assistant list
- composite follow-ups now support targeted component replacement for recognized families, starting with replacement flows such as `DNS -> Health Checks`
- the first explicit family capability matrix is now in place for supported composite replacement sources and targets in the edge/security perimeter
- the deterministic composite dependency resolver now composes additional mixed-service bundles instead of collapsing to a single edge component, including `WAF`, `DNS`, `Health Checks`, `Network Firewall`, `Monitoring`, and `Notifications HTTPS Delivery`
- the deterministic composite dependency resolver now also composes more family-resolver-driven business bundles instead of dropping them during mixed architectures, including:
  - `Base Database Service`
  - `Database Cloud Service`
  - `Oracle Integration Cloud`
  - `Oracle Analytics Cloud`
  - `Log Analytics`
- the deterministic composite dependency resolver now also composes more data-platform families in mixed architectures, including:
  - `Autonomous AI Lakehouse`
  - `Autonomous AI Transaction Processing`
  - `OCI Data Integration`
- the deterministic composite dependency resolver now also composes more storage-heavy and exadata families in mixed architectures, including:
  - `OCI File Storage`
  - `OCI Archive Storage`
  - `OCI Infrequent Access Storage`
  - `OCI Object Storage Requests`
  - `Exadata Exascale`
- the deterministic composite dependency resolver now also composes more serverless and edge-adjacent families in mixed architectures, including:
  - `OCI Functions`
  - `OCI API Gateway`
- composite segment parsing now preserves more mixed-bundle usage signals, including:
  - `GB processed per hour`
  - `execution hours per month`
- composite segment parsing now also preserves:
  - storage performance units for `File Storage`
  - storage model selection for `Exadata Exascale`
- regression coverage now includes replacement of an existing capacity reservation modifier instead of duplicating it
- regression coverage now includes active license flips for:
  - Oracle Integration Cloud Standard
  - Autonomous AI Lakehouse
- regression coverage now includes a negative guard for Block Volume to ensure unsupported `BYOL` follow-ups do not alter the quote
- regression coverage now includes composite load-balancer removal via shorthand (`sin LB`)
- regression coverage now includes composite component replacement via natural-language follow-up (`cambia DNS por Health Checks 10 endpoints`)
- regression coverage now includes a guardrail proving unsupported composite replacements outside the family capability matrix do not mutate the active quote
- workbook-origin active quotes can now switch Flex shape families through a minimal shape-only follow-up while preserving sizing and attached block storage
- regression coverage now includes workbook-origin shape switching from `VM.Standard3.Flex` to shapes such as `VM.Standard.E4.Flex`
- workbook-origin compute quotes now preserve attached block storage when a minimal follow-up applies a compute modifier such as `preemptible`
- regression coverage now includes workbook-origin capacity-reservation follow-ups while preserving attached block storage
- regression coverage now also includes combined workbook-origin shape-plus-modifier follow-ups while preserving attached block storage, including:
  - `VM.Standard.E4.Flex preemptible`
  - `VM.Standard.E5.Flex capacity reservation 0.7`
- workbook coverage now also includes an aggregate guided inventory golden case that validates:
  - multiple rows in one workbook
  - selected AMD `E5.Flex` shape reuse across the workbook
  - shared `VPU` override propagation
  - combined deterministic quote totals across derived requests
- RVTools coverage now also includes an aggregate migration golden case that validates:
  - multiple VMs in one workbook
  - service VM exclusion
  - powered-off VM warning retention
  - Windows VM warning retention
  - combined deterministic quote totals across derived requests
- regression coverage now also includes combined RVTools-origin shape-plus-modifier follow-ups while preserving VMware sizing, including:
  - `Use VM.Standard.E4.Flex preemptible`
  - `Use VM.Standard.E5.Flex capacity reservation 0.7`
- quote export endpoint coverage now runs fully inside the sandbox without opening a loopback listener
- active-quote follow-up quantity replacements are now partially driven by family metadata in `service-families.js` for covered families such as:
  - `DNS`
  - `API Gateway`
  - `Email Delivery`
  - `IAM SMS`
  - `Notifications SMS Outbound`
  - `Data Safe`
  - `Network Firewall`
  - `Health Checks`
  - `Data Integration`
  - `Fleet Application Management`
  - `Oracle Threat Intelligence Service`
  - `OCI Generative AI Agents Data Ingestion`
  - `OCI Generative AI Vector Store Retrieval`
  - `OCI Generative AI Web Search`
  - `OCI Generative AI Large Cohere`
  - `OCI Generative AI Small Cohere`
  - `OCI Generative AI Embed Cohere`
  - `OCI Generative AI Large Meta`
  - `OCI Vision Image Analysis`
  - `OCI Vision OCR`
- for those covered families, `assistant.js` now treats family metadata as the primary replacement path before falling back to generic replacements for uncovered families
- transaction-based active-quote follow-ups are now fully declarative for the covered AI and Vision families, so the generic `transactions` fallback was removed from `assistant.js`
- canonical family reconstruction now merges parsed active-quote inputs with intent inputs and rejects canonical rewrites that would drop family-owned replacement signals from the active quote source
- active-quote follow-up replacements for `instances`, `users`, `queries`, `API calls`, `emails`, `messages`, `delivery operations`, `firewalls`, `endpoints`, `databases`, `workspaces`, `managed resources`, `jobs`, `Gbps`, `Mbps`, and `VPU` are now owned by family metadata for the covered families instead of shared assistant fallbacks
- workbook-origin and RVTools-origin compute quotes now also preserve `VPU` overrides through declarative `compute_flex` follow-up rules while switching shapes or applying combined shape-plus-`VPU` follow-ups
- active-quote family detection now prefers concrete Flex-shape prompts over generic compute families so workbook and RVTools follow-ups resolve against the correct metadata owner
- the remaining generic active-quote replacement fallback in `assistant.js` is now effectively empty for the currently hardened quantity and sizing categories
- workbook and RVTools coverage now also validates workbook-derived compute requests composed with shared edge services such as:
  - Flexible Load Balancer + DNS
  - FastConnect + DNS on aggregate guided-workbook totals
  - Monitoring Retrieval + Health Checks on both single-request RVTools paths and aggregate guided-workbook totals
  - Flexible Load Balancer + DNS on aggregate RVTools migration totals
  - Flexible Load Balancer + Monitoring Retrieval on aggregate guided-workbook totals
  - FastConnect + Health Checks on aggregate RVTools migration totals
  - Flexible Load Balancer + Monitoring Retrieval on aggregate RVTools migration totals
  - FastConnect + Health Checks on aggregate guided-workbook totals
- workbook-focused regression fixtures now also use reusable aggregate builders so additional guided-bundle cases can be added without repeating the full RVTools or inventory workbook scaffolding each time
- parity coverage now also includes mixed database, integration, analytics, observability, and edge bundles:
  - Base Database + Data Safe + Load Balancer + DNS
  - Base Database + Oracle Integration Cloud + Oracle Analytics Cloud + FastConnect + DNS
  - Database Cloud Service + Data Safe + Load Balancer + DNS
  - Database Cloud Service + Network Firewall + Monitoring + Health Checks
  - Database Cloud Service + Oracle Integration Cloud + Oracle Analytics Cloud + FastConnect
  - Database Cloud Service BYOL + Oracle Integration Cloud BYOL + Oracle Analytics Cloud + Object Storage
  - Database Cloud Service + File Storage + Load Balancer + DNS
  - Exadata Dedicated Infrastructure + Log Analytics + Monitoring + Health Checks
  - Exadata Dedicated Infrastructure + Oracle Integration Cloud + Oracle Analytics Cloud + Object Storage + Load Balancer
  - Oracle Integration Cloud + Oracle Analytics Cloud + Log Analytics + FastConnect
  - Oracle Integration Cloud + Oracle Analytics Cloud + File Storage + FastConnect
- parity coverage now also includes isolated database family coverage for:
  - Database Cloud Service Enterprise License Included
- parity coverage now also includes mixed autonomous and integration bundles:
  - Autonomous AI Lakehouse + Data Integration + Object Storage
  - Autonomous AI Transaction Processing + FastConnect + Monitoring + Health Checks
- parity coverage now also includes mixed storage-heavy architectures:
  - Exadata Exascale + File Storage + DNS
  - Archive Storage + Infrequent Access Storage + Object Storage Requests + Load Balancer
- parity coverage now also includes serverless edge bundles:
  - OCI Functions + API Gateway + DNS
- parity coverage now also includes observability-heavy database bundles:
  - Base Database + Log Analytics + Monitoring Ingestion + Health Checks
  - Database Cloud Service + Data Safe + Monitoring Retrieval + Notifications
  - Exadata Cloud@Customer + Data Safe + Monitoring Retrieval + Health Checks
- parity coverage now also includes autonomous platform bundles:
  - Autonomous AI Lakehouse + Data Integration + FastConnect + Monitoring Ingestion
  - Autonomous AI Lakehouse + Network Firewall + Monitoring Retrieval + Notifications
  - Autonomous AI Transaction Processing + Data Integration + Monitoring Retrieval + Notifications
  - Autonomous AI Transaction Processing + Load Balancer + DNS + Health Checks
- workbook coverage now also includes shared connectivity plus observability composition:
  - RVTools-derived compute + FastConnect + Monitoring Retrieval
  - guided inventory aggregates + FastConnect + Monitoring Retrieval
- workbook and RVTools follow-up coverage now also includes persisted mixed bundles where compute shape, VPU, or capacity reservation changes must preserve `FastConnect + Monitoring Retrieval`
- workbook and RVTools follow-up coverage now also includes persisted mixed bundles where shared `FastConnect` or `Monitoring Retrieval` components are explicitly removed without dropping compute and storage context
- workbook and RVTools follow-up coverage now also includes persisted mixed bundles where shared services are safely replaced, including `FastConnect -> DNS`, `Monitoring Retrieval -> Health Checks`, `DNS -> Health Checks`, and `Health Checks -> DNS`
- workbook and RVTools follow-up coverage now also includes persisted mixed bundles where parameter-only follow-ups mutate the intended shared service in place, including `FastConnect bandwidth`, `DNS query volume`, and `Health Checks endpoint count`
- workbook and RVTools follow-up coverage now also includes symmetric persisted mixed `FastConnect + Monitoring Retrieval` regressions across both source types for:
  - `Monitoring Retrieval` removal
  - `FastConnect -> DNS`
  - `Monitoring Retrieval -> Health Checks`
- workbook and RVTools follow-up coverage now also includes persisted mixed `FastConnect + Health Checks` regressions for:
  - RVTools-origin `Health Checks` endpoint mutations that preserve neighboring `FastConnect`
  - workbook-origin `Health Checks` removal that preserves neighboring `FastConnect`
  - RVTools-origin `Health Checks -> DNS` replacement that preserves neighboring `FastConnect`
- workbook and RVTools follow-up coverage now also includes symmetric persisted mixed `FastConnect + DNS` regressions for:
  - workbook-origin `DNS` removal that preserves neighboring `FastConnect`
  - RVTools-origin `FastConnect` removal that preserves neighboring `DNS`
  - workbook-origin `DNS -> Health Checks` replacement that preserves neighboring `FastConnect`
- workbook and RVTools follow-up coverage now also includes persisted mixed `Load Balancer + Monitoring Retrieval` regressions for:
  - workbook-origin shape-plus-`VPU` changes that must preserve both shared services
  - RVTools-origin shape-plus-capacity-reservation changes that must preserve both shared services
  - workbook-origin `Load Balancer` bandwidth mutations that must preserve neighboring `Monitoring Retrieval`
  - RVTools-origin `Load Balancer` bandwidth mutations that must preserve neighboring `Monitoring Retrieval`
- workbook and RVTools follow-up coverage now also includes symmetric persisted mixed `Load Balancer + Monitoring Retrieval` regressions for:
  - workbook-origin `Monitoring Retrieval` removal that preserves neighboring `Load Balancer`
  - RVTools-origin `Monitoring Retrieval` removal that preserves neighboring `Load Balancer`
  - RVTools-origin `Load Balancer` removal that preserves neighboring `Monitoring Retrieval`
  - workbook-origin `Monitoring Retrieval -> Health Checks` replacement that preserves neighboring `Load Balancer`
- workbook and RVTools follow-up coverage now also includes persisted mixed `Load Balancer + DNS` bundles where shared services can be removed or replaced safely without dropping compute or block storage context, including:
  - `DNS` query-volume changes
  - `DNS -> Health Checks`
  - `DNS` removal across workbook-origin and RVTools-origin sources
  - `Load Balancer` removal across workbook-origin and RVTools-origin sources
- workbook and RVTools follow-up coverage now also includes persisted mixed `Load Balancer + Health Checks` bundles where shared services can be removed or replaced safely without dropping compute or block storage context, including:
  - `Load Balancer` bandwidth changes across workbook-origin and RVTools-origin sources
  - `Load Balancer` removal across workbook-origin and RVTools-origin sources
  - `Health Checks` removal across workbook-origin and RVTools-origin sources
  - `Health Checks -> DNS`
- workbook and RVTools follow-up coverage now also includes persisted mixed `Monitoring Retrieval + Health Checks` bundles where neighboring observability services can now be safely removed, replaced, or mutated in place without dropping compute or block storage context
- workbook and RVTools follow-up coverage now also includes persisted mixed `Flexible Load Balancer + Monitoring Retrieval` bundles where monitoring-only datapoint changes mutate just the observability segment while preserving the neighboring load balancer plus the surrounding compute/storage quote context
- active `OCI Monitoring` follow-ups now preserve neighboring composite context when `Monitoring Retrieval` switches to `Monitoring Ingestion`, including persisted mixed bundles that combine monitoring with `FastConnect`, `Flexible Load Balancer`, or `Health Checks`
- conceptual prerequisite questions such as required inputs before quoting a service now stay in discovery mode even when the controller returns `quote_request`
- active-quote conceptual follow-ups now answer in natural language instead of mutating the persisted quote source for covered composition questions such as:
  - required quote `SKU` / component questions
  - compute composition checks such as `Only OCPU, no disk, no memory?`
- discovery and explanation questions with enough structured inputs to be quotable now stay in `product_discovery` instead of being force-promoted to deterministic quote mode by registry `topService` matching
- pricing-dimension discovery guardrails now also explicitly cover `OCI Monitoring Retrieval` prompts that include datapoint volumes, so structured discovery answers stay in `product_discovery` even when the route model over-predicts a deterministic quote path
- short active-quote discovery questions now skip the early session-quote prompt merge, so billing and component questions do not become accidentally quotable before intent guardrails run
- `normalizer.js` now also de-prioritizes explicit `quote_request` routes when the prompt text is clearly discovery/explanation-oriented, including pricing-dimension prompts that contain measurable inputs
- natural Spanish prerequisite and quote-preparation phrasings such as `Que me pides para cotizar ...?`, `Antes de cotizar ... que informacion necesito?`, and `Como preparo una quote de ...?` now also normalize into `product_discovery` instead of drifting into generic answer or quote mode
- hybrid quote-lead prompts such as `Ayudame a cotizar ... que datos faltan?` or `Quote ... but tell me first what inputs you need` now also normalize into `product_discovery` instead of being emitted as deterministic quotes
- active-quote conceptual pricing questions such as `Como se cobra esto?` and generic SKU requirement questions now also stay in discovery/answer mode instead of forcing `quote_followup` mutation paths
- colloquial Spanish extraction now also recognizes low-risk wording variants such as `memoria`, `almacenamiento`, `usuarios`, and `instancias de WAF`, so those inputs survive normalization instead of being lost before deterministic quoting

Validation status as of April 13, 2026:

- targeted suites for workbook, parity, assistant follow-ups, metadata, and session follow-up helpers are green
- quote export endpoint tests are green in sandbox through the socketless export-response harness
- current assistant follow-up regression suite result: `152 pass / 0 fail`
- current compute/composite follow-up regression suite result: `155 pass / 0 fail`
- platform follow-up regression suite result: `35 pass / 0 fail`
- routing/discovery regression suite result: `53 pass / 0 fail`
- service-families metadata suite result: `15 pass / 0 fail`
- session follow-up helper suite result: `9 pass / 0 fail`
- assistant session/context helper suite result: `6 pass / 0 fail`
- composite quote segmentation helper suite result: `5 pass / 0 fail`
- composite quote builder helper suite result: `5 pass / 0 fail`
- assistant quote rendering helper suite result: `3 pass / 0 fail`
- assistant quote narrative helper suite result: `5 pass / 0 fail`
- assistant quote enrichment helper suite result: `3 pass / 0 fail`
- workbook-focused suite result: `40 pass / 0 fail`
- current parity suite result: `157 pass / 0 fail`
- quote export endpoint suite result: `3 pass / 0 fail`
- current full-suite result in sandbox: `835 pass / 0 fail`

Live assistant validation baseline as of April 10, 2026:

- fixed live quality regression command is now available:
  - `npm run quality:assistant:fixed`
- fixed report path:
  - `/tmp/pricing-assistant-quality-20260410-final.json`
- current live quality baseline:
  - `100 / 100 pass`
  - `averageScore = 0.9865`
  - `failures = 0`
  - `throttledRetries = 0`
- this baseline complements parity and follow-up regressions by validating semantic discovery quality for major OCI services instead of only deterministic arithmetic or route safety

## Execution Principles

When choosing work, prefer this order:

1. expand tests around the desired behavior
2. move behavior into metadata, registries, or context packs
3. reduce narrow prompt-specific handling in `assistant.js`
4. add operational hardening once the behavior is stable

Avoid treating one-off prompt fixes as progress unless they improve:

- parity
- deterministic runtime behavior
- declarative metadata
- follow-up behavior that is reusable across families

## Workstreams

### 1. OCI Calculator Parity Expansion

Status: highest priority

Goal:

- widen confidence in deterministic quoting through more golden scenarios

Primary files:

- [calculator-parity.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/calculator-parity.test.js)
- [focused assistant regression suites](/Users/javierchan/Documents/GitHub/oci/pricing/server/test)
- [excel.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/excel.test.js)

Immediate task list:

- add more multi-service bundled parity cases
- add more database combinations:
  - Base Database + storage variants
  - Autonomous variants + attached storage assumptions
  - Exadata combinations beyond the current baseline
- add more analytics and integration combinations:
  - OIC + OAC
  - analytics + storage
  - analytics + integration + networking bundles
- add more mixed networking and security bundles:
  - load balancer + WAF + DNS + health checks
  - firewall + observability combinations
- add more workbook and RVTools parity-style golden cases

Recently completed in this workstream:

- added a mixed observability parity bundle that combines:
  - `Monitoring Ingestion`
  - `Monitoring Retrieval`
  - `Notifications HTTPS Delivery`
  - `Log Analytics archival storage`
- added a larger enterprise operations/security parity bundle that combines:
  - monitoring ingestion + retrieval
  - log analytics active + archival storage
  - notifications HTTPS delivery
  - DNS
  - health checks
  - network firewall
- added a larger global customer platform parity bundle that combines:
  - mixed `E4.Flex` + `E5.Flex` compute
  - block, file, and object storage
  - load balancer, WAF, firewall, DNS, health checks, and FastConnect
  - Oracle Integration Cloud + Oracle Analytics Cloud
  - Base Database Service
  - log analytics active + archival storage
- added enterprise database bundles that combine Base Database, Database Cloud Service, and Exadata Cloud@Customer with Data Safe, monitoring, health checks, notifications, and log analytics
- widened deterministic parity around observability-heavy database scenarios without changing the broader execution sequence
- added autonomous database bundles that combine Autonomous AI Lakehouse and Autonomous AI Transaction Processing with Data Integration, firewall, load balancer, DNS, monitoring, notifications, and health checks
- added a new analytics/integration workspace parity bundle that combines:
  - Oracle Integration Cloud Standard
  - Oracle Analytics Cloud Professional
  - OCI Data Integration workspace usage
  - FastConnect
  - Log Analytics archival storage
- added a new Base Database parity bundle that combines:
  - Base Database Service
  - Oracle Integration Cloud Standard
  - Oracle Analytics Cloud Professional
  - Data Safe for on-premises and compute databases
  - Monitoring ingestion
- added a new autonomous storage parity bundle that combines:
  - Autonomous AI Lakehouse License Included
  - autonomous database storage
  - Object Storage
  - Log Analytics archival storage
  - Notifications HTTPS delivery
- added a new serverless edge/security parity bundle that combines:
  - Flexible Load Balancer
  - Web Application Firewall
  - API Gateway
  - DNS
  - Health Checks
  - Notifications HTTPS delivery
- added a new Base Database BYOL transport-platform parity bundle that combines:
  - Base Database Service BYOL
  - Oracle Integration Cloud Standard BYOL
  - Oracle Analytics Cloud Professional BYOL OCPU
  - FastConnect
- added a new Database Cloud Service BYOL OCPU parity bundle that combines:
  - Database Cloud Service BYOL
  - Oracle Integration Cloud Enterprise BYOL
  - Oracle Analytics Cloud Professional BYOL OCPU
  - Object Storage
- added a new Exadata Dedicated transport-and-file-storage platform bundle that combines:
  - Exadata Dedicated Infrastructure
  - Oracle Integration Cloud Standard License Included
  - Oracle Analytics Cloud Enterprise
  - File Storage
  - FastConnect
- added workbook and RVTools regressions that compose workbook-derived compute workloads with shared `FastConnect + Monitoring Retrieval` services
- added workbook-origin and RVTools-origin follow-up regressions that preserve shared `FastConnect + Monitoring Retrieval` services when mixed quotes are mutated through shape, VPU, and capacity-reservation changes
- added workbook-origin and RVTools-origin follow-up regressions that preserve shared `Load Balancer + DNS` services when mixed quotes are mutated through shape, VPU, and capacity-reservation changes
- added RVTools aggregate workbook coverage for shared `FastConnect + Monitoring Retrieval` so multi-VM transport-plus-observability totals now stay protected alongside the existing edge and health-check bundles
- added guided inventory aggregate workbook coverage for shared `Load Balancer + Health Checks` so AMD guided workloads now also keep that edge-plus-probing combination stable under the same shared-service total model
- fixed composite follow-up metadata so workbook-origin and RVTools-origin mixed quotes can remove shared `FastConnect` and `Monitoring Retrieval` services safely, then locked that behavior with regressions
- extended composite follow-up metadata so workbook-origin and RVTools-origin mixed quotes can also replace shared `FastConnect`, `Monitoring Retrieval`, `DNS`, and `Health Checks` services safely, then locked that behavior with regressions
- fixed composite follow-up replacement routing so parameter-only mutations in mixed workbook/RVTools quotes target the intended shared family instead of falling back to append behavior, then locked that behavior with regressions for `FastConnect bandwidth`, `DNS query volume`, and `Health Checks endpoint count`
- revalidated parity coverage at `146 pass / 0 fail` and the full server suite at `678 pass / 0 fail` after landing the new BYOL and Exadata platform bundles
- revalidated workbook-focused coverage at `35 pass / 0 fail` and the full server suite at `680 pass / 0 fail` after landing the new aggregate workbook shared-service cases
- added workbook-origin and RVTools-origin mixed follow-up regressions for the shared `Load Balancer + Health Checks` bundle so persisted quotes now explicitly protect:
  - `Load Balancer` removal without dropping compute, block storage, or `Health Checks`
  - `Health Checks` removal without dropping compute, block storage, or `Load Balancer`
  - `Health Checks -> DNS` replacement while preserving the neighboring `Load Balancer`
- revalidated the focused mixed-compute assistant follow-up suite at `90 pass / 0 fail` and the full server suite at `686 pass / 0 fail` after landing the new `Load Balancer + Health Checks` persisted-bundle regressions
- added workbook-origin and RVTools-origin mixed follow-up regressions for the shared `Load Balancer + DNS` bundle so persisted quotes now explicitly protect:
  - `DNS -> Health Checks` replacement from workbook-origin quotes while preserving the neighboring `Load Balancer`
  - `DNS` removal from workbook-origin quotes without dropping compute, block storage, or `Load Balancer`
  - `Load Balancer` removal from RVTools-origin quotes without dropping compute, block storage, or `DNS`
- revalidated the focused mixed-compute assistant follow-up suite at `93 pass / 0 fail` and the full server suite at `689 pass / 0 fail` after landing the new `Load Balancer + DNS` persisted-bundle regressions
- added symmetric workbook-origin and RVTools-origin mixed follow-up regressions for the shared `FastConnect + Monitoring Retrieval` bundle so persisted quotes now explicitly protect:
  - `Monitoring Retrieval` removal from workbook-origin quotes without dropping compute, block storage, or `FastConnect`
  - `FastConnect -> DNS` replacement from RVTools-origin quotes while preserving the neighboring `Monitoring Retrieval`
  - `Monitoring Retrieval -> Health Checks` replacement from workbook-origin quotes while preserving the neighboring `FastConnect`
- revalidated the focused mixed-compute assistant follow-up suite at `96 pass / 0 fail` and the full server suite at `692 pass / 0 fail` after landing the new `FastConnect + Monitoring Retrieval` persisted-bundle regressions
- added workbook-origin and RVTools-origin mixed follow-up regressions for the shared `Load Balancer + Monitoring Retrieval` bundle so persisted quotes now explicitly protect:
  - workbook-origin shape plus `VPU` changes without dropping the neighboring `Load Balancer` and `Monitoring Retrieval`
  - RVTools-origin shape plus `capacity reservation` changes without dropping the neighboring `Load Balancer` and `Monitoring Retrieval`
  - workbook-origin `Load Balancer` bandwidth changes without dropping the neighboring `Monitoring Retrieval`
- revalidated the focused mixed-compute assistant follow-up suite at `99 pass / 0 fail` and the full server suite at `695 pass / 0 fail` after landing the new `Load Balancer + Monitoring Retrieval` persisted-bundle regressions
- parallel lane work added workbook-origin and RVTools-origin mixed follow-up regressions for the shared `FastConnect + Health Checks` bundle so persisted quotes now explicitly protect:
  - `Health Checks` endpoint mutations from RVTools-origin quotes while preserving neighboring `FastConnect`
  - `Health Checks` removal from workbook-origin quotes without dropping compute, block storage, or `FastConnect`
  - `Health Checks -> DNS` replacement from RVTools-origin quotes while preserving neighboring `FastConnect`
- parallel lane work also added RVTools aggregate workbook coverage for the shared `Load Balancer + Health Checks` bundle so the migration aggregate path now matches the existing guided-inventory aggregate coverage for that same edge-plus-probing combination
- revalidated the focused mixed-compute assistant follow-up suite at `102 pass / 0 fail`, the workbook-focused suite at `36 pass / 0 fail`, and the full server suite at `699 pass / 0 fail` after integrating the parallel lanes
- a subsequent parallel lane round added workbook-origin and RVTools-origin mixed follow-up regressions for the shared `Load Balancer + Monitoring Retrieval` bundle so persisted quotes now explicitly protect:
  - `Monitoring Retrieval` removal from workbook-origin quotes while preserving neighboring `Load Balancer`
  - `Load Balancer` removal from RVTools-origin quotes while preserving neighboring `Monitoring Retrieval`
  - `Monitoring Retrieval -> Health Checks` replacement from workbook-origin quotes while preserving neighboring `Load Balancer`
- that same parallel round also added RVTools aggregate workbook coverage for the shared `FastConnect + DNS` bundle and new deterministic parity for:
  - `Database Cloud Service BYOL + OIC Standard BYOL + OAC Professional + Monitoring Retrieval + Health Checks`
  - `Base Database Service BYOL + FastConnect + Network Firewall + DNS + Monitoring Ingestion`
- revalidated the focused mixed-compute assistant follow-up suite at `105 pass / 0 fail`, the workbook-focused suite at `37 pass / 0 fail`, the parity suite at `148 pass / 0 fail`, and the full server suite at `705 pass / 0 fail` after integrating the second parallel lane round
- a later parallel lane round added workbook-origin and RVTools-origin mixed follow-up regressions for the shared `FastConnect + DNS` bundle so persisted quotes now explicitly protect:
  - `DNS` removal from workbook-origin quotes while preserving neighboring `FastConnect`
  - `FastConnect` removal from RVTools-origin quotes while preserving neighboring `DNS`
  - `DNS -> Health Checks` replacement from workbook-origin quotes while preserving neighboring `FastConnect`
- that same round also added RVTools aggregate workbook coverage for the shared `Monitoring Retrieval + Health Checks` observability-edge bundle and new deterministic parity for:
  - `Database Cloud Service BYOL + OIC Enterprise BYOL + OAC Professional BYOL + Network Firewall + Monitoring Retrieval`
  - `Base Database Service Enterprise License Included + File Storage + Object Storage + Monitoring Ingestion`
- revalidated the focused mixed-compute assistant follow-up suite at `108 pass / 0 fail`, the workbook-focused suite at `38 pass / 0 fail`, the parity suite at `150 pass / 0 fail`, and the full server suite at `711 pass / 0 fail` after integrating the latest parallel lane round
- a subsequent consolidation slice added workbook aggregate coverage for the shared `FastConnect + Load Balancer` bundle and refreshed the shared observability-edge workbook path for `Monitoring Retrieval + Health Checks`
- the next workbook symmetry slice added the guided-inventory mirror for the shared `FastConnect + Load Balancer` aggregate bundle, so both RVTools and inventory workbook paths now protect that shared edge combination
- the next follow-up symmetry slice added the `RVTools` mirror for `Load Balancer + Health Checks -> DNS`, so that shared edge replacement now works in both source directions instead of only the workbook-origin path
- the next declarative slice added active-quote replacement metadata for `OCI Monitoring`, so `Monitoring Ingestion <-> Monitoring Retrieval` plus datapoint mutations now flow through family-owned rules instead of ad hoc handling
- that same slice added direct runtime regressions for active `OCI Monitoring` quote flips in both directions and extended the follow-up capability artifact coverage so the generated registry stays aligned with the new metadata
- the next parity slice added two smaller observability-edge regression cases so deterministic totals are now pinned for:
  - `Monitoring Ingestion + Health Checks`
  - `Monitoring Retrieval + Health Checks`
- that same slice expanded deterministic parity for:
  - `Database Cloud Service BYOL + OIC Standard BYOL + OAC Professional + Monitoring Retrieval + Monitoring Ingestion`
  - `Base Database Service BYOL + File Storage + Archive Storage + Infrequent Access retrieval + Monitoring Ingestion`
- a follow-up metadata slice moved `OCI Data Safe` and `OCI Log Analytics` composite replacement ownership into declarative family metadata and locked that capability through both unit tests and the emitted follow-up capability matrix artifact
- the next mixed-follow-up symmetry slice extended the same `Monitoring Retrieval -> Monitoring Ingestion` protection to persisted `Flexible Load Balancer + Monitoring Retrieval` bundles across both workbook-origin and RVTools-origin quotes, proving the monitoring replacement fix is not limited to `FastConnect` composites
- the next observability symmetry slice extended that same `Monitoring Retrieval -> Monitoring Ingestion` protection to persisted `Monitoring Retrieval + Health Checks` bundles across both workbook-origin and RVTools-origin quotes, proving the monitoring replacement fix now holds across the three hardened observability/edge neighbor patterns
- the next observability-removal slice closed the remaining mixed `Monitoring Retrieval + Health Checks` removal symmetry by proving workbook-origin `Monitoring Retrieval` removal and RVTools-origin `Health Checks` removal both preserve the neighboring service and the surrounding compute/storage quote context
- the next observability-parameter slice closed the remaining parameter-only symmetry for mixed `Monitoring Retrieval + Health Checks` bundles by proving both workbook-origin and RVTools-origin datapoint changes mutate only the monitoring segment while preserving neighboring `Health Checks` plus the surrounding compute/storage quote context
- the next load-balancer observability slice closed the same parameter-only symmetry for mixed `Flexible Load Balancer + Monitoring Retrieval` bundles by proving both workbook-origin and RVTools-origin datapoint changes mutate only the monitoring segment while preserving the neighboring load balancer plus the surrounding compute/storage quote context
- the next fastconnect-observability symmetry slice closed the remaining parameter-only and bandwidth-mirror gaps for mixed `FastConnect + Monitoring Retrieval` bundles by proving workbook-origin and RVTools-origin datapoint changes mutate only the monitoring segment while preserving neighboring `FastConnect`, and by proving the RVTools-origin bandwidth-only follow-up mutates only the `FastConnect` segment while preserving monitoring plus the surrounding compute/storage quote context
- the next fastconnect-health-checks symmetry slice closed the remaining workbook/RVTools mirror gaps for mixed `FastConnect + Health Checks` bundles by proving both source types now preserve neighboring `FastConnect` when `Health Checks` endpoint counts change, when `Health Checks` is removed, and when `Health Checks` is replaced by `DNS`
- the next observability-dns slice added the missing RVTools mirror for `Health Checks -> DNS` inside mixed `Monitoring Retrieval` bundles and added a workbook-origin parameter-only regression proving `DNS` query-volume changes preserve neighboring `Monitoring Retrieval` plus the surrounding compute/storage quote context
- the next observability-dns symmetry slice closed the remaining RVTools parameter mirror for shared `Monitoring Retrieval + DNS` bundles and added a workbook-origin removal regression, proving both source types now preserve neighboring `Monitoring Retrieval` when `DNS` query volume changes and proving workbook-origin `DNS` removal preserves the surrounding compute/storage quote context
- the next observability-dns removal slice closed the remaining RVTools removal mirror for shared `Monitoring Retrieval + DNS` bundles, so both workbook-origin and RVTools-origin quotes now preserve neighboring `Monitoring Retrieval` when `DNS` is removed from the persisted quote source
- the next observability-dns datapoint slice closed the remaining monitoring-parameter mirror for shared `Monitoring Retrieval + DNS` bundles, proving both workbook-origin and RVTools-origin quotes now preserve neighboring `DNS` when `Monitoring Retrieval` datapoint changes are applied to the persisted quote source
- the next fastconnect-dns parameter slice closed the remaining DNS-volume mirror for shared `FastConnect + DNS` bundles, proving both workbook-origin and RVTools-origin quotes now preserve neighboring `FastConnect` when `DNS` query-volume changes are applied to the persisted quote source
- the next fastconnect-observability-dns parameter slice closed the remaining DNS-volume mirror for shared `FastConnect + Monitoring Retrieval + DNS` bundles, proving both workbook-origin and RVTools-origin quotes now preserve neighboring `FastConnect` and `Monitoring Retrieval` when `DNS` query-volume changes are applied to the persisted quote source
- the next fastconnect-health-checks-dns symmetry slice closed the remaining source mirror for shared `FastConnect + Health Checks + DNS` bundles, proving both workbook-origin and RVTools-origin `DNS` query-volume changes preserve neighboring `FastConnect` and `Health Checks` plus the surrounding compute/storage quote context
- the next fastconnect-health-checks-dns removal symmetry slice closed the remaining source mirror for removing `DNS` from shared `FastConnect + Health Checks + DNS` bundles, proving both workbook-origin and RVTools-origin quotes preserve neighboring `FastConnect`, neighboring `Health Checks`, and the surrounding compute/storage quote context
- the next load-balancer-dns parameter symmetry slice closed the remaining source mirror for shared `Load Balancer + DNS` bundles, proving both workbook-origin and RVTools-origin quotes now preserve neighboring `Flexible Load Balancer` when `DNS` query-volume changes are applied to the persisted quote source
- the next load-balancer-observability parameter symmetry slice closed the remaining source mirror for shared `Load Balancer + Monitoring Retrieval` bundles, proving both workbook-origin and RVTools-origin quotes now preserve neighboring `Monitoring Retrieval` when `Load Balancer` bandwidth changes are applied to the persisted quote source
- the next load-balancer-health-checks removal symmetry slice closed the remaining source mirror for removing `Load Balancer` from shared `Load Balancer + Health Checks` bundles, proving both workbook-origin and RVTools-origin quotes now preserve neighboring `Health Checks` plus the surrounding compute/storage quote context
- the next load-balancer-health-checks removal symmetry slice also closed the remaining source mirror for removing `Health Checks` from shared `Load Balancer + Health Checks` bundles, proving both workbook-origin and RVTools-origin quotes now preserve neighboring `Flexible Load Balancer` plus the surrounding compute/storage quote context
- the next load-balancer-dns removal symmetry slice closed the remaining source mirror for removing `DNS` from shared `Load Balancer + DNS` bundles, proving both workbook-origin and RVTools-origin quotes now preserve neighboring `Flexible Load Balancer` plus the surrounding compute/storage quote context
- the next load-balancer-dns removal symmetry slice also closed the remaining source mirror for removing `Load Balancer` from shared `Load Balancer + DNS` bundles, proving both workbook-origin and RVTools-origin quotes now preserve neighboring `DNS` plus the surrounding compute/storage quote context
- the next load-balancer-health-checks parameter symmetry slice closed the remaining source mirror for `Load Balancer` bandwidth changes inside shared `Load Balancer + Health Checks` bundles, proving both workbook-origin and RVTools-origin quotes now preserve neighboring `Health Checks` plus the surrounding compute/storage quote context
- the next OIC Standard license symmetry slice closed the reverse `BYOL -> License Included` path for persisted `Oracle Integration Cloud Standard` quotes, so license-mode follow-ups now round-trip cleanly in both directions for that family
- the next monitoring discovery guardrail slice closed an explicit route-safety gap for `OCI Monitoring Retrieval` pricing-dimension prompts with datapoint volumes, proving those requests stay in `product_discovery` instead of drifting into deterministic quote mode
- revalidated the focused mixed-compute assistant follow-up suite at `151 pass / 0 fail`, the platform follow-up regression suite at `35 pass / 0 fail`, the routing/discovery regression suite at `50 pass / 0 fail`, the service-families metadata suite at `15 pass / 0 fail`, the session follow-up helper suite at `9 pass / 0 fail`, the workbook-focused suite at `40 pass / 0 fail`, the parity suite at `154 pass / 0 fail`, and the full server suite at `765 pass / 0 fail` after integrating the latest regression and metadata slices
- the next load-balancer observability removal symmetry slice closed the remaining source mirror for removing `Monitoring Retrieval` from shared `Load Balancer + Monitoring Retrieval` bundles, proving both workbook-origin and RVTools-origin quotes preserve neighboring `Flexible Load Balancer` plus the surrounding compute/storage quote context
- the next parity hardening slice added deterministic coverage for a `Network Firewall + WAF + Load Balancer + DNS + Health Checks` composite edge/security bundle, expanding mixed networking/security proof without adding runtime risk
- revalidated the focused mixed-compute assistant follow-up suite at `152 pass / 0 fail`, the parity suite at `155 pass / 0 fail`, and the full server suite at `767 pass / 0 fail` after integrating the latest symmetry and parity slices
- the next input-interpretation slice hardened discovery routing for natural Spanish prerequisite and quote-preparation prompts, proving phrases such as `Que me pides para cotizar ...?`, `Antes de cotizar ... que informacion necesito?`, and `Como preparo una quote de ...?` stay in `product_discovery` instead of drifting into generic answer or deterministic quote paths
- revalidated the focused interpretation lanes at `82 pass / 0 fail`, the routing/discovery regression suite at `51 pass / 0 fail`, and the full server suite at `771 pass / 0 fail` after integrating the latest input-interpretation guardrails
- the next hybrid-intent slice hardened discovery routing for quote-lead prompts that actually ask for missing inputs first, proving phrases such as `Ayudame a cotizar OIC Standard, que datos faltan?` and `Quote OCI DNS, but tell me first what inputs you need` stay in `product_discovery` instead of being mis-routed into deterministic quote paths
- that same slice also hardened active-quote conceptual guards so pricing-explanation and generic SKU requirement questions stay in answer/discovery mode instead of forcing `quote_followup` mutation on the persisted quote source
- revalidated the focused interpretation lanes at `99 pass / 0 fail`, the routing/discovery regression suite at `53 pass / 0 fail`, and the full server suite at `777 pass / 0 fail` after integrating the latest hybrid-intent and active-quote guardrails
- the next extraction slice hardened low-risk colloquial Spanish input parsing for `memoria`, `almacenamiento`, `usuarios`, and `instancias de WAF`, so those values now survive normalization into structured inputs instead of being lost before deterministic quote shaping
- revalidated the extraction lane at `28 pass / 0 fail` and the full server suite at `781 pass / 0 fail` after integrating the latest colloquial-input normalization guards
- the next compact-input extraction slice hardened low-risk normalization for abbreviated and magnitude-compressed usage wording, so prompts such as `250k reqs`, `10k queries`, and `2.5m GB de trafico` now survive into structured inputs instead of being dropped during normalization
- that same slice also locked the already-working Spanish `ancho de banda` phrasing behind explicit regression coverage, so `Load Balancer con ancho de banda de 300 Mbps` remains protected as the parser evolves
- revalidated the extraction lane at `32 pass / 0 fail`, the routing/discovery regression suite at `53 pass / 0 fail`, and the full server suite at `785 pass / 0 fail` after integrating the latest compact-input normalization guards
- the next spanish-quantity extraction slice hardened a few still-anglophone quantity paths, so prompts such as `8 recursos administrados`, `3 espacios de trabajo`, and `4 nodos` now survive normalization into the existing structured quantity fields instead of being lost before quote shaping
- that same slice also extended compact-number support to those quantity-oriented fields, keeping the parser consistent as the project adds more colloquial usage phrasing
- revalidated the extraction lane at `35 pass / 0 fail`, the routing/discovery regression suite at `53 pass / 0 fail`, and the full server suite at `788 pass / 0 fail` after integrating the latest spanish-quantity normalization guards
- the next spanish-transactional extraction slice hardened request-volume parsing for `consultas`, `solicitudes`, and `peticiones`, so Spanish transactional prompts now survive normalization into `requestCount` instead of being dropped unless the user phrased them in English
- that same slice kept the change deliberately narrow to first-turn extraction only, preserving the existing routing/discovery guardrails while improving quote-readiness for DNS, API Gateway, WAF, and similar transactional families
- revalidated the extraction lane at `38 pass / 0 fail`, the routing/discovery regression suite at `53 pass / 0 fail`, and the full server suite at `791 pass / 0 fail` after integrating the latest spanish-transactional normalization guards
- the next spanish transactional follow-up slice extended active-quote mutation support for DNS, API Gateway, and WAF so short follow-ups such as `7m consultas por mes`, `2m solicitudes por mes`, and `1.5m peticiones por mes` now reuse the active quote instead of falling back to a fresh quote path
- that same slice kept the runtime canonical internally by converting those Spanish follow-up volumes back into family-native prompt text before deterministic quoting, which preserved quote stability while widening natural-language input support
- revalidated the focused assistant follow-up suite at `155 pass / 0 fail`, the routing/discovery regression suite at `53 pass / 0 fail`, and the full server suite at `794 pass / 0 fail` after integrating the latest spanish transactional follow-up guards
- the next parity slice expanded mixed `database + analytics + integration` proof with a shared workspace-and-storage bundle for `Base Database Service + Oracle Integration Cloud + Oracle Analytics Cloud + OCI Data Integration + File Storage`
- that same parity slice also expanded mixed BYOL platform proof with `Database Cloud Service + Oracle Integration Cloud + Oracle Analytics Cloud + OCI Data Integration processed throughput + Object Storage`, so both workspace-based and throughput-based integration paths are now pinned in deterministic totals
- revalidated the parity suite at `157 pass / 0 fail`, the service-families metadata suite at `15 pass / 0 fail`, and the full server suite at `796 pass / 0 fail` after integrating the latest mixed platform parity additions
- the next boundary-hardening slice completed the first low-risk extractions from `assistant.js`, moving registry-query shaping into `request-query-helpers.js` and assumption formatting into `quote-assumptions.js` without changing runtime behavior
- that same slice added direct unit coverage for the extracted helpers and kept the affected routing and post-clarification flows green, confirming the extraction reduced assistant-owned surface area without altering quote behavior
- revalidated the new helper suites, the affected routing suites, and the full server suite at `802 pass / 0 fail` after integrating the latest boundary-hardening extraction slice
- the next boundary-hardening slice continued the same low-risk extraction track by moving `buildServiceUnavailableMessage()` into `assistant-response-helpers.js`, keeping the fallback message reusable while removing another small policy-free helper from `assistant.js`
- that same slice added direct unit coverage for the extracted fallback helper and revalidated the intent and discovery consumers, confirming the extraction kept assistant behavior stable while shrinking inline helper surface area
- revalidated the new fallback-helper suite, the affected intent/discovery suites, and the full server suite at `804 pass / 0 fail` after integrating the latest boundary-hardening extraction slice
- the next boundary-hardening slice extracted the flex-comparison helper cluster into `flex-comparison-helpers.js`, removing the parsing and comparison-context support logic from `assistant.js` while keeping early-routing and post-intent behavior stable
- that same slice added focused helper coverage and revalidated the affected routing, follow-up, flex-comparison-flow, intent, and full backend suites to confirm no regression in comparison handling
- the next boundary-hardening slice extracted session/context shaping into `assistant-session-context.js`, moving quote summarization, export-payload shaping, and session-summary assembly out of `assistant.js` without changing server-authoritative session behavior
- that same slice added direct unit coverage for session/context shaping and revalidated routing/discovery, composite follow-up, quote export, and the full backend suite at `814 pass / 0 fail`
- the next boundary-hardening slice extracted composite detection and segmentation into `composite-quote-segmentation.js`, moving the parsing support for mixed-service bundles out of `assistant.js` while leaving deterministic composite assembly in place for a later bounded cut
- that same slice added focused unit coverage for composite segmentation and revalidated bundle regressions, routing/discovery, quote export, and the full backend suite at `819 pass / 0 fail`
- the next boundary-hardening slice extracted composite deterministic quote assembly into `composite-quote-builder.js`, moving bundle composition, canonical fallback preference, and quote-selection logic out of `assistant.js` while preserving the same deterministic collaborators
- that same slice added focused unit coverage for composite quote assembly and revalidated direct fast paths, bundle regressions, quote-entry preparation, and the full backend suite at `824 pass / 0 fail`
- the next boundary-hardening slice extracted the assistant-side deterministic quote rendering helpers into `assistant-quote-rendering.js`, moving markdown rendering and numeric display formatting out of `assistant.js` while keeping the assistant-specific formatting contract unchanged
- that same slice added focused helper coverage and revalidated post-clarification routing, direct fast paths, bundle regressions, and the full backend suite at `827 pass / 0 fail`
- the next boundary-hardening slice extracted deterministic narrative/profile shaping into `assistant-quote-narrative.js`, moving profile inference, deterministic expert-summary construction, considerations fallback logic, consumption-group explanation, and shared currency formatting out of `assistant.js` while keeping quote narrative assembly and GenAI enrichment orchestration centralized
- that same slice added focused narrative-helper coverage and revalidated deterministic summary behavior, direct fast paths, post-clarification routing, bundle regressions, and the full backend suite at `832 pass / 0 fail`
- the next boundary-hardening slice extracted quote-enrichment support into `assistant-quote-enrichment.js`, moving enrichment-context shaping, migration-note gating, and sanitization utilities out of `assistant.js` while keeping the `runChat()` call and final quote-narrative orchestration centralized
- that same slice added focused enrichment-helper coverage and revalidated sanitization behavior, direct fast paths, post-clarification routing, bundle regressions, and the full backend suite at `835 pass / 0 fail`

Suggested first gaps to cover:

- bundled database + analytics + integration scenarios
- bundled integration + analytics + storage scenarios
- workbook-derived bundles that include compute plus storage plus follow-up modifiers
- larger mixed edge architectures with both security and observability lines

Exit criteria:

- new parity cases exist for each pending bundle category from the roadmap
- new cases cover both isolated family pricing and mixed-architecture pricing
- no new family support is merged without a parity or regression case

### 2. Declarative Coverage Refactor

Status: second priority

Goal:

- move product behavior out of `assistant.js` and into reusable metadata-driven layers

Primary files:

- [assistant.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/assistant.js)
- [service-families.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/service-families.js)
- [context-packs.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/context-packs.js)
- [normalizer.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/normalizer.js)

Immediate task list:

- inventory manual branches in `assistant.js` that are really family policy
- continue moving clarification requirements into `service-families.js`
- move pricing dimension explanations into `context-packs.js`
- move reusable canonical request shaping into `service-families.js`
- continue formalizing `quotePlan` as the contract between intent and pricing
- continue extracting comparison-specific clarification and response shaping out of `assistant.js`

Recently completed in this workstream:

- extracted the first declarative follow-up rule layer from `assistant.js`
- kept behavior stable through regression coverage before and after the refactor
- extracted a second declarative layer for active-quote follow-up quantity replacements so covered families can own their own replacement patterns in `service-families.js`
- reduced dependence on the generic replacement fallback by skipping it when a covered family already resolved the follow-up through metadata
- completed the current active-quote replacement hardening wave so the covered quantity and sizing follow-ups now resolve through family metadata instead of shared assistant rules
- hardened active-quote family detection for workbook and RVTools quotes with explicit Flex shapes so shape-plus-sizing follow-ups route to `compute_flex`
- moved the current non-follow-up extracted-input aliasing for `security_waf` and `security_data_safe` out of `assistant.js` into declarative family metadata in `service-families.js`
- added focused unit coverage for family input normalization so future family migrations can land without expanding assistant branching
- moved the structured discovery fallback builder out of `assistant.js` and into `context-packs.js`, so SKU-composition and billing-guidance fallbacks now live beside the rest of the service context assembly
- extracted discovery and billing-question classification into a dedicated declarative module so `assistant.js` no longer owns those regex rules inline
- extracted lightweight heuristic intent construction and discovery override behavior into a dedicated module so `assistant.js` no longer decides those fallback routes inline
- extracted reconciliation between analyzed intent and heuristic fallback into a dedicated helper so `assistant.js` no longer merges those decision paths inline
- extracted quote-followup route forcing and modify-quote override behavior into a dedicated helper so `assistant.js` no longer mutates those follow-up intent fields inline
- extracted contextual follow-up post-processing and post-intent Flex-comparison preparation into a dedicated helper so `assistant.js` no longer mutates those request-shaping fields inline
- extracted Flex-comparison clarification and deterministic reply shaping into a dedicated helper so `assistant.js` no longer duplicates that comparison policy before and after intent analysis
- extracted greeting and FastConnect-specific early deterministic replies into a dedicated helper so `assistant.js` no longer owns those canned-response guards inline
- extracted generic compute-shape clarification detection into a dedicated helper so `assistant.js` no longer parses VM sizing clarification policy inline
- extracted license-choice detection and clarification decision logic into a dedicated helper so `assistant.js` no longer owns that BYOL-versus-License-Included policy inline
- extracted BYOL ambiguity detection and quote-line filtering into the same license helper so `assistant.js` no longer owns most of the license-selection policy
- extracted mixed-license ambiguity clarification payload building into the same helper so `assistant.js` no longer formats that BYOL confirmation branch inline
- extracted quote-unresolved payload shaping into a dedicated helper so `assistant.js` no longer owns both the family-specific and generic unresolved-quote response branches inline
- extracted the final answer-mode fallback payload shaping into a dedicated helper so `assistant.js` no longer owns the last generic guidance branch inline
- extracted post-reformulation quote clarification state handling into a dedicated helper so `assistant.js` no longer owns pre-quote clarification, missing-input gating, and clarification-flag cleanup inline
- extracted canonical family request shaping and preflight quote selection into a dedicated helper so `assistant.js` no longer merges parsed active-quote inputs, canonical rewrites, modifier preservation, and preflight quote preference inline
- added focused unit coverage for canonical request guardrails so family rewrites that would drop family-owned replacement signals fall back to the safer active-quote request instead of mutating the quote source incorrectly
- kept family input normalization reusable in the same helper path so family-owned aliases such as WAF instance counts remain normalized before canonical request reconstruction
- extracted quote entry preparation into a dedicated helper so `assistant.js` no longer owns route-driven follow-up request reuse, uncovered-compute discovery fallback gating, and deterministic top-service promotion inline
- added focused unit coverage for quote entry preparation, including `effectiveQuoteText` selection, unsupported compute fallback detection, and safe deterministic promotion of catalog-backed services
- validated the extraction with assistant regressions covering workbook-style route follow-ups, unsupported legacy VM aliases, and deterministic HPC service quoting
- documented a project-level sub-agent operating model in `docs/SUBAGENT_STRATEGY.md` so future parallel execution can accelerate helper extraction, test growth, and docs maintenance without diluting architectural ownership of the core assistant flow
- extracted the early deterministic direct-quote fast paths into a dedicated helper so `assistant.js` no longer owns the initial composite-quote and simple transactional quote branches inline before intent analysis
- added focused unit coverage for those fast paths, including composite success, transactional service-level success, and null fallthrough when the request must continue into the intent pipeline
- revalidated the extraction with assistant regressions for composite bundles and storage/network narratives plus calculator parity cases that depend on the same deterministic entry behavior
- extracted the remaining pre-intent early-exit orchestration into a dedicated helper so `assistant.js` no longer owns greeting replies, generic compute shape clarification payload shaping, early flex-comparison clarification, and direct flex comparison replies inline
- added focused unit coverage for that early-routing helper and revalidated it with the existing greeting, compute-shape, and flex-comparison suites plus assistant regressions for pre-intent discovery and composite quote behavior
- validated this slice using the new sub-agent strategy: a bounded explorer confirmed the extraction boundary and regression set while the primary agent kept integration, verification, and documentation ownership
- extracted the mid-flow discovery routing into a dedicated helper so `assistant.js` no longer owns registry-query construction, catalog listing replies, structured discovery fallback routing, and general-answer discovery payload shaping inline
- added focused unit coverage for discovery routing, including deterministic `topService` selection, catalog-response fast paths, structured discovery replies, and null fallthrough into quote flow
- revalidated the extraction with discovery classifier, context-pack fallback coverage, and broad assistant discovery regressions covering catalog requests, billing questions, required-input questions, SKU composition prompts, and safe service-unavailable fallbacks
- consolidated the quote-entry transition into `quote-entry-preparation.js` so `assistant.js` no longer owns unsupported-compute discovery fallback payload shaping or deterministic `topService` promotion inline before quote request shaping
- expanded focused unit coverage for quote-entry preparation to include safe unsupported-compute discovery payloads and promoted deterministic service routing after discovery has already fallen through
- revalidated that consolidation with assistant regressions covering unsupported legacy VM aliases, billing prompts that must remain in discovery, deterministic HPC quoting, and Autonomous AI Lakehouse quote entry behavior
- extended the same helper into a quote-ready state contract so `assistant.js` no longer stitches together family resolution, quote-entry fallback handling, deterministic top-service promotion, and request shaping inline before clarification
- added focused unit coverage for quote-ready state preparation, including the guardrail that skips request shaping when unsupported compute must fall back to discovery and the happy path that returns `familyMeta`, `reformulatedRequest`, and `preflightQuote`
- revalidated that contract with assistant regressions covering deterministic HPC entry, license-choice entry paths, active FastConnect follow-ups, compute shape follow-ups, and quote narratives for FastConnect and Block Volume
- extracted the post-clarification response phase into a dedicated helper so `assistant.js` no longer owns license-choice prompting, final clarification payload shaping, deterministic quote execution, BYOL ambiguity handling, unresolved quote routing, and generic answer fallback inline
- added focused unit coverage for post-clarification routing across clarification-first behavior, license-choice prompts, successful quote execution, unresolved quote fallback, and generic answer fallback
- revalidated the extraction with assistant regressions covering OIC Standard and Autonomous AI Lakehouse license-choice paths, unresolved family-specific quote behavior, VM clarification guardrails, and deterministic quote narratives
- extracted the remaining intent-resolution bridge into a dedicated helper so `assistant.js` no longer owns GenAI intent analysis fallback, quote-followup route overrides, post-intent follow-up reconciliation, and post-intent flex comparison terminal replies inline
- added focused unit coverage for that bridge, including GenAI failure fallback, quote-followup override ordering, post-intent flex comparison terminal replies, and normal intent pass-through
- revalidated the extraction with intent/follow-up helper suites plus assistant regressions covering service-unavailable fallback, discovery guardrails, quote-followup reuse, and flex comparison reply behavior
- extracted active-quote clarification and license-follow-up heuristics into `clarification-followup.js` so short clarification answers, product-context recovery, license directive normalization, session quote reuse, and inline shape-selection rewrites no longer remain embedded in `assistant.js`
- added focused unit coverage for the new clarification-followup helper, including contextual clarification merges, prior-product recovery, license-mode directive extraction, and inline shape replacement guardrails
- revalidated that extraction with a green `11 pass / 0 fail` helper suite while keeping the full server suite green at `675 pass / 0 fail`
- extracted active-quote session mutation orchestration into `session-quote-followup.js` so composite service removal/replacement, license-mode rewrites, currency changes, modifier persistence, active family inference, and route-driven follow-up prompt reuse no longer remain embedded in `assistant.js`
- added focused unit coverage for the new session follow-up helper, including shape switching with preserved block storage, composite removals and sibling replacements, active-family inference for Flex quotes, route-driven follow-up reuse, critical modifier preservation, and short prefixed-answer normalization
- revalidated that session follow-up extraction with a green `19 pass / 0 fail` focused helper run and a green `675 pass / 0 fail` full server suite
- completed a full green pass of `pricing/server/test/*.test.js` after the refactor wave, confirming that the extracted orchestration helpers still compose correctly across regressions, parity, workbook flows, export paths, and helper suites

Refactor targets to prefer:

- family-specific clarification prompts
- family-specific follow-up transformations
- discovery responses based on family options and required inputs
- safe unsupported guidance based on registry/context data instead of custom branches

Exit criteria:

- reduced family-specific branching in `assistant.js`
- new family additions mostly require metadata + context pack changes
- `quotePlan` carries enough structured intent that fewer assistant heuristics are needed

Current status note:

- `assistant.js` is now primarily a coordinator over helper modules instead of the main owner of family policy and response formatting
- the next highest-value slices are coverage expansion, parity hardening, and deeper follow-up capability rollout, not helper extraction for its own sake

### 3. Follow-Up Coverage Expansion

Status: third priority

Goal:

- make quote follow-ups more complete and less ad hoc across families

Primary files:

- [assistant.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/assistant.js)
- [service-families.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/service-families.js)
- [focused assistant regression suites](/Users/javierchan/Documents/GitHub/oci/pricing/server/test)

Immediate task list:

- define a capability matrix for supported follow-up operations by family
- cover more licensing changes across database, integration, and analytics families
- support more add/remove component follow-ups for mixed bundles
- expand modifier updates beyond the current hardened compute set
- cover more family-specific quantity updates on active quotes that are not yet represented in metadata

Missing follow-up categories to close next:

- family-specific licensing flips that currently rely on narrow heuristics
- mixed bundle component replacement, not only component removal
- more currency and modifier changes on non-compute families
- conceptual follow-ups against an active quote that should answer instead of mutate

Recommended next implementation slice:

- encode family-level follow-up capabilities in metadata
- start with licensing-sensitive families:
  - Base Database
  - Oracle Integration Cloud
  - Oracle Analytics Cloud

Exit criteria:

- each supported family documents what follow-ups are allowed
- each supported follow-up type has regression coverage
- follow-up behavior is driven by metadata where possible

Latest completed slice:

- added deterministic regression coverage for active-quote license flips in `Base Database Service` and OAC OCPU families
- expanded the assistant fixture catalog so follow-up regressions now exercise real Base Database and OAC Enterprise OCPU SKUs instead of no-op gaps
- corrected `service-families.js` capability evaluation so `null` optional inputs are treated as missing, which keeps `OAC users` quotes non-licensable while restoring `OAC OCPU` license flips
- encoded metadata-driven quantity replacement for `Base Database Service` and OAC OCPU quotes so active follow-ups replace the existing sizing signal instead of appending duplicate quantities into the prompt
- added deterministic regressions for active Base Database OCPU/storage changes and OAC Professional/Enterprise OCPU changes
- extended the same metadata-driven pattern to `Database Cloud Service` and `Exadata Exascale`, including Exascale storage-model replacement between filesystem and smart database storage
- added deterministic regressions for active Database Cloud Service OCPU changes plus Exadata Exascale ECPU, storage-size, and storage-model changes
- extended the same active-quote hardening slice to edition-only and infrastructure-only follow-ups that were previously under-detected by the session follow-up gate
- added deterministic regressions for:
  - `Database Cloud Service` edition changes
  - `Exadata Dedicated Infrastructure` ECPU changes on X11M infrastructure
  - `Exadata Dedicated Infrastructure` X11M infrastructure swaps
  - `Exadata Cloud@Customer` ECPU changes on X10M infrastructure
  - `Exadata Cloud@Customer` X10M infrastructure swaps
- extended family metadata so `Base Database Service` edition follow-ups replace the active edition token instead of appending a second edition into the persisted prompt
- added deterministic regressions for:
  - `Base Database Service` edition changes while preserving license mode, compute sizing, and storage
  - `Base Database Service` compute-mode shifts from `OCPUs` to `ECPUs`
  - `Database Cloud Service` license flips for `Extreme Performance` so edition-sensitive BYOL routing stays deterministic
- added deterministic regressions for:
  - `Base Database Service` ECPU quotes switching from `License Included` to `BYOL`
  - `Base Database Service` ECPU edition swaps such as `Enterprise -> Standard`
  - `Database Cloud Service` `Enterprise -> Standard` edition swaps on `License Included`
  - `Database Cloud Service` `Extreme Performance -> Standard` edition swaps on `BYOL`
- extended composite follow-up metadata so persisted mixed bundles can now remove `OCI Data Safe`, `OCI Log Analytics`, `Oracle Integration Cloud Standard`, and `Oracle Analytics Cloud Professional` without dropping the rest of the quote
- added deterministic regressions for those four composite-removal paths across mixed database, observability, integration, and analytics bundles
- hardened the assistant follow-up orchestrator so an explicit composite removal short-circuits later family replacement passes, avoiding collateral edits such as `sin OIC Standard` mutating `Base Database Service Enterprise` into `Standard`
- extended the same composite follow-up metadata so persisted mixed bundles can now replace `Oracle Integration Cloud Standard -> Oracle Integration Cloud Enterprise` and `Oracle Analytics Cloud Professional -> Oracle Analytics Cloud Enterprise` safely inside the same quote
- added deterministic regressions for those sibling-service replacement paths across mixed platform bundles that also keep `Base Database Service` intact
- hardened the assistant follow-up orchestrator so explicit composite replacements also short-circuit later family replacement passes, avoiding collateral edits such as `cambia OIC Standard por OIC Enterprise ...` mutating `Base Database Service Enterprise` into `Standard`
- added the reverse deterministic regressions for `Oracle Integration Cloud Enterprise -> Oracle Integration Cloud Standard` and `Oracle Analytics Cloud Enterprise -> Oracle Analytics Cloud Professional`, confirming the same mixed-bundle safety in both directions without further production changes
- extended family metadata so `OCI Data Safe` can now switch between `Database Cloud Service` and `On-Premises Databases`, normalizing the quantity wording between `databases` and `target databases` instead of appending inconsistent tokens
- extended family metadata so `OCI Log Analytics` can now switch between `Active Storage` and `Archival Storage` while preserving the storage-capacity token
- added deterministic regressions for those two family-owned variant swaps both on direct active quotes and inside persisted mixed database bundles that also include `Exadata Cloud@Customer`
- added the reverse deterministic regressions for the same `OCI Data Safe` and `OCI Log Analytics` variant swaps, confirming symmetric behavior for both direct active quotes and persisted mixed database bundles without additional production changes
- added focused `service-families` unit coverage so the follow-up capability matrix itself is now validated directly for:
  - `OIC` / `OAC` composite replacement capability flags
  - `Data Safe` variant and quantity replacement rules
  - `Log Analytics` variant and capacity replacement rules
  - composite-removal registry membership for `Data Safe` and `Log Analytics`
- added a reusable follow-up capability matrix export in `service-families.js` so tests and future tooling can inspect supported family behavior directly instead of inferring it from raw metadata or long assistant regressions
- emitted that same capability matrix into `pricing/data/rule-registry/followup_capability_matrix.json` and added a rule-registry test so the generated artifact stays aligned with hardened family metadata
- revalidated with:
  - `node --test pricing/server/test/service-families.test.js`
  - `node --test pricing/server/test/rule-registry.test.js`
  - `node --test pricing/server/test/assistant-*.test.js`
  - `node --test pricing/server/test/*.test.js`

### 4. Workbook And RVTools Hardening

Status: parallel with parity work

Goal:

- make workbook-guided quoting a first-class tested path, not just a convenience path

Primary files:

- [excel.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/excel.js)
- [index.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/index.js)
- [excel.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/excel.test.js)

Immediate task list:

- add more workbook shape-selection cases
- add more RVTools processor and operating-system edge cases
- add more workbook-origin follow-up regression cases
- validate storage override handling across more workbook shapes and source platforms

Specific gaps worth prioritizing:

- workbook flows with explicit target shape changes after the first quote
- workbook flows with licensing-sensitive downstream services
- RVTools cases with larger mixed inventories and clearer warning behavior

Exit criteria:

- workbook-origin quotes are covered by regression tests across more than one source shape/profile
- workbook follow-up behavior is persisted and re-applied safely
- warnings remain deterministic and auditable

### 5. Observability And Operational Hardening

Status: fourth priority

Goal:

- make runtime behavior easier to debug, validate, and operate safely

Primary files:

- [index.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/index.js)
- [session-store.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/session-store.js)
- [catalog.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/catalog.test.js)
- [session-store.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/session-store.test.js)
- [quote-export.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/quote-export.test.js)

Immediate task list:

- add structured per-turn logs for:
  - route
  - `quotePlan`
  - context pack summary
  - quote source
  - warnings
- strengthen startup and `/api/health` diagnostics
- expand tests around versioned session writes and conflict handling

### 5A. Safe Parallel Execution Lanes

Status: in progress

Goal:

- increase delivery throughput without increasing behavioral drift, merge churn, or regression ambiguity

Current operating decision:

- use `3 execution lanes` with up to `4 sub-agents` plus one primary integrator for this stage
- keep `assistant.js`, `service-families.js`, and shared plan/docs under single-writer ownership
- treat lane-based ownership as the required operating model, not an optional coordination preference

Recently advanced:

- partitioned the biggest regression hotspot by extracting stable blocks out of [assistant-regressions.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/assistant-regressions.test.js)
- introduced a shared assistant regression harness in [assistant-test-helpers.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/assistant-test-helpers.js) so new suites reuse the same `assistant.js` bootstrap and catalog fixture instead of duplicating setup
- split low-risk, high-signal regression domains into dedicated files:
  - [assistant-followup-compute-composite-regressions.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/assistant-followup-compute-composite-regressions.test.js)
  - [assistant-deterministic-service-bundles-regressions.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/assistant-deterministic-service-bundles-regressions.test.js)
  - [assistant-expert-summary.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/assistant-expert-summary.test.js)
  - [assistant-sanitization.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/assistant-sanitization.test.js)
- extracted a second bounded lane for platform and database follow-ups into:
  - [assistant-followup-platform-database-regressions.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/assistant-followup-platform-database-regressions.test.js)
- extracted the `routing/discovery` regression lane into:
  - [assistant-routing-discovery-regressions.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/assistant-routing-discovery-regressions.test.js)
- extracted the deterministic compute-shape lane into:
  - [assistant-deterministic-compute-regressions.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/assistant-deterministic-compute-regressions.test.js)
- extracted the canonical request / request-shaping lane into:
  - [assistant-request-shaping-regressions.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/assistant-request-shaping-regressions.test.js)
- extracted the direct-quote unit-conversion lane into:
  - [assistant-direct-quote-unit-conversions.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/assistant-direct-quote-unit-conversions.test.js)
- extracted the last residual deterministic-quote lane into:
  - [assistant-residual-deterministic-quotes.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/assistant-residual-deterministic-quotes.test.js)
- extracted the flex-comparison tail into:
  - [assistant-flex-comparison-regressions.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/assistant-flex-comparison-regressions.test.js)
- retired [assistant-regressions.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/assistant-regressions.test.js) after the remaining coverage was fully partitioned into focused suites
- hardened the emitted follow-up capability matrix artifact with an explicit `security_waf` guard in [rule-registry.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/rule-registry.test.js), so the registry suite now fails if `OCI Web Application Firewall` loses its canonical entry, composite remove/replace flags, or active-quote rule presence
- revalidated with:
  - `node --test pricing/server/test/assistant-routing-discovery-regressions.test.js pricing/server/test/assistant-followup-platform-database-regressions.test.js pricing/server/test/assistant-followup-compute-composite-regressions.test.js pricing/server/test/assistant-deterministic-service-bundles-regressions.test.js pricing/server/test/assistant-deterministic-compute-regressions.test.js pricing/server/test/assistant-request-shaping-regressions.test.js pricing/server/test/assistant-direct-quote-unit-conversions.test.js pricing/server/test/assistant-residual-deterministic-quotes.test.js pricing/server/test/assistant-flex-comparison-regressions.test.js pricing/server/test/assistant-expert-summary.test.js pricing/server/test/assistant-sanitization.test.js`
  - `node --test pricing/server/test/*.test.js`

Reference:

- [PARALLEL_EXECUTION_LANES.md](/Users/javierchan/Documents/GitHub/oci/pricing/docs/PARALLEL_EXECUTION_LANES.md)
- [SUBAGENT_STRATEGY.md](/Users/javierchan/Documents/GitHub/oci/pricing/docs/SUBAGENT_STRATEGY.md)

Immediate task list:

- keep follow-up metadata work isolated from orchestration work
- reduce regression hotspot pressure by partitioning broad assistant coverage over time
- keep docs and registry alignment under a dedicated lane instead of piggybacking on runtime slices
- use the `3-lane` / `4-sub-agent` model as the proving ground before considering broader multi-agent parallelism
- keep future assistant regression additions routed into the existing focused suites instead of recreating a new monolith

Exit criteria:

- the team can run parallel slices without conflicting edits on the current hotspot files
- validation ownership is clear per lane
- the `3-lane` / `4-sub-agent` model shows higher throughput without more regression churn

### 6. Structured Discovery Knowledge Layer

Status: future strategic workstream

Goal:

- improve discovery, SKU-composition, billing-explanation, and required-input answers without relying on an expanding set of prompt-specific rules in `assistant.js`

Why this workstream exists:

- recent manual evaluations showed that the current discovery path is operational but still uneven on deeper conceptual prompts such as:
  - service quote composition
  - required quote inputs
  - billing dimension explanations
  - cross-variant comparisons such as `Standard vs Enterprise` or `BYOL vs License Included`
- the current architecture already prefers deterministic and metadata-driven behavior, so the next meaningful step is not “more regex”, but a richer structured knowledge layer that the assistant can retrieve and explain consistently

Strategic intent:

- keep deterministic pricing as the source of truth
- keep `GenAI` responsible for interpretation and explanation, not arithmetic
- reduce future maintenance cost by replacing one-off discovery heuristics with structured service blueprints and reusable response plans

Primary files expected to change when this work starts:

- [service-families.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/service-families.js)
- [context-packs.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/context-packs.js)
- [assistant.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/assistant.js)
- [normalizer.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/normalizer.js)
- new generated or curated registry artifacts under:
  - `pricing/data/rule-registry/`

Proposed design direction:

- introduce `service composition blueprints` per family
- introduce a small set of declarative `response types`
- improve retrieval so the assistant answers from the right blueprint rather than from free-form inference

Proposed blueprint contract per family:

- canonical family id
- quote intent aliases and discovery aliases
- required inputs:
  - mandatory
  - optional
  - conditional
- quote composition:
  - required pricing components
  - optional components
  - variant-specific components
- billing dimensions:
  - metric name
  - pricing unit
  - what user input drives the quantity
- licensing structure:
  - `BYOL`
  - `License Included`
  - cases where licensing does not apply
- example deterministic quote patterns
- known pitfalls and unsupported assumptions

Examples of families to pilot first:

- `compute_vm_generic`
- `integration_oic`
- `storage_block`
- `database_base_db`
- `network_load_balancer`

Proposed response types to introduce:

- `sku_composition`
- `billing_explanation`
- `required_inputs`
- `variant_comparison`
- `quote_request`
- `quote_followup`

Expected runtime flow after this work:

1. normalize prompt text
2. classify response type and likely family
3. retrieve the relevant family blueprint and context pack
4. answer from structured fields instead of free-form improvisation
5. fall back safely only when the blueprint is missing or insufficient

What this should reduce over time:

- family-specific regex growth
- prompt-specific branching in `assistant.js`
- misleading partial answers that are directionally correct but operationally incomplete
- model-to-model variability for conceptual discovery questions

What this should improve:

- consistency of discovery answers across model changes
- accuracy of SKU-composition explanations
- coverage for “what do I need before quoting X?” questions
- quality of service-variant explanations such as `Standard vs Enterprise`
- resilience when switching GenAI models with different prompt behavior

Evaluation strategy when this workstream starts:

- convert a curated set of manual discovery prompts into a fixed capability regression
- score by:
  - route correctness
  - family correctness
  - concept coverage
  - required SKU / component coverage
  - unsupported-case honesty
- keep service-level manual review for the first pilot families before widening the blueprint perimeter

Suggested implementation order:

1. define the blueprint schema and a minimal loader
2. pilot `compute_vm_generic` and `integration_oic`
3. route `sku_composition` and `required_inputs` answers through the blueprint layer
4. add `billing_explanation` support for storage and networking families
5. expand to database and security families
6. retire overlapping heuristics from `assistant.js` once parity is proven

Entry criteria for starting this workstream:

- the current declarative refactor wave has reduced enough inline assistant logic that a new blueprint layer can be added cleanly
- the active parity and follow-up work is stable enough that discovery improvements do not compete with unresolved deterministic regressions

Exit criteria:

- at least the pilot families answer structured discovery questions primarily from blueprints instead of prompt-specific assistant logic
- model swaps do not materially change the quality of core discovery answers for the pilot set
- new family discovery support mostly requires blueprint/context data instead of adding more assistant branching
- expand tests around session isolation and race-style mutation sequences
- revisit HTTP endpoint tests that currently require loopback listening in restricted environments

Exit criteria:

- operators can identify why a request routed to discovery, clarify, or quote
- startup diagnostics explain catalog state and degraded modes clearly
- session mutation conflict behavior is covered by more than the current baseline tests

### 6. Generic Question Routing Hardening

Status: in progress

Goal:

- prevent generic pricing questions from collapsing into deterministic quotes when the user is really asking for guidance, prerequisites, billing dimensions, or quote composition

Recent progress:

- backend guardrails now keep prerequisite questions in `product_discovery` even when the controller says `quote_request`
- active-session conceptual questions that reuse an existing quote now stay in `answer` mode for covered composition prompts instead of being force-mutated into `quote_followup`
- registry-backed `topService` fallback no longer force-quotes discovery and explanation prompts just because the request includes enough measurable inputs
- `normalizer` coverage now also locks explicit measurable-input discovery prompts into `product_discovery` so controller `quote_request` outputs are normalized away earlier in the stack
- assistant regressions now explicitly cover:
  - "What inputs do I need before quoting Health Checks in OCI?"
  - "What inputs do I need before quoting Base Database Service?"
  - "Which SKUs are required to quote a Virtual Machine instance and its components?"
  - "Only OCPU, no disk, no memory?"
  - "How is OCI Health Checks billed for 12 endpoints?"
  - "Explain OCI FastConnect pricing dimensions for 10 Gbps."

Primary files:

- [intent-extractor.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/intent-extractor.js)
- [normalizer.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/normalizer.js)
- [assistant.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/assistant.js)
- [context-packs.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/context-packs.js)
- [focused assistant regression suites](/Users/javierchan/Documents/GitHub/oci/pricing/server/test)
- [normalizer.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/normalizer.test.js)

Pending task list:

- reduce controller bias toward `shouldQuote=true` for broader open-ended discovery or explanatory questions beyond the currently covered patterns
- prevent `topService` registry matches from forcing a deterministic quote when the user intent is discovery or explanation in more ambiguous service mentions
- expand the conceptual-question guardrails beyond the current covered prompts for prerequisites, components, and quote composition
- expand structured context-pack coverage for:
  - quote prerequisites
  - quote composition
  - billing dimensions by family

Exit criteria:

- generic pricing questions route to `product_discovery` or `general_answer` by default unless the user explicitly asks for a quote
- active-session conceptual questions about an existing quote return explanations instead of unintended quote mutations
- regression coverage exists for ambiguous prompts such as:
  - "Which SKUs are required to quote a Virtual Machine instance and its components?"
  - "Only OCPU, no disk, no memory?"
  - "What inputs do I need before quoting this service?"

## Suggested Sequence

### Phase 0. Safety Net

- inventory test gaps
- add missing parity and workbook regression cases before refactors

### Phase 1. Expand Confidence

- land parity additions
- land workbook and RVTools hardening cases
- land follow-up regression cases for the highest-value families

### Phase 2. Refactor Toward Metadata

- reduce manual assistant branches
- push family behavior into `service-families.js`
- push discovery and explanation structure into `context-packs.js`

### Phase 3. Expand Follow-Up Depth

- implement capability-driven follow-up support across more families
- ensure each new supported follow-up has regression tests

### Phase 4. Operational Hardening

- add observability
- improve startup and health reporting
- harden concurrency and endpoint testing

### Phase 5. Generic Question Hardening

- harden routing for discovery and explanatory prompts
- keep generic and conceptual questions out of deterministic quote paths
- add regressions for ambiguous prompts before expanding frontend guidance UX

### Phase 6. Model-Deterministic Boundary Hardening

- preserve deterministic pricing as the execution contract
- let `GenAI` handle interpretation, normalization, clarification, and explanation
- reduce ad hoc rule growth by moving reusable behavior into metadata, blueprints, and response plans
- avoid shifting final pricing arithmetic or SKU selection into model-only behavior

This phase does not replace the current roadmap. It formalizes the intended division of responsibility so future simplification work stays aligned with the existing architecture.

## Next Concrete Tasks

These are the recommended next tasks to execute immediately:

1. Extract the composite detection and segmentation helper cluster from `assistant.js` into a bounded helper module:
   - completed in `composite-quote-segmentation.js`
2. Extract the deterministic composite quote assembly cluster from `assistant.js` into a bounded helper module:
   - completed in `composite-quote-builder.js`
3. Extract the next bounded deterministic narrative/profile helper cluster:
   - completed in `assistant-quote-narrative.js`
4. After narrative/profile shaping is isolated, define the next boundary cut between:
   - deterministic narrative/profile helpers
   - GenAI quote-enrichment orchestration
   - context-pack / explanation shaping helpers
5. Continue the model-vs-deterministic boundary strategy by moving reusable interpretation support into metadata or helper modules, not into more prompt-specific branches

## Definition Of Progress

This work should be considered real progress only when at least one of these is true:

- parity coverage increases
- declarative family metadata replaces manual assistant logic
- deterministic follow-up behavior becomes reusable across families

### 6. Model-Deterministic Boundary Strategy

Status: active strategic track, executed incrementally without changing the current roadmap order

Goal:

- reduce long-term maintenance cost without weakening deterministic pricing guarantees
- keep the pricing agent strong at natural-language understanding while preventing model drift in final quote construction
- replace future prompt-specific branches with structured metadata and knowledge artifacts where possible

Working rule:

- do not move arithmetic, SKU selection, or final quote composition responsibility out of the deterministic engine
- do move interpretation, discovery, explanation, and reusable family semantics into structured metadata and retrieval-friendly artifacts

What is already covered:

- the architecture already keeps `GenAI` on interpretation and explanation while deterministic pricing remains the source of truth
- `assistant.js` has already been reduced from a monolithic policy owner into more of an orchestrator over helper modules
- active-quote follow-up behavior is already moving into family-owned metadata and a reusable capability matrix
- routing hardening already protects discovery and conceptual questions from falling into quote execution when they should stay explanatory
- low-risk normalization work already broadens user-language coverage without changing the deterministic quote contract
- parity and regression coverage already give us a safety net so structural simplifications can happen without blind spots

What is still missing:

- a written responsibility map for which behaviors belong in:
  - `assistant.js`
  - `service-families.js`
  - `context-packs.js`
  - deterministic quote/build logic
- declarative `service blueprints` for discovery-heavy families so required inputs, composition, billing dimensions, and licensing answers stop depending on narrow assistant heuristics
- a small set of reusable `response types` for discovery answers such as:
  - required inputs
  - billing explanation
  - quote composition
  - variant comparison
- an explicit review pass over remaining `assistant.js` branches to decide:
  - keep
  - move to metadata
  - move to structured knowledge
- a pruning rule so future parity additions stay focused on high-value deterministic contracts instead of turning into an unbounded combinatorial suite

Priority order inside this strategy:

1. document the ownership boundary clearly so new work stops adding accidental assistant policy
2. inventory remaining `assistant.js` branches and classify them by destination
3. pilot structured service blueprints for a small family set with high discovery value:
   - `compute_vm_generic`
   - `integration_oic`
   - `database_base_db`
   - `storage_block`
   - `network_load_balancer`
4. route discovery-style answers through those blueprints before expanding more one-off heuristics
5. only after the blueprint layer proves stable, revisit whether some parity cases are redundant versus still contract-critical

Recommended next implementation slice for this track:

- add the boundary strategy to the execution plan
- treat the `assistant.js` branch inventory as the first concrete deliverable
- use [Assistant Branch Inventory](/Users/javierchan/Documents/GitHub/oci/pricing/docs/ASSISTANT_BRANCH_INVENTORY.md) as the tracking artifact for milestone status, branch classification, and anti-loop scope control
- keep current parity / workbook / follow-up slices moving in parallel, but evaluate each new change against the boundary rule before adding fresh assistant-owned logic

Exit criteria:

- contributors can explain where new behavior belongs before implementing it
- discovery improvements are increasingly powered by structured family knowledge instead of prompt-specific conditionals
- deterministic pricing remains the source of truth for quote totals and line-item composition
- future rule growth shifts from ad hoc branches toward metadata and curated knowledge artifacts
- runtime diagnostics or concurrency behavior become measurably stronger

If a change only fixes one prompt phrasing and does not improve those dimensions, it should not count as a milestone.
