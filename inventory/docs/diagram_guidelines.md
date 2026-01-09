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
- Tenancy boundary is labeled as the root compartment. (project/architecture_references/oci-core-landingzone-oracle.zip:oci-core-landingzone-oracle/oci-core-landingzone.drawio:197)
- An enclosing compartment wraps functional compartments. (project/architecture_references/oci-core-landingzone-oracle.zip:oci-core-landingzone-oracle/oci-core-landingzone.drawio:212)

2) Functional compartments are named and separated by responsibility.
- Network, Security, and App compartments are explicitly labeled. (project/architecture_references/oci-core-landingzone-oracle.zip:oci-core-landingzone-oracle/oci-core-landingzone.drawio:277, project/architecture_references/oci-core-landingzone-oracle.zip:oci-core-landingzone-oracle/oci-core-landingzone.drawio:3897, project/architecture_references/oci-core-landingzone-oracle.zip:oci-core-landingzone-oracle/oci-core-landingzone.drawio:4752)
- Observability and Management is also a distinct compartment. (project/architecture_references/jms-oci-topology-oracle.zip:jms-oci-topology-oracle/jms-oci-topology.drawio:3437)

3) Network topology is modeled with explicit VCNs and subnets.
- VCN grouping is emphasized in the core landing zone. (project/architecture_references/oci-core-landingzone-oracle.zip:oci-core-landingzone-oracle/oci-core-landingzone.drawio:1382)
- Subnets are named and shown as distinct layers. (project/architecture_references/oci-core-landingzone-oracle.zip:oci-core-landingzone-oracle/oci-core-landingzone.drawio:1622, project/architecture_references/oci-core-landingzone-oracle.zip:oci-core-landingzone-oracle/oci-core-landingzone.drawio:1767, project/architecture_references/oci-core-landingzone-oracle.zip:oci-core-landingzone-oracle/oci-core-landingzone.drawio:1912)
- A simpler pattern still shows VCN and subnets explicitly. (project/architecture_references/integration-architecture-pattern-1-oracle.zip:integration-architecture-pattern-1-oracle/integration-architecture-pattern-1.drawio:62, project/architecture_references/integration-architecture-pattern-1-oracle.zip:integration-architecture-pattern-1-oracle/integration-architecture-pattern-1.drawio:77, project/architecture_references/integration-architecture-pattern-1-oracle.zip:integration-architecture-pattern-1-oracle/integration-architecture-pattern-1.drawio:172)

4) External connectivity is explicit and labeled.
- Internet and DRG are called out in the core landing zone. (project/architecture_references/oci-core-landingzone-oracle.zip:oci-core-landingzone-oracle/oci-core-landingzone.drawio:1482, project/architecture_references/oci-core-landingzone-oracle.zip:oci-core-landingzone-oracle/oci-core-landingzone.drawio:322)
- Internet and gateways are also explicit in other references. (project/architecture_references/jms-oci-topology-oracle.zip:jms-oci-topology-oracle/jms-oci-topology.drawio:227, project/architecture_references/ai-llm-workflow-architecture-oracle.zip:ai-llm-workflow-architecture-oracle/ai-llm-workflow-architecture.drawio:87, project/architecture_references/ai-llm-workflow-architecture-oracle.zip:ai-llm-workflow-architecture-oracle/ai-llm-workflow-architecture.drawio:312)

5) Security and IAM overlays are represented as first-class elements.
- IAM Identity Domain is called out in the landing zone. (project/architecture_references/oci-core-landingzone-oracle.zip:oci-core-landingzone-oracle/oci-core-landingzone.drawio:7032)
- Security Zone appears in multiple references. (project/architecture_references/oci-core-landingzone-oracle.zip:oci-core-landingzone-oracle/oci-core-landingzone.drawio:8107, project/architecture_references/jms-oci-topology-oracle.zip:jms-oci-topology-oracle/jms-oci-topology.drawio:6697)
- IAM is explicitly represented. (project/architecture_references/jms-oci-topology-oracle.zip:jms-oci-topology-oracle/jms-oci-topology.drawio:6022)

6) Legends are used to explain notation or status.
- The landing zone diagram includes a legend block. (project/architecture_references/oci-core-landingzone-oracle.zip:oci-core-landingzone-oracle/oci-core-landingzone.drawio:162)

7) Workload-specific compartments are still explicitly labeled.
- Data Integration Compartment is labeled as a boundary in the integration pattern. (project/architecture_references/integration-architecture-pattern-1-oracle.zip:integration-architecture-pattern-1-oracle/integration-architecture-pattern-1.drawio:337)
- A generic Compartment boundary is labeled in the AI workflow diagram. (project/architecture_references/ai-llm-workflow-architecture-oracle.zip:ai-llm-workflow-architecture-oracle/ai-llm-workflow-architecture.drawio:32)

## Diagram Guidelines for OCI Inventory Outputs

### How to Use These Guidelines

- Treat the requirements in "Additional Abstraction Requirements (OCI-Aligned)" as mandatory.
- Use "Observed Patterns (Evidence-Based)" as supporting evidence, not as hard requirements.
- If any guidance conflicts, the OCI-aligned abstraction requirements take precedence.

### 1) Consolidated Architecture Diagram (High-Level)

- Always show the Tenancy boundary and an enclosing compartment to provide context. (project/architecture_references/oci-core-landingzone-oracle.zip:oci-core-landingzone-oracle/oci-core-landingzone.drawio:197, project/architecture_references/oci-core-landingzone-oracle.zip:oci-core-landingzone-oracle/oci-core-landingzone.drawio:212)
- Use functional compartments (Network, Security, App, Observability/Management) as the primary grouping axis. (project/architecture_references/oci-core-landingzone-oracle.zip:oci-core-landingzone-oracle/oci-core-landingzone.drawio:277, project/architecture_references/oci-core-landingzone-oracle.zip:oci-core-landingzone-oracle/oci-core-landingzone.drawio:3897, project/architecture_references/oci-core-landingzone-oracle.zip:oci-core-landingzone-oracle/oci-core-landingzone.drawio:4752, project/architecture_references/jms-oci-topology-oracle.zip:jms-oci-topology-oracle/jms-oci-topology.drawio:3437)
- Inside Network compartments, show VCNs and at least named subnets to mirror OCI architectural conventions. (project/architecture_references/oci-core-landingzone-oracle.zip:oci-core-landingzone-oracle/oci-core-landingzone.drawio:1382, project/architecture_references/oci-core-landingzone-oracle.zip:oci-core-landingzone-oracle/oci-core-landingzone.drawio:1622)
- Explicitly render Internet/DRG/gateways when present to anchor ingress and egress. (project/architecture_references/oci-core-landingzone-oracle.zip:oci-core-landingzone-oracle/oci-core-landingzone.drawio:1482, project/architecture_references/oci-core-landingzone-oracle.zip:oci-core-landingzone-oracle/oci-core-landingzone.drawio:322, project/architecture_references/jms-oci-topology-oracle.zip:jms-oci-topology-oracle/jms-oci-topology.drawio:227)
- Include IAM and Security Zone overlays where available, placed at the tenancy or security boundary level. (project/architecture_references/oci-core-landingzone-oracle.zip:oci-core-landingzone-oracle/oci-core-landingzone.drawio:7032, project/architecture_references/oci-core-landingzone-oracle.zip:oci-core-landingzone-oracle/oci-core-landingzone.drawio:8107)
- Provide a legend or notation key in the diagram to explain symbols and status. (project/architecture_references/oci-core-landingzone-oracle.zip:oci-core-landingzone-oracle/oci-core-landingzone.drawio:162)

### 2) Workload-Specific Diagrams (Detailed)

- Keep the compartment boundary visible, even for a single workload. (project/architecture_references/integration-architecture-pattern-1-oracle.zip:integration-architecture-pattern-1-oracle/integration-architecture-pattern-1.drawio:337, project/architecture_references/ai-llm-workflow-architecture-oracle.zip:ai-llm-workflow-architecture-oracle/ai-llm-workflow-architecture.drawio:32)
- Show VCNs and subnets explicitly to clarify placement and network segmentation. (project/architecture_references/integration-architecture-pattern-1-oracle.zip:integration-architecture-pattern-1-oracle/integration-architecture-pattern-1.drawio:62, project/architecture_references/integration-architecture-pattern-1-oracle.zip:integration-architecture-pattern-1-oracle/integration-architecture-pattern-1.drawio:77, project/architecture_references/integration-architecture-pattern-1-oracle.zip:integration-architecture-pattern-1-oracle/integration-architecture-pattern-1.drawio:172)
- Keep Internet/gateway/DRG elements visible if the workload has external connectivity. (project/architecture_references/ai-llm-workflow-architecture-oracle.zip:ai-llm-workflow-architecture-oracle/ai-llm-workflow-architecture.drawio:87, project/architecture_references/ai-llm-workflow-architecture-oracle.zip:ai-llm-workflow-architecture-oracle/ai-llm-workflow-architecture.drawio:312, project/architecture_references/ai-llm-workflow-architecture-oracle.zip:ai-llm-workflow-architecture-oracle/ai-llm-workflow-architecture.drawio:1742)
- Use solution-specific compartment naming (for example, "Data Integration Compartment") when applicable. (project/architecture_references/integration-architecture-pattern-1-oracle.zip:integration-architecture-pattern-1-oracle/integration-architecture-pattern-1.drawio:337)

### 3) Labeling and Grouping Conventions

- Use explicit labels for compartments and key zones to communicate responsibility. (project/architecture_references/oci-core-landingzone-oracle.zip:oci-core-landingzone-oracle/oci-core-landingzone.drawio:277, project/architecture_references/oci-core-landingzone-oracle.zip:oci-core-landingzone-oracle/oci-core-landingzone.drawio:3897)
- Use named subnets rather than unlabeled containers. (project/architecture_references/oci-core-landingzone-oracle.zip:oci-core-landingzone-oracle/oci-core-landingzone.drawio:1622, project/architecture_references/oci-core-landingzone-oracle.zip:oci-core-landingzone-oracle/oci-core-landingzone.drawio:1767)
- Keep explicit labels for Internet and DRG to anchor the topology. (project/architecture_references/oci-core-landingzone-oracle.zip:oci-core-landingzone-oracle/oci-core-landingzone.drawio:1482, project/architecture_references/oci-core-landingzone-oracle.zip:oci-core-landingzone-oracle/oci-core-landingzone.drawio:322)

## Implementation Mapping for This Project

These patterns map cleanly to the inventory pipeline outputs:

- Tenancy and Compartment boundaries: `compartmentId` and compartment lineage.
- Network boundaries: VCN and subnet resources.
- External connectivity: DRG, gateways, and Internet.
- Security overlays: IAM identity domains and Security Zone resources (when discoverable).

Use these as the target structure for consolidated and workload diagrams to align with OCI architecture
references and to keep diagrams detailed yet readable.

## Additional Abstraction Requirements (OCI-Aligned)

To ensure generated diagrams follow the canonical OCI architectural abstraction, the following rules apply in addition to the existing guidelines:

### A) Canonical Containment Hierarchy
All diagrams MUST reflect the OCI containment model:
```
Tenancy -> Region (optional) -> Compartment -> VCN -> Subnet -> Resource
```
- The tenancy boundary MUST be shown.
- Every subnet MUST be drawn inside a named VCN.
- Every resource with a VNIC MUST be drawn inside a subnet.
- Managed services without VNICs MUST NOT be inside VCNs.

### B) Functional Grouping as Overlays
Functional compartments (Network, Security/IAM, App/Workloads, Observability/Management, Data/Storage) are logical overlays on top of the canonical OCI hierarchy, not replacements for it.
A resource always belongs to a real OCI compartment and may additionally be shown within a functional grouping space.

### C) In-VCN vs Out-of-VCN Services
Resources MUST be separated based on whether they live inside the VCN:
- Inside VCN (via subnet & VNIC): Compute, DB systems with VNICs, OKE nodes, Load Balancers, etc.
- Outside VCN but inside tenancy: Object Storage, Logging, Metrics, Vault, Events, Identity Domains, Edge services, Media Assets, etc.

This distinction MUST be visible on consolidated and workload diagrams.

### D) External Connectivity Completeness
If present in inventory, diagrams MUST expose at least the following edge elements:
- Internet Gateway
- NAT Gateway
- Service Gateway
- DRG
- VPN / FastConnect

Gateway elements MUST be placed at VCN or tenancy edges and labeled explicitly.

### E) IAM & Security Overlays
Security/IAM constructs MUST be drawn as overlays at the correct scope:
- Tenancy / Identity Domain
- Compartment
- VCN / Subnet / NSG

Examples include: IAM Domains, IAM Policies, Security Zones, NSGs, Security Lists.  
These MUST NOT be drawn as peer workloads.

### F) Minimum Labeling Conventions
The following elements MUST be labeled:
- Tenancy name
- Compartment names
- VCN names
- Subnet names (or role labels such as "Public Subnet", "Private Subnet")
- Gateway types (IGW, NAT, SGW, DRG, VPN, FastConnect)

Optional aggregation is allowed (for example, “Compute x3”).

### G) Readability Requirements
Generated diagrams MUST include:
- A legend if icons, colors, or status indicators are used.
- At least one logical flow line when relevant (for example, compute -> storage, compute -> internet/DRG).
- Aggregation of homogeneous resources when counts exceed readability thresholds.

## Data-Driven Rendering Requirements

The guidelines above define *what* must be represented in OCI diagrams and *how* it should be abstracted.
This section defines *how the available data sources MUST be used* to drive diagram generation and reporting.

Unless explicitly stated otherwise, "the graph" refers to the combined model derived from inventory data,
graph node/edge exports, and relationship files (for example: `graph_nodes.*`, `graph_edges.*`,
`relationships.*`, and similar sources).

### 1) Use of Graph Relationships (Flows and Dependencies)

- Workload-specific diagrams MUST NOT be rendered as collections of unconnected boxes.
- For each workload diagram, the generator MUST use graph relationships to draw at least one end-to-end
  value flow, such as:
  - `Compute/Service -> Workflow -> Media Assets -> Bucket -> CDN/Edge`
  - `Compute -> BootVolume/BlockVolume`
- When explicit edges exist in the graph (for example, `IN_VNIC`, `IN_SUBNET`, `IN_VCN`,
  attachment/usage edges, media/streaming relationships), they MUST be preferred over heuristics.
- When explicit relationships are missing but resource types and names strongly suggest a relationship,
  the generator MAY draw a best-effort set of edges, provided it does not create obviously false
  dependencies.
- Relationships that are purely administrative (for example, `IN_COMPARTMENT`) MUST be used for
  placement/containment but SHOULD NOT be rendered as visible connectors unless they add clarity.

### 2) IAM and Policy Relationships

- IAM domains, policies, and security constructs MUST be treated as overlays with relationships, not only
  as isolated nodes.
- The generator MUST:
  - Place IAM/policy/security nodes at the correct scope (tenancy, compartment, or VCN/subnet/NSG).
  - Draw edges from policies to the primary resources or workloads they enable or protect, when this can
    be reasonably inferred from:
    - Policy names and statements.
    - Target resource types (for example, Object Storage, Media services, Streaming).
- The generator MUST avoid rendering every individual policy statement. Policies MAY be aggregated or
  represented by a small number of representative edges (for example, one policy node connected to the
  main bucket or workflow it governs).

### 3) Tags and Metadata Overlays

- Tags and metadata present on resources (for example: team/owner tags, lifecycle tags, created-by,
  created-at) MUST be available to the diagram generator as first-class input.
- Diagrams MUST support optional overlays based on tags/metadata, such as:
  - Ownership/team badges applied to resources or groups.
  - Lifecycle hints (for example, resources marked as ephemeral or scheduled for deletion).
- Unless a specific view is declared as tag-focused, the generator MUST summarize tag information instead
  of dumping full tag structures into node labels (for example, "Team: Media", "Lifecycle: Ephemeral",
  not entire tag JSON blobs).

### 4) Graph Integrity and Anomaly Reporting

- Graph integrity metrics (for example: `N/M` edges reference known node IDs, counts by relationship
  type) MUST be computed as part of the pipeline.
- The textual report MUST contain a Graph Health section summarizing at least:
  - Overall edge integrity (for example, "137/137 edges reference known node IDs").
  - Counts of relationship types that are relevant for placement and flows (for example, `IN_COMPARTMENT`,
    `IN_VCN`, `IN_SUBNET`, `IN_VNIC`, `USES_ROUTE_TABLE`, `USES_SECURITY_LIST`).
- The generator SHOULD detect and report anomalies that are relevant for diagrams, such as:
  - Resources that appear in compartments but not in any VCN when they would normally require network
    placement.
  - Subnets without associated route tables or security lists.
  - VCNs that have public subnets but no Internet/NAT/DRG gateways.
- Diagram generation MUST NOT fail because of these anomalies; instead, anomalies MUST be surfaced
  clearly in the report, and MAY be highlighted in diagrams (for example, using a warning icon or
  special label).

### 5) Alignment Between Reports and Diagrams

- The "At a Glance" and "Workloads & Services" sections of the textual report are authoritative for:
  - Which workloads exist.
  - How many resources they contain.
  - Their high-level purpose and classification.
- For every workload listed in the report, there MUST be a clearly identifiable visual representation
  in one or more diagrams (tenancy, network, workload, or consolidated views).
- Workload names, counts, and classifications used in diagrams MUST be consistent with the textual
  report:
  - Diagrams MUST use the same workload identifiers (for example, `sandbox`, `edge`, `media`,
    `output/filename`).
  - Aggregated counts in diagrams (for example, `MediaAsset x87`) MUST be reconcilable with counts in
    the report.

### 6) Readability and Legend Updates

- When additional overlays are introduced (for example, IAM relationships, tag-based ownership markers,
  graph health indicators), the legend MUST be updated or extended so that the notation remains
  understandable without referencing the code.
- If a view aggregates resources of the same type (for example, `MediaAsset x87`), the diagram MUST
  still expose at least one representative logical flow using those resource types, so that the reader
  can understand how the workload behaves.
- The generator SHOULD prefer aggregation and summarization over adding raw, low-level details that
  would make the diagram unreadable.

### 7) Automation and Drift Enforcement

- This document is the source of truth for OCI diagram abstraction and data usage. Any automated agent
  or code generator that modifies diagram generation MUST treat these rules as a contract.
- If generated diagrams or reports drift from these guidelines (for example, resources rendered outside
  the expected hierarchy, workloads without flows, policies rendered without any relationships),
  automated refactoring SHOULD:
  - Prefer bringing the code and templates back into compliance with this document.
  - Only change this document when there is an intentional design decision to evolve the abstraction or
    data usage model.
- When this document is updated, corresponding changes MUST be applied to:
  - The code that builds the internal graph.
  - The diagram generation logic.
  - The report generation logic.
  - Any agent configuration described in `AGENTS.md`.

### Where these requirements do NOT apply (and why)

The abstraction rules defined above intentionally do **not** prescribe:
- Visual layout style (horizontal, vertical, swimlanes, grid, etc.)
- Iconography sets or design themes
- Arrow or connector styles
- Diagram zoom levels (L0/L1/L2/L3 views)
- Optional visual layers (e.g., traffic flows, service dependencies, SLIs/SLOs)
- Rendering-density heuristics (other than minimum readability rules)
- Vendor tooling constraints or diagram-as-code syntax preferences

These elements are not part of the OCI architectural **abstraction** model. They belong to the **presentation** layer and may vary based on tooling, audience, or documentation style.

## Data-Driven Rendering Requirements

Diagram generation MUST leverage all relevant inventory and graph data made available by the pipeline. In particular:

### 1) Graph Relationships (Flows and Dependencies)
- Workload diagrams MUST use graph relationships (for example: `IN_VNIC`, `IN_SUBNET`, `IN_VCN`, `USES_ROUTE_TABLE`, media/streaming edges) to draw at least one meaningful end-to-end flow per workload.
- Graph placement relationships (for example: `IN_COMPARTMENT`, `IN_VCN`, `IN_SUBNET`) MUST drive location and containment on the diagram, not manual heuristics.
- Administrative containment relationships SHOULD NOT be drawn as visible edges unless they add clarity.

### 2) IAM and Policies as Relationships
- IAM policies MUST be drawn as overlays with inferred edges to the resources or workloads they primarily enable or protect (for example: Object Storage, Media workflows).
- The generator MUST avoid listing raw IAM statements and SHOULD summarize or aggregate policy relationships.

### 3) Tag and Metadata Overlays
- Tags and metadata (for example: team/owner, lifecycle, createdBy/createdAt) MUST be available to the renderer.
- Diagrams MAY show optional badge overlays or groupings derived from tag metadata, without dumping full tag structures.

### 4) Graph Integrity and Anomaly Surfacing
- Graph integrity (for example: `N/M edges reference known nodes`) MUST be surfaced in the textual report.
- Resource anomalies (for example: subnet without route table, VCN with public subnet but no gateway) SHOULD be surfaced in the report and MAY be annotated visually.
- Diagram generation MUST NOT fail due to anomalies.

### 5) Report ↔ Diagram Alignment
- Every workload listed in the report MUST have a corresponding visual representation.
- Workload names and resource counts in diagrams MUST match those in the report (aggregation allowed, semantics MUST match).
- The “At a Glance” and “Workloads & Services” sections are authoritative for workload existence and MUST drive workload-level diagrams.

These requirements ensure that the generative pipeline takes full advantage of structural, relational, metadata, and integrity information available from inventory and graph sources, instead of producing purely structural or cosmetic diagrams.

## Change Control

- If you change diagram structure or section expectations, update:
  - `docs/diagram_guidelines.md`
  - `docs/architecture.md`
  - `AGENTS.md`
