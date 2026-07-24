# Commercial Review Work Queue

## Purpose

M71 adds an operational work queue to Admin Pricing so the governed global OCI
catalog can be reviewed in a deterministic order. It does not create a second
commercial authority and it cannot approve, reject, resolve, promote, or publish
commercial artifacts.

The queue projects three existing sources from the active approved global
commercial release:

- open `CommercialException` records;
- `CommercialMappingCandidate` records still blocked or pending review; and
- `ProductCoverageCandidate` records still pending review and sourced from the
  same commercial document.

If there is no approved, validated release whose metadata scope is
`global_oci_catalog`, the queue is empty. Browser fixtures and narrower releases
cannot silently become the operational source.

## Authority boundary

The existing candidate, exception, product-coverage, and release review routes
remain the only commercial decision paths. The work queue stores only:

- assignee;
- operational state: `unassigned`, `assigned`, `in_progress`, or
  `waiting_evidence`;
- due date;
- an operational note; and
- the actor who last updated the assignment.

There is deliberately no `approved`, `resolved`, `rejected`, `completed`, or
`published` state in this model. When an authoritative source item reaches a
terminal disposition through its existing governed route, it naturally leaves
the unresolved queue.

## Deterministic priority

Priority is computed at read time. It schedules review and never represents
commercial confidence or approval.

| Signal | Points |
|---|---:|
| High / medium / low exception severity | 80 / 50 / 20 |
| Mapping disposition required | 40 |
| Product coverage ready / blocked by release / blocked by evidence | 80 / 60 / 30 |
| Part number participates in an approved BOM mapping | 30 |
| Dependency, relationship, or entitlement blocker | 25 |
| Governed blockers | 5 each, capped at 20 |
| Operational due date passed | 20 |

The resulting tiers are:

- urgent: 120 or more;
- high: 90–119;
- normal: 50–89; and
- low: below 50.

Every queue row returns the individual signals and points so an Admin can explain
why it was ordered. Stable sorting uses score, due date, source creation date,
entity type, and entity identifier.

## Persistence and audit

`commercial_review_assignments` has one row per `(entity_type, entity_id)`.
Assignments are independent of source records and are replaced atomically.
Every mutation emits `commercial_review_assignment_updated` with the old and new
operational values. Prompt, response, pricing, and customer content are not
introduced by this workflow.

## API

- `GET /api/v1/pricing/review-work-queue`
  returns the global-release identity, unfiltered operational summary, filtered
  page, priority signals, ownership, and recommended governed next action.
- `PATCH /api/v1/pricing/review-work-queue/{entity_type}/{entity_id}`
  replaces operational ownership for an unresolved item and returns its updated
  queue projection.

Both routes require the Admin role. The write route rejects inactive or missing
source items and inconsistent states such as `in_progress` without an assignee.

## UI

Admin Pricing → Decisions renders the queue before the existing decision controls.
Admins can search and filter by artifact type, priority, and operational state,
inspect the priority evidence, and update ownership. A direct action scrolls to
the existing governed review controls; the queue itself contains no disposition
button.

## Validation contract

Completion requires:

- migration upgrade to head and downgrade-chain integrity;
- focused queue API tests covering global-release isolation, deterministic
  priority, filters, RBAC, assignment validation, audit, and unchanged source
  disposition;
- full API, frontend unit, TypeScript, ESLint, Ruff, mypy, OpenAPI, and production
  build gates;
- healthy production Docker services;
- live API reconciliation against the current global catalog; and
- browser verification of assignment persistence, responsive light/dark layout,
  and zero console errors.
