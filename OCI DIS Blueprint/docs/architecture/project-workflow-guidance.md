# Project Workflow Guidance

## Intent

Project workflows must make the next governed action obvious without changing
the deterministic source of truth. This guidance layer derives presentation only
from the existing catalog count, QA totals, immutable sizing snapshots, dashboard
risks, and topology route.

## Ordered workflow

1. **Build inventory** — import a governed workbook or create a manual capture.
2. **Resolve QA** — open the bounded catalog queue for pending data or architect
   review; source rows and governed values remain auditable.
3. **Calculate baseline** — create an immutable technical snapshot only after the
   inventory is governed enough to size.
4. **Investigate topology** — use the current-scope dependency map, priority
   paths, and detail panel to understand risk.
5. **Prepare decision** — enter the explicit BOM workspace only after technical
   evidence is available.

The first incomplete or risky stage becomes the recommended next step. A user
may still navigate to any permitted route; the guide is never a workflow lock.

## UX ownership

- Project dashboard owns the next-action card and QA work queue.
- Workspace navigation groups project routes by user intent: build inventory,
  assess architecture, then decide.
- Catalog views are URL-addressable for sharing. User-saved working views are
  stored locally in the browser and are not governed project data.
- Map failures preserve the error message and offer an explicit retry. They must
  not be represented as an empty or healthy topology.
- Capture explains why its required identity fields are needed before data entry.
- Governance surfaces explain that future calculations use newly governed rules,
  while historical snapshots retain immutable provenance.

## Validation contract

The workflow derivation is pure and unit tested for empty inventory, unresolved
QA, missing technical baseline, and ready-to-investigate states. Rendered
validation covers both light and dark themes, keyboard-visible focus, and an
error/retry topology state. No workflow guide writes project data or changes
calculation, QA, pricing, or audit semantics.
