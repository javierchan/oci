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

- `Project.customer_name` is the governed customer identity for the complete
  workspace and is required for every new project. It is shown consistently in
  project, dashboard, and review surfaces and can be changed only through the
  audited project update contract.
- `ExternalCaptureSession` stores customer identity, a source label, the SHA-256
  fingerprint, and the normalization policy for one source submission. Its
  `client_name` preserves source evidence and does not replace the project-level
  customer authority. It never stores a local filesystem path or the source file.
- `ExternalCaptureDraft` stores immutable **supported** source inputs separately
  from the editable canonical proposal, normalization evidence, row-level pattern
  assessment, required-field gaps, and QA preview. Formulas and fields without a
  governed App target are removed before persistence; only their header,
  classification, and exclusion reason remain as value-free audit metadata.
- Every save revalidates the complete `ManualIntegrationCreate` contract and the
  active pattern registry. A missing value remains a visible gap.
- The row-level Import Correction Agent compares received evidence against the
  current App schema, active dictionaries, governed patterns, selected-pattern
  certification, and deterministic QA facts. It may detect interpretation
  deviations beyond known QA codes, but every executable correction is constrained
  to an existing typed App field, grounded evidence, and formula-free values.
- Every analysis is persisted with a fingerprint of the evidence it evaluated.
  Editing a row makes that analysis stale. A current grounded analysis is required
  before approval.
- Applying the correction draft, approving or rejecting the row, and promoting an
  approved record are separate human actions. Promotion calls the same governed
  manual-capture service used by the App.
- A reviewer may apply one current correction draft, an explicit selected set, or
  every currently eligible draft. Bulk execution is only orchestration over the
  same per-row evidence-hash and typed-patch boundary; it does not start inference,
  widen evidence, invent values, or change approval and promotion state.
- Bulk results report applied, skipped, and failed items independently. A skipped
  row remains visible with a bounded reason such as missing, stale, degraded, or
  human-decision-required analysis; one row cannot make another row eligible.
- Every applied correction invalidates its prior evidence fingerprint and returns
  the row to analysis-required state. The reviewer must run a new grounded analysis
  before any separate approval action becomes available.
- The Import Correction Agent reads aggregate and row-level evidence from this
  session. It explains why a line needs review and can propose a clean mapping,
  but cannot authorize its own correction, approve, reject, or promote a row.

The associated **Capture Review** workspace is deliberately different from the
workbook Import page. Import governs files accepted by the App; Capture Review
governs already-structured evidence supplied through an API or controlled
analyst workflow.

### Customer-held evidence policy

- Customer identity comes only from the governed `Project.customer_name`; a source
  label or capture session cannot replace it.
- The customer workbook stays outside App storage. Local parsing may stage supported
  structured evidence through External Capture, but it must never persist a local
  path or silently upload the file to Object Storage.
- A session may override TBQ only when its recorded normalization policy explicitly
  requires that transformation. Otherwise the received supported value is preserved,
  and a missing or unsupported value remains a human decision.
- Payload, frequency, complexity, tools, and pattern evidence map only when the
  current typed App contract and governed dictionaries support the interpretation.
- A source pattern is not a recommendation. When no grounded recommendation exists,
  the UI and agent contract must state that the recommendation is pending rather
  than manufacturing a source-to-proposal change.
- Every row has an independent explanation and decision boundary. No workbook row is
  automatically corrected, approved, rejected, or promoted.
- A focused row analysis is a strict single-row privacy boundary. Session sample
  rows must be empty, and model proposals that merely repeat the current App record
  are retained only as no-op diagnostics rather than executable correction drafts.
- Before OCI Generative AI receives customer-derived evidence, the operator must
  obtain explicit consent that names the configured destination, region, model, and
  the exact sanitized evidence fields.

## Acceptance Criteria

- Current and supported historical official templates still import directly.
- External files persist source rows but create no catalog rows before approval.
- Ambiguous payload, aggregate-volume, fan-out, and dictionary values generate
  explicit questions.
- External formulas are represented only by value-free exclusion metadata, are
  never persisted as operational row data, never executed, and cannot populate a
  governed field or agent correction draft.
- The newest unresolved mapping review resumes after navigation or reload without
  requiring the user to recover a batch from history.
- Structured evidence sessions survive navigation and expose supported source
  values, value-free exclusions, canonical proposals, required gaps, pattern
  recommendations, and persisted row-level agent guidance.
- Local customer files and local paths never enter App storage or API responses.
- A structured row can enter the catalog only after schema validation, a current
  grounded row analysis, explicit architect approval, and explicit promotion.
- A reviewer can map a column to a canonical target or evidence-only, save a
  profile, approve, and materialize rows exactly once.
- All decisions, profile use, and materialization are audit events.
