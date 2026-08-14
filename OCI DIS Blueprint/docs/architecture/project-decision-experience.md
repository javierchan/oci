# Project Decision Experience

## Purpose

The project dashboard now composes existing governed evidence into an operational
decision layer. It does not introduce a new calculation, commercial approval, or
system of record.

## Delivered capabilities

- **Decision Brief:** derives a readiness state from the latest immutable
  technical snapshot, QA, payload-evidence confidence, and priority attention.
- **Attention Center:** ranks explicit QA gaps, dashboard risks, graph paths,
  coverage gaps, and the latest BOM publication state. Each item links to its
  existing evidence surface.
- **Critical topology routes:** the map selects the requested shared path, or
  highlights the three highest-risk paths on its initial project load.
- **Guided / Expert:** a durable browser preference. Guided retains the same
  governed routes and evidence while suppressing advanced dashboard density;
  Expert retains the complete technical surface.
- **Goal onboarding:** project-local, durable intent selection routes a user to
  import, QA, sizing, or BOM work without a generic product tour.
- **Shared views:** catalog filters and topology focus can be saved as shared,
  project-scoped views as well as copied as URLs.
- **Change and adoption signals:** the dashboard compares consecutive immutable
  technical/dashboard snapshots and labels audit-derived activity truthfully.

## Governance boundaries

The decision layer is presentation-only. It reuses existing routes for catalog
mutations, AI-review recommendation acceptance, scenario simulation, BOM review,
and publication. It never infers a commercial approval or modifies governed
records. Activity signals are audit-derived and are explicitly not productivity
or cost-savings metrics.

## Governed coordination persistence

Shared views persist only labels and explicit filter/focus state; their catalog,
graph, and snapshot evidence remains authoritative. Creating or deleting a view
emits an `AuditEvent`.

The Attention Center may create a project-scoped coordination task for an existing
deterministic item. It carries an evidence link, assignee, due date, status, note,
and resolution evidence. It is deliberately not an approval and cannot alter QA,
topology, technical sizing, AI proposals, or BOM publication. Resolution requires
concise evidence and every task mutation is audited. Overdue status is derived at
read time; this feature does not claim notifications or external escalation.

## Validation

- Unit tests cover deterministic attention and decision derivation.
- The frontend TypeScript, ESLint, and production build gates remain authoritative.
- Visual checks cover the Dashboard decision path and Guided/Expert state. Map
  data uses the existing catalog graph API; local browser environments must be
  able to reach the configured public API base for full graph rendering.
