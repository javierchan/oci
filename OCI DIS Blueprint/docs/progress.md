## M11 — Navigation + Color System + Light/Dark Theme

**Completed:** 2026-04-14
**Status:** ✅ Complete

### What was implemented

- `apps/web/components/breadcrumb.tsx` — reusable breadcrumb navigation for project and admin pages
- `apps/web/lib/use-theme.ts` and `apps/web/components/theme-toggle.tsx` — persistent light, dark, and system theme switching
- `apps/web/app/layout.tsx` and `apps/web/app/globals.css` — no-flash theme initialization and semantic color tokens for shared surfaces, badges, and tables
- `apps/web/components/qa-badge.tsx`, `apps/web/components/pattern-badge.tsx`, and `apps/web/components/complexity-badge.tsx` — semantic badge styling driven by the color token system
- Breadcrumbs added across projects, dashboard, import, catalog, detail, capture, graph, and admin routes
- Contextual actions added on the integration detail page and catalog row actions updated to support direct view and edit navigation
- Admin governance pages, forms, and integration detail lineage cards updated to use theme-aware surfaces and contrast-safe table styling

### Verification results

```text
TypeScript: 0 errors
ruff: All checks passed!
pytest: 26 passed, 2 warnings
docker compose ps: 6/6 containers Up
Page reachability:
200 /projects
200 /projects/4ae6fef1-61c2-4df0-bdfc-f25148365a9d
200 /projects/4ae6fef1-61c2-4df0-bdfc-f25148365a9d/import
200 /projects/4ae6fef1-61c2-4df0-bdfc-f25148365a9d/catalog
200 /projects/4ae6fef1-61c2-4df0-bdfc-f25148365a9d/catalog/48728494-d042-4124-a272-eb9bc47b2dce
200 /projects/4ae6fef1-61c2-4df0-bdfc-f25148365a9d/capture
200 /projects/4ae6fef1-61c2-4df0-bdfc-f25148365a9d/capture/new
200 /projects/4ae6fef1-61c2-4df0-bdfc-f25148365a9d/graph
200 /admin
200 /admin/patterns
200 /admin/dictionaries
200 /admin/assumptions
```

### Gaps / known limitations

None

---
