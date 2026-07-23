# DIS Technical Demand Propagation

## Purpose

This contract keeps Integration Canvas, BOM, and Pricing aligned on the same
deterministic interpretation of technical demand. It prevents every product in a
route from receiving a blind copy of the integration payload and prevents a BOM
from being approved when a service still needs an explicit transport or metering
decision.

## Authoritative flow

1. The governed catalog supplies payload, response size, execution cadence,
   fan-out, retries, and the saved directed Canvas route.
2. The API converts that evidence into pure `FlowEvidence`.
3. The calc engine propagates evidence through each route node in order.
4. A registered metric adapter converts the effective node demand into the
   commercial unit used by the approved Service Product mapping.
5. Canvas presents the same input/output evidence and monthly metric values that
   the BOM engine persists in immutable line provenance.
6. BOM approval and publication reject blocked or explicit-input-required demand.

The calc engine remains pure Python. It has no database, HTTP, or ORM dependency.
Service mappings and metering policies remain governed database data rather than
formula branches in API routes or React components.

## Route semantics

Payload is propagated over directed connections. A downstream node receives the
upstream output, not the original integration payload by default.

Each node records:

- input and output payload per message,
- input and output messages per execution,
- fragments per input message,
- effective fan-out,
- executions and messages per month,
- payload strategy,
- offloaded payload when a pointer strategy is selected,
- commercial metric quantities, formulas, and source evidence,
- node-local blockers, inherited upstream blockers, and required user decisions.

Node-local and inherited blockers remain separate. The adapter for the current
service always evaluates its own governed transport and metering rules. A later
service receives unresolved upstream blockers as `upstream_blockers` and cannot
price demand until those decisions are resolved, but it does not relabel an
upstream limit as one of its own. For example, Queue owns a 256 KB transport
decision while a following Functions node reports that the route is blocked
upstream.

Supported payload strategies are:

- `native`: the service processes the effective upstream message directly;
- `fragment`: the message is divided according to the service transport limit;
- `object_storage_pointer`: the body is offloaded and the route carries the
  configured pointer payload.

The App never selects fragmentation or pointer offload merely to make a route
pass. The strategy must be present in governed scenario or service evidence.

## Critical product behavior

- **Oracle Integration 3**: payload contributes 50 KB billing blocks. A payload
  larger than 50 KB is not treated as an invalid message solely because it spans
  multiple billable units.
- **OCI Queue**: request demand is calculated independently for put, get, delete,
  and update operations using 64 KB request units. A message over the governed
  transport maximum requires an explicit fragmentation or pointer strategy.
- **OCI Streaming**: put and consumer/get demand, transfer, and retained storage
  use the propagated message and fragment counts. Payload over the governed
  message maximum requires an explicit strategy.
- **OCI API Gateway, Functions, and Object Storage**: request, execution,
  transfer, and storage demand use the effective payload at their position in the
  route. Object Storage pointer mode retains both offloaded body and pointer
  evidence.
- **Data Integration, Data Integrator, GoldenGate, IAM, Observability, Events, and
  Process Automation**: required mappings use registered adapters when demand is
  derivable. Metrics that cannot be derived from integration flow remain
  `explicit_input_required`; they are never estimated with a generic payload
  percentage.

## Coverage invariant

Every approved required Service Product mapping used by the BOM must have a
registered deterministic metric adapter. The test suite compares the approved
mapping registry to the adapter registry and fails on either missing or orphaned
keys.

An unsupported metric returns `blocked`. A metric that legitimately depends on a
client planning input returns `explicit_input_required`. Both states block BOM
approval and publication while still allowing the scenario to remain a reviewable
draft.

## Validation boundaries

Regression coverage includes:

- OIC 50/51 KB billing blocks,
- Queue 64/65 KB request units and 256/257 KB transport decisions,
- Streaming 1 MB boundary,
- batching, fan-out, retries, fragmentation, and pointer offload,
- sequential payload transformation,
- complete approved mapping-to-adapter coverage,
- typed technical-demand API responses,
- immutable BOM provenance and publication blocking,
- Canvas formatting for status, payload, messages, and monthly metrics.

Official source changes are adopted through Service Product governance and its
verification workflow. Runtime calculations do not scrape documentation or
silently replace approved policy.
