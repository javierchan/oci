# Assistant Branch Inventory

## Purpose

This document tracks the boundary-hardening work for `pricing/server/assistant.js`.

Document role:

- this file is the source of truth for the `assistant.js` boundary-hardening track
- it is a tracking artifact for ownership reduction, not the general work plan
- active sequencing lives in [Execution Plan](/Users/javierchan/Documents/GitHub/oci/pricing/docs/EXECUTION_PLAN.md)
- architecture intent lives in [Architecture](/Users/javierchan/Documents/GitHub/oci/pricing/docs/ARCHITECTURE.md)
- the full docs map lives in [Docs Guide](/Users/javierchan/Documents/GitHub/oci/pricing/docs/README.md)

It exists to answer:

- which remaining behaviors still live in `assistant.js`
- which of those behaviors should stay in orchestration
- which should move into metadata or structured knowledge
- what the next achievable slice is
- how to avoid rework, loops, or speculative refactors

This is a tracking artifact, not a redesign proposal.

## Working Rules

- keep `assistant.js` as an orchestrator, not a growing policy sink
- do not move deterministic pricing arithmetic or SKU selection into model-only behavior
- do not refactor a branch unless its destination is explicit
- do not count inventory work as complete unless the branch has been classified
- do not start broad rewrites from this document; use it to create bounded slices

## Classification Buckets

- `keep_in_assistant_orchestration`
  - sequencing, payload selection, and high-level control flow
- `move_to_service_families`
  - family capabilities, family-owned replacements, required-input semantics, quote composition semantics
- `move_to_context_packs`
  - structured discovery and explanation content, reusable knowledge presentation, catalog-backed answer shaping
- `move_to_helper_module`
  - reusable non-family logic that does not belong inline in `assistant.js`
- `move_to_deterministic_quote_logic`
  - deterministic quote construction, canonical quote preference, bundle composition, or quote rendering that should live closer to quote/build modules than to assistant orchestration
- `move_to_structured_knowledge`
  - blueprint-driven discovery or explanation behavior that should be backed by curated artifacts

## Execution Track

### Milestone 0. Tracking Setup

Status: done

Exit criteria:

- execution plan references this inventory as the first concrete deliverable for the boundary strategy
- this document defines classification buckets, scope rules, and anti-loop rules

### Milestone 1. Top-Level Orchestration Inventory

Status: done

Scope:

- inventory the top-level branches inside `respondToAssistant()`
- confirm which checkpoints are true orchestration and should stay centralized

Exit criteria:

- each top-level branch point is listed
- each branch point has a classification
- each branch point has a rationale

Current inventory:

| Branch / checkpoint | Current owner | Classification | Rationale |
| --- | --- | --- | --- |
| `effectiveUserText` via session follow-up merge | `assistant.js` calling session helpers | `keep_in_assistant_orchestration` | This is request assembly and state reconciliation, not family policy. |
| `resolveEarlyAssistantRouting()` | helper | `keep_in_assistant_orchestration` | Early exits and flex-comparison routing are control-flow decisions. |
| `resolveDirectQuoteFastPath()` | helper | `keep_in_assistant_orchestration` | Fast-path selection is orchestration, even though helpers may still shrink internally. |
| `resolveIntentPipeline()` | helper | `keep_in_assistant_orchestration` | Intent ordering and payload short-circuiting should remain centralized. |
| `buildDiscoveryRoutingState()` + `resolveDiscoveryRoutePayload()` | helper + assistant pipeline | `keep_in_assistant_orchestration` | Route choice stays here; discovery content should keep moving out. |
| `prepareQuoteCandidateState()` | helper | `keep_in_assistant_orchestration` | Quote-entry sequencing belongs in orchestration, while family semantics belong elsewhere. |
| `reconcileQuoteClarificationState()` | helper | `keep_in_assistant_orchestration` | Clarification gate selection is orchestration over family metadata. |
| `resolvePostClarificationRouting()` | helper | `keep_in_assistant_orchestration` | Final payload resolution is a coordinator responsibility. |

Notes:

- the top-level flow is already mostly in the right place
- the main remaining risk is not the existence of these checkpoints, but helper internals that may still carry policy that belongs elsewhere

### Milestone 2. Helper Ownership Review

Status: in progress

Scope:

- inspect assistant-owned or assistant-adjacent helpers that still encode policy
- classify which helpers are stable orchestration utilities and which still hide family or discovery policy

Initial candidate areas:

- composite request detection and segmentation helpers
- quote narrative and expert-summary shaping
- assumption filtering and preservation rules
- registry-query shaping
- profile-selection logic for deterministic summaries

Initial helper inventory:

| Helper group | Example functions | Classification | Rationale |
| --- | --- | --- | --- |
| Discovery-query shaping | `buildRegistryQuery()` | `move_to_helper_module` | This is reusable discovery preprocessing and does not need to stay in assistant orchestration. |
| Family input normalization bridge | `enrichExtractedInputsForFamily()` | `move_to_service_families` | The behavior is family-owned and already delegated to family normalization. |
| Flex comparison context extraction | `isFlexComparisonRequest()`, `detectFlexComparisonModifier()`, `extractFlexComparisonContext()` | `move_to_helper_module` | This is reusable intent-support logic, not top-level orchestration policy. |
| Composite signal detection and splitting | `hasCompositeServiceSignal()`, `splitCompositeQuoteSegments()`, `normalizeCompositeSegment()` | `move_to_helper_module` | This is parsing and normalization support that should not stay inline in `assistant.js`. |
| Composite deterministic quote assembly | `buildCompositeQuoteFromSegments()`, `choosePreferredQuote()`, `quoteSegmentWithCanonicalFallback()` | `move_to_deterministic_quote_logic` | These functions are deterministic quote-building behavior, not model orchestration. |
| Assumption preservation rules | `formatAssumptions()`, `shouldKeepSourceAssumption()` | `move_to_helper_module` | These are reusable formatting/filtering policies that can be tested independently. |
| Session quote summarization | `summarizeQuoteForSession()`, `buildQuoteExportPayload()`, `buildAssistantSessionSummary()`, `buildAssistantSessionContext()` | `move_to_helper_module` | Session-shaping logic is cross-cutting support behavior, not assistant policy. |
| Deterministic narrative and profile shaping | `inferQuoteTechnologyProfile()`, `buildDeterministicExpertSummary()`, `buildDeterministicConsiderationsFallback()`, `buildConsumptionExplanation()` | `move_to_helper_module` | The deterministic explanation layer has now been extracted into a bounded helper module; future context-pack convergence can build on that smaller surface area. |
| Quote markdown rendering helpers | `toMarkdownQuote()`, `fmt()`, `money()` | `move_to_deterministic_quote_logic` | Quote rendering belongs closer to deterministic quote output than to assistant control flow. |
| Generic service-unavailable fallback | `buildServiceUnavailableMessage()` | `move_to_helper_module` | This is reusable response fallback logic and should not stay inline by default. |

Exit criteria:

- each candidate helper is classified
- each move candidate is assigned a destination bucket
- the next implementation slice is bounded to one helper group at a time

Current read:

- the top-level orchestration flow is already in better shape than the helper layer
- the recent low-risk extraction wave validated the helper-module pattern for assistant-owned support logic without changing pricing behavior
- the next higher-value extraction area is now the boundary between deterministic narrative helpers and GenAI enrichment orchestration, because rendering, segmentation, assembly, and deterministic narrative shaping already have dedicated destinations

Recently validated slice:

- extracted `buildRegistryQuery()` into [request-query-helpers.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/request-query-helpers.js)
- extracted `formatAssumptions()` and `shouldKeepSourceAssumption()` into [quote-assumptions.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/quote-assumptions.js)
- extracted `buildServiceUnavailableMessage()` into [assistant-response-helpers.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/assistant-response-helpers.js)
- extracted the flex-comparison helper cluster into [flex-comparison-helpers.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/flex-comparison-helpers.js):
  - `isFlexComparisonRequest()`
  - `detectFlexComparisonModifier()`
  - `extractFlexShapes()`
  - `findLatestFlexComparisonPrompt()`
  - `extractFlexComparisonContext()`
  - `parseCapacityReservationUtilization()`
  - `parseBurstableBaseline()`
  - `parseStandaloneNumericAnswer()`
  - `parseOnDemandMode()`
- extracted the session/context helper cluster into [assistant-session-context.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/assistant-session-context.js):
  - `extractInlinePartNumbers()`
  - `summarizeQuoteForSession()`
  - `buildQuoteExportPayload()`
  - `buildAssistantSessionSummary()`
  - `buildAssistantSessionContext()`
- extracted the composite detection and segmentation helper cluster into [composite-quote-segmentation.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/composite-quote-segmentation.js):
  - `hasCompositeServiceSignal()`
  - `splitCompositeQuoteSegments()`
  - `shouldAppendGlobalHours()`
  - `normalizeCompositeSegment()`
- extracted the composite deterministic quote assembly cluster into [composite-quote-builder.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/composite-quote-builder.js):
  - `buildCompositeQuoteFromSegments()`
  - `choosePreferredQuote()`
  - `quoteSegmentWithCanonicalFallback()`
- extracted the assistant deterministic quote rendering cluster into [assistant-quote-rendering.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/assistant-quote-rendering.js):
  - `toMarkdownQuote()`
  - `fmt()`
  - `money()`
- extracted the assistant deterministic narrative/profile cluster into [assistant-quote-narrative.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/assistant-quote-narrative.js):
  - `inferQuoteTechnologyProfile()`
  - `buildDeterministicExpertSummary()`
  - `buildDeterministicConsiderationsFallback()`
  - `buildConsumptionExplanation()`
  - `classifyConsumptionGroup()`
  - `formatMoney()`
- extracted the assistant quote-enrichment support cluster into [assistant-quote-enrichment.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/assistant-quote-enrichment.js):
  - `buildQuoteEnrichmentContextBlock()`
  - `sanitizeQuoteEnrichment()`
  - `shouldAllowMigrationNotes()`
- extracted the assistant quote-narrative assembly cluster into [assistant-quote-assembly.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/assistant-quote-assembly.js):
  - `buildQuoteNarrativeLead()`
  - `buildQuoteNarrativeMessage()`
- extracted the deterministic quote payload builder into [quote-response-payload.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/quote-response-payload.js):
  - `buildDeterministicQuotePayload()`
- extracted the quote narrative/orchestration cluster into [assistant-quote-orchestrator.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/assistant-quote-orchestrator.js):
  - `buildGenAIQuoteEnrichment()`
  - `buildQuoteNarrative()`
- added focused unit coverage in:
  - [request-query-helpers.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/request-query-helpers.test.js)
  - [quote-assumptions.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/quote-assumptions.test.js)
  - [assistant-response-helpers.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/assistant-response-helpers.test.js)
  - [flex-comparison-helpers.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/flex-comparison-helpers.test.js)
  - [assistant-session-context.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/assistant-session-context.test.js)
  - [composite-quote-segmentation.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/composite-quote-segmentation.test.js)
  - [composite-quote-builder.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/composite-quote-builder.test.js)
  - [assistant-quote-rendering.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/assistant-quote-rendering.test.js)
  - [assistant-quote-narrative.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/assistant-quote-narrative.test.js)
  - [assistant-quote-enrichment.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/assistant-quote-enrichment.test.js)
  - [assistant-quote-assembly.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/assistant-quote-assembly.test.js)
  - [quote-response-payload.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/quote-response-payload.test.js)
  - [assistant-quote-orchestrator.test.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/test/assistant-quote-orchestrator.test.js)
- revalidated the affected routing, bundle, intent, follow-up, quote-export, deterministic-summary, sanitization, quote-assembly, quote-payload, quote-orchestration, and full server suites at `841 pass / 0 fail`

### Milestone 3. Structured Knowledge Pilot Targets

Status: pending

Scope:

- choose the first discovery-heavy families to pilot service blueprints

Recommended pilot set:

- `compute_vm_generic`
- `integration_oic`
- `database_base_db`
- `storage_block`
- `network_load_balancer`

Exit criteria:

- pilot families are frozen
- blueprint fields are defined before implementation starts

### Milestone 4. Pruning Rule For Future Coverage

Status: pending

Scope:

- define when a new parity case is required versus when an existing contract already covers the behavior

Exit criteria:

- new parity additions can be justified by contract value
- the suite does not grow only because a prompt phrasing changed

## Anti-Loop Guardrails

- if a slice does not classify branches or reduce assistant-owned policy, it is not boundary-strategy progress
- if a proposed refactor changes ownership but not behavior, require a bounded destination and exit criteria before editing code
- if a new test only duplicates an already-protected contract shape, do not count it as a milestone
- if a helper contains both orchestration and policy, split the inventory first and refactor only one side per slice

## Next Slice

The next concrete slice for this track is:

1. keep `assistant.js` responsible for quote-narrative orchestration while deterministic narrative support now lives in `assistant-quote-narrative.js`
2. define the next bounded cut between:
   - quote routing/orchestration in `assistant.js`
   - the routing helpers that invoke `buildQuoteNarrative()`
   - a reusable quote-routing adapter boundary
3. continue inventorying assistant-owned helpers that still encode policy after the narrative extraction is no longer inline
