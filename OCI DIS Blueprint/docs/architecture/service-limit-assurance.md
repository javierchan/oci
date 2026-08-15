# Governed Service Limit Assurance

**Status:** implemented claim-level assurance contract

**Effective baseline:** migrations `20260814_0058`–`20260814_0061`

**Scope:** OCI product maximums, quotas, billing granularities, design-time
constraints, performance ceilings, and other normalized Service Product rules
used by the App.

## 1. Executive decision

The App must never equate “an Oracle page was downloaded” with “the maximum in
the App was verified.” The authoritative runtime value remains the approved
`ServiceLimit`; every statement about its documentary confidence is a separate,
claim-level record tied to one exact source hash.

The reliability boundary is therefore:

1. `ServiceLimit` owns the approved value and deterministic behavior.
2. `ServiceEvidenceSource` owns the official URL, current content hash, and
   source-level freshness.
3. `ServiceLimitEvidenceClaim` proves whether an eligible numeric approved value
   was located in that exact source version.
4. `ServiceVerificationFinding` owns conflicts and documentary drift requiring
   a decision.
5. Runtime consumers use the approved `ServiceLimit`; they never calculate from
   model prose or directly scraped text.

This contract intentionally distinguishes registry assurance from exhaustive
Oracle-document completeness. A trusted report proves every active rule in the
App against its assigned source. It does not claim that Oracle has no additional
limit that has not yet entered the registry.

## 2. Responsibility model

| Capability | Owner | May change runtime values? | Human decision |
| --- | --- | --- | --- |
| App routes, entities, workflows, help content, retrieval manifest, embeddings | App Knowledge Governance Agent | No Service Product mutation | None for a validated atomic rebuild |
| Scheduled retrieval, allowlist enforcement, hashing, claim extraction, freshness, explicit gaps | Automated Evidence Verifier | No | None when the source hash and value are unchanged |
| Concise explanation of persisted source-governance state | Official Source Governance Agent | No; inspection only | None for the explanation |
| Conflicting value from an official source | Admin review workflow | Yes, only after deterministic validation and acceptance | Required |
| Constraint semantics (`hard_limit`, `billing_granularity`, applicability, enforcement) | Application engineering/governance | Yes, through code, migration, fixtures, and release validation | Required engineering review |
| Client-specific quotas or approved tenant overrides | Deployment/project governance | Must not overwrite the global Oracle baseline | Required when introduced |

The App Knowledge Governance Agent may index the approved Service Product
projection so the assistant can explain it, but that projection is not a second
authority and embeddings never update a limit.

## 3. Why approval is selective

Routine proof refresh is automatic. A human does not approve a successful
re-download when the content hash and located value remain unchanged.

A human is required when:

- an official document hash changes, because the change can introduce a new
  qualifier or a limit that is not yet registered;
- a located value conflicts with the approved value;
- the source moved, became unavailable, or is no longer Oracle-controlled;
- a proposed change affects unit, scope, applicability, constraint kind, or
  enforcement semantics;
- a tenant-specific quota is being confused with the global documented baseline.

The verifier can propose a value and compatible unit. It cannot reinterpret a
billing increment as a payload ceiling, convert a fixed limit into an adjustable
quota, or silently broaden applicability.

## 4. Limit taxonomy

Every active rule must declare independent constraint kind, enforcement, scope,
applicability, normalized value/unit, and increase policy. For example, Oracle
documents OIC adapter limits by operation and endpoint mode, while the 50 KB OIC
value is a billing increment rather than a universal payload maximum. OCI Queue
documents a 256 KB message maximum and separate request, throughput, retention,
and storage boundaries. OCI Streaming documents a 1 MB message maximum, 7-day
retention maximum, and partition-scoped throughput. API Gateway distinguishes
fixed internal limits from configurable timeouts and requestable tenancy quotas.

Primary references:

- [Oracle Integration 3 Service Limits](https://docs.oracle.com/en/cloud/paas/application-integration/oracle-integration-oci/service-limits.html)
- [Oracle Integration 3 Adapter Limits](https://docs.oracle.com/en/cloud/paas/application-integration/oracle-integration-oci/component-adapters.html)
- [OCI Queue limits](https://docs.oracle.com/en-us/iaas/Content/queue/overview.htm#Service_Limits)
- [OCI Streaming resource limits](https://docs.oracle.com/en-us/iaas/Content/Streaming/Concepts/streamingoverview_topic-Limits_on_Streaming_Resources.htm)
- [OCI API Gateway internal limits](https://docs.oracle.com/en-us/iaas/Content/APIGateway/Reference/apigatewaylimits.htm)
- [OCI limits by service](https://docs.oracle.com/en-us/iaas/Content/General/service-limits/default.htm)

## 5. Assurance states

| State | Meaning | Permitted claim |
| --- | --- | --- |
| `confirmed` | Current approved value was located in the current verified source hash | Documentary evidence is current for this registered rule |
| `conflict` | Located value differs from the approved value | Review required; approved value remains unchanged |
| `not_located` | Assigned source was fetched but the bounded parser did not prove the claim | Source is available; this rule is not documentary-confirmed |
| `source_attention` | Source is unavailable, changed, pending review, or its hash differs from the claim | Do not describe the rule as current |
| `unverified` | No current claim exists | Approved runtime value with no claim-level proof |

Library status is `trusted` only when every active numeric rule is `confirmed`.
Boolean, textual, lifecycle, and required-configuration rules are counted as
non-numeric and excluded from parser coverage; their semantics remain governed
by engineering fixtures and review rather than a misleading numeric parser. Any
conflict or source-attention state produces `attention`; all other incomplete
coverage produces `incomplete`.

## 6. Operational flow

```mermaid
sequenceDiagram
    participant Beat as "Celery Beat"
    participant V as "Automated Evidence Verifier"
    participant Oracle as "Allowlisted Oracle source"
    participant DB as "Governed PostgreSQL"
    participant Admin as "Admin reviewer"
    participant Runtime as "Calc, QA, Canvas, BOM, exports"

    Beat->>V: "Verify sources due under freshness policy"
    V->>Oracle: "GET allowlisted URL"
    Oracle-->>V: "Document content"
    V->>V: "Normalize, hash, locate registered claims"
    V->>DB: "Persist claim history and current projection"
    alt "Same source hash and same value"
        V->>DB: "Mark claim confirmed"
    else "Changed source or conflicting value"
        V->>DB: "Create finding; preserve approved value"
        Admin->>DB: "Accept, dismiss, or retain for review"
    else "Claim not located or source unavailable"
        V->>DB: "Record explicit coverage gap"
    end
    DB-->>Runtime: "Approved ServiceLimit plus assurance metadata"
```

## 7. Release and operating gates

A Service Product limit package is ready for a customer-facing deliverable only
when all applicable gates pass:

- 100% of active numeric `hard_limit`, `billing_granularity`, `calculate`,
  quota, retention, and performance rules in the deliverable are `confirmed`
  against current official hashes;
- no open high-severity changed-limit, deprecation, or source-unavailable finding
  affects the proposed architecture;
- every runtime rule has constraint kind, enforcement, scope, applicability,
  normalized value, and unit;
- every source is Oracle-controlled and allowlisted;
- deterministic fixtures prove blocking, warning, or calculation behavior;
- exported artifacts include the Service Rule Bundle version and freshness;
- the assurance report is captured with the deliverable date.

The API contract is `GET /api/v1/service-products/limit-assurance`. The Admin
Service Product Library shows total claim coverage and a per-product breakdown.
The product detail page shows the assurance status of each maximum.

## 8. Observed baseline and interpretation

The pre-claim baseline observed on 2026-08-14 contained 23 active products, 173
active rules, 97 evidence sources, and 91 source pages labeled verified. Of those
rules, 89 are numeric claim-eligible rules and 84 are non-numeric capability,
configuration, lifecycle, or informational rules. None of the 173 rules had an
individual retrieval timestamp. This proved that the
previous `verified` label measured page retrieval/hash state, not the exact
limit claim.

Migration `20260814_0058` intentionally starts eligible rules as `unverified` until
the automated verifier records claim-level proof. This is a truthfulness change,
not a regression: unknown confidence is now visible instead of being inferred
from a page-level badge.

Migration `20260814_0059` corrects the canonical source assignment for API
Gateway, Streaming, and Queue from broad landing pages to the registered Oracle
pages that actually define their limits. Bounded scans prioritize sources that
have active rules assigned, so `max_sources` cannot be consumed first by an
unrelated pricing or tutorial page.

Migration `20260814_0060` corrects rate semantics that the legacy suffix
inference had represented as elapsed seconds or plain MB. Queue and Streaming
throughput now use `MB/s`; request rates use `requests/s`. Claim extraction
compares compound units without converting a rate into an elapsed duration.

Migration `20260814_0061` makes the parser version part of claim identity. A new
verifier release therefore creates a new immutable result for the same source
hash instead of rewriting the interpretation produced by the prior release.

The post-migration real-source smoke on 2026-08-14 checked the canonical Oracle
pages registered for API Gateway, Queue, and Streaming. It confirmed 2 of 11,
10 of 16, and 0 of 9 numeric limits respectively, with no conflicts or source
failures. Global numeric claim coverage was 13.48%. This is the accepted honest
baseline for the assurance mechanism, not release approval for the library:
the remaining `not_located` claims require source mapping or parser remediation
before a customer-facing bundle can pass the 100% gate in section 7.

## 9. Closed design decisions

- Raw source content is not copied into App Knowledge or model prompts by default;
  bounded excerpts and hashes are persisted with findings and claims.
- The scheduled verifier is enabled by default and protected by a Redis lease.
- The global Oracle baseline and future tenant-specific quota overrides remain
  separate authorities.
- Verification is limited to Oracle-controlled allowlisted hosts.
- HTTP retrieval is the baseline adapter; another adapter must honor the same
  claim and assurance contract.
- The Official Source Governance Agent explains persisted evidence. It does not
  edit Oracle documentation or autonomously mutate runtime limits.
