# Architecture

## Execution Status

This architecture is partially implemented.

### Implemented

- OCI live catalog ingestion
- workbook and PDF extraction tooling
- service registry and coverage endpoint
- intent extraction through OCI GenAI
- normalization layer
- deterministic quotation engine
- dependency resolver for selected domains
- pasted image support
- Excel input support
- VMware RVTools input support with migration-aware VM filtering and VMware-to-OCI CPU normalization
- `BYOL` clarification handling

### Being Expanded

- registry-driven service matching
- registry-driven required-input detection
- broader dependency modeling
- broader licensing and ambiguity handling
- parity validation against OCI Calculator

### Not Yet Complete

- full service-family coverage across all OCI services
- complete prerequisite modeling across all workbook services
- full explanation layer for all `L3/L4` services
- full regression suite for representative OCI Calculator exports

## Goal

`pricing` is intended to become a deterministic OCI estimation engine with a natural-language assistant on top, not a pure chatbot that invents prices.

The target behavior is:

1. Understand user intent from text, images, spreadsheets, and calculator exports.
2. Normalize that input into a structured internal request.
3. Resolve OCI services, SKUs, prerequisites, and licensing variants.
4. Calculate pricing deterministically from Oracle reference data.
5. Explain the result in natural language without changing the numbers.

## Core Principle

Use:

- `GenAI` for interpretation
- `registry + rules` for decisioning
- `deterministic pricing engine` for calculation

Do not use GenAI for:

- final price calculation
- SKU invention
- tier selection without validation
- free-form licensing assumptions

## Source Of Truth

The repo uses a layered source strategy:

1. OCI live catalog JSON
   - `products.json`
   - `metrics.json`
   - `productpresets.json`
   - Purpose: active SKU pricing and machine-readable metrics

2. Oracle localizable price list workbook
   - `pricing/data/source-docs/current/ORACLE+PAAS+AND+IAAS+PUBLIC+CLOUD+LOCALIZABLE+PRICE+LIST.xls`
   - Purpose: service names, metrics, prerequisites, structured reference pricing context

3. Oracle global price list PDFs
   - `pricing/data/source-docs/current/ORACLE+PAAS+AND+IAAS+PUBLIC+CLOUD+GLOBAL+PRICE+LIST.pdf`
   - `pricing/data/source-docs/current/ORACLE+PAAS+AND+IAAS+PUBLIC+CLOUD+GLOBAL+PRICE+LIST+SUPPLEMENT.pdf`
   - Purpose: contractual notes, minimums, restrictions, prerequisite semantics

4. OCI Calculator artifacts
   - screenshots and exported JSON
   - Purpose: validation and parity checks, not primary pricing logic

## Runtime Layers

### 1. Intent Extraction

Files:

- `server/intent-extractor.js`
- `server/genai.js`

Responsibilities:

- classify the request
- extract candidate service family
- extract numeric sizing inputs
- ask for clarification when needed

### 2. Normalization

Files:

- `server/normalizer.js`
- `server/service-families.js`

Responsibilities:

- normalize aliases and wording
- convert loose prompts into canonical internal requests
- infer service family
- rescue deterministic quotes when inputs are already sufficient
- apply source-aware normalization for imported assets such as RVTools workbooks, including VMware service-VM exclusion and `vCPU -> OCPU` conversion

### 3. Service Registry

Files:

- `server/service-registry.js`
- `server/workbook-rules.js`
- `server/catalog.js`
- `data/rule-registry/service_family_rules.json`
- `data/rule-registry/coverage_matrix.json`
- `data/rule-registry/vm_shape_rules.json`

Responsibilities:

- unify catalog and workbook service metadata
- track patterns, required inputs, and coverage level
- act as the main registry for broad OCI service coverage
- persist extracted rule artifacts so gaps can be measured outside the runtime

### 3a. Extracted Rule Artifacts

Files:

- `tools/build_rule_registry.py`
- `tools/build_vm_shape_rules.py`
- `tools/build_coverage_artifacts.js`

Responsibilities:

- turn `XLS + PDF` extracts into reusable JSON artifacts
- persist calculator-style VM shape mappings in `vm_shape_rules.json`
- group workbook services into family-level artifacts in `service_family_rules.json`
- publish a machine-readable `coverage_matrix.json` with:
  - source counts
  - runtime coverage levels
  - vm-shape coverage
  - lowest-coverage services

This is the path to broad SKU coverage. It converts local source material into auditable data instead of repeating one-off fixes in prompt logic.

### 4. Dependency Resolution

Files:

- `server/dependency-resolver.js`

Responsibilities:

- resolve services into billable SKUs
- handle prerequisites
- distinguish product-level vs service-level quotes
- enforce special rules like `BYOL` ambiguity handling

### 5. Deterministic Pricing

Files:

- `server/quotation-engine.js`
- `server/catalog.js`
- `server/consumption-model.js`

Responsibilities:

- compute quantities
- apply pricing tiers
- calculate monthly and annual totals
- keep results auditable

### 6. Presentation

Files:

- `server/assistant.js`
- `app/index.html`

Responsibilities:

- produce human-readable responses
- preserve deterministic totals
- show clarifications before unsafe quotes

## Coverage Model

Coverage is tracked in `server/service-registry.js` with levels:

- `L0`: not usable
- `L1`: searchable only
- `L2`: deterministically quotable
- `L3`: quotable + explainable
- `L4`: quotable + explainable + prerequisites/licensing modeled

Coverage should be improved by:

1. adding service metadata to the registry
2. improving consumption-pattern inference
3. improving prerequisite modeling
4. improving ambiguity handling for licensing and variants
5. regenerating extracted artifacts from source documents and checking the coverage matrix

Not by adding one-off prompt hacks.

## Professional Development Rule

When adding support for a new OCI service, prefer this order:

1. add or improve registry metadata
2. add or improve consumption pattern handling
3. add or improve prerequisite and licensing logic
4. add test cases
5. only then add narrow domain-specific fallback logic if still necessary

If a fix only works for one prompt and does not improve the registry or model, it is usually the wrong abstraction.

## Practical Milestone Definition

Use these milestone definitions when planning work:

- `Done`
  - implemented in runtime
  - validated with at least one real end-to-end test
- `In Progress`
  - code structure exists, but domain coverage is still partial
- `Next`
  - prioritized but not yet implemented

This keeps the repo aligned around reachable, reviewable increments instead of vague “future support”.
