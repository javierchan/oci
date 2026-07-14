# Contextual Support Assistant

**Status:** Implemented
**Agent:** `support_assistant`
**Runtime:** Docker `agent-worker`, Celery `agents` queue
**Provider:** OCI Generative AI `openai.gpt-oss-20b`

## Purpose

The OCI DIS App Assistant is a persistent floating support surface for questions
about OCI DIS Architect and the governed project context visible in the App. It
can explain App workflows, integrations, topology, patterns, Service Products,
volumetry, pricing, and BOM evidence. It does not answer unrelated questions and
cannot mutate project data.

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
- Global routes first receive a bounded project index. Project-specific questions
  then resolve their dossier from the route, explicit attachments, a project name
  in recent user questions, or the sole active project. Multiple active candidates
  remain ambiguous and require an explicit selection; the model never guesses.
- Evidence retrieval is intent-aware. A cost question loads the latest immutable
  BOM totals, monthly and peak run rate, price coverage, publication status, and
  the project/BOM routes even when the user is currently in Admin or Projects.
- Exact portfolio counts and commercial totals render from deterministic App
  evidence. OCI synthesis remains available for explanation, comparison, and
  recommendations, but it cannot relabel or paraphrase authoritative quantities.
- Previous user questions provide continuity. Previous model answers are never
  reintroduced as architecture evidence.
- Citations are App routes, not fabricated external references.

## Domain Boundary

A deterministic preflight classifier runs before OCI inference. Explicit outside
topics are refused, and questions without App/domain terms require referential
language plus attached App context. Refusal responses are application-owned; OCI
cannot override them. Provider failure returns an honest deterministic fallback.
An output-grounding gate also rejects unsupported sensitive claims, invented
approval/deployment actions, Markdown tables, and excessive verbosity. Rejected
synthesis is replaced by a concise App-owned answer built from the same evidence,
while the AgentRun records that grounding fallback occurred.

## Persistence

- `support_conversations`: active browser-session conversation.
- `support_messages`: user/assistant turns, status, AgentRun linkage, context, citations.
- `support_attachments`: explicit component context pinned to a user message.
- `agent_runs`, `agent_steps`, and `agent_artifacts`: auditable model/tool execution.

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
