# Codex Task — M22 Completion: QA Coverage + Confidence Signals

## Situation

The workbook enhancement analysis shows that readiness and forecast quality are
currently understated in one direction and overstated in another:

1. QA activation can miss active rows when the formal integration ID is blank.
2. Forecast-like technical metrics can appear precise even when payload coverage
   is sparse and the underlying signal is weak.

This milestone makes the system more truthful. QA must evaluate all active rows
based on workbook participation rules, trigger vocabulary must align with workbook
capture semantics, and the app must communicate forecast confidence explicitly
instead of implying certainty from incomplete data.

No business-logic redesign beyond the milestone scope. Preserve workbook uncertainty;
do not fill missing fields just to turn QA green.

**Read before writing any code:**
1. `AGENTS.md` — QA and parity expectations
2. `docs/reports/workbook-gap-analysis-adn-20260415.md`
3. `packages/calc-engine/src/engine/qa.py` — current QA activation and trigger checks
4. `packages/calc-engine/src/engine/importer.py` — row inclusion semantics
5. `apps/api/app/services/dashboard_service.py` — forecast and coverage payloads
6. `apps/web/app/projects/[projectId]/page.tsx` — dashboard rendering
7. `apps/web/app/projects/[projectId]/catalog/[integrationId]/page.tsx` — QA reasons UI
8. `apps/web/components/graph-detail-panel.tsx` or other readiness surfaces if they surface confidence

Do not paper over source gaps by inventing missing IDs, payloads, or patterns.

---

## Task 1 — Decouple QA activation from formal ID presence

### Workbook issue to fix

The workbook enhancement notes explicitly call out that QA should not depend only
on the formal integration ID column. Active rows can still require governance and
technical validation even when the formal ID is blank.

### What to change

In `packages/calc-engine/src/engine/qa.py`:
- audit the gating condition that decides whether a row receives QA evaluation
- stop using formal ID presence as the primary activation condition
- instead, base QA activation on workbook participation rules such as inclusion in
  the active catalog/import set

If the calc engine needs additional flags from the importer to determine “active row”
status safely, pass them explicitly rather than inferring from loosely related fields.

### Verification

Add tests proving:
- an active row with blank formal ID still receives QA evaluation
- excluded or intentionally skipped rows still remain outside QA

---

## Task 2 — Align trigger vocabulary with workbook semantics

### Confirmed drift

Workbook-valid values include:
- `Scheduled`
- `REST Trigger`
- `SOAP Trigger`
- `Event Trigger`

Current QA vocabulary is narrower and can reject valid workbook capture text.

### What to change

In `packages/calc-engine/src/engine/qa.py`:
- reconcile trigger validation with the workbook capture vocabulary
- support workbook-valid labels directly or normalize them explicitly before validation
- keep fallback behavior conservative; do not silently convert unknown trigger text into a valid category

In any frontend label helpers:
- ensure user-facing QA messages reflect the workbook trigger naming, not only internal enums

### Verification

Add tests for:
- `REST Trigger`
- `SOAP Trigger`
- `Event Trigger`
- `Scheduled`

No false `INVALID_TRIGGER_TYPE` should occur for these values.

---

## Task 3 — Add completeness and confidence signals

### Workbook issue to fix

The workbook enhancement sheet highlights sparse payload coverage and forecast risk.
A technical forecast that uses only a small subset of rows should communicate that
confidence is limited.

### What to change

In the dashboard API and frontend:
- compute and surface completeness indicators for at least:
  - payload coverage
  - pattern coverage
  - trigger coverage
  - formal ID coverage
  - fan-out coverage if relevant to current formulas
- display a low-confidence warning when forecast-like metrics are derived from sparse coverage

Suggested backend payload shape:

```python
{
  "coverage": {
    "payload": {"complete": 13, "total": 289, "ratio": 0.045},
    "pattern": {...},
    "trigger": {...},
  },
  "forecast_confidence": "low"
}
```

Use the existing dashboard payload if it already has a compatible structure.

### Verification

Dashboard expectations:
- low coverage results in explicit low-confidence messaging
- strong coverage removes or downgrades the warning
- technical totals remain visible, but confidence is not hidden

---

## Task 4 — Improve QA reason messaging without masking uncertainty

### What to change

In frontend QA surfaces:
- keep human-readable reason cards
- add coverage-aware hints where applicable
- distinguish between:
  - invalid value
  - missing value
  - low-confidence estimate because source data is sparse

The goal is not to turn every issue into a QA failure. Some should remain confidence
signals or forecast caveats rather than row-blocking validation errors.

### Verification

An integration with missing payload but otherwise valid architecture should:
- communicate missing payload coverage clearly
- not pretend the forecast is high confidence
- still preserve the raw source uncertainty

---

## Task 5 — Keep workbook uncertainty intact

### What to change

Audit the import, QA, and dashboard chain for any logic that:
- substitutes defaults just to make QA pass
- converts blank payloads into zero without evidence
- treats unknown pattern or trigger values as valid by coercion

Replace those shortcuts with explicit uncertainty handling and clear messaging.

### Verification

Add tests or assertions that unknown or missing source evidence:
- remains visibly incomplete
- affects confidence correctly
- does not silently become a “green” result

---

## Final Verification

Run all of the following:

```bash
./.venv/bin/python -m pytest --tb=short -q 2>&1 | tail -10
./.venv/bin/python -m ruff check . 2>&1 | tail -10
./.venv/bin/python -m mypy apps/api/app --ignore-missing-imports --no-error-summary 2>&1 | tail -10
cd apps/web && npx tsc --noEmit --skipLibCheck 2>&1 | tail -10; cd ../..
cd apps/web && npx eslint . --ext .ts,.tsx --max-warnings 0 2>&1 | tail -10; cd ../..
```

Manual verification:
- confirm active rows without formal ID still get QA results
- confirm workbook-valid trigger labels do not fail QA
- confirm the dashboard shows explicit low-confidence messaging when payload coverage is sparse

---

## Definition of Done

M22 is complete only when all of the following are true:

- QA activation no longer depends on formal ID presence alone
- Workbook trigger vocabulary is accepted or explicitly normalized
- Dashboard and related surfaces communicate coverage and forecast confidence
- Missing source evidence remains visible rather than being coerced into “green”
- All five quality gates remain green

