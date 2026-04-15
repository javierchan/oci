# Codex Task — Browser Test Findings: Bug Fixes + UX Enhancements

## Situation

A full browser walkthrough of the running application identified 5 bugs and 7 UX
enhancements. This task fixes all of them. No new features. No database schema changes.
No new npm packages unless explicitly listed below.

**Read before writing any code:**
1. `apps/web/app/globals.css` — CSS variable token system and dark mode overrides
2. `apps/web/lib/use-theme.ts` — theme hook and localStorage persistence
3. `apps/web/app/layout.tsx` — no-flash script in `<head>`
4. `apps/web/app/projects/[projectId]/catalog/[integrationId]/page.tsx` — detail page layout
5. `apps/web/app/projects/[projectId]/capture/new/page.tsx` — capture wizard
6. `apps/web/components/capture-wizard.tsx` — wizard step components
7. `apps/web/app/projects/[projectId]/graph/page.tsx` — graph page
8. `apps/web/app/projects/page.tsx` — projects list
9. `apps/web/app/projects/[projectId]/import/page.tsx` — import page
10. `apps/web/app/admin/page.tsx` — admin hub

Execute fixes in the order listed. Verify each fix before moving to the next.
Run `npx tsc --noEmit --skipLibCheck` after every section — must stay at 0 errors throughout.

---

## BUG-01 — Dark mode: form inputs have white background [HIGH]

**Affected files:**
- `apps/web/components/capture-wizard.tsx` — all `<input>`, `<select>`, `<textarea>`
- `apps/web/app/projects/[projectId]/catalog/[integrationId]/page.tsx` — patch form inputs
- Any other component that renders `<input>`, `<select>`, or `<textarea>` with hardcoded
  `bg-white` or no dark variant

**Fix — global baseline in `apps/web/app/globals.css`:**

Add after the existing `:root` and `.dark` blocks:

```css
/* ── Form element dark mode baseline ─────────────────────────────── */
input,
select,
textarea {
  background-color: var(--color-surface);
  color: var(--color-text-primary);
  border-color: var(--color-border);
}

.dark input,
.dark select,
.dark textarea {
  background-color: var(--color-surface-2);
  color: var(--color-text-primary);
  border-color: var(--color-border);
}

/* Placeholder text */
.dark input::placeholder,
.dark textarea::placeholder {
  color: var(--color-text-muted);
}

/* Select arrow color in dark mode */
.dark select {
  color-scheme: dark;
}
```

**Additionally**, grep for `bg-white` in all `.tsx` files under `apps/web/components/`
and `apps/web/app/`. For every `bg-white` on an input, select, or textarea element,
replace with `bg-[var(--color-surface)] dark:bg-[var(--color-surface-2)]`.

```bash
grep -rn "bg-white" apps/web/components/ apps/web/app/ --include="*.tsx" | grep -i "input\|select\|textarea\|form"
```

**Verify:** Switch to Dark mode. Open Capture wizard Step 1 and Step 4. All input fields
must have a dark background with visible placeholder text.

---

## BUG-02 — Dark mode: Dashboard QA Breakdown cards have white/light background [MEDIUM]

**Affected file:** `apps/web/app/projects/[projectId]/page.tsx` (dashboard page)

The OK / REVISAR / PENDING stat cards use hardcoded light color backgrounds (green, yellow,
gray) that have no dark variant.

**Fix:** Find the QA breakdown card elements. Replace any hardcoded color classes with
CSS variable-based tokens:

```tsx
// BEFORE (example):
<div className="bg-green-50 border border-green-200 rounded-lg p-4">

// AFTER:
<div className="bg-[var(--color-qa-ok-bg)] border border-[var(--color-qa-ok-text)]/20
                rounded-lg p-4 text-[var(--color-qa-ok-text)]">
```

Apply the same pattern to REVISAR (yellow) and PENDING (gray) cards using the existing
`--color-qa-*` CSS variables already defined in `globals.css`.

If `--color-qa-ok-bg`, `--color-qa-revisar-bg`, etc. are not yet defined for both
`:root` and `.dark`, add them now:

```css
:root {
  --color-qa-ok-bg:       #dcfce7;
  --color-qa-ok-text:     #15803d;
  --color-qa-revisar-bg:  #fef9c3;
  --color-qa-revisar-text:#92400e;
  --color-qa-pending-bg:  #f1f5f9;
  --color-qa-pending-text:#475569;
}

.dark {
  --color-qa-ok-bg:       #052e16;
  --color-qa-ok-text:     #86efac;
  --color-qa-revisar-bg:  #422006;
  --color-qa-revisar-text:#fcd34d;
  --color-qa-pending-bg:  #1e293b;
  --color-qa-pending-text:#94a3b8;
}
```

**Verify:** Dashboard in dark mode — OK/REVISAR/PENDING cards must have dark backgrounds
and remain readable.

---

## BUG-03 — Phantom scroll space on Integration detail page [HIGH]

**Affected file:** `apps/web/app/projects/[projectId]/catalog/[integrationId]/page.tsx`

Scrolling below the Source Lineage section reveals ~400px of blank space. The Integration
Design Canvas and Save button are unreachable via keyboard (`End` key) or normal scroll.

**Root cause:** The two-column layout uses a sticky or min-height right column that inflates
the scroll container beyond the left column's content height.

**Fix:**

1. Find the two-column grid/flex container wrapping the Source Lineage panel (left) and
   the Architect Patch panel (right).

2. Ensure the outer container uses `items-start` (not `items-stretch`):
   ```tsx
   // BEFORE:
   <div className="grid grid-cols-2 gap-6">
   // AFTER:
   <div className="grid grid-cols-2 gap-6 items-start">
   ```

3. If the right panel has `sticky top-*`, verify it does not have `min-h-screen` or any
   explicit height that exceeds the left column:
   ```tsx
   // Remove any min-h-screen from the right sticky panel
   // Replace with: overflow-y-auto max-h-screen
   ```

4. If the Integration Design Canvas is inside the right column and causes overflow,
   move it below both columns as a full-width section instead.

**Verify:** Open any integration detail. Scroll to the bottom. The page must reach the
canvas / save section with no blank gap. `End` key must land on the last element.

---

## BUG-04 — Theme preference not persisted across page navigation [MEDIUM]

**Affected files:**
- `apps/web/lib/use-theme.ts`
- `apps/web/app/layout.tsx`

Setting Dark mode and navigating to another page resets the toggle to "System". The theme
class is lost on re-mount.

**Fix — `apps/web/lib/use-theme.ts`:**

Ensure the hook initialises from `localStorage` synchronously on first render, not after
an effect delay. The pattern must be:

```typescript
const STORAGE_KEY = 'oci-dis-theme'

export type Theme = 'light' | 'dark' | 'system'

export function useTheme() {
  // Initialise from localStorage immediately (not in useEffect)
  const [theme, setTheme] = useState<Theme>(() => {
    if (typeof window === 'undefined') return 'system'
    return (localStorage.getItem(STORAGE_KEY) as Theme) ?? 'system'
  })

  useEffect(() => {
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
    const isDark = theme === 'dark' || (theme === 'system' && prefersDark)
    document.documentElement.classList.toggle('dark', isDark)
    // Always persist — including 'system' — so navigation restores the correct state
    localStorage.setItem(STORAGE_KEY, theme)
  }, [theme])

  return { theme, setTheme }
}
```

**Fix — `apps/web/app/layout.tsx`:**

Confirm the no-flash inline script uses the same storage key `'oci-dis-theme'`:

```html
<script dangerouslySetInnerHTML={{ __html: `
  (function() {
    try {
      var t = localStorage.getItem('oci-dis-theme');
      var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      if (t === 'dark' || (t !== 'light' && prefersDark)) {
        document.documentElement.classList.add('dark');
      }
    } catch(e) {}
  })();
` }} />
```

**Verify:** Set Dark mode on Projects page. Navigate to Dashboard → Catalog → Capture →
Graph → Admin. Theme must remain Dark on every page without resetting to System.

---

## BUG-05 — System autocomplete: no empty-state feedback [MEDIUM]

**Affected file:** `apps/web/components/capture-wizard.tsx` (Step 2 Source System,
Step 3 Destination System) and `apps/web/components/system-autocomplete.tsx` (if separate)

When typing a system name that has no existing matches in the catalog, the dropdown
disappears silently — users don't know if the system will be created as new or if the
search failed.

**Fix:** Add an empty-state hint row inside the autocomplete dropdown when the API
returns an empty array:

```tsx
{suggestions.length === 0 && query.length >= 2 && (
  <div className="px-3 py-2 text-sm text-[var(--color-text-muted)] italic
                  border border-[var(--color-border)] rounded-md mt-1
                  bg-[var(--color-surface-2)]">
    No existing systems match "{query}" — it will be created as a new system.
  </div>
)}
```

Show this hint only when:
- The user has typed at least 2 characters
- The API has responded (not still loading)
- The suggestions array is empty

Also add a loading spinner or "Searching…" micro-text while the debounced request
is in-flight.

**Verify:** On Capture wizard Step 2, type "SAP". The hint "No existing systems match
'SAP' — it will be created as a new system." must appear below the input.

---

## ENH-01 — Projects list: disambiguate duplicate project names [MEDIUM]

**Affected file:** `apps/web/app/projects/page.tsx`

Multiple projects named "Docker Smoke" with identical metadata make the list unusable.

**Fix:** Add the short project ID (last 8 chars of UUID) as a subtle suffix when two or
more projects share the same name:

```tsx
// In the project row, detect duplicates:
const nameCounts = projects.reduce((acc, p) => {
  acc[p.name] = (acc[p.name] ?? 0) + 1
  return acc
}, {} as Record<string, number>)

// In the row render:
<span className="font-medium">{project.name}</span>
{nameCounts[project.name] > 1 && (
  <span className="ml-2 text-xs text-[var(--color-text-muted)] font-mono">
    #{project.id.slice(-8)}
  </span>
)}
```

**Verify:** Projects page shows duplicate "Docker Smoke" entries each with a unique
`#xxxxxxxx` suffix.

---

## ENH-02 — Graph: empty-state callout when topology is trivial [LOW]

**Affected file:** `apps/web/app/projects/[projectId]/graph/page.tsx`

When a project has fewer than 3 distinct system nodes, the graph shows a minimal
single-edge diagram that provides no topological insight.

**Fix:** Add a contextual info banner above the graph canvas when `nodes.length < 3`:

```tsx
{nodes.length < 3 && (
  <div className="mx-4 mb-3 px-4 py-3 rounded-lg border
                  border-[var(--color-border)] bg-[var(--color-surface-2)]
                  text-sm text-[var(--color-text-secondary)]">
    <span className="font-medium text-[var(--color-text-primary)]">Limited topology: </span>
    This project's integrations share fewer than 3 distinct systems.
    Import a workbook with varied source and destination system names to see
    the full dependency map.
  </div>
)}
```

**Verify:** Graph page for "Parity Test" project shows the info banner. A project with
10+ real system names should NOT show the banner.

---

## ENH-03 — Capture wizard Step 4: OIC Estimate activation hint [LOW]

**Affected file:** `apps/web/components/capture-wizard.tsx` (Technical step)
or `apps/web/components/oic-estimate-preview.tsx`

The OIC Estimate panel shows "—" with no explanation of how to populate it.

**Fix:** In the OIC Estimate preview panel, when both `frequency` and `payloadKb` are
null/empty, replace the "—" metrics with an activation prompt:

```tsx
{!frequency || !payloadKb ? (
  <p className="text-xs text-[var(--color-text-muted)] text-center py-4">
    Select a <strong>Frequency</strong> and enter a <strong>Payload KB</strong>
    above to preview OIC billing and pack pressure.
  </p>
) : (
  // existing billing metrics display
)}
```

**Verify:** On Capture wizard Step 4 with empty Frequency/Payload fields, the OIC
Estimate panel shows the activation hint instead of "—".

---

## ENH-04 — Admin hub: global-scope warning [LOW]

**Affected file:** `apps/web/app/admin/page.tsx`

The admin page header has no explicit warning that changes affect all projects globally.

**Fix:** Add a warning banner directly below the page header description:

```tsx
<div className="mt-3 flex items-start gap-2 px-4 py-3 rounded-lg
                bg-amber-50 dark:bg-amber-950/40
                border border-amber-300 dark:border-amber-700
                text-amber-800 dark:text-amber-300 text-sm">
  <span className="mt-0.5">⚠️</span>
  <span>
    Changes here affect <strong>all projects</strong>. System patterns
    (seeded from the workbook) can be edited but not deleted.
    Dictionary and assumption changes take effect on the next recalculation.
  </span>
</div>
```

**Verify:** Admin hub `/admin` shows the amber warning banner in both light and dark mode.

---

## ENH-05 — Import history: show original filename [LOW]

**Affected file:** `apps/web/app/projects/[projectId]/import/page.tsx`

The Import History table shows a truncated UUID batch ID — users can't correlate batches
with the files they uploaded.

**Fix:** The `GET /api/v1/imports/{project_id}` response already includes batch metadata.
Check if the response includes a `source_filename` or `original_filename` field. If so,
display it in place of the raw UUID:

```tsx
<td className="text-sm font-mono text-[var(--color-text-secondary)]">
  {batch.source_filename
    ? <span title={batch.id}>{batch.source_filename}</span>
    : <span className="opacity-60">{batch.id.slice(0, 8)}…</span>
  }
</td>
```

If the API does not return a filename, add a `tooltip` showing the full batch UUID on
hover of the truncated ID — at minimum users can copy it.

**Verify:** Import history shows file-based labels or hoverable full UUIDs.

---

## ENH-06 — Catalog: add "Clear all filters" button [MEDIUM]

**Affected file:** `apps/web/app/projects/[projectId]/catalog/page.tsx`
or `apps/web/components/catalog-table.tsx`

After applying search + dropdown filters, there is no single action to reset all filters.

**Fix:** Add a "Clear" button that appears only when any filter is active:

```tsx
const hasActiveFilters = search !== '' || qaStatus !== 'All' ||
                         pattern !== 'All' || brand !== 'All'

{hasActiveFilters && (
  <button
    onClick={() => { setSearch(''); setQaStatus('All'); setPattern('All'); setBrand('All') }}
    className="text-sm px-3 py-1.5 rounded border border-[var(--color-border)]
               text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-2)]
               transition-colors"
  >
    Clear filters
  </button>
)}
```

Place it immediately to the right of the Brand dropdown, before the integration counter.

**Verify:** Apply a search term + QA Status filter. "Clear filters" button appears.
Clicking it resets all three dropdowns and the search field simultaneously.

---

## ENH-07 — Capture wizard: persist form state in sessionStorage [MEDIUM]

**Affected file:** `apps/web/components/capture-wizard.tsx`

Navigating away from the wizard (e.g. clicking a sidebar link) destroys all entered
form data with no warning.

**Fix — Part A: warn before leaving:**

Add a `beforeunload` / navigation guard using Next.js router events:

```tsx
useEffect(() => {
  const hasData = formData.interfaceName || formData.sourceSystem || formData.destinationSystem
  if (!hasData) return

  const handleBeforeUnload = (e: BeforeUnloadEvent) => {
    e.preventDefault()
    e.returnValue = ''
  }
  window.addEventListener('beforeunload', handleBeforeUnload)
  return () => window.removeEventListener('beforeunload', handleBeforeUnload)
}, [formData])
```

**Fix — Part B: persist to sessionStorage:**

```tsx
const SESSION_KEY = `capture-wizard-${projectId}`

// On every formData change, save to sessionStorage:
useEffect(() => {
  sessionStorage.setItem(SESSION_KEY, JSON.stringify({ step, formData }))
}, [step, formData])

// On mount, restore from sessionStorage:
useEffect(() => {
  const saved = sessionStorage.getItem(SESSION_KEY)
  if (saved) {
    const { step: s, formData: f } = JSON.parse(saved)
    setStep(s)
    setFormData(f)
  }
}, [])

// On successful submit, clear session:
const handleSubmit = async () => {
  // ... existing submit logic ...
  sessionStorage.removeItem(SESSION_KEY)
}
```

**Verify:** Fill Steps 1–3 of the wizard. Navigate to Catalog. Return to Capture → New
Integration. Form data and current step must be restored. After successful submit, the
session key must be cleared.

---

## Final Verification Pass

Run all of these after completing every section:

```bash
# 1. TypeScript — must be 0 errors
cd apps/web && npx tsc --noEmit --skipLibCheck 2>&1 | tail -10; cd ../..

# 2. Ruff — must be clean
./.venv/bin/python -m ruff check . 2>&1

# 3. Parity tests — must be 26/26
./.venv/bin/python -m pytest packages/calc-engine/src/tests/ -q 2>&1 | tail -5

# 4. Docker stack — all 6 containers Up
docker compose ps 2>&1

# 5. API health
curl -sf http://localhost:8000/health
```

---

## Documentation Update

After all fixes and enhancements are verified, append to `docs/progress.md`:

```markdown
## Browser Test Remediation — Bug Fixes + UX Enhancements

**Completed:** {today's date}
**Status:** ✅ Complete

### What was fixed

**Bugs:**
- BUG-01: Dark mode form inputs — added CSS baseline for input/select/textarea in globals.css
- BUG-02: Dashboard QA cards dark mode — replaced hardcoded colors with CSS variable tokens
- BUG-03: Phantom scroll on detail page — fixed two-column layout with items-start
- BUG-04: Theme not persisted across navigation — fixed useTheme hook init + storage key consistency
- BUG-05: Autocomplete silent empty state — added "will be created as new" hint + loading indicator

**Enhancements:**
- ENH-01: Projects list duplicate names — added #id suffix for disambiguating duplicate project names
- ENH-02: Graph trivial topology — added info banner when nodes < 3
- ENH-03: OIC Estimate activation hint — replaced "—" with prompt when frequency/payload are empty
- ENH-04: Admin hub global scope warning — added amber warning banner
- ENH-05: Import history filename — showing source filename or hoverable UUID
- ENH-06: Catalog clear filters button — appears when any filter is active
- ENH-07: Capture wizard sessionStorage — form state persisted; beforeunload guard added

### Verification results

```text
TypeScript: 0 errors
ruff: All checks passed!
pytest: 26 passed
docker compose: 6/6 containers Up
```

### Gaps / known limitations

None

---
```

Then update `README.md` milestone table to add a "Browser QA" row:

| Milestone | Description | Status | Completed |
|-----------|-------------|--------|-----------|
| Browser QA | Bug fixes + UX enhancements from live browser test | ✅ Complete | {date} |

Commit:
```bash
git add -A
git commit -m "fix: browser test findings — dark mode inputs, scroll bug, theme persistence, UX enhancements"
git add docs/progress.md README.md
git commit -m "docs: browser QA remediation complete"
```

---

## Language

All code comments, variable names, commit messages, and documentation in English (US).
User-facing strings that are already in Spanish (form placeholders, frequency labels,
system names from the domain) must not be translated.
