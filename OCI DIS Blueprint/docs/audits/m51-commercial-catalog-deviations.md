# M51 Commercial Catalog Independent Deviation Audit

## Audit Status

**Global commercial catalog: APPROVED WITH TERMINAL DISPOSITIONS. App BOM: APPROVED WITH EXCLUSIONS.**

This audit records the independent validation of the proposed M51 commercial
catalog contract against the official Oracle PaaS and IaaS Localizable Price List,
its Supplement, the existing public OCI source strategy, and the quotation
governance requirements documented in this repository. It is the independent
release control for the completed M51 implementation.

The implementation persists documentary terms, constraints, relationships,
semantic states, generated candidates, rule fixtures, and immutable releases.
Global release `commercial-20260720043236` contains terminal dispositions for all
1,182 catalog candidates: 229 quote-ready and 953 blocked with governed reasons.
The independent review actor is `codex-m51-global-catalog-review`.

The App BOM remains intentionally narrower. It enables 27 of the 32 currently
mapped SKUs. `B88299`, `B88406`, `B92993`, `B93496`, and `B93497` remain excluded
because their commercial dependencies are not resolved by authoritative evidence.

The imported workbook produced 1,149 initial review items. The persisted catalog
currently contains 1,121 open exceptions after governed decisions. These exceptions
remain visible for remediation and are intentionally separate from the global
terminal-disposition count. A blocked disposition is not an approval and cannot be
used for BOM publication.

This is truthful global governance, not blanket quotation approval. Every candidate
is approved for quotation or blocked with reasons; supported BOM lines may use only
the exact 27-SKU App allowlist. The 953 blocked candidates and five excluded App
mappings cannot enter a published BOM.

## Field-Level Authority Matrix

The prior assumption of one blanket source precedence is rejected. Commercial
authority is assigned per field:

| Commercial field | Authority | Audit requirement |
| --- | --- | --- |
| Customer price | Approved contractual rate card | Override public rate only; retain public terms and evidence. |
| Public PAYG rates and tiers | OCI public pricing API | Persist exact decimals, currency, tiers, source hash, and timestamp. |
| Commitment term type and value | Localizable Price List | Preserve the workbook label, including Annual Commitment, Annual Flex, and Monthly Flex. |
| Metric minimum and billing guidance | Localizable Price List | Persist a typed constraint with explicit scope and evidence. |
| Entitlements and prerequisites | Supplement | Persist typed relationships with resolution status and confidence. |
| Product identity, price type, decimal allowance, availability | `products.json` | Reconcile exact source identity; conflicts block approval. |
| Metric identity and presentation | `metrics.json` | Preserve metric IDs and labels; do not infer the formula from text alone. |
| Estimator composition hints | `productpresets.json` | Candidate-generation evidence only; never approval evidence by itself. |

Any disagreement between authoritative fields creates a blocking exception. Source
ordering or a successful fetch cannot resolve a semantic conflict.

## Required Contract Deviations

### 1. Typed commercial terms

A single `annual_commitment_value` is insufficient. The normalized contract must
store a typed commercial term and value so Annual Commitment, Annual Flex, Monthly
Flex, and future explicit workbook labels cannot be conflated.

### 2. Scoped, repeatable constraints

Scalar minimum and increment fields are insufficient. Each constraint must be
typed, repeatable, scoped, evidenced, and reviewable. Required scopes include at
least capacity, time, storage, backup, request, message, tenant, subscription, and
environment where the source states them.

For `B95701`, metric minimum `2` is minimum ECPU capacity, not two monthly
ECPU-hours. For `B95754`, database-storage and backup increments are separate
rules and must not overwrite each other.

### 3. Relationship resolution

Entitlements and prerequisites require relationship type, source identity, target
identity, resolution status, confidence, and evidence. An exact target part number
may be resolved deterministically. A name-only dependency remains unresolved and
blocks quote-ready publication until an audited decision is recorded.

### 4. Source-state preservation

Blank, `-`, `Always Free`, and `See Additional Information` are separate semantic
states. None is equivalent to numeric zero. The parser and persistence contract
must preserve the original state and its evidence.

### 5. Complete price-family support

Price type cannot be derived solely from metric text. Approved rule families must
cover the official structured price types used by the catalog, including `HOUR`,
`HOUR_UTILIZED`, `MONTH`, `DAY`, and `PER_ITEM`, together with their aggregation,
proration, minimum, increment, and tier semantics.

## Automation Boundary

### Deterministic automation permitted

- exact part-number and source-ID identity;
- exact decimal extraction without binary floating-point conversion;
- numeric metric minimum extraction with explicit scope;
- structured decimal allowance, availability, and price-type ingestion;
- approved exact-phrase mappings for billing granularity and minimum duration;
- explicit part-number dependency linking;
- exact cross-source price and metric reconciliation;
- draft classification, candidate generation, and fixture execution.

### Human review required

- BYOL eligibility and customer entitlement;
- name-only dependencies;
- `See above`, `OR equivalent`, `See Additional Information`, and continuation rows;
- prose that contains multiple constraints without an approved deterministic split;
- commitment eligibility, discount thresholds, private rates, and regional eligibility;
- conflicting rates, metrics, product identities, or relationship evidence;
- any new formula family, low-confidence candidate, or unresolved source drift.

OCI Generative AI may summarize, compare, and prioritize review evidence. It may
not calculate authoritative totals, approve a mapping, resolve a relationship, or
close an exception.

## Mandatory Acceptance Fixtures

| Fixture | Required assertion |
| --- | --- |
| `B95701` terms | PAYG `0.336`, Annual Commitment `0.336`, `ECPU Per Hour`, minimum capacity `2`, per-second billing, and 60-second minimum runtime are preserved with evidence. |
| `B95701` dependency | Quote-ready publication remains blocked until the Exadata Storage prerequisite is resolved and approved. |
| `B95703` | BYOL eligibility requires an explicit audited decision. |
| `B95754` | Database-storage and backup increments remain separate typed constraints. |
| `B88206` | A continuation row is not interpreted as a price tier or second SKU. |
| `B92072` | Prorated fractional million API calls remain fractional when the official metric allows decimals. |
| `B92598` | Workspace hours require explicit input; no universal `744`-hour default is applied. |
| `B93306` | One-minute increments and tenant-scoped allowances are tested separately. |
| Tier families | Zero, below-minimum, exact-boundary, and above-boundary quantities use independent expected results. |
| Cross-source conflict | Any API, Price List, Supplement, products, or metrics disagreement creates a blocking exception. |
| Candidate approval | Generated candidates remain drafts until fixtures pass and approval is audited. |
| BOM publication | Publication fails when a required price, term, mapping, relationship, rule, or evidence reference is absent. |

## Release Decision

M51 is complete. Global release `commercial-20260720043236` is the authoritative
catalog-disposition baseline: all 1,182 candidates are terminal, with 229 quote-ready
and 953 blocked. The prior release `commercial-20260720042814`, which exposed stale
generator evidence by approving only one candidate, is retained as superseded audit
history. The corrective finalization revalidated each candidate through its
deterministic rule and fixture before recording the final decision.

BOM generation must still pin the exact approved App allowlist, block lines outside
its 27-SKU scope, and display excluded SKUs and reasons. Historical BOMs remain
immutable and tied to their original commercial release. The independent engineering
control is defined in `docs/architecture/commercial-consistency-test-agent.md`; it
validates implementation semantics against documentary evidence and is separate from
the read-only App `Official Source Governance Agent`.

## Validation Evidence

### Official source reconciliation (2026-07-20)

The current Localizable Price List workbook and the approved structured OCI
sources were reconciled by normalized part number before candidate generation:

| Source | Distinct SKU identities | Version evidence |
| --- | ---: | --- |
| Localizable Price List workbook | 1,163 | SHA-256 `263060bda2eb99867d04a0ab9ea090347602ef28b25fddd274ebd0c32f1599e9` |
| OCI Public Pricing API, USD | 658 | `lastUpdated=2026-07-16T13:52:41.483Z`; SHA-256 `73099e750880991da6fd704ff1da3127b660a918f4fe04cdfa170c0f1073f366` |
| Cloud Estimator `products.json` | 674 | build `439`, `2026-07-16T11:00:10Z`; SHA-256 `0c3c8ac1d079a39a6db3e0139a924b0b02b8cde67417b9ff04f616fc3f04bd3b` |

The workbook contains 506 identities absent from the Pricing API and 507 absent
from `products.json`. The Pricing API contains one identity absent from the
workbook (`B109480`). Cloud Estimator contains 18 `FR` identities absent from
both of the other sources. The union contains 1,182 governed candidate
identities and is persisted in the document manifest as an exact, sorted diff.

The Pricing API remains authoritative for public PAYG prices and typed tiers.
For the 506 workbook-only identities, the workbook commercial term may provide a
source-labelled price fallback, but the candidate remains blocked until its
metric, terms, quantity behavior, relationships, and quotation fixture are
reviewed. PAYG and Annual Commitment are persisted as separate commercial terms
even when their current numeric values are equal. `products.json`,
`metrics.json`, and `productpresets.json` govern structured identity, metric
display, decimal-input behavior, and estimator composition; they do not replace
contract terms from the workbook or prices from the Pricing API.

Repeated workbook occurrences are modeled as one SKU identity with every
official product path retained. Canonical placement uses semantic hierarchy with
a deterministic tie-break independent of page order. Conflicts compare only
overlapping non-null normalized identity fields; workbook placement and
source-labelled tiers do not create false conflicts. The current workbook has
1,065 multi-location SKUs. Nine SKUs contain ten material identity or metric
conflicts and are routed to explicit review instead of being reassigned
silently.

Workbook layout validation is fail-closed: both governed sheets and their
required semantic headers must be recognized, and the Price List must yield at
least one valid OCI part number. A layout change cannot degrade into an empty or
apparently successful catalog.

Validated on 2026-07-20 against the production Docker stack and the persisted
global commercial release:

- workspace `.venv` API suite: 214 passed;
- calc engine: 55 passed; pricing engine: 35 passed;
- frontend unit and contract suite: 94 passed;
- frontend TypeScript, ESLint, Ruff, mypy, and `npm audit --audit-level=high`: passed;
- canonical browser E2E: 17 passed and one conditional dossier test skipped, with
  terminal source-sync and BOM jobs, two
  environments, governed monthly quantities, exports, mobile inspector, and no
  horizontal overflow;
- Admin Pricing visual inspection in the isolated Codex browser: desktop dark and
  390-pixel mobile geometry, zero browser-console errors, no horizontal overflow,
  truthful 1,182/229/953 global counts, and explicit 27 enabled plus five excluded
  App BOM mappings; the official `B107951` detail displayed its Exadata product
  name, semantic hierarchy, two workbook placements, metric, and commercial term
  without treating the workbook placeholder `-` as a product entitlement;
- deterministic candidate revalidation: passed and confirmed idempotent; it updates
  rule evidence without granting human approval;
- OpenAPI artifact check inside `ocidisblueprint-api:latest`: passed;
- production migration: `20260720_0043 (head)`;
- production image scan: API reports zero findings; web reports zero critical/high,
  one medium BusyBox finding with no fixed Alpine package available, and zero low;
- production services: API, PostgreSQL, Redis, and MinIO healthy; web, worker,
  beat, and dedicated agent worker running.

The remaining risk is explicit rather than hidden: 953 blocked candidates, 1,121
open catalog exceptions, and five excluded App SKUs are not approved for BOM
publication. This audit approves the global disposition baseline and the pinned
27-SKU App BOM scope; it does not reinterpret a blocked disposition as commercial
eligibility.
