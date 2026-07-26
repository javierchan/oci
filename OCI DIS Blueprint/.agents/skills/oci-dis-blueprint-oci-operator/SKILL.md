---
name: oci-dis-blueprint-oci-operator
description: Operate, inspect, validate, deploy, and document OCI resources used by the OCI DIS Blueprint application. Use for OCI authentication and tenancy discovery, Generative AI model or embedding readiness, App Assistant provider diagnostics, IAM and quota analysis, OCI resource changes, deployment validation, and reconciliation of OCI runtime state with this repository.
---

# OCI DIS Blueprint OCI Operator

Operate OCI only for the application at:

```text
/Users/javierchan/Documents/GitHub/oci/OCI DIS Blueprint
```

Treat repository evidence and live OCI observations as separate authorities.
Never import operational state, credentials, resource identifiers, or assumptions
from another workspace.

## Hydrate repository truth

Before acting, read in this order:

1. `AGENTS.md`
2. `README.md`
3. `Checkpoint.md` or another repository tracking artifact, when present
4. The relevant documents under `docs/architecture/`
5. The effective configuration, service, router, migration, and test files
6. `.env.example` and `docker-compose.yml`
7. Git status and registered worktrees

Repository state overrides remembered chat context. Do not read secret values from
`.env`, OCI config keys, mounted secret files, Vault bundles, or Terraform state.

## Classify the operation

Classify each request before using OCI:

- **Inspect:** authentication, inventory, models, policies, quotas, limits, logs,
  provider status, or drift. Keep the operation read-only.
- **Validate:** run bounded synthetic smoke tests and repository gates. Avoid
  customer content and persistent OCI resources.
- **Mutate:** create, update, tag, deploy, rotate, or delete OCI resources. Resolve
  exact targets read-only first and require the user's authority for the specific
  state change.

Do not turn an inspection request into a mutation. Never create a dedicated AI
cluster or model endpoint when on-demand inference satisfies the repository
contract.

## Authenticate without exposing secrets

Keep these authentication boundaries explicit:

- OCI CLI or SDK signer authenticates control-plane discovery.
- The OCI Generative AI API-key file authenticates App inference.
- `OCI_GENAI_PROJECT_ID` and `OCI_GENAI_COMPARTMENT_ID` are non-secret resource
  identifiers, but still avoid printing them unless exact diagnosis requires it.

Prefer the callable OCI connector. Discover its command schema, then prove identity
with a harmless tenancy or region query. If it times out, report authentication as
unverified and distinguish timeout, network, signer, authorization, and service
availability instead of guessing.

Use the workspace's established interactive-authentication flow:

1. Open the OCI tenancy sign-in in external Chrome.
2. Select `OracleIdentityCloudService`.
3. Stop for the user to complete credentials and MFA.
4. Verify that Chrome reached OCI Console in the intended region.
5. Perform subsequent OCI discovery and operations through OCI CLI, the OCI MCP
   connector, or the OCI Python SDK.

Use external Chrome only for OCI authentication. Use the in-App browser for other
browser validation unless the user explicitly requests Chrome. A browser session
does not by itself prove that a CLI security-token profile is valid; validate each
authentication boundary independently before relying on it.

For local runtime credentials, verify only:

- whether the configured file exists;
- whether the container mount exists;
- owner and permission mode;
- whether required non-secret settings are present.

Never print, hash, copy into the repository, or return the secret contents.

## Validate Generative AI and embeddings

For App Assistant or embedding work, reconcile:

1. `docs/architecture/contextual-support-assistant.md`
2. `docs/architecture/app-knowledge-base.md`
3. `docs/architecture/oci-generative-ai.md`
4. `apps/api/app/core/config.py`
5. `apps/api/app/services/genai_client.py`
6. `apps/api/app/services/app_knowledge_service.py`
7. `apps/api/scripts/build_app_knowledge.py`
8. `apps/api/app/knowledge/derived_app_knowledge.json`
9. Focused embedding, knowledge, and contextual-support tests

Establish all of the following before calling embeddings enabled:

- configured model and region match a live on-demand model available to the tenancy;
- control-plane access and runtime bearer authentication are both proven;
- compartment/project scope and required policies or service limits are valid;
- the committed knowledge artifact contains provider vectors for every eligible
  retrieval unit in one consistent model and dimension space;
- document vectors are generated with `SEARCH_DOCUMENT`;
- runtime questions use `SEARCH_QUERY`;
- a synthetic, non-customer smoke query returns a vector of the expected dimension;
- runtime retrieval reports the provider embedding space, not silent local fallback;
- deterministic fallback still works when OCI is unavailable.

Use only synthetic text for live smoke tests unless the user explicitly authorizes
external transmission of the exact customer evidence and scope. Do not send prompts,
catalog rows, project records, pricing, or user conversations while testing embeddings.

## OCI mutation safeguards

Before a resource mutation:

1. Identify tenancy, region, compartment, resource OCID, current lifecycle state,
   dependencies, and tags through read-only calls.
2. Compare the proposed state with repository architecture and environment config.
3. State the exact mutation and rollback or recovery path.
4. Apply the smallest supported change.
5. Re-read the OCI resource and validate the application path.

Preserve the retention-tag policy documented in
`docs/architecture/oci-generative-ai.md`. Do not copy identity or creation tags
from another resource. Never delete or rotate credentials without explicit user
authorization and a verified replacement path.

## Validation and reconciliation

Use production Docker contracts; do not install host dependencies. Choose gates
proportional to the change:

- focused API tests for the affected provider or knowledge path;
- `scripts/build_app_knowledge.py --check`;
- provider-embedding build using the production/quality container when required;
- sanitized real-provider smoke;
- Docker health and API provider-status checks;
- App Assistant evaluation and browser workflow when runtime behavior changes;
- Ruff, mypy, frontend, OpenAPI, and full gates for implementation changes.

After validation, synchronize code, tests, architecture docs, `AGENTS.md`, and the
active tracking artifact. Never mark work complete while provider access is
unverified, vectors are incomplete, runtime silently falls back, or a required
gate has not run.

Report:

- discovered repository contract;
- observed OCI state;
- changes made;
- executable validation evidence;
- assumptions;
- remaining risks or blockers;
- the next concrete action.
