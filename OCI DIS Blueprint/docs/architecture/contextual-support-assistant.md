# Contextual Support Assistant

**Status:** Implemented
**Agent:** `support_assistant`
**Runtime:** Docker `agent-worker`, Celery `agents` queue
**Provider:** OCI Generative AI `openai.gpt-oss-20b`

## Purpose

The OCI DIS App Assistant is a persistent, general support surface for every
OCI DIS Architect App question. It can explain workflows, projects, imports,
capture, catalog, integrations, topology, patterns, Service Products, volumetry,
pricing, BOM, governance, exports, and specialized agents. Current project or
route context is optional: it improves a record-specific answer but never blocks
general App guidance. It does not answer clearly unrelated questions and cannot
mutate project data.

## Session Isolation

The current product has no external identity provider. The browser creates one
opaque UUID in local storage and sends it as `X-Support-Session-Id`. PostgreSQL
conversations are readable only when both conversation ID and session UUID match;
unauthorized lookups return 404. This is an explicit transitional identity
boundary, not a substitute for authentication. A future IdP must bind the same
conversation contract to its authenticated subject.

## Context Contract

- Current route and page title are attached to every turn.
- Project and integration IDs are derived only from valid App routes.
- Users can add up to eight explicit App contexts while navigating, then submit
  them with a question.
- The worker can read bounded App navigation, governance counts, pattern and
  Service Product metadata, project portfolio, import, integration definition,
  ordered business-process flow, Dashboard, deployment-scenario, and BOM evidence
  through typed SQLAlchemy queries owned by the application service.
- Global and project routes receive the same general App capability. Project-specific
  questions resolve their dossier from explicit attachments, a project name in recent
  user questions, a clear reference such as “this project”, or the sole active
  project. Multiple active candidates remain ambiguous only for a genuinely
  project-specific question; the model never guesses.
- Evidence retrieval is intent-aware. General pricing and billing questions explain
  the governed BOM workflow without pretending the current route is a quote. When
  a follow-up identifies a Service Product, edition, or license model, the assistant
  resolves that reference from dialogue, retrieves its approved SKU and price-item
  evidence, and lets the provider explain the result naturally. A project-cost
  question loads the latest immutable BOM totals, monthly and peak run rate, price
  coverage, publication status, and the project/BOM routes.
- Exact portfolio counts and commercial totals render from deterministic App
  evidence. OCI synthesis remains available for explanation, comparison, and
  recommendations, but it cannot relabel or paraphrase authoritative quantities.
- Previous user questions provide continuity. Previous model answers are never
  reintroduced as architecture evidence.
- A small persisted context ledger retains only resolved, App-owned references:
  active Service Product, pattern, project, language, and the latest topic. It
  deliberately does not retain a provider answer, inferred price, or arbitrary
  user profile. The assistant shows the resolved ledger in the conversation UI
  so a user can see which governed context is active.
- A typed routing policy classifies the **current** turn before evidence is
  loaded. Portfolio, project-cost, commercial, workflow, project-context, and
  general App-help contracts are distinct. Conversation history may resolve a
  reference such as “that service”, but cannot carry an old commercial topic
  into a new question about a pattern, import, or topology.
- Routine workflow questions use concise application-owned explanations before
  OCI synthesis: Import, Capture, Catalog/QA, volumetry, Dashboard, Map,
  BOM & Cost, exports, Governance, and agents. Product, project, and price
  facts are still retrieved dynamically from approved App evidence; no Service
  Product list is embedded in the response policy.
- Citations are App routes, not fabricated external references.

## Domain Boundary

A deterministic preflight classifier runs before OCI inference. Clearly external
topics are refused. A question submitted from an App route is treated as a general
App-help request even when it does not name a feature; the current view provides
context rather than a restriction. Refusal responses are application-owned; OCI
cannot override them. Provider failure returns an honest deterministic fallback.
A single centralized output-grounding gate also rejects unsupported sensitive claims, invented
approval/deployment actions, Markdown tables, and excessive verbosity. Rejected
synthesis is replaced by a concise App-owned answer built from the same evidence,
while the AgentRun records that grounding fallback occurred.

## Persistence

- `support_conversations`: active browser-session conversation.
- `support_messages`: user/assistant turns, status, AgentRun linkage, context, citations.
- `support_attachments`: explicit component context pinned to a user message.
- `agent_runs`, `agent_steps`, and `agent_artifacts`: auditable model/tool execution.

The `context_state` JSON field on `support_conversations` is schema-governed by
the service rather than client-editable. It is a compact reference ledger, not
a second source of project, price, or technical facts; each new turn retrieves
those facts again from the authoritative App tables.

## Clear History

Users can clear the visible transcript for their current browser session from the
assistant header. The destructive action requires explicit confirmation and is
blocked while an assistant response is pending. The API validates both conversation
ID and opaque session UUID, deletes only `support_messages` and
`support_attachments`, and returns the same active empty conversation so navigation
and session isolation remain stable.

Governed `AgentRun`, step, and artifact records are retained for operational audit.
The clear event stores only previous and resulting message/attachment counts; it
never copies prompt or response content into `AuditEvent`.

## UI Behavior

The assistant is mounted in the root Next.js layout. Open state, session identity,
conversation history, pending execution, and pinned contexts survive App Router
navigation. The floating panel uses a stable header, scroll-isolated conversation,
single composer, explicit `Add context` action, and icon-only send command. It uses
existing theme tokens and remains responsive on mobile and desktop without covering
its own controls. A separate icon command opens the accessible Clear history
confirmation and is disabled when history is empty or a response is running.

Provider synthesis is constrained to short, decision-oriented answers in the
user's language. It prioritizes governed counts and statuses, avoids Markdown
tables, and cannot introduce unsupported regulations, products, limits, or risks.
Internal redaction markers and unresolved route placeholders fail the output-
grounding gate and are replaced with the App-owned governed answer.
The fallback uses the same project dossier, so a provider degradation still
returns useful governed portfolio or BOM facts instead of generic navigation copy.

## Response quality and evaluation

Every assistant run preserves the selected response contract and evidence in its
auditable `AgentRun`. The shared output gate removes model meta-reasoning and
rejects unsupported sensitive claims; the App-owned deterministic answer is
returned when a precise route, pattern, product, commercial mapping, project
portfolio, or workflow explanation is already available. Agent Operations shows
grounding/fallback state and evidence completeness for retained executions.
When that direct answer is selected, the worker skips OCI inference entirely;
this avoids adding latency, cost, and model variance to facts the App has
already resolved. The run records that deterministic path alongside the same
evidence artifact and citations.

`apps/api/scripts/evaluate_support_assistant.py` exercises the public support
API with fresh session IDs. Its bounded suite covers each major App workspace,
commercial explanation, refusal, a service follow-up, and a deliberate
commercial-to-pattern topic switch. It creates only disposable support
conversations and agent audit records; it never mutates project or governance
data. The script accepts at most ten numbered iterations so a release review can
record a finite improve-and-retest cycle.
