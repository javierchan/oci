# Governed External Import Intake

## Purpose

The official offline template is the only direct-import contract. A workbook without
its supported manifest is external evidence: it must be staged, mapped, reviewed,
and approved before it can create `CatalogIntegration` records or influence QA,
volumetry, topology, recommendations, or BOM.

## Lifecycle

```text
upload to object storage
  -> parse immutable source rows
  -> official template? materialize deterministically
  -> external workbook? Mapping review
  -> Import Correction Agent guidance + user decisions
  -> approve mapping contract
  -> materialize governed catalog rows
  -> QA and downstream calculations
```

`mapping_review` is a terminal hold for downstream calculations, not a failure.
The raw workbook and `SourceIntegrationRow.raw_data` remain immutable in MinIO and
PostgreSQL. Approval creates an auditable mapping contract; reprocessing uses the
same source rows rather than modifying their values.

The state is stored in the same bounded `ImportBatch.status` lifecycle as queued,
processing, completed, and failed work. Migration `20260717_0039` expands the
legacy column capacity so this explicit hold cannot degrade into a failed import.

When a user returns to the project Import route without an explicit `batch_id`, the
App restores the newest `mapping_review` batch. Its source rows, draft mapping,
semantic questions, formula evidence, and Import Correction Agent guidance remain
available across navigation and reloads. Completed historical batches stay in the
ledger and are opened only when the user explicitly selects them.

## Mapping Contract

Every source column is classified as one of:

- `mapped`: explicitly connected to one canonical application field.
- `candidate`: proposed from a governed header alias and requires review where the
  field has semantic or commercial impact.
- `evidence_only`: retained as lineage but never used by calculations.
- `unrecognized`: retained and surfaced to the user until it is intentionally
  classified.

The contract records source header, target field, unit, semantic role, aggregation
window, transformation, confidence, and decision rationale. It never infers a
formula merely from a numeric column name.

## Volumetry Safety

`payload_per_execution_kb` accepts a value only when the user confirms it is a
single-operation payload. Aggregate values such as `Volumetria actual` stay as
evidence unless their period, operation count, and fan-out semantics are explicitly
captured. A mapping review asks whether a total is per operation, daily, monthly,
or already includes destinations. Missing evidence blocks the mapping rather than
turning an aggregate into an unsafe payload estimate.

## Formula Safety

Official templates remain formula-free in the capture range and fail validation
when that contract is violated. External workbooks follow a separate evidence
policy so a client formula does not prevent the Import Correction Agent from
helping the user:

- Formula expressions and cached workbook values are preserved with their source
  coordinates, but the API never evaluates the expressions.
- Commercial formulas such as price and cost totals are classified as commercial
  evidence and cannot map into operational Catalog fields.
- Derived demand formulas such as calculated messages or executions remain
  evidence-only until the user supplies the underlying governed business meaning.
- A column containing only footer formulas can still map its non-formula rows; the
  formula rows are ignored during operational materialization.
- Formula-bearing workbooks never auto-apply a saved mapping profile. They return
  to mapping review because a formula can change the semantic boundary even when
  the visible headers are unchanged.

Summary rows such as Total, Subtotal, or Grand Total remain immutable source
evidence but are excluded from integration candidates when they contain no source,
destination, or integration identity.

## Import Correction Agent

The agent is advisory and conversational. It reads the staged contract, row samples,
dictionary candidates, and unmapped headers; it explains the risk and asks focused
questions. It cannot create a global dictionary option, approve a mapping, or
materialize catalog data. Deterministic services validate every approved target,
unit, alias, and formula boundary.

## Reusable Profiles

An approved external mapping can be saved as a project-scoped profile. A future
workbook auto-applies it only when the normalized header fingerprint matches exactly.
Profiles never become global defaults automatically; promotion requires separate
governance work and evidence.

## Acceptance Criteria

- Current and supported historical official templates still import directly.
- External files persist source rows but create no catalog rows before approval.
- Ambiguous payload, aggregate-volume, fan-out, and dictionary values generate
  explicit questions.
- External formulas are visible in the same Import review, are never executed, and
  cannot silently populate governed operational fields.
- The newest unresolved mapping review resumes after navigation or reload without
  requiring the user to recover a batch from history.
- A reviewer can map a column to a canonical target or evidence-only, save a
  profile, approve, and materialize rows exactly once.
- All decisions, profile use, and materialization are audit events.
