# OCI Pricing Workbook Parity Specification

## Status and scope

This specification defines the focused workbook-parity contract for the governed
OCI pricing and BOM capability. It is intentionally limited to Oracle Integration
Cloud (OIC), Data Integration, Functions, Streaming, Queue, GoldenGate, and API
Gateway.

The authorized reference is `OCI_Estimation_Sheet_Customer_WIP.xlsm`, inspected
read-only with SHA-256:

`277394526572ad92c4b21a235dbc63c90f8dcc14bd06f9ee36dfc4c4b8dd3435`

The source workbook is labeled `Confidential - Oracle Internal`. The repository
therefore stores only compact, sanitized fixtures containing the public SKU,
metric, price, tier, formula, and source-location evidence required for tests. It
does not contain the workbook, customer data, the complete price list, the full
preset taxonomy, VBA source, or unrelated AWS query definitions.

The planning artifact calls this work `M26` Phase 0. `AGENTS.md` already contains
two historical milestones numbered M26; this document does not renumber existing
milestones and uses "pricing parity specification" as the unambiguous identifier.

## Workbook inventory

| Sheet | Visibility | Used range | Pricing/BOM responsibility |
| --- | --- | --- | --- |
| `Usage` | hidden | `A1:N79` | Workbook usage guidance. |
| `Quotation` | hidden | `A1:W97` | Three environment sections, row-level quantity/instance/hour pricing, and annual extension. |
| `Summary` | hidden | `A1:U33` | Consolidates equivalent quotation lines and totals quantities. |
| `Quotation_Sample` | hidden | `A1:W97` | Sample quotation behavior. |
| `Summary_Sample` | hidden | `A1:U97` | Sample summary behavior. |
| `BOM` | visible | `A1:DI1001` | Four-year, monthly quantity and price schedule. |
| `Consideraciones` | visible | empty | User considerations surface. |
| `Master Brief` | visible | `A1:AO64` | Estimation brief. |
| `Componentes Dashboard` | visible | `A1:AZ59` | Component dashboard. |
| `Consumo Dashboard` | visible | `A1:AS577` | Consumption dashboard. |
| `OCI Pricing List` | visible | `A1:K732` | Cached public OCI price rows in table `O_OCI_PRICING_TABLE`. |
| `OCI Product Presets List` | visible | `A1:G805` | Cached product-to-preset rows in `O_OCI_PRODUCT_PRESETS_TABLE`. |
| `Master Sheet` | very hidden | `A1:C1085` | Hierarchical category and named-range source in `OCI_SERVICE_CATEGORY_TABLE`. |
| `Settings` | hidden | `A1:D12` | Update URLs, currency, language, proxy, and compute modifier SKU lists. |

The workbook contains 22 Power Query connections named for AWS billing queries.
They are unrelated to OCI list-price refresh and are not part of this parity
contract. OCI refresh is implemented by VBA HTTP GET requests.

## Online update contract

### Workbook endpoints

The `Settings` table contains these unauthenticated JSON endpoints:

- products: `https://www.oracle.com/a/ocom/docs/cloudestimator2/data/products.json`
- product presets: `https://www.oracle.com/a/ocom/docs/cloudestimator2/data/productpresets.json`
- metrics: `https://www.oracle.com/a/ocom/docs/cloudestimator2/data/metrics.json`

The configured language is `en`; the configured currency is `USD`. The price and
preset cache timestamps are `2026-07-11T00:21:51Z` and
`2026-07-11T00:21:55Z`, respectively.

### `FetchOCIPrice2`

`FetchOCIPrice2` performs the following ordered operation:

1. Read endpoint, currency, and optional proxy settings.
2. Download `metrics.json` and map metric IDs to display names.
3. Download `products.json`.
4. For each product, choose the `currencyCodeLocalizations` entry whose currency
   equals the configured currency, case-insensitively.
5. Emit one table row for every price entry, including repeated rows for tiered
   SKUs.
6. Prefix the B part number to the display name when it is absent.
7. Normalize the metric label `Load Balancer` to `Load Balancer Hour`.
8. Stage all 11 output columns in memory. Replace the table only after a complete,
   non-empty response has been parsed.
9. Record the item count and refresh time.
10. Refresh presets, rebuild category names, and recalculate every worksheet whose
    code name includes `Quotation`.

The HTTP helper uses GET, JSON, a 60-second timeout, an optional configured proxy,
Windows automatic proxy discovery, and at most four attempts separated by five
seconds. Mac responses receive a UTF-8/mojibake normalization pass before JSON
parsing. Failures retain the previous table and report the failing stage.

### `FetchOCIProductPresets2`

For each preset, category, and product part number, this routine finds every
matching pricing row. Tiered display names are serialized as
`<display-name>#[<rangeMin>-<rangeMax>]`. It then atomically replaces the seven
column preset table and rebuilds the hierarchical `Master Sheet` plus workbook
defined names used by quotation dropdowns.

## Cached price schema

`O_OCI_PRICING_TABLE` contains:

1. `No.`
2. `Part Number`
3. `Display Name`
4. `Price Type`
5. `Currency Code`
6. `Metric Display Name`
7. `Service Category DisplayName`
8. `PAY_AS_YOU_GO`
9. `Range Min`
10. `Range Max`
11. `Range Unit`

Prices and quantities must be represented as decimal strings in test fixtures and
as `Decimal` values in the engine. Floating-point database fields are not a parity
reference.

## Price types and extension formulas

### Workbook UDF flow

For each `Quotation` line:

```text
metric              = GetProductMetric(product)
rate                = CalcRate(reservation_utilization, preemptible, burst_baseline)
hourly_unit_price   = GetPAYGPricePerHour2(product, rate)
monthly_unit_price  = GetPAYGPricePerMonth2(product, hourly_unit_price, hours, rate)
monthly_line_amount = monthly_unit_price * instances * metric_quantity
annual_line_amount  = monthly_line_amount * 12
```

`GetPAYGPriceFromPriceList` parses the B part number and optional `#[min-max]`
suffix, then matches `Part Number`, `Range Min`, and `Range Max` exactly.

### `HOUR`

`GetPAYGPricePerHour2` returns `PAY_AS_YOU_GO * rate`.
`GetPAYGPricePerMonth2` multiplies that result by the line's monthly hours.

Equivalent formula:

```text
monthly = metric_quantity * instances * unit_price * rate * monthly_hours
```

### `HOUR_UTILIZED`

The workbook treats this price type as hourly in the UDF path. Its formula is the
same as `HOUR`. The App may expose an explicit utilization ratio, but the effective
hours passed to the parity calculation must reconcile to the workbook's monthly
hours.

### `MONTH`

`GetPAYGPricePerHour2` returns `-`. The monthly UDF retrieves the price directly
and applies `rate`; it does not multiply by monthly hours.

Equivalent formula:

```text
monthly = metric_quantity * instances * unit_price * rate
```

### Four-year BOM sheet

The visible `BOM` sheet uses a simpler governed schedule:

```text
included_price     = list_price * (1 - discount), or zero when disabled
monthly_line_price = monthly_quantity * included_price * hour_or_month_factor
annual_total       = sum(month_1 ... month_12)
```

The factor is 744 for hourly metrics and 1 for monthly metrics. Each of four years
has 12 quantity columns, 12 calculated price columns, and one annual total.

## 744-hour behavior

When a product is selected in `Quotation`, the worksheet change handler initializes
metric quantity to 1, instances to 1, and monthly hours to 744. The `BOM` sheet also
stores 744 as its global monthly-hour assumption.

744 is a workbook convention (`31 days * 24 hours`), not a calendar-derived value.
Parity tests therefore pass 744 explicitly. Production deployment scenarios may
override billable hours, but must preserve the selected value in the immutable BOM
snapshot and must never silently call a calendar function.

The convention is not a universal Data Integration sizing rule. A Data Integration
workspace is billed for accumulated time while it is running; stopping it makes it
unavailable and stops workspace billing until it is started again. The App therefore
keeps the environment runtime ceiling separate from each product metric, requires an
explicit workspace-hour quantity, and treats `744` only as an `Always on` shortcut.
Pipeline Operator execution hours are also explicit and independent from workspace
runtime. Partial operator hours use the governed one-minute increment and the price
tiers retain the tenant-level free allowance evidence.

## Commercial quantity policy evidence

The authorized `ORACLE PAAS AND IAAS PUBLIC CLOUD` localizable XLS, global PDF, and
global supplement are policy evidence, not a bundled price source. The current
Oracle pricing adapter remains authoritative for rates and immutable price snapshots.
The reference files establish these quoting semantics for the governed mappings:

- API Gateway part `B92072` is priced per one million API calls and the global list
  explicitly states that partial millions are prorated. The trailing note reference
  in the localizable list is not a commercial minimum. The App therefore preserves
  the exact million-call fraction as the canonical billable quantity. A whole-million
  planning envelope may be displayed as an optional reserve, but it never changes
  the deterministic BOM total.
- Data Integration part `B92598` is workspace usage per hour. The quantity must be
  the planned running hours for each workspace and environment, not an inherited
  744-hour calendar constant.
- Data Integration part `B92599` is processed GB and remains a continuous measured
  quantity independent from workspace runtime.
- Data Integration part `B93306` is Pipeline Operator execution time. Partial hours
  use a one-minute minimum and governed tiers represent the first 30 execution hours
  per tenant and month.

Every normalized BOM period retains measured quantity, billable quantity, optional
planning envelope, increment, minimum, aggregation window, proration policy, free-tier
scope, usage basis, and source policy evidence. This prevents product selection,
pricing, and client workload assumptions from collapsing into one opaque number.

Tenant-level allowances are allocated once per SKU and contract month, in persisted
environment order. They never restart for each environment or BOM line. Streaming
PUT/GET operations, Streaming retention, and Queue push/get/delete/update operations
require explicit evidence; no universal multiplier is supplied by the App.

## Product-level commercial coverage

Every normalized Service Product has one governed publication policy even when it
does not own a standalone OCI SKU. Product-footprint detection is independent from
SKU mappings, so an unmapped product cannot disappear from a scenario or BOM.

The supported policies are:

- `direct_mapping_required`: approved meters must price the product directly;
- `included_zero`: retain a visible included/non-billable line with zero amount;
- `dependencies_required`: price approved Compute, storage, network, or adjacent
  dependencies after the architect supplies the required design inputs;
- `external_rate_required`: require an approved contractual or external rate card;
- `explicit_metric_selection`: require the architect to select the applicable
  optional meter rather than automatically quoting every available add-on.

Each approved mapping also declares `required`, `optional`, or `dependency` scenario
selection. Required mappings seed new plans. Optional IAM and observability meters
remain available but start unselected. Dependency-owned meters can only be introduced
through the product's governed dependency path. Publication remains blocked when a
detected product lacks its policy, required mappings, inputs, or approved price evidence.

The contract covers 20 normalized products. OCI Events is included with downstream
targets priced separately; Oracle Integration Process Automation is dependency-owned
and requires OIC edition and entitlement evidence. Neither relies on a mapping-owned
fallback, and both retain normalized limits, sources, and interoperability rules.

## Compute modifier behavior

`CalcRate` starts at 1 and applies these rules in order:

1. A numeric capacity-reservation utilization `u` produces
   `u + (1 - u) * 0.85`.
2. Any non-empty/non-`-` preemptible value overrides the result with `0.5`.
3. A numeric non-`-` burst baseline overrides all prior values with that baseline.
4. If all three concatenated inputs are empty, the result is empty.

These modifiers are retained as a focused compatibility rule, but they are not
applied to the seven integration-service fixtures unless explicitly present.

## Tier semantics

The workbook stores repeated rows per SKU. `GetSpecifiedRangePrice` considers a
row a match when:

```text
rangeMin <= usage_quantity <= rangeMax
```

Non-numeric minimum and maximum values become `0` and `999999999999999`.
At shared boundaries such as Functions `40`, Queue `1`, and Data Integration
operator execution `30`, both raw rows are mathematically inclusive. The lower
row appears first and is therefore selected first.

The App intentionally normalizes this order-dependent behavior to non-overlapping
tiers:

```text
first tier:  minimum = unbounded, maximum = source rangeMax inclusive
next tiers:  minimum = source rangeMin exclusive, maximum = source rangeMax inclusive
```

This preserves the workbook outcome at exact boundaries while allowing the engine
to reject truly overlapping or uncovered ranges deterministically. Fixtures retain
both the raw workbook bounds and the normalized bounds.

Free allowances represented as zero-price tiers are allocated once at the
tenancy/scenario scope by the App before pricing paid consumption. The workbook
requires the user to select the appropriate range-specific preset and does not
prevent the same free range from being reused on multiple lines.

## Summary aggregation

`UpdateSummaryBtn_Click` groups rows by product display name, monthly hours,
capacity reservation, preemptible state, and burst baseline. For equivalent rows,
it sums `metric quantity * instances`; instance count is intentionally hidden.
The summary then recalculates rather than summing previously displayed rounded
line amounts.

The App must aggregate unrounded deterministic results and round only at the output
boundary. Line totals, service totals, environment totals, and overall totals must
reconcile with an explicit rounding variance.

## Intentional App differences

| Workbook behavior | Governed App behavior |
| --- | --- |
| VBA executes network requests in a user workbook. | Backend adapters fetch data; browsers and exported workbooks never execute pricing macros. |
| Refresh overwrites mutable worksheet tables. | Every refresh creates a hashed immutable price snapshot; diffs require governed review. |
| Legacy static web assets are the embedded source. | A supported Oracle pricing adapter is authoritative; the legacy assets are compatibility evidence only. |
| Tier boundary resolution depends on row order. | Tiers use explicit lower-exclusive/upper-inclusive bounds and reject ambiguity. |
| A user selects a range-specific display name. | The engine selects the tier from governed usage and records the selected source price item. |
| Free tiers can be reused on multiple rows. | Free allocations are tenancy/scenario scoped and consumed once in deterministic order. |
| `744` is inserted automatically. | Environment runtime is an explicit ceiling; product runtime is planned independently and `744` is only an acknowledged always-on shortcut. |
| A single mutable currency setting controls refresh. | Currency is part of the price snapshot; currencies are never silently converted or mixed. |
| Discounts are editable cells. | Public list, contract rate, and approved manual rate are separate provenance modes; discounts cannot be inferred. |
| Summary uses worksheet mutation and hidden columns. | BOM inputs/results are typed records with immutable provenance and audit events. |
| Workbook results are estimates. | App exports remain estimates/BOMs and must not be labeled official Oracle quotes. |

## Focused fixture contract

Fixtures under `packages/test-fixtures/pricing/` use this contract:

- one JSON document per service;
- USD values copied from the cached workbook rows;
- decimal values encoded as strings;
- workbook sheet/row evidence for each price item;
- raw and normalized tier bounds where applicable;
- compact synthetic parity cases with no customer identifiers;
- expected unrounded and currency-rounded outputs;
- no live-network dependency.

The fixture scenarios exercise:

- OIC hourly 5K-message packs and BYOL alternatives;
- Data Integration workspace, data processed, and utilized execution hours;
- Functions execution-time and invocation free allowances;
- Streaming transfer and hourly storage;
- Queue request allowance;
- GoldenGate license-included and BYOL OCPU hours;
- API Gateway monthly million-call units.

## Acceptance checks

1. Every JSON file parses with the standard library and contains no numeric JSON
   values for monetary amounts.
2. Every referenced price item exists in the authorized workbook cache.
3. Boundary fixtures preserve the lower-tier result at 40, 30, and 1.
4. Hourly cases use explicit 744 or another explicit effective-hour input.
5. Expected unrounded results reproduce the documented formula exactly.
6. Expected currency outputs use USD precision and commercial half-up rounding.
7. Fixtures contain no customer data and do not reproduce the complete workbook.
8. No test requires Excel, VBA, network access, or the source `.xlsm`.
