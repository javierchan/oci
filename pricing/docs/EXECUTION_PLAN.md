# Execution Plan

## Purpose

This document turns the current `pricing` roadmap into an executable work plan.

Use it to answer:

- what to do next
- in what order to do it
- which files are most likely to change
- how to know when a workstream is actually complete

This plan is intentionally tactical. It complements:

- [Coverage Roadmap](/Users/javierchan/Documents/GitHub/oci/pricing/docs/COVERAGE_ROADMAP.md)
- [Architecture](/Users/javierchan/Documents/GitHub/oci/pricing/docs/ARCHITECTURE.md)

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
- conceptual prerequisite questions such as required inputs before quoting a service now stay in discovery mode even when the controller returns `quote_request`
- active-quote conceptual follow-ups now answer in natural language instead of mutating the persisted quote source for covered composition questions such as:
  - required quote `SKU` / component questions
  - compute composition checks such as `Only OCPU, no disk, no memory?`
- discovery and explanation questions with enough structured inputs to be quotable now stay in `product_discovery` instead of being force-promoted to deterministic quote mode by registry `topService` matching
- short active-quote discovery questions now skip the early session-quote prompt merge, so billing and component questions do not become accidentally quotable before intent guardrails run
- `normalizer.js` now also de-prioritizes explicit `quote_request` routes when the prompt text is clearly discovery/explanation-oriented, including pricing-dimension prompts that contain measurable inputs

Validation status as of April 9, 2026:

- targeted suites for workbook, parity, and assistant follow-ups are green
- quote export endpoint tests are green in sandbox through the socketless export-response harness
- current assistant follow-up regression suite result: `242 pass / 0 fail`
- workbook-focused suite result: `27 pass / 0 fail`
- current parity suite result: `136 pass / 0 fail`
- quote export endpoint suite result: `3 pass / 0 fail`
- current full-suite result in sandbox: `483 pass / 0 fail`

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
- [assistant-regressions.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/assistant-regressions.test.js)
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

- added enterprise database bundles that combine Base Database, Database Cloud Service, and Exadata Cloud@Customer with Data Safe, monitoring, health checks, notifications, and log analytics
- widened deterministic parity around observability-heavy database scenarios without changing the broader execution sequence
- added autonomous database bundles that combine Autonomous AI Lakehouse and Autonomous AI Transaction Processing with Data Integration, firewall, load balancer, DNS, monitoring, notifications, and health checks
- added workbook and RVTools regressions that compose workbook-derived compute workloads with shared `FastConnect + Monitoring Retrieval` services
- added workbook-origin and RVTools-origin follow-up regressions that preserve shared `FastConnect + Monitoring Retrieval` services when mixed quotes are mutated through shape, VPU, and capacity-reservation changes
- fixed composite follow-up metadata so workbook-origin and RVTools-origin mixed quotes can remove shared `FastConnect` and `Monitoring Retrieval` services safely, then locked that behavior with regressions
- extended composite follow-up metadata so workbook-origin and RVTools-origin mixed quotes can also replace shared `FastConnect`, `Monitoring Retrieval`, `DNS`, and `Health Checks` services safely, then locked that behavior with regressions
- fixed composite follow-up replacement routing so parameter-only mutations in mixed workbook/RVTools quotes target the intended shared family instead of falling back to append behavior, then locked that behavior with regressions for `FastConnect bandwidth`, `DNS query volume`, and `Health Checks endpoint count`

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

Recently completed in this workstream:

- extracted the first declarative follow-up rule layer from `assistant.js`
- kept behavior stable through regression coverage before and after the refactor
- extracted a second declarative layer for active-quote follow-up quantity replacements so covered families can own their own replacement patterns in `service-families.js`
- reduced dependence on the generic replacement fallback by skipping it when a covered family already resolved the follow-up through metadata
- completed the current active-quote replacement hardening wave so the covered quantity and sizing follow-ups now resolve through family metadata instead of shared assistant rules
- hardened active-quote family detection for workbook and RVTools quotes with explicit Flex shapes so shape-plus-sizing follow-ups route to `compute_flex`

Refactor targets to prefer:

- family-specific clarification prompts
- family-specific follow-up transformations
- discovery responses based on family options and required inputs
- safe unsupported guidance based on registry/context data instead of custom branches

Exit criteria:

- reduced family-specific branching in `assistant.js`
- new family additions mostly require metadata + context pack changes
- `quotePlan` carries enough structured intent that fewer assistant heuristics are needed

### 3. Follow-Up Coverage Expansion

Status: third priority

Goal:

- make quote follow-ups more complete and less ad hoc across families

Primary files:

- [assistant.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/assistant.js)
- [service-families.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/service-families.js)
- [assistant-regressions.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/assistant-regressions.test.js)

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
- [assistant-regressions.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/assistant-regressions.test.js)
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

## Next Concrete Tasks

These are the recommended next tasks to execute immediately:

1. Add parity cases for:
   - mixed networking/security bundles
   - more database combinations
   - analytics + integration bundles
2. Add workbook and RVTools regression cases for:
   - shape changes after the initial workbook quote
   - workbook-origin modifier updates
   - larger VMware inventory cases
3. Build an `assistant.js` branch inventory and label each branch as:
   - move to `service-families`
   - move to `context-packs`
   - keep in assistant orchestration
4. Define a follow-up capability matrix per family before adding more ad hoc follow-up code
5. After the current sequence is stable, schedule the generic-question routing hardening slice for backend intent and fallback control

## Definition Of Progress

This work should be considered real progress only when at least one of these is true:

- parity coverage increases
- declarative family metadata replaces manual assistant logic
- deterministic follow-up behavior becomes reusable across families
- runtime diagnostics or concurrency behavior become measurably stronger

If a change only fixes one prompt phrasing and does not improve those dimensions, it should not count as a milestone.
