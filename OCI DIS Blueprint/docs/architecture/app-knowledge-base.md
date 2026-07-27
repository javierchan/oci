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
| User purpose and workflow | `app/knowledge/app_knowledge.yaml` | Versioned App contract; validated by the Knowledge Governance Agent and CI |
| Products, SKUs, patterns, dictionaries, projects, and BOM facts | Active database records | Queried for each support request |

The derived manifest is deterministic and committed as
`app/knowledge/derived_app_knowledge.json`. Its SHA-256 source hash makes drift
visible without treating generated content as a second source of truth. Each
retrieval unit carries a deterministic local semantic vector. Release builds
may also cache OCI Cohere Embed v4 vectors in the same artifact; the build
script never sends a support question or customer evidence when generating
that cache.

The current production artifact contains `282/282` OCI provider vectors in one
`Cohere Embed v4.0` 512-dimension space. The local 384-dimension vectors remain
packaged for build-time validation and unconfigured test environments; they are
never mixed with OCI vectors in one similarity search and are not a production
runtime fallback.

## Runtime flow

1. `build_support_evidence` resolves the current route, explicit contexts, and
   relevant live database evidence.
2. The knowledge retriever embeds the question once and ranks small curated
retrieval units by cosine similarity. A configured production runtime requires
the complete cached OCI vector space and one successful OCI query embedding;
either failure terminates the assistant run instead of silently switching
vector spaces. Route affinity is only a bounded tie-breaker.
   Cached vectors use OCI's native `EmbedText` inference API with
   `SEARCH_DOCUMENT`; runtime questions use `SEARCH_QUERY`. Embedding transport
   is intentionally separate from the OpenAI-compatible Chat and Responses
   transports used for synthesis.
3. Retrieval assigns one of five response intents: capability inquiry, workflow
   guidance, concept explanation, evidence interpretation, or off-topic.
4. For a project or integration question, persisted evidence takes priority:
   current integration/process context, latest BOM and line items, latest
   completed Architecture Review, commercial coverage, and the latest scenario
   including environments and ramp phases.
5. Capability questions are matched only against explicit `supported_actions`.
   The resulting `documented` or `not_documented` assessment is an authoritative
   input, not a model inference.
6. The provider receives only the bounded entries, allowed routes, live facts,
   and answer contract. A named Service Product is expanded with commercial
   evidence only when the question actually asks for pricing, billing, or BOM.
7. The output gate rejects unsupported feature, workflow, route, export, SKU,
   price, or mutation claims.
8. When provider synthesis, query embedding, or output grounding fails, the App
   fails the response closed. It returns no deterministic substitute and no
   citations. The retained AgentRun records the failing stage for operations.

Support and Knowledge Maintenance use the settings-driven
`openai.gpt-oss-120b` override. Specialized architecture agents continue to use
the default `openai.gpt-oss-20b` model. Resolving one use case creates a settings
copy and never mutates the cached global settings object.

## Maintenance and review

The App Knowledge Governance Agent runs automatically on the existing governed
agent worker and owns derived-contract synchronization plus OCI embedding
generation. It compares the active manifest with the curated guide through two
separate lanes:

1. Deterministic validation reports dead references, stale media types, missing
   fields, and unowned Next.js routes. CI treats these as build failures.
2. Model-assisted semantic review compares the App explanation with a bounded
   inventory of executable routes, endpoint summaries, entities, and exports.
   The model must return structured drafts with exact derived evidence
   references. The API rejects malformed drafts, unknown sections, unsupported
   fields, and invented references before anything can be persisted.

The image never needs the monorepo source tree: CI rebuilds the manifest from
executable source and rejects deterministic drift before the image is
published. At runtime, the scheduled agent regenerates a complete provider
vector space in a temporary artifact and publishes it atomically only after
source hash, model, dimensions, coverage, and drift validation pass. No routine
human approval is requested. If validation fails, the last complete artifact
remains active and the unresolved contradiction is reported as an operational
finding; a model response alone can never override executable evidence.

```bash
cd apps/api
../../.venv/bin/python scripts/build_app_knowledge.py
../../.venv/bin/python scripts/build_app_knowledge.py --provider-embeddings
../../.venv/bin/python scripts/build_app_knowledge.py --check
```

The canonical GitHub workflow runs `--check`. It fails for an uncovered Next
route, missing endpoint, stale entity, or export media type that differs from
the executable router. Tests also inject a fake route and fake CSV export to
prove the negative gate. Provider tests use mocked transport and do not call
OCI.

Browser CI keeps provider-free and provider-enabled contracts explicit. The
baseline container environment has no OCI key mount or Project OCID, so its
assistant E2E must observe a persisted `failed` response with no citations for
an in-scope question; it may never accept substitute content. The real-provider
browser case runs only when both governed OCI settings are present and then
requires an actual grounded answer and executable App links. Off-topic
redirection is validated by its terminal delivery state, App-bounded content,
and executable governed action rather than by matching one fixed sentence.
Playwright retains traces, screenshots, and its HTML report on failure, and
GitHub publishes those files as a short-lived diagnostic artifact.

The support capability matrix additionally asserts the `openai.gpt-oss-120b`
use-case override, the five-intent contract, documented versus absent
capabilities, governed export media types, source attribution, and
placeholder-free App routes through a mocked provider execution. Embedding
tests supply provider vectors and a mocked embedding transport, and evidence
tests seed BOM lines and Architecture Review results. No test calls OCI.

The July 25, 2026 live release validation authenticated the tenancy through the
workspace's external-Chrome security-token flow, confirmed the configured model
as active on demand in `us-chicago-1`, regenerated all `282` provider vectors,
passed the deterministic manifest check and focused API suite, and completed
the public support evaluation. Retained AgentRun evidence reports
`app_knowledge.embedding_space = provider`, five semantic matches, and the
committed source hash.
