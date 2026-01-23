# OCI Architecture Visual Style Guide

This document defines the visual layout and styling conventions for curated OCI
architecture diagrams (SVG or Draw.io). It complements the abstraction and
containment rules in `docs/diagram_guidelines.md`.

If a visual rule here conflicts with abstraction or data rules in
`docs/diagram_guidelines.md`, the abstraction rules win.

Applies to:
- `diagrams/architecture/diagram.arch.tenancy.svg`
- `diagrams/architecture/diagram.arch.vcn.<vcn>.svg`
- `diagrams/architecture/diagram.arch.workload.<workload>.svg`
- Optional `.drawio` variants for the same scopes.

Does not apply to Mermaid `.mmd` diagrams.

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

Required boundaries:
- L0 Tenancy: scope header or light frame.
- L1 Compartment(s): labeled boxes with clear boundaries.
- L2 VCN(s): labeled boxes inside the owning compartment.
- L3 Lanes: horizontal swimlanes for functional domains.

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
- Shape: rounded rectangle.
- Fill: white or light neutral.
- Border: solid, 1px, dark gray or black.
- Label font: regular, 12-14pt depending on output size.
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

Optional layer coloring:
- Tenancy frame: very light gray background.
- Compartment frames: white background, solid border.
- VCN frame: light blue background.
- Lanes: alternating very light neutrals.
- External domains: light orange/yellow border.

Iconography (optional):
- Use OCI official icons if available (LB, OKE, Autonomous DB, Object Storage,
  Security Zone, Logging/Monitoring, DRG/Gateways).
- If icons are unavailable, use labeled node boxes.

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
- Render every subnet in SVG.
- Merge multiple compartments into a single unlabeled block.

---

## Change Control

If you change the visual style or lane layout rules, update:
- `docs/architecture_visual_style.md`
- `docs/diagram_guidelines.md`
- `docs/architecture.md`
- `AGENTS.md`
