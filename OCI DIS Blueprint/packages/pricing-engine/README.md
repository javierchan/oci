# OCI DIS Pricing Engine

Pure Python calculations for governed OCI Bill of Materials snapshots. The
package has no database, HTTP, queue, or framework dependencies.

All monetary and usage calculations use `Decimal`. Callers must allocate shared
free tiers before pricing lines, pass an immutable currency rule, and preserve
the returned unrounded amount for aggregate reconciliation.

Supported monthly pricing models:

- `hourly`: configured quantity multiplied by billable hours;
- `monthly`: configured quantity charged once per month;
- `per_item`: chargeable consumption divided by the SKU billing unit;
- `hour_utilized`: configured quantity, billable hours, and utilization ratio.

Tier selection follows the OCI workbook convention: `rangeMin` is exclusive and
`rangeMax` is inclusive. A zero-usage line costs zero without requiring a tier.
