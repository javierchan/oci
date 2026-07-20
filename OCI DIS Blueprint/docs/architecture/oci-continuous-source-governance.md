# Continuous OCI Source Governance

## Purpose

OCI DIS Architect verifies the official OCI commercial and estimator sources before
new public-list BOMs are generated. The process detects source drift, preserves the
retrieved evidence, evaluates the impact on governed Service Products, and executes
deterministic quotation fixtures before a changed catalog can be promoted.

This control does not automatically make a blocked product quote-ready. M51 established
the global governed baseline for every persisted public OCI candidate, while the App
BOM continues to use its exact approved allowlist. This workflow keeps both the global
dispositions and the narrower BOM mappings current, reports source drift and excluded
SKUs explicitly, and prevents stale or unverified evidence from being used as if it
were approved.

## Verified Sources

Commercial catalog verification retrieves the following four HTTPS sources as one
atomic validation unit:

| Source | Purpose |
|---|---|
| Oracle public price endpoint configured on `PriceSource` | Current public SKU prices and tiers for the selected currency |
| `products.json` | Cloud Estimator product definitions |
| `metrics.json` | Metering and billing metric definitions |
| `productpresets.json` | Estimator presets and product configuration evidence |

Every response must be a non-empty JSON object from an allowlisted Oracle hostname.
The job retries transient source failures three times. A partial retrieval fails the
whole job and the previous approved evidence remains authoritative.

Service Product verification is a separate, complementary control. It retrieves the
current allowlisted Oracle documentation registered by the governed Service Products;
the source count is therefore dynamic rather than fixed at four. It detects changes to
service limits, billing granularity, quotas, adapters, interoperability, and product
guidance without treating a document hash change as an approved runtime rule.

## Rule Ownership Boundary

Runtime behavior is deterministic. `ServiceLimit` records and the normalized service
rule registry own each rule's applicability, constraint kind, enforcement action,
unit, and currently approved value. Canvas validation, recalculation, Dashboard,
Architecture Review, BOM evidence, and exports consume that same registry.

The Official Source Governance Agent is an evidence and proposal layer:

1. it retrieves only registered Oracle-controlled sources;
2. it extracts a candidate value, unit, citation, retrieval time, and source hash;
3. it cannot change deterministic applicability, constraint kind, or enforcement;
4. deterministic semantic fixtures validate the candidate before review;
5. an administrator explicitly accepts or rejects the finding;
6. only an accepted finding updates the governed value and audit trail.

The agent also reports the latest commercial release scope and candidates whose
generator or quotation fixture requires deterministic revalidation. It remains
read-only: revalidation, candidate disposition, exception closure, and release
promotion are explicit Admin actions. A separate engineering-time Commercial
Consistency Test Agent validates implementation and fixtures against documentary
evidence; it is not registered in the product runtime and cannot mutate App data.

For example, Oracle Integration's 50 KB rule is governed as billing granularity and
uses `calculate` enforcement: a larger payload consumes multiple message packs. It is
not a universal payload rejection threshold. Adapter-specific hard limits remain
separate `hard_limit` rules and block only when their governed applicability matches.
This separation prevents an LLM, a source wording change, or a duplicated constant in
application code from silently changing architecture decisions.

## Runtime Flow

1. Celery Beat invokes `execute_scheduled_oci_governance_task` once per configured
   interval.
2. The task obtains a Redis lease. A concurrent run exits as `skipped` and does not
   create duplicate evidence.
3. The worker retrieves the four commercial sources concurrently and normalizes the
   price payload through the existing pricing service.
4. The raw source payloads are written to Object Storage under
   `governance/oci-sources/jobs/{job_id}/` with their SHA-256 hashes and record counts.
5. A `GovernanceChangeSet` records source drift, changed price signatures, affected
   approved SKU mappings, and affected Service Products.
6. One `QuotationRegressionRun` executes for every approved commercial policy
   family. It verifies mapping presence, candidate-SKU availability, quantity
   behavior, increments, and minimums.
7. A failed family blocks the change set. An unchanged, fully passing verification
   becomes `not_required`. A changed, fully passing verification becomes
   `ready_for_review`.
8. An administrator reviews the evidence in Admin Pricing. Promotion is explicit;
   generated mappings and changed price snapshots never self-approve.
9. Promotion atomically supersedes the prior public snapshot for the same source and
   currency and records actor, timestamp, notes, and audit evidence.
10. Public-list BOM generation requires a passed, approved or no-change verification
    within the configured freshness window.

## Configuration

| Variable | Production default | Meaning |
|---|---:|---|
| `OCI_GOVERNANCE_SCHEDULE_ENABLED` | `true` | Enables the official-source schedule |
| `OCI_GOVERNANCE_SCHEDULE_SECONDS` | `86400` | Verification interval |
| `OCI_GOVERNANCE_LOCK_TTL_SECONDS` | `3600` | Redis lease duration |
| `OCI_GOVERNANCE_MAX_SOURCE_AGE_HOURS` | `72` | Maximum accepted verification age for a new public-list BOM |
| `OCI_GOVERNANCE_CURRENCY` | `USD` | Scheduled public-list currency |
| `SERVICE_VERIFICATION_SCHEDULE_ENABLED` | `true` | Enables official Service Product documentation verification |
| `SERVICE_VERIFICATION_SCHEDULE_SECONDS` | `86400` | Service Product verification interval |

The production Docker topology must include `beat`, `worker`, Redis, PostgreSQL, and
the configured Object Storage service. The scheduler is intentionally not embedded
in the web or API process.

## Review And Acceptance

An administrator accepts a changed source set only when:

- all four source artifacts are present and hash-addressed;
- source counts are plausible and the retrieval status is `verified`;
- every approved commercial policy family has a terminal regression result;
- regression coverage is 100% and no family is failed;
- changed SKUs and affected Service Products have been reviewed;
- material price, metric, preset, edition, BYOL, dependency, minimum, or tier changes
  have an explicit review note;
- quotation fixtures still reproduce governed quantity and pricing behavior.

Approval does not certify an Oracle quote. It promotes governed public evidence for
planning estimates. Contractual rate cards continue through their separate authorized
CSV and approval path.

## Failure And Recovery

| Condition | Runtime behavior | Recovery |
|---|---|---|
| One source is unavailable or invalid | Job fails; no partial change set is promoted | Correct connectivity and rerun; the prior approved snapshot remains active |
| Redis lease already exists | Scheduled invocation is skipped | Wait for the active run or investigate a stale lease after its TTL |
| A governed SKU is absent from the candidate price feed | Its family regression fails and the change set is blocked | Review retirement/replacement evidence and update the mapping through governance |
| Quantity policy is invalid | Family regression fails | Correct the governed increment, minimum, or behavior and rerun |
| Evidence exceeds the freshness window | New public-list BOM generation is blocked | Complete verification and, when drift exists, approve the change set |
| Object Storage write fails | Verification fails before promotion | Restore Object Storage availability and rerun |

Never bypass a failed regression by editing a snapshot directly. Correct the governed
policy or mapping, execute the fixtures again, and preserve the decision in the audit
trail.

## Operational Checks

Daily operations should confirm:

1. the latest scheduled change set reached `no_change`, `ready_for_review`, or
   `promoted`;
2. four commercial source artifacts exist in Object Storage and the latest scheduled
   Service Product verification has a terminal result for its registered Oracle sources;
3. regression coverage is 100%;
4. blocked or pending-review changes have an owner and decision;
5. the latest approved evidence remains inside the BOM freshness window;
6. Celery Beat and the worker are healthy and the Redis lease is not stuck.

Release validation additionally executes API, calc-engine, pricing-engine, frontend,
OpenAPI, migration, Docker, browser, and quotation/BOM regression gates. Source hashes,
approval state, regression summaries, and immutable artifact references are the
traceable evidence of completion.
