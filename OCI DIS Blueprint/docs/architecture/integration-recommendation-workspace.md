# Prescriptive Recommendation And Draft Simulation Workspace

## Purpose

The workspace turns governed reviews into bounded architecture decisions. An
integration review compares the saved canvas with up to three governed
alternatives, while project, topology, and BOM reviews expose typed actions that
explain what to change, how to implement it, how to validate it, and what impact
to expect.

The workspace never lets an LLM invent topology, service limits, quantities, or
prices. It is advisory until an architect explicitly saves a validated draft.

## Decision Flow

1. The deterministic engine reads the integration, Canvas V4 state, selected
   pattern, trigger, payload, frequency, G01-G18 combinations, normalized Service
   Products, limits, and interoperability rules.
2. It creates at most three valid candidates: minimum change, higher resilience,
   and lower service footprint. Identical candidates are removed.
3. Each candidate receives a typed canvas diff, implementation sequence,
   prerequisites, validation plan, evidence IDs, compatibility checks, and a
   truthful cost boundary.
4. OCI Generative AI compares and explains only those candidates. It cannot add a
   new alternative or claim an uncomputed cost.
5. `Preview on canvas` records an audit decision and returns the candidate without
   mutating `CatalogIntegration`.
6. The App displays the candidate as a dashed, read-only overlay. `Apply to draft`
   changes only local unsaved canvas state; `Save canvas` remains the explicit
   governed mutation.
7. `Simulate impact` evaluates the unsaved connected draft through the same
   deterministic volumetry and BOM engines used by persisted jobs. It writes no
   catalog row, volumetry snapshot, BOM snapshot, or audit decision.
8. Commercial simulation uses an explicitly selected approved deployment
   scenario, or the latest approved project scenario. It reports monthly,
   contractual, and ramp deltas only when pricing coverage is complete.
9. Explicit-unit plans remain authoritative. Existing product quantities are
   preserved; a newly introduced product is a sizing requirement, never an
   invented client quantity. The architect must still save, recalculate, and
   publish through the governed workflows.

## Authority Boundaries

| Concern | Authority |
|---|---|
| Valid candidate topology | Deterministic G01-G18 and Canvas semantics |
| OCI limits and interoperability | Normalized Service Product rules |
| Candidate comparison and explanation | OCI Generative AI |
| Volumetry | Deterministic calculation engine |
| Monthly and contractual cost | Deterministic pricing and BOM engines |
| Final design decision | Authenticated architect action and audit trail |

## API Contract

Integration-scope AI Review results may contain `recommendation_workspace` with
the saved state, recommendation basis, recommended candidate ID, and candidate
list. Candidate selection uses:

`POST /api/v1/ai-reviews/{job_id}/recommendations/{candidate_id}/select-draft`

The endpoint requires a mutation-capable role, rejects incomplete or blocked
reviews, records only the selected candidate and typed diff in audit evidence,
and returns the candidate. It does not write canvas or architect fields.

An unsaved connected draft can be evaluated with:

`POST /api/v1/ai-reviews/projects/{project_id}/integrations/{integration_id}/simulate-draft`

The response contains saved-versus-proposed row metrics, consolidated project
metrics, rule provenance, design warnings, and an optional commercial section.
Commercial results are bound to an approved deployment scenario and contain the
monthly series used to derive contract and ramp deltas. `persisted` is always
`false` for this endpoint.

Project and topology reviews may contain `action_workspace`. Published BOM
snapshots expose the same typed workspace. Each action contains a priority,
status, rationale, implementation sequence, validation plan, expected impact,
evidence references, confidence, and a governed App deep link.

## UX Contract

- Recommendation cards lead with intent, governed combination, confidence, and
  typed topology changes.
- Every candidate exposes deterministic checks and a concrete implementation and
  validation plan.
- Commercial copy distinguishes computed deltas, incomplete price coverage,
  missing approved scenarios, and explicit-unit quantities that require sizing.
- The canvas labels animated edges as modeled direction; the animation is not
  runtime telemetry and honors reduced-motion preferences.
- Selected components expose editable labels and notes plus governed role,
  pricing basis, SLA, and key limit context.
- Pattern changes remain a separate architect-owned confirmation.

## Validation

Required gates are the focused AI Review API contract, Ruff, mypy, frontend unit
tests, strict TypeScript and ESLint, Node 26 production build, generated OpenAPI,
production Docker health, and browser flows that run a real integration review,
preview a candidate, apply it to an unsaved draft, simulate technical and
commercial impact, inspect project/topology/BOM actions, and verify no automatic
catalog or snapshot mutation.
