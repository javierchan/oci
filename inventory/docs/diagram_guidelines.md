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

- Treat the requirements in **"Additional Abstraction Requirements (OCI-Aligned)"** and **"Data-Driven Rendering Requirements"** as **mandatory**.
- Use **"Observed Patterns (Evidence-Based)"** as supporting evidence, not as hard requirements.
- If any guidance conflicts, the **OCI-aligned abstraction and data-driven requirements take precedence**.

---

### 1) Consolidated Architecture Diagram (High-Level)

- Always show the Tenancy boundary and an enclosing compartment. (oci-core-landingzone.drawio:197, 212)
- Use functional compartments (Network, Security, App, Observability/Management) as the primary grouping axis.
- Inside Network compartments, show VCNs and named subnets.
- Explicitly render Internet/DRG/gateways when present.
- Include IAM and Security Zone overlays at tenancy or boundary level.
- Provide a legend for symbols and status.

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
- Aggregation is not permitted for inventory diagrams. Use grouping and layout to manage density.

---

## Implementation Mapping for This Project

These patterns map cleanly to inventory pipeline outputs:

- Tenancy & compartments → `compartmentId` and lineage
- Network boundaries → VCN + subnets
- External connectivity → DRG, gateways, Internet
- Security overlays → IAM Identity Domains, Security Zones

Use these as the target structure for diagrams.

---

## Additional Abstraction Requirements (OCI-Aligned)

### A) Canonical Containment Hierarchy

OCI containment MUST be reflected:

```

Tenancy -> Region (optional) -> Compartment -> VCN -> Subnet -> Resource

```

Rules:

- Tenancy boundary MUST be shown.
- Subnets MUST be inside named VCNs.
- Resources with VNIC MUST be inside subnets.
- Managed services without VNIC MUST NOT be inside VCNs.

---

### B) Functional Grouping as Overlays

Functional compartments (Network, Security/IAM, App/Workloads, Observability/Management, Data/Storage) are **overlays**, not replacements for OCI hierarchy.

---

### C) In-VCN vs Out-of-VCN Services

MUST visually distinguish:

- **Inside VCN**: Compute, OKE nodes, LBs, DB (with VNIC), etc.
- **Outside VCN but inside tenancy**: Object Storage, Logging, Metrics, Vault, Events, Identity, Edge, Media Assets, etc.

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

### E) IAM & Security Overlays

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

Diagrams MUST include:

- Legend if using icons/colors/status
- At least one logical flow line if relevant
- No aggregation or omission; use grouping and layout to preserve readability

---

### Where abstraction requirements do NOT apply (and why)

The abstraction rules do **NOT** prescribe:

- Visual layout (horizontal/vertical/swimlanes/grid)
- Iconography or theme
- Arrow/connector styles
- Zoom levels (L0/L1/L2/L3)
- Optional layers (traffic flows, SLOs, dependencies)
- Rendering-density heuristics
- Vendor tooling or syntax preferences

These are **presentation layer** concerns and intentionally not part of OCI abstraction.

---

## Data-Driven Rendering Requirements

The guidelines above define *what* must be represented in OCI diagrams and *how* it should be abstracted.  
This section defines *how data sources MUST be used* to drive generation.

Unless stated otherwise, "the graph" refers to combined data from inventory, graph nodes, graph edges, and relationship files.

---

### 1) Use of Graph Relationships (Flows and Dependencies)

- Workload diagrams MUST NOT be disconnected collections of boxes.
- Generator MUST draw at least one end-to-end value flow per workload (e.g., `Compute -> Workflow -> Media Assets -> Bucket -> CDN/Edge`).
- Prefer explicit edges (`IN_VNIC`, `IN_SUBNET`, `IN_VCN`, media relationships, attachment edges).
- When edges are missing, generator MAY infer relationships if not obviously false.
- Administrative relationships (e.g., `IN_COMPARTMENT`) MUST drive placement but SHOULD NOT be drawn unless clarifying.

---

### 2) IAM and Policy Relationships

- IAM constructs MUST be overlays with **relationships**, not isolated nodes.
- Generator MUST:
  - Place IAM/policy nodes at correct scope.
  - Draw edges to protected/enabled resources when inference is reasonable.
- Policies MAY be aggregated rather than expanded statement-by-statement.

---

### 3) Tags and Metadata Overlays

- Tags/metadata (team, lifecycle, createdBy/At) MUST be available to renderer.
- Diagram MAY show badges or overlays.
- Full tag dumps MUST NOT be placed inside labels.

---

### 4) Graph Integrity and Anomaly Reporting

Renderer MUST:

- Compute integrity metrics (e.g., `137/137 edges valid`)
- Include Graph Health section in report
- Detect anomalies (e.g., subnet w/o route table, VCN w/o gateways)
- NOT fail due to anomalies — surface instead

---

### 5) Alignment Between Reports and Diagrams

- "At a Glance" and "Workloads & Services" sections are **authoritative**.
- Every workload listed MUST appear in diagrams.
- Counts MUST reconcile (aggregation allowed).
- Identifiers MUST match (`sandbox`, `edge`, `media`, etc.)

---

### 6) Readability and Legend Updates

- New overlays (IAM, tags, health) MUST update legend.
- Grouping MUST still show at least one representative logical flow.
- Summaries are not permitted; diagrams must remain full-detail.

---

### 7) Full-Detail Coverage (No Omission)

- All nodes and edges from `graph_nodes.jsonl` and `graph_edges.jsonl` MUST be rendered in inventory diagrams.
- Consolidated diagrams MUST include the complete inventory scope without aggregation or omission.
- Use grouping, lane structure, and layout (not summarization) to manage density.

---

### 8) Automation and Drift Enforcement

- This document is the **source of truth** for abstraction and data usage.
- Agents/generators MUST treat these rules as a **contract**.
- If drift occurs, generators SHOULD self-correct to restore compliance.
- Updates to this document MUST update:
  - graph builder
  - diagram generator
  - report generator
  - `AGENTS.md`

---

## Change Control

If diagram structure or section expectations change, update:

- `docs/diagram_guidelines.md`
- `docs/architecture.md`
- `AGENTS.md`

---
