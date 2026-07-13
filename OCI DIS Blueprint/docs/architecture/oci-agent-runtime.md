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

| Agent | Product location | Authorized tool |
|---|---|---|
| Architecture Review | Dashboard, Catalog, Integration | `load_architecture_review_evidence` |
| Service Product Verification | Library > Service Products | `verify_official_service_sources` |
| Import Quality | Import Review | `inspect_import_quality` |
| Integration Design | Integration Canvas | `inspect_integration_design` |
| Topology Investigation | Map | `inspect_topology_context` |
| BOM Scenario | BOM & Cost | `inspect_bom_scenario` |
| OCI DIS App Assistant | Global floating assistant | `answer_app_support_question` |

Canvas and topology are specialized architecture scopes, not duplicate engines.
The Service Verification tool may retrieve only registered Oracle-controlled
sources and creates findings; an Admin must accept any governed rule update.

## Persisted Contract

- `agent_runs`: scope, definition version, terminal state, provider metadata,
  token totals, cancellation, and compatibility-job linkage.
- `agent_steps`: sanitized progress and tool-call diagnostics.
- `agent_artifacts`: governed evidence used by the run.
- `agent_approvals`: explicit human decision records for proposed mutations.
- `AuditEvent`: run creation, completion, cancellation, and approval decisions.

Static definitions in `app/agents/registry.py` are version controlled. Runtime
prompts cannot be edited through the database or UI.

## OCI Contract

Agent calls require the existing read-only `sk-` secret file,
`OCI_GENAI_BASE_URL`, `OCI_GENAI_PROJECT_ID` sent as `OpenAI-Project`, and
the canonical `openai.gpt-oss-20b` model name configured by `OCI_GENAI_MODEL_ID`.

The project OCID is not a secret. It supplies OCI retention and isolation
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

## Execution

1. A contextual product action creates its specialized compatibility job when needed.
2. The API validates service-layer RBAC and creates `AgentRun`.
3. Celery routes the task exclusively to the `agents` queue.
4. OCI Responses is attempted first to call the one allowlisted tool; an endpoint-level
   compatibility failure uses Chat Completions without changing the tool contract.
5. The Docker worker executes the deterministic tool and returns bounded evidence.
6. OCI Guardrails evaluates input and output; provider or safety failure falls back
   to an honest deterministic summary or explicit refusal.
7. The worker persists evidence, diagnostics, terminal state, and audit.
8. Mutations remain on existing explicit review/apply endpoints.

## Deployment

Local and production-mode Docker use the same immutable API image. The
`agent-worker` has no source bind mount and receives the OCI API key through the
same read-only secret override as API and worker. The image can later be pushed
to OCIR and used by OCI Hosted Agentic Applications without changing tool contracts.

## Validation

- API tests cover catalog visibility, RBAC, run persistence, deterministic
  completion, cancellation, project headers, tool calls, evidence return, and token accounting.
- Docker tests cover backend, frontend, migration, and image contracts.
- `scripts/smoke_oci_agent.py` performs a sanitized real-provider Function Calling smoke.
- Browser validation covers Agent Operations, global project selection, direct
  Architecture Review launch, contextual agent workflows, provider telemetry,
  and honest degraded status.

## References

- [Enterprise AI Agents in OCI Generative AI](https://docs.oracle.com/en-us/iaas/Content/generative-ai/agents.htm)
- [OCI OpenAI-Compatible Endpoints](https://docs.oracle.com/en-us/iaas/Content/generative-ai/openai-compatible-api.htm)
- [OCI Generative AI Projects](https://docs.oracle.com/en-us/iaas/Content/generative-ai/projects.htm)
