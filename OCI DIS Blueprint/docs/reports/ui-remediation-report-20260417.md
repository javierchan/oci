# UI Remediation Report

**Date:** 2026-04-17  
**Scope:** Resolve the open frontend issues identified in the full Playwright + static UI audit and document the outcome.

## Summary

This remediation pass addressed the open issues carried forward from the audit backlog across the application shell, projects list, catalog table, capture wizard, and admin patterns workspace. The goal of this pass was to eliminate the user-visible regressions and workflow issues that were already confirmed by screenshots, console output, and static inspection.

## Issues Resolved

### 1. Sidebar duplicate heading and missing project context
- **Status:** Resolved
- **Problem:** The shell sidebar rendered a top-level `h1`, creating duplicate page-level heading semantics, and the "Current Project" card showed the raw UUID instead of a human-readable project name.
- **Fix:** Replaced the sidebar brand `h1` with a non-heading text element and added a client-side project lookup so the nav displays the live project name with UUID fallback and truncation.
- **Files:** `apps/web/components/nav.tsx`

### 2. Dark-mode hydration mismatch warning
- **Status:** Resolved
- **Problem:** Theme initialization could set the `dark` class before hydration, causing React hydration warnings on the root HTML element.
- **Fix:** Added `suppressHydrationWarning` to the root `<html>` element while preserving the existing pre-hydration theme initialization script.
- **Files:** `apps/web/app/layout.tsx`

### 3. Projects page mobile clipping and cramped layout
- **Status:** Resolved
- **Problem:** The projects list relied on a wide desktop table, which clipped and degraded usability on small screens.
- **Fix:** Added a dedicated mobile card layout and restricted the full table to `md+` breakpoints.
- **Files:** `apps/web/components/projects-page-client.tsx`

### 4. Archive action mutating immediately without confirmation
- **Status:** Resolved
- **Problem:** Archive executed immediately, while delete already had a confirm modal. This made the archive workflow inconsistent and too easy to trigger by accident.
- **Fix:** Added an archive confirmation modal using the shared `ConfirmModal` pattern.
- **Files:** `apps/web/components/projects-page-client.tsx`

### 5. Raw network error copy in project mutations
- **Status:** Resolved
- **Problem:** Failed project mutations could surface raw transport errors such as `Failed to fetch`.
- **Fix:** Added friendlier mutation error messaging that explains the likely local-stack issue while preserving specific API messages when available.
- **Files:** `apps/web/components/projects-page-client.tsx`

### 6. Catalog icon-only action buttons missing accessible labels
- **Status:** Resolved
- **Problem:** Icon-only edit buttons in the catalog table did not expose accessible names.
- **Fix:** Added contextual `aria-label` values to both mobile and desktop pencil buttons.
- **Files:** `apps/web/components/catalog-table.tsx`

### 7. Capture wizard still using light-only slate/white presentation
- **Status:** Resolved
- **Problem:** The wizard and preview surfaces still leaned on hardcoded `slate-*` and `bg-white` classes, reducing dark-mode consistency.
- **Fix:** Reworked the capture wizard, review panels, QA preview, OIC preview, and key step forms to use the shared tokenized surfaces and text colors. Warning/success states were kept but now include dark-mode support where needed.
- **Files:**  
  `apps/web/components/capture-wizard.tsx`  
  `apps/web/components/capture-step-identity.tsx`  
  `apps/web/components/capture-step-source.tsx`  
  `apps/web/components/capture-step-destination.tsx`  
  `apps/web/components/capture-step-technical.tsx`  
  `apps/web/components/capture-step-review.tsx`  
  `apps/web/components/qa-preview.tsx`  
  `apps/web/components/oic-estimate-preview.tsx`

### 8. Admin patterns edit mode too dense
- **Status:** Resolved
- **Problem:** The edit/create form and the full pattern table rendered together, producing a crowded admin experience and pushing the active form too far down the page.
- **Fix:** Collapsed the directory table while a pattern form is open and replaced it with a focused status card explaining the table is intentionally hidden during editing.
- **Files:** `apps/web/app/admin/patterns/page.tsx`

## Validation

### Frontend
- `cd apps/web && npx tsc --noEmit --skipLibCheck`
  - Result: passed with exit code `0`
- `cd apps/web && npx eslint . --ext .ts,.tsx --max-warnings 0`
  - Result: passed with exit code `0`

### Backend
- `cd apps/api && ./.venv/bin/python -m pytest --tb=short -q`
  - Result: `20 passed`
- `cd apps/api && ./.venv/bin/python -m ruff check .`
  - Result: `All checks passed!`

### Targeted verification
- Confirmed no remaining `window.confirm()` usage in `apps/web`.
- Confirmed catalog action buttons now expose `aria-label`.
- Confirmed the layout now uses `suppressHydrationWarning`.
- Confirmed the nav renders formatted project labels instead of always showing the raw UUID.

## Residual Risk

- This pass resolves the open issues already called out in the audit backlog, but a fresh visual sweep is still recommended to capture any secondary spacing or contrast regressions introduced by the new responsive and tokenized styling.
- The capture wizard now uses token-aware surfaces in its main panels, but future component additions in that flow should continue following the same tokenized approach to avoid reintroducing light-only styling drift.

## Recommended Next Step

Run a focused post-fix Playwright smoke pass on:
- `/projects`
- `/projects/[projectId]`
- `/projects/[projectId]/capture/new`
- `/projects/[projectId]/catalog`
- `/admin/patterns`

This will close the loop between the remediation code and the original screenshot-based findings.
