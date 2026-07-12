# OCI Generative AI Integration

**Status:** Implemented
**Region:** `us-chicago-1`
**Model:** `OpenAI gpt-oss-20b`
**Transport:** OCI OpenAI-compatible Responses-first API with governed Chat fallback

## Purpose

OCI Generative AI adds advisory synthesis and governed Function Calling to the
application's architecture, verification, import, design, topology, and BOM agents. Deterministic services remain authoritative
for findings, service limits, quantities, prices, totals, patches, and audit.

## Runtime Contract

- Base URL: `https://inference.generativeai.us-chicago-1.oci.oraclecloud.com/openai/v1`
- Preferred endpoint: `/responses`
- Compatibility fallback: `/chat/completions` only after an endpoint-level `404` or `405`
- Capability cache: one hour by default, preventing a failed Responses probe on every request
- Agent project: `OCI_GENAI_PROJECT_ID`, sent as `OpenAI-Project`
- Guardrails scope: `OCI_GENAI_COMPARTMENT_ID`, sent only to OCI ApplyGuardrails
- Model: canonical OCI model name `openai.gpt-oss-20b` configured as `OCI_GENAI_MODEL_ID`
- Authentication: OCI Generative AI API key in `Authorization: Bearer <secret>`
- Local secret source: `~/.oci-genai/api_key`
- Container secret path: `/tmp/oci-dis-home/.oci-genai/api_key`
- Local Project name: `OCI_DIS_Architect` in `javierchan.co`, `us-chicago-1`
- Local API key resource: `OCI_DIS_Architect_API`; one-year primary secret

The secret is bind-mounted read-only, copied by the production entrypoint with
mode `0400`, and read only by the backend. It must never be committed, placed in
`.env`, returned by an endpoint, rendered in the browser, or included in logs.
Production deployments should inject the same file contract from OCI Vault or an
equivalent approved secret manager.

## Governed Flow

1. The application assembles deterministic findings, metrics, topology evidence,
   stress scenarios, or BOM scenario inputs.
2. OCI Guardrails evaluates prompt injection, harmful content, and PII before inference;
   detected PII is redacted and blocked classes fail closed by default.
3. OCI GenAI receives a bounded instruction, governed JSON evidence, and an
   HMAC-derived `safety_identifier` that contains no App identity.
4. Responses is attempted first. Endpoint unavailability falls back to Chat;
   transient `408`, `429`, and selected `5xx` responses use bounded exponential
   backoff with full jitter and honor `Retry-After`.
5. The generated summary is evaluated by Guardrails and remains advisory; it
   cannot mutate catalog or pricing data.
6. The application records only normalized status, model, summary, OCI request ID,
   and token counts in diagnostics; deterministic evidence remains available.
7. Missing credentials, blocked content, or provider failure falls back to an
   honest deterministic or refusal state.

## Consumers

- Project and integration Architecture Review
- Dashboard, map, catalog, and canvas review entry points through the shared review job
- BOM deployment-scenario assistant
- Service Product Verification, Import Quality, Integration Design, and Topology Investigation agents

All multi-step executions run in the dedicated Docker `agent-worker`. See
[`oci-agent-runtime.md`](./oci-agent-runtime.md).

Service Product verification retains deterministic official-source retrieval.
GenAI summarizes findings but cannot decide source freshness or overwrite normalized rules.

## Validation

- Unit tests assert redaction, provider status, bearer authentication, Responses
  capability fallback, Chat compatibility, retry timing, safety identity,
  Guardrails blocking/redaction, response parsing, and token metadata.
- A sanitized smoke script calls the real model and emits no secret data.
- Full API, calc-engine, pricing-engine, frontend, OpenAPI, Docker, and browser
  quality gates protect the integration from regression.

## References

- [OCI OpenAI-Compatible Endpoints](https://docs.oracle.com/en-us/iaas/Content/generative-ai/openai-compatible-api.htm)
- [OCI Generative AI API Keys](https://docs.oracle.com/en-us/iaas/Content/generative-ai/api-keys.htm)
