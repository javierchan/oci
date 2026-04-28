# UI Remediation Execution Plan

**Date:** 2026-04-17  
**Purpose:** Turn the audit findings into an execution-ready plan, confirm what is already complete, and define the next sequence for stabilization and follow-through.

## Current State

The originally open audit findings have been addressed in code during this pass. The immediate plan now shifts from discovery into verification, regression prevention, and cleanup of any secondary issues uncovered by the post-fix visual sweep.

## Workstreams

### Workstream 1 — Post-fix visual verification
- Re-run focused Playwright screenshots for the routes touched by this remediation.
- Compare new captures against the original audit screenshots in `docs/audit-screenshots/`.
- Confirm:
  - no duplicate heading behavior in the shell
  - project names render in nav
  - projects page remains usable on mobile
  - archive now requires explicit confirmation
  - admin patterns editing is visually less dense
  - capture wizard remains readable in dark mode

**Exit criteria:** no regressions on the touched routes and no new console errors introduced by the fixes.

### Workstream 2 — Accessibility and semantics hardening
- Re-run the quick a11y sweep on the touched routes.
- Confirm icon-only catalog actions announce correctly.
- Confirm each page still exposes a single meaningful `h1`.
- Confirm modal focus behavior remains correct for archive and delete actions.

**Exit criteria:** no known unlabeled action buttons on the audited routes and no duplicate top-level heading regressions.

### Workstream 3 — Capture flow consistency
- Inspect any remaining warning/success surfaces in the capture flow for token consistency.
- Keep moving hardcoded visual styles toward shared surface/text tokens when practical.
- Add regressions to the UI review checklist so future capture-flow work preserves dark-mode compatibility.

**Exit criteria:** capture flow follows the same tokenized visual system across main panels and step content.

### Workstream 4 — Admin surface polish
- Validate the hidden-table behavior in `admin/patterns` for both create and edit flows.
- If users still need quick context during editing, add a compact side summary instead of reopening the full table.
- Carry the same density rule to other admin screens if similar form-plus-table crowding exists.

**Exit criteria:** editing flows stay focused, with reference context available in a lightweight form.

## Priority Order

1. Post-fix Playwright smoke on touched routes
2. Accessibility/semantics sweep
3. Capture-flow consistency cleanup
4. Broader admin-surface density review

## Definition of Done

This remediation track is complete when:
- targeted Playwright verification is rerun after the fixes
- touched routes show no reopened audit findings
- frontend quality gates stay green
- backend quality gates stay green
- the remediation report and plan remain current with actual validated state

## Recommended Operating Rhythm

- Use the report in `docs/reports/ui-remediation-report-20260417.md` as the source of truth for what is fixed.
- Use this plan as the sequence for final verification and any follow-up polish.
- If new issues appear during the next Playwright pass, append them as net-new items instead of reopening already-resolved findings without evidence.
