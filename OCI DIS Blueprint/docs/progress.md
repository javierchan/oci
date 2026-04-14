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

## M13 — Integration Design Canvas

**Completed:** 2026-04-14
**Status:** ✅ Complete

### What was implemented

- `apps/web/components/integration-canvas.tsx` — reactive architecture-flow canvas that renders source, selected OCI tool nodes, and destination in canonical left-to-right order
- `apps/web/components/integration-patch-form.tsx` — canvas integration directly below the core-tools selector so unsaved pattern and tool changes update the design preview immediately
- Client-side execution and billing estimates added to the canvas annotation strip to show payload, OIC billing messages, and destination context without requiring a save round-trip

### Verification results

```text
TypeScript: 0 errors
Detail route reachability: OK
docker compose ps: 6/6 containers Up
```

### Gaps / known limitations

None

---

## M12 — Source Lineage + Template

**Completed:** 2026-04-14
**Status:** ✅ Complete

### What was implemented

- `apps/api/app/schemas/catalog.py` and `apps/api/app/services/catalog_service.py` — lineage responses now include `column_names` and `import_batch_date`, with canonical field labels derived from the stored import header map
- `apps/web/app/projects/[projectId]/catalog/[integrationId]/page.tsx` — source lineage now renders human-readable field names, hides empty columns by default, and exposes a `Show all columns` toggle
- `apps/api/app/routers/exports.py` and `apps/api/app/services/export_service.py` — added `GET /api/v1/exports/template/xlsx` to generate the offline capture workbook with instructions, styled headers, example row, validations, and frozen panes
- `apps/web/components/import-upload.tsx` — added the download action for the capture template directly on the import screen
- `apps/web/lib/types.ts` — updated frontend lineage contracts for the new API shape

### Verification results

```text
TypeScript: 0 errors
ruff: All checks passed!
pytest: 26 passed, 2 warnings
docker compose ps: 6/6 containers Up
Lineage smoke:
- column_names present: True
- import_batch_date present: True
Template smoke:
- bytes returned: 6314
- header row starts with: ['#', 'ID de Interfaz', 'Marca', 'Proceso de Negocio', 'Interfaz']
- example row TBQ: Y
- freeze panes: A6
Template import smoke:
- import status: completed
- loaded count: 1
- excluded count: 0
```

### Gaps / known limitations

None

---
