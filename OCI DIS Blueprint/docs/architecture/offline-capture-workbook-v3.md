# Governed Offline Capture Workbook v3.1

## Purpose

`GET /api/v1/exports/template/xlsx` returns the formal en-US offline capture
surface for OCI DIS Architect. It is generated from the same governed patterns,
dictionaries, Service Product Library, limits, interoperability rules, and
reviewed evidence used by the App.

The workbook is designed for users who may not yet understand integration
architecture, OCI services, or the App. It explains the workflow, keeps examples
outside the importable sheet, validates important inputs, and preserves missing
information without inventing values.

## Workbook Contract

| Sheet | Purpose | Imported |
|---|---|---|
| `Start Here` | Plain-language workflow, rules, and capture legend | No |
| `Dashboard` | Offline progress, criticality distribution, and pending decisions | No |
| `Client Catalogs` | Editable customer vocabulary used as dropdown suggestions | No |
| `Integration Catalog` | Blank 500-row governed capture surface | Yes |
| `Preflight Validation` | Formula-driven readiness and conditional checks | No |
| `Guided Examples` | Practical applicability example per active pattern | No |
| `Field Guide` | Definitions, examples, App usage, and missing-data impact | No |
| `Patterns` | Certified tool-agnostic patterns and OCI implementation guidance | No |
| `OCI Services` | Active normalized Service Product Library snapshot | No |
| `OCI Limits` | Active normalized service limits and official sources | No |
| `Interoperability` | Active directional service compatibility rules | No |
| `_Lists` | Very-hidden validation lists and template manifest | No |

The capture sheet and headers are a versioned contract. Current v3.1 workbooks
with renamed or reordered headers are rejected. Unversioned v1, governed v2, and
Spanish v3.0 workbooks remain accepted and receive an explicit compatibility
label in import metadata.

`TBQ` controls commercial eligibility, not technical inclusion. `Y` includes the
integration in governance and BOM/pricing. `N` keeps it in Catalog, QA, topology,
Canvas, and technical volumetry while excluding it from the economic exercise.
The known `Duplicado 2` source defect is rejected from the active catalog and
retained only in immutable source lineage.

Legacy `Uncertainty` and `Proceso de Negocio DueDiligence` columns are accepted
for backward compatibility but ignored. Business Process is the sole canonical
business-process field, and evidence gaps are represented by missing governed
inputs and QA findings rather than a free-form confidence field.

## Data Ownership

- Column metadata: `capture_template_service.COLUMNS`.
- Pattern narratives and selection aids: `pattern_definitions`.
- Dropdowns: active dictionaries, pattern IDs, and editable client catalogs.
- Product documentation: normalized Service Product Library tables.
- Limits: active `service_limits`.
- Compatibility: active `service_interoperability_rules`.
- Evidence dates and URLs: `service_evidence_sources`.

The download path does not call the internet. The Service Verification Agent
refreshes governed evidence separately; the workbook exports only the reviewed
database snapshot.

## Safety And Integrity

- The importable sheet contains no example rows.
- Capture formulas are rejected before parsing.
- Generated reference text is neutralized when it starts with a formula prefix.
- List validation uses workbook-defined names rather than inline CSV formulas.
- `_Lists` records template version, minimum importer version, generation time,
  capacity, and governed-source counts.
- Reference sheets are protected; the capture sheet remains editable.
- No macros, external connections, credentials, or live web queries are present.

## Round-Trip Acceptance

Automated contract tests generate v3.1, populate a Y and an N row, import both,
assert technical inclusion and commercial eligibility, and verify that the two
removed legacy columns are absent. Separate fixtures prove that historical
Spanish workbooks still import while those fields are ignored.
