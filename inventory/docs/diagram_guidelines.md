# Architecture Reference Diagram Guidelines

## Scope

This report distills layout and abstraction guidance from the reference diagrams in
`project/architecture_references/`. The sources are drawio assets inside the
reference zip files and are cited with file paths and line numbers.

## Evidence Sources

- Core landing zone reference: `project/architecture_references/oci-core-landingzone-oracle.zip:oci-core-landingzone-oracle/oci-core-landingzone.drawio`
- JMS topology reference: `project/architecture_references/jms-oci-topology-oracle.zip:jms-oci-topology-oracle/jms-oci-topology.drawio`
- Integration pattern reference: `project/architecture_references/integration-architecture-pattern-1-oracle.zip:integration-architecture-pattern-1-oracle/integration-architecture-pattern-1.drawio`
- AI workflow reference: `project/architecture_references/ai-llm-workflow-architecture-oracle.zip:ai-llm-workflow-architecture-oracle/ai-llm-workflow-architecture.drawio`

## Observed Patterns (Evidence-Based)

1) Tenancy and compartment hierarchy is explicit.
   - Tenancy boundary is labeled as the root compartment. (oci-core-landingzone.drawio:197)
   - An enclosing compartment wraps functional compartments. (oci-core-landingzone.drawio:212)
2) Functional compartments are named and separated by responsibility.
   - Network, Security, and App compartments are explicitly labeled. (oci-core-landingzone.drawio:277, 3897, 4752)
   - Observability and Management is also a distinct compartment. (jms-oci-topology.drawio:3437)
3) Network topology is modeled with explicit VCNs and subnets.
   - VCN grouping is emphasized in the core landing zone. (oci-core-landingzone.drawio:1382)
   - Subnets are named and shown as distinct layers. (oci-core-landingzone.drawio:1622, 1767, 1912)
   - Simple workloads still show VCNs and subnets. (integration-pattern.drawio:62, 77, 172)
4) External connectivity is explicit and labeled.
   - Internet and DRG are called out. (oci-core-landingzone.drawio:1482, 322)
   - Internet and gateways are also explicit in other references. (jms-oci-topology.drawio:227, ai-workflow.drawio:87, 312)
5) Security and IAM overlays are represented as first-class elements.
   - IAM Identity Domain is called out. (oci-core-landingzone.drawio:7032)
   - Security Zone appears in multiple diagrams. (oci-core-landingzone.drawio:8107, jms-oci-topology.drawio:6697)
   - IAM is explicitly represented. (jms-oci-topology.drawio:6022)
6) Legends are used to explain notation or status.
   - The landing zone includes a legend block. (oci-core-landingzone.drawio:162)
7) Workload-specific compartments are still explicitly labeled.
   - Data Integration Compartment is a clear boundary. (integration-pattern.drawio:337)
   - Generic Compartment boundary is labeled in AI workflow. (ai-workflow.drawio:32)

---

## Diagram Guidelines for OCI Inventory Outputs

### How to Use These Guidelines

- Treat the requirements in "Additional Abstraction Requirements (OCI-Aligned)" and "Data-Driven Rendering Requirements" as mandatory.
- Use "Observed Patterns (Evidence-Based)" as supporting evidence, not as hard requirements.
- If any guidance conflicts, the OCI-aligned abstraction and data-driven requirements take precedence.

---

### 1) Consolidated Flowchart Diagram (Global Summary)

- Applies to `diagram.consolidated.flowchart.mmd`.
- Always show the Tenancy boundary and Regions at depth 1.
- At depth 2+, include Compartment -> VCN -> Subnet hierarchy with category counts.
- Use Region as the primary grouping under Tenancy to represent global footprints.
- Explicitly render Internet/DRG/gateways when present and connected in the graph.

#### 1a) Consolidated Outputs and Depth Levels (Implementation)

The pipeline emits one consolidated diagram per run:
- `diagrams/consolidated/diagram.consolidated.flowchart.mmd` (Mermaid flowchart).

The flowchart output is the global connectivity map at depth 1; at depth > 1 it renders a consolidated summary hierarchy
(Tenancy -> Region -> Compartment -> VCN -> Subnet) with category counts.

When Mermaid size limits are exceeded, additional split outputs may be emitted:
- `diagrams/consolidated/diagram.consolidated.flowchart.region.<region>.mmd` or `diagram.consolidated.flowchart.compartment.<compartment>.mmd`
- `diagrams/workload/diagram.workload.<workload>.partNN.mmd`

Depth controls are a rendering knob for consolidated outputs and the tenancy view; per-VCN diagrams remain full detail and workload diagrams remain full detail for their workload scope.
- Depth 1 (Global Map): tenancy + regions only, rendered in `diagram.consolidated.flowchart.mmd`. No compartments at this level.
- Depth 2+ (Consolidated flowchart): summary hierarchy with category counts (Compute/Network/Storage/Policy/Other) inside VCN-level,
  subnet, and out-of-VCN containers; no per-resource nodes or relationship edges.

Global and consolidated flowcharts use `flowchart TD` for readability; regional/workload flowcharts continue to use `flowchart LR`.

If consolidated output exceeds Mermaid text limits, the renderer reduces depth until it fits and annotates the diagram with a NOTE comment.
If consolidated output still exceeds Mermaid text limits at depth 1, the renderer splits the consolidated view by region (preferred) or by top-level compartment and writes a stub consolidated diagram that references the split outputs.

Cross-region links in the global flowchart MUST be drawn only from explicit DRG/RPC constructs; inferred traffic lines are forbidden.

Per-VCN diagrams are generated at full detail; if an individual diagram exceeds Mermaid text limits, it is skipped and recorded in the report summary.

Workload diagrams are generated at full detail for the workload scope; if a workload diagram exceeds Mermaid text limits, it is split into deterministic overflow parts. If a single-node slice still exceeds the limit, that node is skipped and recorded in the report summary.

---

### 1b) Tenancy Diagram (High-Density Shell)

Applies to `diagrams/tenancy/diagram.tenancy.mmd`. This diagram is designed to survive high-density tenancies without exceeding Mermaid limits.

- Depth 1 (Tenancy Level): show Tenancy + Regions + top-level Compartments only. No resources.
- Depth 2 (Compartment Level): inside each compartment, show only VCNs and Subnets.
- Depth 3 (Resource Level): resources exist only inside Subnets or as an Out-of-VCN summary.

Mandatory aggregation (per Subnet or Out-of-VCN container):
- Instances -> Instances (n=X)
- Boot/Block volumes -> Block Storage (n=X)
- LogAnalyticsEntity + Alarm + Metric -> Observability Suite (n=X)
- Autonomous Database -> Autonomous DBs (n=X)
- Exadata VM Clusters -> Exadata VM Clusters (n=X)
- All other resource types -> <Type> (n=X)

Noise reduction:
- No functional overlays or management flows.
- Labels must exclude OCIDs, versions, and timestamps.
- No edges from individual resources to OCI Services. Use a single edge from the VCN boundary to OCI Services when a Service Gateway exists.

Visual requirements:
- Global direction must be LR; inside compartments must be TB.
- Mermaid node IDs must be semantic (no hashed/hex IDs).

---

### 2) Workload-Specific Diagrams (Detailed)

- Keep compartment boundary visible.
- Show VCNs and subnets explicitly.
- Keep Internet/gateways/DRG visible for connected workloads.
- Use solution-specific compartment naming when applicable.

---

### 3) Labeling and Grouping Conventions

- Label compartments and key zones.
- Label subnets (role labels allowed).
- Label Internet and DRG.
- Aggregation is not permitted for per-VCN and workload diagrams. Consolidated diagrams at depth 2 may aggregate counts by resourceType or category as defined above.

---

## Implementation Mapping for This Project

These patterns map cleanly to inventory pipeline outputs:
- Tenancy and compartments -> compartmentId and lineage
- Network boundaries -> VCN + subnets
- External connectivity -> DRG, gateways, Internet
- Security overlays -> IAM Identity Domains, Security Zones

Use these as the target structure for diagrams.

---

## Additional Abstraction Requirements (OCI-Aligned)

### A) Canonical Containment Hierarchy

OCI containment MUST be reflected:

Tenancy -> Compartment -> VCN -> Subnet -> Resource

Regions and Availability/Fault Domains are overlays:
- Region boundaries MUST be visible in multi-region views but do not break compartment or VCN containment.
- AD/FD SHOULD be represented as lanes, dashed columns, or labels grouping resources logically, without introducing extra nested containers.

Rules:
- Tenancy boundary MUST be shown.
- Region boundaries are a primary grouping axis for multi-region inventories (overlay, not strict containment).
- Subnets MUST be inside named VCNs.
- Resources SHOULD be annotated or grouped by AD/FD when mapping data is available.
- Resources with VNIC MUST be inside subnets.
- Managed services without VNIC MUST NOT be inside VCNs.

---

### B) Functional Grouping as Overlays

Functional compartments (Network, Security/IAM, App/Workloads, Observability/Management, Data/Storage) are overlays, not replacements for OCI hierarchy.

---

### C) In-VCN vs Out-of-VCN Services

MUST visually distinguish:
- Inside VCN: Compute, OKE nodes, LBs, DB (with VNIC), etc.
- Outside VCN but inside tenancy: Object Storage, Logging, Metrics, Vault, Events, Identity, Edge, Media Assets, etc.

---

### D) External Connectivity Completeness

If present in inventory, diagrams MUST expose:
- Internet Gateway
- NAT Gateway
- Service Gateway
- DRG
- VPN / FastConnect

Gateways MUST be placed at VCN/tenancy edge and labeled.

---

### E) IAM and Security Overlays

IAM/security constructs MUST be drawn as overlays at correct scope:
- Tenancy / Identity Domain
- Compartment
- VCN / Subnet / NSG

Examples: IAM Domains, IAM Policies, Security Zones, NSGs, Security Lists.

---

### F) Minimum Labeling Conventions

MUST label:
- Tenancy name
- Compartment names
- VCN names
- Subnet names (or roles)
- Gateway types (IGW, NAT, SGW, DRG, VPN, FastConnect)

---

### G) Readability Requirements

Diagrams MUST be explicit about their scope and level of detail.

Overview views MAY aggregate resources by type/category and MAY filter the scope (e.g., env=prod, workload=<name>, tier=critical), as long as:
- The view clearly indicates it is an overview/filtered view (by name, filename, or diagram comments).
- A corresponding full-detail view exists for that scope (subject to Mermaid size limits).

Additional readability requirements:
- Legend if using icons/colors/status.
- At least one logical flow line if relevant.

---

### H) Optional Iconography and Styling (Best-Effort)

When supported by the renderer, specialized services MAY use specific Mermaid icons:
- Queue/Streaming: queue
- Identity/IAM: identity
- Notification/ONS: notification
- Load Balancers: loadbalancer
- Security (WAF/NSG): security
- Compute/Instances: compute
- Storage/Volumes: storage
- Databases: database
- Gateways: cloud
- External/Internet: cloud

Dynamic Styling Rules (best-effort):
- Environment: Nodes SHOULD be styled by environment tags (prod = orange border, nonprod = dashed gray).
- Health: Nodes with errors SHOULD display an alert badge and use an alert style class.

These are presentation layer concerns and intentionally not part of OCI abstraction.

Note: consolidated diagram depth levels are an implementation detail for this pipeline, but the depth-specific aggregation and scoping rules above are mandatory for consolidated outputs.

---

## Data-Driven Rendering Requirements

The guidelines above define what must be represented in OCI diagrams and how it should be abstracted.
This section defines how data sources MUST be used to drive generation.

Unless stated otherwise, "the graph" refers to combined data from inventory, graph nodes, graph edges, and relationship files.

---

### 1) Use of Graph Relationships (Flows and Dependencies)

- Workload diagrams SHOULD NOT be disconnected collections of boxes.
- Generator SHOULD draw at least one end-to-end value flow per workload when edges allow it.
- Prefer explicit edges (IN_VNIC, IN_SUBNET, IN_VCN, media relationships, attachment edges).
- When edges are missing, generator MAY infer relationships if not obviously false.
- Administrative relationships (e.g., IN_COMPARTMENT) MUST drive placement but SHOULD NOT be drawn unless clarifying.

---

### 2) IAM and Policy Relationships

- IAM/policy overlays SHOULD appear in workload diagrams when data is available.
- IAM constructs SHOULD be overlays with relationships, not isolated nodes.
- Generator SHOULD:
  - Place IAM/policy nodes at correct scope.
  - Draw edges to protected/enabled resources when inference is reasonable.
  - Aggregate policies rather than expand statement-by-statement when detail is excessive.

---

### 3) Tags and Metadata Overlays

- Tags/metadata (team, lifecycle, createdBy/At) SHOULD be available to renderer when present in inventory.
- Diagram MAY show badges or overlays.
- Full tag dumps MUST NOT be placed inside labels.

---

### 4) Graph Integrity and Anomaly Reporting

Renderer MUST:
- Compute integrity metrics (e.g., 137/137 edges valid).
- Include Graph Health section in report.
- Detect anomalies (e.g., subnet w/o route table, VCN w/o gateways).
- NOT fail due to anomalies -- surface instead.

---

### 5) Alignment Between Reports and Diagrams

- "At a Glance" and "Workloads and Services" sections are authoritative.
- Every workload listed SHOULD appear in diagrams.
- Counts SHOULD reconcile (aggregation allowed).
- Identifiers SHOULD match (sandbox, edge, media, etc.).

---

### 6) Readability and Legend Updates

- New overlays (IAM, tags, health) SHOULD update legend.
- Grouping SHOULD still show at least one representative logical flow.
- Diagrams should favor legibility; overview and full-detail expectations are defined below.

---

### 7) Scope Definition (Views)

Scope defines which inventory/graph elements a diagram is responsible for rendering.
Common scope types include:
- A single VCN (optionally filtered by tags such as env, workload, team).
- A single workload (resources tagged with workload=<name> plus their direct dependencies).
- A tenancy slice (e.g., all env=prod resources in a region).

Each diagram MUST have an implied or documented scope, expressed via its filename and/or comments in the `.mmd` output
(`diagram.workload.<workload>.mmd`, `diagram.network.<vcn>.mmd`, `diagram.tenancy.mmd`, split parts, etc.).
The diagram content SHOULD align with how the scope was derived from nodes, tags, and relationships.

The generator emits `%% Scope:` and `%% View:` comments near the top of each `.mmd` file to make scope and detail level explicit.

---

### 8) Full-Detail Coverage and Overview Views

Full-detail views:
- For each scope (see Scope Definition), there MUST be at least one full-detail view where all nodes and edges in that scope are rendered, subject only to Mermaid text limits.
- If a full-detail diagram exceeds Mermaid text limits, the existing split/skip logic applies, and splits/skips MUST be recorded in the report summary.

Overview views:
- Additional views over the same scope MAY aggregate resources and/or filter them (e.g., only prod, only network resources), as long as:
  - The view clearly indicates that it is an overview/filtered view (by name or description).
  - The union of full-detail views still covers the entire graph (no resources are globally lost; omissions are per-view by design).

Consolidated flowcharts:
- Consolidated flowcharts MUST include the complete inventory scope; depth 2+ aggregates counts by category but must not omit resources.
- If depth is reduced due to Mermaid limits, it must be annotated in the diagram output.
- If the consolidated output still exceeds limits at depth 1, it must be split by region or top-level compartment with a stub diagram that references the split outputs.

---

### 9) Automation and Drift Enforcement

- This document is the source of truth for abstraction and data usage.
- Agents/generators MUST treat these rules as a contract.
- If drift occurs, generators SHOULD record violations in the report and follow-up in code changes.
- Updates to this document MUST update:
  - graph builder
  - diagram generator
  - report generator
  - AGENTS.md

---

## Where Abstraction Requirements Do Not Apply (and Why)

The abstraction rules do NOT prescribe:
- Visual layout (horizontal/vertical/swimlanes/grid)
- Iconography or theme
- Arrow/connector styles
- Zoom levels (L0/L1/L2/L3)
- Optional layers (traffic flows, SLOs, dependencies)
- Rendering-density heuristics
- Vendor tooling or syntax preferences

---

## Change Control

If diagram structure or section expectations change, update:
- `docs/diagram_guidelines.md`
- `docs/architecture.md`
- `AGENTS.md`
