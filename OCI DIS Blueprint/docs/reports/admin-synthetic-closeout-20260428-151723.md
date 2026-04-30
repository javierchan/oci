# Admin Synthetic Open Topics Closeout

**Date:** 2026-04-28
**Status:** Complete

## Scope

Close the two remaining admin synthetic gaps identified in the previous
milestone snapshot:

1. retry runtime automation against the live stack
2. repo-owned browser E2E coverage for the admin synthetic pages

## What Changed

- Added `apps/api/scripts/smoke_admin_synthetic_retry.py`
  - Seeds a bounded failed source job through the service layer
  - Calls the real retry API
  - Waits for the retried job to reach a terminal state
  - Validates bounded row/system/pattern targets
  - Cleans up the seeded failed source job at the end
- Added a focused API regression in
  `apps/api/app/tests/test_admin_synthetic_api.py`
  - verifies failed synthetic jobs without persisted assets can still be
    cleaned up safely
- Added Playwright browser E2E coverage
  - `apps/web/playwright.config.ts`
  - `apps/web/e2e/admin-synthetic.spec.ts`
  - `apps/web/vitest.config.ts`
- Added repo scripts in `apps/web/package.json`
  - `npm run test:e2e:install`
  - `npm run test:e2e`
- Updated README and architecture/progress docs so the runtime validation
  contract matches the verified repo state

## Validation Evidence

```text
apps/api focused pytest:
  cd apps/api && ./.venv/bin/python -m pytest app/tests/test_admin_synthetic_api.py -q
  -> 10 passed

apps/api full pytest:
  cd apps/api && ./.venv/bin/python -m pytest --tb=short -q
  -> 33 passed

apps/api ruff:
  cd apps/api && ./.venv/bin/python -m ruff check .
  -> All checks passed!

apps/web unit tests:
  cd apps/web && npm test
  -> 9 passed

apps/web type-check:
  cd apps/web && npm run type-check
  -> 0 errors

apps/web lint:
  cd apps/web && npm run lint -- --max-warnings 0
  -> 0 errors / 0 warnings

live smoke:
  ./.venv/bin/python apps/api/scripts/smoke_admin_synthetic_lab.py
  -> job_id=6d414d1c-2010-4d03-bedf-b6ff721691a6
  -> status=cleaned_up

retained smoke:
  ./.venv/bin/python apps/api/scripts/smoke_admin_synthetic_lab.py --preset-code retained-smoke
  -> job_id=b5cf81b0-9f46-46db-9a77-a9acc445adf1
  -> initial_terminal_status=completed
  -> status=cleaned_up

retry smoke:
  ./.venv/bin/python apps/api/scripts/smoke_admin_synthetic_retry.py
  -> source_job_id=2670e093-8a8e-48f9-ab60-7093293bf2d5
  -> retried_job_id=e30fb7b5-87aa-46af-9307-067736583463
  -> source_job_final_status=cleaned_up
  -> retried_job_status=cleaned_up

browser E2E:
  cd apps/web && npm run test:e2e:install
  cd apps/web && npm run test:e2e
  -> 2 passed
```

## Result

The remaining admin synthetic open topics are now closed:

- retry runtime automation is covered by a live bounded smoke helper
- browser E2E is covered by a repo-owned Playwright suite
- the regression gates remained green after the changes

## Remaining Gaps

None identified in the closed scope.
