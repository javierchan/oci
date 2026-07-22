# Governed App Knowledge Base

The contextual assistant may describe only product behavior that OCI DIS
Architect can prove from its executable contracts or from the human-owned App
guide. This boundary prevents a language model from turning plausible product
ideas into claims about features, routes, workflows, or exports that do not
exist.

## Sources of authority

| Knowledge | Authority | Update mechanism |
| --- | --- | --- |
| Next.js screens | `apps/web/app/**/page.tsx` | Derived by `scripts/build_app_knowledge.py` |
| API operations | `docs/api/openapi.yaml` | Derived from generated OpenAPI |
| Export media types | Router response declarations plus OpenAPI | Derived by source inspection |
| Persisted entities | SQLAlchemy models and API schemas | Derived by Python AST inspection |
| User purpose and workflow | `app/knowledge/app_knowledge.yaml` | Human-authored and reviewed |
| Products, SKUs, patterns, dictionaries, projects, and BOM facts | Active database records | Queried for each support request |

The derived manifest is deterministic and committed as
`app/knowledge/derived_app_knowledge.json`. Its SHA-256 source hash makes drift
visible without treating generated content as a second source of truth.

## Runtime flow

1. `build_support_evidence` resolves the current route, explicit contexts, and
   relevant live database evidence.
2. The knowledge retriever ranks curated sections by question terms and current
   route. Explicit question terms outrank a generic route match.
3. The provider receives only the bounded entries, allowed routes, live facts,
   and answer contract.
4. The output gate rejects unsupported feature, workflow, route, export, SKU,
   price, or mutation claims.
5. When the provider is unavailable or its answer fails grounding, the App
   returns a deterministic answer from the same knowledge entry. Unknown
   capabilities are stated as not documented.

Support and Knowledge Maintenance use the settings-driven
`openai.gpt-oss-120b` override. Specialized architecture agents continue to use
the default `openai.gpt-oss-20b` model. Resolving one use case creates a settings
copy and never mutates the cached global settings object.

## Maintenance and review

The Knowledge Maintenance Agent runs on the existing governed agent worker. It
compares the immutable derived manifest packaged in the production image with
the curated guide and persists a job plus review candidates through two
separate lanes:

1. Deterministic validation reports dead references, stale media types, missing
   fields, and unowned Next.js routes. CI treats these as build failures.
2. Model-assisted semantic review compares the human explanation with a bounded
   inventory of executable routes, endpoint summaries, entities, and exports.
   The model must return structured drafts with exact derived evidence
   references. The API rejects malformed drafts, unknown sections, unsupported
   fields, and invented references before anything can be persisted.

The image never needs the monorepo source tree: CI rebuilds the manifest from
executable source and rejects deterministic drift before the image is
published. An administrator must explicitly accept or reject every persisted
candidate with a rationale.

Acceptance records disposition and audit evidence only. Neither the agent nor
the review endpoint edits the YAML file. A human applies the approved
documentation change, regenerates the manifest, and validates it in CI. An OCI
provider failure or invalid JSON response cannot suppress deterministic checks
or create a candidate.

```bash
cd apps/api
../../.venv/bin/python scripts/build_app_knowledge.py
../../.venv/bin/python scripts/build_app_knowledge.py --check
```

The canonical GitHub workflow runs `--check`. It fails for an uncovered Next
route, missing endpoint, stale entity, or export media type that differs from
the executable router. Tests also inject a fake route and fake CSV export to
prove the negative gate. Provider tests use mocked transport and do not call
OCI.
