# Governed External Import Intake

## Purpose

The official offline template is the only direct-import contract. A workbook without
its supported manifest is external evidence: it must be staged, mapped, reviewed,
and approved before it can create `CatalogIntegration` records or influence QA,
volumetry, topology, recommendations, or BOM.

## Lifecycle

```text
official workbook upload
  -> Object Storage artifact
  -> parse immutable source rows
  -> mapping review when the template contract is external
  -> approve mapping contract
  -> materialize governed catalog rows

structured external evidence
  -> retain the client file outside the App
  -> stage source values + proposed canonical values through the API
  -> Import Correction Agent guidance
  -> line-by-line architect correction and approval
  -> explicit promotion through governed manual capture
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

## Structured External Capture Review

An analyst may need to demonstrate or migrate a real customer work-in-progress
catalog without treating its file format as an import contract. The
`/projects/{project_id}/external-capture` API provides this bounded path:

- `ExternalCaptureSession` stores customer identity, a source label, the SHA-256
  fingerprint, and the normalization policy. It never stores a local filesystem
  path or the source file.
- `ExternalCaptureDraft` stores the immutable source values separately from the
  editable canonical proposal, normalization evidence, row-level pattern
  assessment, required-field gaps, and QA preview.
- Every save revalidates the complete `ManualIntegrationCreate` contract and the
  active pattern registry. A missing value remains a visible gap.
- Approval is a human decision with rationale. Promotion is a second explicit
  action that calls the same governed manual-capture service used by the App.
- The Import Correction Agent reads aggregate and row-level evidence from this
  session. It can prioritize decisions, but cannot approve or promote a row.

The associated **Capture Review** workspace is deliberately different from the
workbook Import page. Import governs files accepted by the App; Capture Review
governs already-structured evidence supplied through an API or controlled
analyst workflow.

### Demonstration policy

For the **ADN - Retail Merchandising** customer exercise:

- customer: **Innovación y Conveniencia, S.A. de C.V.**
- every proposal uses `TBQ=Y`, while the original TBQ value remains source evidence;
- `Tamaño KB` is proposed as KB per execution and remains reviewable;
- frequency and complexity use only active dictionary values;
- every row has an independent pattern recommendation and rationale;
- no workbook is uploaded to App storage;
- no row is automatically approved or promoted.

## Acceptance Criteria

- Current and supported historical official templates still import directly.
- External files persist source rows but create no catalog rows before approval.
- Ambiguous payload, aggregate-volume, fan-out, and dictionary values generate
  explicit questions.
- External formulas are visible in the same Import review, are never executed, and
  cannot silently populate governed operational fields.
- The newest unresolved mapping review resumes after navigation or reload without
  requiring the user to recover a batch from history.
- Structured evidence sessions survive navigation and expose source values,
  canonical proposals, required gaps, pattern recommendations, and agent guidance.
- Local customer files and local paths never enter App storage or API responses.
- A structured row can enter the catalog only after schema validation, explicit
  architect approval, and explicit promotion.
- A reviewer can map a column to a canonical target or evidence-only, save a
  profile, approve, and materialize rows exactly once.
- All decisions, profile use, and materialization are audit events.
