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
- Users can pin up to eight App views while navigating, then submit them with a question.
- The worker loads bounded project, integration, latest Dashboard risk and maturity,
  scenario, and latest BOM evidence through typed SQLAlchemy queries owned by the
  application service.
- The model receives the latest 12 completed turns and sanitized governed evidence.
- Citations are App routes, not fabricated external references.

## Domain Boundary

A deterministic preflight classifier runs before OCI inference. Explicit outside
topics are refused, and questions without App/domain terms require referential
language plus attached App context. Refusal responses are application-owned; OCI
cannot override them. Provider failure returns an honest deterministic fallback.

## Persistence

- `support_conversations`: active browser-session conversation.
- `support_messages`: user/assistant turns, status, AgentRun linkage, context, citations.
- `support_attachments`: explicit component context pinned to a user message.
- `agent_runs`, `agent_steps`, and `agent_artifacts`: auditable model/tool execution.

## UI Behavior

The assistant is mounted in the root Next.js layout. Open state, session identity,
conversation history, pending execution, and pinned contexts survive App Router
navigation. The floating panel uses existing theme tokens and remains responsive
on mobile and desktop.

Provider synthesis is constrained to short, decision-oriented answers in the
user's language. It prioritizes governed counts and statuses, avoids Markdown
tables, and cannot introduce unsupported regulations, products, limits, or risks.
