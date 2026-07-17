# Governed OCI Generative AI Agent Runtime

**Status:** Implemented and production-validated
**Runtime:** Dedicated Docker `agent-worker` on Celery queue `agents`
**Provider:** OCI OpenAI-compatible Responses-first API with governed Chat fallback

## Decision

OCI DIS Architect uses a hybrid agent architecture. OCI Generative AI performs
model inference and Function Calling. A repository-owned Docker worker enforces
authorization, tool schemas, deterministic execution, evidence boundaries,
terminal states, cancellation, audit, and human approval.

The application never gives the model SQL, shell, Docker, arbitrary URL, or raw
database access. Function tools call existing service-layer functions. Calc,
QA, service rules, topology metrics, import parsing, prices, and BOM totals remain
the sole deterministic authorities.

## Agent Catalog

| Agent | Product location | Governed capability |
|---|---|---|
| Architecture Remediation | Dashboard, Catalog, Integration | Compare blockers, prepare remediation drafts, approve, execute, and post-validate |
| Official Source Governance | Library > Service Products | Compare official evidence, prepare governed updates, and validate quote fixtures |
| Import Correction | Import Review | Prioritize quality gaps, prepare correction drafts, and validate downstream impact |
| Integration Design Optimizer | Integration Canvas | Compare deterministic candidates and simulate an approved draft before explicit save |
| Topology Resilience | Map | Analyze blast radius and prepare auditable mitigation drafts |
| BOM Scenario Optimizer | BOM & Cost | Compare baseline, phased, and availability alternatives and create an approved scenario draft |
| OCI DIS Decision Assistant | Global floating assistant | Answer from App evidence and route material decisions to the specialized workspace |

Canvas and topology are specialized architecture scopes, not duplicate engines.
The Service Verification tool may retrieve only registered Oracle-controlled
sources and creates findings; an Admin must accept any governed rule update.

## Persisted Contract

- `agent_runs`: scope, definition version, terminal state, provider metadata,
  token totals, cancellation, and compatibility-job linkage.
- `agent_steps`: sanitized progress and tool-call diagnostics.
- `agent_artifacts`: governed evidence used by the run.
- `agent_approvals`: explicit human decisions, execution status, bounded execution
  results, and post-validation evidence for proposed changes.
- `AuditEvent`: run creation, completion, cancellation, and approval decisions.

Every completed run stores two additional result contracts without changing the
authoritative evidence tables:

- `brief`: headline, finding, why it matters, next actions, validation, evidence
  identifiers, and confidence.
- `output_quality`: normalization state, grounding decision, deterministic fallback
  reason, and evidence-completeness percentage.
- `decision_workspace`: up to three typed alternatives with changes, impact,
  missing inputs, implementation steps, validation, confidence, and completion contract.

The worker also persists proposal artifacts for alternatives that can become a
governed draft. Approval and execution are separate commands. Execution is
idempotent, emits audit evidence, and creates a post-validation artifact. Canvas
execution remains a simulation until an architect explicitly saves the draft;
BOM execution creates a draft deployment scenario, never an approved quote.

Static definitions in `app/agents/registry.py` are version controlled. Runtime
prompts cannot be edited through the database or UI.

## OCI Contract

Agent calls require the existing read-only `sk-` secret file,
`OCI_GENAI_BASE_URL`, `OCI_GENAI_PROJECT_ID` sent as `OpenAI-Project`, and
the canonical `openai.gpt-oss-20b` model name configured by `OCI_GENAI_MODEL_ID`.

API-key authenticated Responses calls use OCI's versioned
`/20231130/actions/v1/responses` route; Chat fallback remains on
`/openai/v1/chat/completions`. The project OCID is not a secret. It supplies OCI retention and isolation
settings. Long-term memory is disabled by application policy; every run sends a
bounded context and stores authoritative evidence in PostgreSQL.

The local validation Project is named `OCI_DIS_Architect` in `javierchan.co`,
`us-chicago-1`. OCI enforces a minimum one-hour retention for responses and
conversations, so both values use that minimum while application requests set
`store: false`. Long-term memory and short-term memory compaction remain disabled.

The dedicated API key resource is named `OCI_DIS_Architect_API`; its primary
secret is named `OCI_DIS_Architect_Primary` and expires after one year. The
secret exists only on macOS at `~/.oci-genai/api_key` (`0600`, parent directory
`0700`). Docker bind-mounts that file read-only and the entrypoint copies it to
`/tmp/oci-dis-home/.oci-genai/api_key` with mode `0400` before dropping to UID
`10001`. Neither value nor Project OCID is committed.

Provider status is operational, not configuration-only. Mounted credentials and
Project metadata produce `configured`; only a persisted successful synthesis or
Function Calling run produces `available`. A failed latest attempt produces
`degraded` while the deterministic review and allowlisted application tools remain
usable. The global command palette launches the real project Architecture Review
and requires explicit project selection when no project route is active.

Provider telemetry is also operational rather than inferred from configuration.
The centralized OCI transport records fixed counters in shared Redis for retries,
Guardrails decisions, `429`, `5xx`, transport failures, Responses fallbacks, and
terminal degradations. Agent Operations reads these counters from the restricted
`/api/v1/agents/provider-metrics` endpoint. Redis outages do not block agents;
the endpoint switches to a clearly labeled process-local fallback. No user,
session, project, prompt, response, request ID, or tool name is a metric label.

Outcome value is a separate concern. The restricted
`/api/v1/agents/value-metrics` endpoint calculates only observable facts over the
latest 50 retained runs: completed executions, OCI synthesis, grounding fallback,
high-completeness briefs, actionable recommendations, approval decisions,
post-approval reruns, and median runtime. It does not estimate labor saved or
business benefit that the App has not measured.

## Output Governance

All seven agents use one server-side output gate after OCI inference and before
UI persistence. It rejects internal tool/prompt narration, Markdown tables,
internal placeholders, unsupported material numeric claims, unverified mutation
claims, excess length, verification freshness without retrieved sources, and BOM
commercial claims without priced evidence. The deterministic tool output then
builds the same explainable hierarchy for the UI. Provider text remains advisory;
the structured brief and evidence artifact are generated from App-owned data.

All specialized agents use the shared decision workspace. Human approval never
executes a change. The separate execution command calls only an allowlisted,
typed application action and records a post-validation result. Existing domain
approval and explicit Canvas save behavior remain authoritative.

## Execution

1. A contextual product action creates its specialized compatibility job when needed.
2. The API validates service-layer RBAC and creates `AgentRun`.
3. Celery routes the task exclusively to the `agents` queue.
4. The worker loads bounded deterministic evidence and builds a typed decision
   workspace from valid application candidates.
5. OCI Responses is attempted first for grounded synthesis; an endpoint-level
   compatibility failure uses Chat Completions without changing the evidence contract.
6. The worker prepares approval-gated proposal artifacts for executable alternatives.
7. OCI Guardrails evaluates input and output; provider or safety failure falls back
   to an honest deterministic summary or explicit refusal.
8. The shared output gate grounds and structures the result or replaces it with a
   deterministic explainable brief.
9. The worker persists evidence, alternatives, proposals, output quality,
   diagnostics, terminal state, and audit.
10. A human approves or rejects a proposal. A second explicit command executes an
    allowlisted action and persists post-validation; domain approval remains separate.

## Deployment

Local and production-mode Docker use the same immutable API image. The
`agent-worker` has no source bind mount and receives the OCI API key through the
same read-only secret override as API and worker. The image can later be pushed
to OCIR and used by OCI Hosted Agentic Applications without changing tool contracts.

## Validation

- API tests cover catalog visibility, RBAC, four-stage run persistence,
  cancellation, evidence return, alternatives, proposal decisions, idempotent
  execution, post-validation, and token accounting.
- Docker tests cover backend, frontend, migration, and image contracts.
- `scripts/smoke_oci_agent.py` performs a sanitized real-provider Function Calling smoke.
- Browser validation covers Agent Operations, global project selection, direct
  Architecture Review launch, contextual agent workflows, provider telemetry,
  and honest degraded status.

## References

- [Enterprise AI Agents in OCI Generative AI](https://docs.oracle.com/en-us/iaas/Content/generative-ai/agents.htm)
- [OCI OpenAI-Compatible Endpoints](https://docs.oracle.com/en-us/iaas/Content/generative-ai/openai-compatible-api.htm)
- [OCI Generative AI Projects](https://docs.oracle.com/en-us/iaas/Content/generative-ai/projects.htm)
