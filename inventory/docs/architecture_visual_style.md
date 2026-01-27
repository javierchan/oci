# OCI Architecture Visual Style Guide

This document defines the visual layout and labeling conventions for curated OCI
architecture diagrams (Mermaid `.mmd`). It complements the abstraction and
containment rules in `docs/diagram_guidelines.md`.

If a visual rule here conflicts with abstraction or data rules in
`docs/diagram_guidelines.md`, the abstraction rules win.

Applies to:
- `diagrams/architecture/diagram.arch.tenancy.mmd`
- `diagrams/architecture/diagram.arch.vcn.<vcn>.<suffix>.mmd`
- `diagrams/architecture/diagram.arch.workload.<workload>.<suffix>.mmd`
- `diagrams/architecture/diagram.arch.compartment.<compartment>.mmd`

---

## 1) Layout Model (Nested Context)

Architecture diagrams SHOULD use a nested structure that makes OCI containment
explicit and keeps functional lanes readable:

```
+-------------------------------------------------------------+
|                    TENANCY CONTEXT (L0)                     |
|  +-------------------------------------------------------+  |
|  |               COMPARTMENT CONTEXT (L1)                |  |
|  |   +-----------------------------------------------+   |  |
|  |   |               VCN CONTEXT (L2)                |   |  |
|  |   |   +---------------------------------------+   |   |  |
|  |   |   |    ARCHITECTURE LANES (L3)            |   |   |  |
|  |   |   |  Network | App | Data | Security |   |   |   |  |
|  |   |   |  Observability | Other              |   |   |  |
|  |   |   +---------------------------------------+   |   |  |
|  |   +-----------------------------------------------+   |  |
|  +-------------------------------------------------------+  |
+-------------------------------------------------------------+
```

Required boundaries (Mermaid C4 or flowchart subgraphs):
- L0 Tenancy: scope header or light frame.
- L1 Compartment(s): labeled boxes with clear boundaries.
- L2 VCN(s): labeled boxes inside the owning compartment.
- L3 Lanes: subgraphs or container boundaries for functional domains.

If a workload spans multiple compartments:
- Each compartment MUST appear as its own L1 box.
- VCNs MUST appear inside the compartment where they exist.

Geography overlays (Region, AD, FD) are optional and MUST follow
`docs/diagram_guidelines.md` (overlay-only, no extra containment).

---

## 2) Lanes (Functional Domains)

Lanes SHOULD be ordered left-to-right as:
1. Network
2. App
3. Data
4. Security
5. Observability
6. Other

Rules:
- Lanes group conceptual components, not individual resources.
- Each lane has a title bar.
- If a lane is empty for the scope, it MAY be omitted.

---

## 3) Concept Nodes (Architectural Building Blocks)

A concept node is a logical building block (for example, "OKE Cluster",
"Ingress Load Balancer", "Object Storage", "Autonomous Database").

Visual requirements:
- Use Mermaid `Container` or boxed flowchart nodes for concepts.
- Keep labels concise and human-readable.
- Labels MUST NOT include counts, OCIDs, timestamps, or resource IDs.

Acceptable labels:
- `OKE Cluster`
- `Ingress Load Balancer`
- `Autonomous Database`
- `Object Storage`
- `Observability Suite`

Forbidden labels:
- `ocid1.instance.oc1...`
- `nodepool-202401231230111`
- `boot-volume-20240201-1200`
- `OKE Nodes (n=3)`

---

## 4) Connectivity and Edges

Edges represent architectural connectivity, not packet-level flows.

Conventions:
- Directional arrows for request/response or control.
- Optional labels for protocol or access class (for example, `HTTPS`, `Private`).
- Reduce edge count in curated views to avoid hairballs.

Network boundaries:
- Public connectivity MAY be shown as an arrow to `Internet` or through `IGW`.
- Private connectivity MUST respect VCN boundaries.

---

## 5) Color and Styling

Neutral palette is recommended to avoid visual overload.

Optional layer coloring (if Mermaid themes are used):
- Tenancy boundary: light neutral.
- Compartment boundaries: subtle neutral.
- VCN boundary: light blue.
- Lanes: alternating light neutrals.
- External domains: light orange/yellow.

Iconography (optional):
- Mermaid C4 supports sprites/icons only when configured; default to labeled nodes.

---

## 6) External Domains (On-Prem / SaaS / Other Clouds)

External systems MUST be visually separated from OCI:
- Use dashed-border boxes for On-Prem, SaaS, or other clouds.
- Label the external domain clearly.
- Show connectivity via VPN or FastConnect where relevant.

Example:

```
+-------------------------------+
| On-Prem                       |
|  LDAP Server                  |
|  ERP                          |
+-------------------------------+
          |
    (VPN / FastConnect)
          |
```

---

## 7) Minimum Labels

Every architecture diagram MUST label:
- Tenancy name (header)
- Compartment name(s)
- VCN name(s)
- External domain(s)
- Gateways if present (IGW, NAT, SGW, DRG, VPN, FastConnect)

---

## 8) Legend (Optional but Recommended)

If icons, colors, or overlays are used, include a small legend.

Example:

```
Legend:
- Solid border = OCI resource
- Dashed border = External domain
- Blue box = VCN
- Lane order: Network -> App -> Data -> Security -> Observability -> Other
```

---

## 9) Typography and Sizing

Recommended defaults:
- Font: Source Sans / Helvetica / Arial or equivalent.
- Title font: 16-18pt.
- Lane headers: 14-16pt.
- Node labels: 12-14pt.

---

## 10) Examples (Structural Templates)

Single-compartment workload:

```
TENANCY: <name>

+-------------------------------------------------------------+
| COMPARTMENT: <name>                                         |
| +---------------------------------------------------------+ |
| | VCN: <name>                                             | |
| | +-----------------------------------------------------+ | |
| | | Network | App | Data | Security | Observability     | | |
| | +-----------------------------------------------------+ | |
| +---------------------------------------------------------+ |
+-------------------------------------------------------------+
```

Multi-compartment workload:

```
TENANCY: <name>

+-----------------------------------------------------------------------+
| COMPARTMENT: <A>     | COMPARTMENT: <B>        | COMPARTMENT: <C>     |
| +------------------+ | +---------------------+ | +------------------+ |
| | VCN: <vcnA>      | | | VCN: <vcnB>         | | | VCN: <vcnC>      | |
| | +--------------+ | | | +----------------+  | | | +--------------+ | |
| | | lanes...     | | | | | lanes...      |  | | | | lanes...     | | |
| | +--------------+ | | | +----------------+  | | | +--------------+ | |
| +------------------+ | +---------------------+ | +------------------+ |
+-----------------------------------------------------------------------+
```

---

## 11) Strict "Do / Do Not"

Do:
- Start from compartment context.
- Show tenancy and VCN boundaries.
- Use lanes for architecture roles.
- Use conceptual components, not raw inventory resources.
- Separate external domains.
- Use clean labels (for example, `Ingress LB`, `Autonomous DB`).
- Show gateways for edge connectivity when present.

Do not:
- Show raw inventory IDs or OCIDs.
- Show job history (runs, executions, tasks).
- Show boot volumes as components.
- Use `(n=X)` in labels.
- Render every subnet node.
- Merge multiple compartments into a single unlabeled block.

---

## Change Control

If you change the visual style or lane layout rules, update:
- `docs/architecture_visual_style.md`
- `docs/diagram_guidelines.md`
- `docs/architecture.md`
- `AGENTS.md`
