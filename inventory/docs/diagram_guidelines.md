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

## Change Control

- If you change diagram structure or section expectations, update:
  - `docs/diagram_guidelines.md`
  - `docs/architecture.md`
  - `AGENTS.md`
