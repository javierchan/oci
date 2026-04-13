# Assistant Quality Regression

## Purpose

This document defines the fixed live-quality regression for the `pricing` assistant.

Document role:

- this file is the source of truth for the live semantic-quality regression against the running assistant
- deterministic runtime coverage does not belong here; that lives in [Coverage Roadmap](/Users/javierchan/Documents/GitHub/oci/pricing/docs/COVERAGE_ROADMAP.md)
- tactical sequencing does not belong here; that lives in [Execution Plan](/Users/javierchan/Documents/GitHub/oci/pricing/docs/EXECUTION_PLAN.md)
- the full docs map lives in [Docs Guide](/Users/javierchan/Documents/GitHub/oci/pricing/docs/README.md)

The goal is different from deterministic calculator parity:

- parity proves that the pricing engine resolves SKUs and totals correctly
- assistant regressions prove routing, follow-ups, and guardrails
- the quality regression proves that the assistant answers human pricing questions with enough semantic accuracy, consistency, and service context

This regression is intentionally run against the live API exposed by the local container at `http://localhost:8742`.

## Fixed Command

Run the fixed baseline from [package.json](/Users/javierchan/Documents/GitHub/oci/pricing/server/package.json):

```bash
npm run quality:assistant:fixed
```

This executes:

- `100` live discovery-style iterations
- `seed = 20260410`
- `concurrency = 1`
- `delay = 800ms`
- `jitter = 300ms`
- `maxRetries = 3`
- report path:
  - `/tmp/pricing-assistant-quality-20260410-final.json`

The low request rate is deliberate. It keeps the regression representative while avoiding avoidable OCI GenAI throttling.

## What This Regression Measures

Each iteration asks a real human-style discovery or pricing-model question and scores the reply on five dimensions:

1. API health
   The call must return `HTTP 200` and `payload.ok = true`.
2. Correct response mode
   The assistant must answer in `mode = answer`, not produce a deterministic quote.
3. Correct route
   The request must stay in `product_discovery` with `shouldQuote = false`.
4. Correct family grounding
   The response must map to the expected OCI family or to an explicitly allowed equivalent family id.
5. Semantic concept coverage
   The response must mention the expected pricing dimensions, quote components, or prerequisite inputs for that service.

For services with known multi-SKU composition, the regression also checks whether the answer includes the expected part numbers when that is appropriate.

## Scoring Model

Each response gets a score from `0.0` to `1.0`.

Current weights:

- `0.15` API returned `200` and `payload.ok = true`
- `0.15` response stayed in `mode = answer`
- `0.20` response stayed in `product_discovery` with `shouldQuote = false`
- `0.20` detected family matched the expected family
- `0.25` concept-group coverage
- `0.05` expected part-number coverage when the scenario includes SKU checks

Pass threshold:

- `score >= 0.85`
- and no hard validation errors

Warnings do not fail a scenario by themselves, but they are preserved in the JSON report for analysis.

## Service Coverage

The fixed regression currently exercises the assistant across these service areas:

- OCI Compute Virtual Machine
- Oracle Integration Cloud
- OCI Load Balancer
- OCI Block Volume
- OCI File Storage
- OCI Functions
- OCI Network Firewall
- OCI Web Application Firewall
- Base Database Service
- Autonomous AI Lakehouse
- Exadata Exascale
- OCI Health Checks
- OCI API Gateway
- OCI FastConnect
- OCI Monitoring
- OCI Notifications HTTPS Delivery
- OCI Email Delivery
- Oracle Analytics Cloud

The intent is to cover:

- single-family pricing-model questions
- multi-SKU composition questions
- prerequisite-input discovery
- services that are frequently composed into larger OCI quotes

## Example Quality Expectations

### Virtual Machine Instances

For VM composition prompts, the assistant is expected to describe a consistent quote in terms of:

- `OCPU`
- `memory`
- `shape`
- `Block Storage`
- `VPU` or storage performance

This protects against shallow or misleading answers such as reducing a VM quote to only one SKU.

### Oracle Integration Cloud

For OIC composition prompts, the assistant is expected to ground the answer in:

- `Standard`
- `Enterprise`
- `BYOL` or `License Included`
- the relevant OIC part numbers:
  - `B89639`
  - `B89643`
  - `B89640`
  - `B89644`

### Flexible Load Balancer

For load balancer pricing-model questions, the assistant is expected to explain:

- base load balancer capacity
- bandwidth in `Mbps-hour`
- and, where applicable, the related SKUs:
  - `B93030`
  - `B93031`

## Output Report

The report is written as JSON to:

- [/tmp/pricing-assistant-quality-20260410-final.json](/tmp/pricing-assistant-quality-20260410-final.json)

Key fields:

- `ok`
- `count`
- `averageScore`
- `failures`
- `throttledRetries`
- `stats`
- `passScore`

If any scenario fails, the report also includes:

- prompt text
- detected family
- concept-match counts
- part numbers found in the message
- a response preview for quick diagnosis

## Baseline Result

Current validated baseline on **April 10, 2026**:

- `100 / 100` passed
- `averageScore = 0.9865`
- `failures = 0`
- `throttledRetries = 0`

This baseline confirms that the assistant is not only reachable, but also semantically consistent for the covered service set.

## Relationship To Other Validation Layers

Use the quality regression together with:

- [ARCHITECTURE.md](/Users/javierchan/Documents/GitHub/oci/pricing/docs/ARCHITECTURE.md)
- [COVERAGE_ROADMAP.md](/Users/javierchan/Documents/GitHub/oci/pricing/docs/COVERAGE_ROADMAP.md)
- [EXECUTION_PLAN.md](/Users/javierchan/Documents/GitHub/oci/pricing/docs/EXECUTION_PLAN.md)
- [assistant-fuzz.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/scripts/assistant-fuzz.js)
- [assistant-quality.js](/Users/javierchan/Documents/GitHub/oci/pricing/server/scripts/assistant-quality.js)

Recommended validation stack:

1. deterministic unit and regression suites
2. calculator parity suite
3. assistant fuzz regression for live API consistency and resilience
4. assistant quality regression for semantic accuracy and discovery quality

## Operational Notes

- This regression depends on the local pricing container being up and reachable.
- It is a live API evaluation, not a pure unit test.
- If the environment blocks loopback access from the sandbox, run it with elevated local permissions.
- Do not increase concurrency casually; OCI GenAI throttling can invalidate the signal.
