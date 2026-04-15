You are working on the `pricing` codebase located at `pricing/` within this repository.

## Context

This is a deterministic OCI pricing engine with a natural-language assistant on top.
The core invariant is: GenAI never calculates prices. All arithmetic is done locally
in `pricing/server/quotation-engine.js`. GenAI is used only for intent classification,
discovery answers, and narrative formatting.

## Before Writing Any Code

Read these files in full, in this order:

1. pricing/docs/IMPROVEMENT_MILESTONES.md   — milestone definitions, target state, and exit criteria
2. pricing/docs/ARCHITECTURE.md             — system design and stable contracts
3. pricing/server/assistant.js              — main orchestration pipeline
4. pricing/server/dependency-resolver.js    — SKU resolution and service detection heuristics
5. pricing/server/genai.js                  — OCI GenAI integration layer
6. pricing/server/session-store.js          — session persistence
7. pricing/server/service-families.js       — declarative family metadata
8. pricing/server/intent-extractor.js       — GenAI intent classification
9. pricing/server/index.js                  — HTTP routes and config loading

Then read the full milestone section for the milestone you are assigned before
writing a single line of code.

## How To Verify

Run `npm test` from `pricing/server/` after every file change.
All existing tests must pass before marking the milestone complete.
Do not mark a milestone complete if any test fails, even tests unrelated
to the milestone — investigate and fix before continuing.

## Prerequisites By Milestone

Check this table before starting. If your milestone lists a prerequisite,
stop and tell the user — do not proceed until the prerequisite is confirmed complete.

| Milestone | Prerequisite |
|-----------|--------------|
| M1        | none |
| M2        | none |
| M3        | none |
| M4        | none |
| M5        | none |
| M6        | M5 must be complete |
| M7        | none |
| M8        | none |
| M9        | M3 must be complete |
| M10       | M5 must be complete |

## Dependencies To Install By Milestone

Only run these if your assigned milestone matches:

- M5: run `npm install pino --save` from `pricing/server/` before writing any code
- M8: run `npm install openapi-schema-validator --save-dev` from `pricing/server/` before writing any code
- All other milestones: no new dependencies required

## Rules

1. Read the full milestone section in IMPROVEMENT_MILESTONES.md before writing any code.
   Each milestone has: Problem, Root Cause, Target State, Files Most Likely To Change,
   and Exit Criteria. The Exit Criteria section defines what done means — satisfy all of them.

2. Do not modify any existing test files. If the milestone requires new tests, create
   them as new files. All existing tests must continue to pass.

3. Only touch files named in the milestone's "Files Most Likely To Change" section,
   plus any new files the milestone explicitly calls for. Do not refactor surrounding
   code unless it directly blocks an exit criterion.

4. Do not add features, abstractions, or improvements beyond what the milestone specifies.
   If you notice an adjacent problem, note it in a comment — do not fix it.

5. When the milestone calls for a new file (e.g., `errors.js`, `logger.js`, `auth.js`,
   `metrics.js`, `intent-schema.js`, `genai-profiles.js`), create it at
   `pricing/server/<filename>` and update every import site in the files listed under
   "Files Most Likely To Change".

6. After all exit criteria pass and `npm test` is green, update the Status field for
   this milestone in the Milestone Index table in `pricing/docs/IMPROVEMENT_MILESTONES.md`
   from `open` to `complete`.

7. End your response with a summary of: files created, files modified, and which
   exit criterion was verified for each item in the Exit Criteria list.

## Constraints

- Node.js only — do not introduce new runtime dependencies unless the milestone
  explicitly names one (see Dependencies To Install By Milestone above)
- No TypeScript — stay in plain JavaScript
- No changes to `pricing/server/quotation-engine.js` or `pricing/server/catalog.js`
  unless the milestone explicitly targets them
- No changes to `pricing/app/` — these milestones are server-only
- Keep existing module exports stable — other files import from the modules you are
  changing; do not rename or remove exports without updating all import sites

## Your Assignment

Begin with M[N] ([Milestone Title]).

Read the full M[N] section in `pricing/docs/IMPROVEMENT_MILESTONES.md` now.
Then propose your implementation plan — what you will change in each file and why —
before writing any code. Wait for approval if this is a destructive change
(deleting functions, removing exports, restructuring a public interface).
Only proceed to implementation after the plan is clear.
