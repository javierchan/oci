# Governed Offline Capture Workbook v2

## Purpose

The workbook downloaded from `GET /api/v1/exports/template/xlsx` is the formal
offline capture surface for OCI DIS Blueprint. It is generated on demand from
the same governed patterns, dictionaries, Service Product Library records,
limits, interoperability rules, and evidence freshness used by the App.

The workbook is intentionally usable by an analyst who does not yet understand
integration architecture, OCI services, or OCI DIS Blueprint. It explains the
workflow, provides examples outside the importable sheet, validates the most
important inputs, and preserves uncertainty rather than encouraging invented
values.

## Workbook Contract

| Sheet | Purpose | Imported |
|---|---|---|
| `Inicio` | Plain-language workflow, rules, and capture legend | No |
| `Catálogo de Integraciones` | Blank 500-row governed capture surface | Yes |
| `Validación Previa` | Formula-driven readiness and conditional checks | No |
| `Ejemplos Guiados` | One practical applicability example per active pattern | No |
| `Guía de Campos` | Field definition, examples, App usage, and missing-data impact | No |
| `Patrones` | Active tool-agnostic pattern library and OCI implementation guidance | No |
| `Servicios OCI` | Active normalized Service Product Library snapshot | No |
| `Límites OCI` | Active normalized service limits and official sources | No |
| `Interoperabilidad` | Active directional service compatibility rules | No |
| `_Listas` | Very-hidden validation lists and template manifest | No |

The capture sheet name and headers are a versioned contract. Template v2
workbooks with renamed or reordered headers are rejected. Unversioned v1
workbooks remain accepted and are labeled `legacy_v1_accepted` in the import
batch metadata.

## Data Ownership

- Column metadata: `capture_template_service.COLUMNS`.
- Pattern narratives and structured selection aids: `pattern_definitions`.
- Dropdowns: active `dictionary_options` and active pattern IDs.
- Product documentation: normalized Service Product Library tables.
- Limits: active `service_limits` only.
- Compatibility: active `service_interoperability_rules` only.
- Evidence dates and URLs: `service_evidence_sources`.

The download path never calls the internet. Verification Agent refreshes the
governed database separately; the workbook exports that reviewed snapshot.

## Safety And Integrity

- The importable sheet contains no example rows.
- Capture formulas are rejected before parsing.
- Generated reference text is neutralized when it begins with an Excel formula prefix.
- List validation uses workbook-defined names rather than inline CSV formulas.
- The `_Listas` manifest records template version, minimum importer version,
  generation timestamp, row capacity, and governed-source counts.
- Reference sheets are protected; the capture sheet remains editable.
- No macros, external workbook connections, credentials, or live web queries are present.

## Round-Trip Acceptance

The automated contract test generates the workbook, populates one capture row,
imports it through the real service, and asserts exactly one source/catalog row
with trigger, pattern, fan-out, payload, core tools, and overlays mapped. Browser
E2E additionally verifies metadata visibility and the downloaded filename from
the production-mode App.
