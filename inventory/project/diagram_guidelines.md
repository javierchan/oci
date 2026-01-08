%% OCI Inventory Diagram Guidelines (Mermaid)

This document defines diagramming design decisions for OCI inventory outputs rendered as Mermaid flowcharts.

Scope:
- Applies to the consolidated diagram and all per-view diagrams emitted under `out/<timestamp>/`.
- Targets OCI components (Tenancy/Compartments, Networking, Workloads/App views).

Note on “online best practices”:
- This guidance is based on widely used cloud architecture diagram conventions and Mermaid flowchart constraints.
- If you want, we can additionally incorporate specific external references (requires explicit approval for network fetching).

---

## Goals (What “Good” Looks Like)

1. Human-first: a reader should understand the architecture story in 30–60 seconds.
2. Deterministic: stable ordering, stable IDs, and stable summarization so diffs are meaningful.
3. Truthful: show only relationships we can justify from inventory metadata (or label inferred flows explicitly).
4. Scalable: large tenancies must remain readable via aggregation and view separation.

Non-goals:
- Exhaustively listing every resource in the consolidated view.
- Rendering every low-level attachment (VNICs, private IPs, ephemeral artifacts) unless specifically requested.

---

## Diagram Set (Required Outputs)

- Raw graph (debug): `diagram_raw.mmd`
  - Purpose: completeness and troubleshooting.
  - Expectation: may be noisy; not optimized for readability.

- Tenancy view: `diagram.tenancy.mmd`
  - Purpose: compartments + key resources + a few representative relationships.

- Network views (per VCN): `diagram.network.<vcn>.mmd`
  - Purpose: topology per VCN (subnets, gateways, key routing intent).

- Workload views (per inferred workload): `diagram.workload.<workload>.mmd`
  - Purpose: application-centric slice showing key components and high-level flows.

- Consolidated (end-user): `diagram.consolidated.mmd`
  - Purpose: a single “map” that contains all the above views, optimized for scanability.

---

## Consolidated Diagram Design Decisions

Because Mermaid cannot truly “include multiple diagrams” in one file, the consolidated diagram must embed all views into one graph. To keep it readable:

1. Consolidated is a *context map*, not a dump
   - Each embedded view should be internally readable, but the consolidated file should still be scannable.
   - Prefer showing a small set of key nodes per view plus summary nodes.

2. Wrapper subgraphs must not reuse root IDs
   - Each embedded view has its own root node (e.g., `TEN_ROOT`, `NET_<vcn>_ROOT`, `WL_<workload>_ROOT`).
   - The *wrapper* subgraph ID must be different (e.g., `TEN_VIEW`, `NET_<vcn>_VIEW`, `WL_<workload>_VIEW`) to avoid Mermaid parent-cycle errors.

3. Context links are dotted and minimal
   - Use `-.->` from `TEN_ROOT` to each view root for navigation/context.
   - Avoid additional cross-view edges unless they are both correct and high-value.

4. One style block per file
   - Consolidated should define `classDef` once.
   - Embedded views should not re-define style blocks when merged.

---

## Visual Grammar (Shapes + Classes)

Use a small, consistent vocabulary. Prefer *borders/dash styles* over heavy colors.

### Node shapes (Mermaid flowchart)
- External actors: `((Users))`, `((Internet))`
- Compute runtime: `((Instance))`, `((OKE Node))`, `((Function))`
- Networking “things”: `[Subnet]`, `[VCN]`, `[IGW]`, `[NAT]`, `[Service GW]`, `[DRG]`
- Storage / data: `[(Object Storage Bucket)]`, `[(Database)]`
- Policy/IAM: `[Policy]`, `[Dynamic Group]`
- Summaries: `[Other … and N more]`

### Classes (role-based)
Define a small set and stick to it:
- `external`: actors outside the tenancy boundary.
- `boundary`: compartments/tenancy/region boundaries or “container” concepts.
- `network`: VCN/Subnet/Gateways/DRG/LB networking components.
- `compute`: instances, OKE nodes, functions.
- `storage`: buckets, DBs, file storage.
- `policy`: policies, groups, dynamic groups.
- `summary`: aggregation nodes.

---

## Edge Semantics (Make Lines Meaningful)

Use edge labels to clarify intent, but keep them short.

- Context / grouping: `A -.-> B`
  - Use only for “belongs to / part of / context link”.

- Data-plane / traffic: `A -->|requests| B`
  - Use for client/server or ingestion/egress.

- Control-plane / configuration: `A -->|configures| B`
  - Use sparingly; prefer leaving it out unless it improves understanding.

- Storage IO: `A -->|reads/writes| B`

Avoid:
- Drawing all discovered edges.
- Drawing inferred edges without labeling them as inferred.

---

## Layout Rules

- Tenancy view: `flowchart TD` (top-down for hierarchy)
- Network view: `flowchart LR` (left-to-right for flows)
- Workload view: `flowchart TD` (top-down for app layering)

Within large subgraphs:
- Set `direction TB` in nested subgraphs.
- Keep subgraph depth shallow where possible (deep nesting becomes unreadable).

---

## Complexity Controls (Mandatory for Large Tenancies)

1. Cap lists, always
   - Example: show up to 8 “key” nodes, then add one summary node: `Other key resources... and N more`.

2. Separate “key” vs “leaf”
   - Key: VCN, Subnet, Instance, LB, Gateway, Bucket, DB, OKE, API Gateway.
   - Leaf/noise: VNICs, private IPs, route rule details, individual media objects, logs/metrics resources.

3. Aggregate repetitive assets
   - For media assets/outputs, show 1–2 representative items + a summary.

4. Deterministic ordering
   - Sort consistently by `(category, type, displayName)`.
   - Ensure the “kept” samples are deterministic.

---

## OCI-Specific Modeling Decisions

### Boundaries
- Always depict boundaries explicitly using subgraphs:
  - Tenancy
  - Compartment
  - VCN
  - Subnet

### Networking (canonical story)
For each VCN view, aim to show:
- Internet → IGW → Public Subnet (ingress)
- Private Subnet → NAT GW (egress)
- Private Subnet → Service GW (OCI services)

Only add the following when present and useful:
- DRG (hub/spoke and on-prem connectivity)
- Local Peering / Remote Peering
- Load Balancer placement (public/private)

### Workloads
Workload views should answer:
- Who calls it? (Users / OCI Services)
- What runs it? (compute)
- Where does data go? (Object Storage / DB)
- What network context is relevant? (VCN/Subnet when attachments are available)

---

## Enhancement Plan (Significant Improvements)

To make the consolidated diagram feel “complete” while staying readable, implement enhancements in layers:

Phase 1 — Readability (no new OCI calls)
- Add a small `Legend` subgraph describing shapes/classes.
- Standardize labels (short + type on second line).
- Ensure every view has a single root anchor (`*_ROOT`).
- Make the consolidated view wrappers (`*_VIEW`) explicit and consistent.

Phase 2 — Better topology (metadata-derived)
- Improve network attachments and show compute placement inside subnets only when subnet/VCN IDs are known.
- Prefer a few high-value edges instead of many low-value ones.

Phase 3 — Relationship enrichers (read-only)
- Enrich explicit relationships (Instance→Subnet, LB→Subnet, RouteTable→Subnet, NSG/SecList→Subnet/Instance) where OCI inventory provides reliable fields.
- Use these enrichers to drive edges rather than heuristic inference.

Phase 4 — Optional views (only if requested)
- IAM / policy view.
- Observability view (logging, monitoring, alarms).
- Data pipeline view (streaming, events, media processing).

---

## Mermaid References

Mermaid Flowcharts Official Docs: https://mermaid.js.org/syntax/flowchart.html

---

## Existing Best-Practice Checklist (Quick)

For large technical architecture diagrams like this (network, tenancy, workload, cloud resource flows), clarity and manageability are key. Follow these rules:

1. Organize with Subgraphs and Sections
Group related resources using Mermaid’s subgraph to separate logical domains (network, compartments, workloads, etc.).
Visually separate high-level entities for better scanning and navigation.
2. Use Concise, Human-Friendly Labels
Use short, descriptive node labels; avoid long IDs or file names.
For repeated or similar resources (such as media assets, jobs, etc.), show a sample and aggregate the rest ("...and N more outputs/objects").
3. Limit Diagram Scope
Avoid showing all resources if they follow similar patterns.
Focus on key resources and flows—summarize repeated or less-important items using grouping nodes or call-out notes.
4. Distinct Node Shapes for Resource Role
Use Flowchart shapes (() for round, [] for rectangle, {{}} for database, etc.) to indicate different resource types.
Example: (compute.Instance), {{Bucket}}, [Public Subnet].
5. Use Direction and Layout Hints
Prefer left-to-right (flowchart LR) or top-to-bottom (flowchart TD) layouts based on your flow.
Explicitly set direction in subgraphs when necessary.
Add whitespace and logical flow to reduce line crossings.
6. Show Only Key Connections
Only draw important relationships (uses, routes, reads/writes), not every possible technical dependency.
Aggregated connections for similar nodes (one line from a compute instance to “All media assets” instead of many lines to each asset).
7. Apply Styles for Emphasis
Use Mermaid’s classDef and node classes to highlight critical components (entry/exit points, security boundaries, etc.).
Consider subtle color or border for different resource types or layers.
8. Use Comments and Labels
Add section comments, labels, and tooltips for context or detailed explanations.
Use Mermaid's showInfo property for tooltips if supported.
9. Keep the Diagram Readable
Never let the diagram grow so large it doesn't fit a normal screen. Split into multiple diagrams/views for different aspects (network, data flows, workload, etc.) if needed.
10. Maintain Diagram in Source
Maintain the diagram "as code" for easy version control.
Use folding/unfolding for sections in the Mermaid editor, or modularize into multiple diagrams.
Typical Structure Example
Tenancy/Compartment Block
Networking Block (Internet, VCN, Gateways, Subnets)
Compute/Storage Block (Instances, Buckets, Volumes)
Workload/Application Block (logical view on top of infra)
External Actors (users, 3rd-party services)
References:
Mermaid Flowcharts Official Docs: https://mermaid.js.org/syntax/flowchart.html
Want a best-practices template with styles or examples for your diagram? Let me know your preference for cleaner shapes, colors, or grouping!

Notes: Summary and Recommendations for Clarity

The attached diagram is a large, multi-subgraph (flowchart TD) that represents resource topology for tenancy, networks, and workloads (content, edge, mediaservice, output), containing repetitive resource nodes and deep nesting.

Clarity Improvements:

Add section comments for each top-level subgraph
Add clear labels in Markdown formatting for main groups (compartments, VCN, workloads)
Simplify long node labels to improve compactness (put truncated name, full name in tooltip or use tooltips if wanted)
Use distinct shapes for key resources (instances, gateways, assets)
Reduce repeated asset and media resource nodes in workloads: show representative samples and a summary node
Ensure connection lines are clear (fewer direct links, more via key resource nodes)
Align subgraphs and use space for separation
Improved, Clearer Diagram Example (Note: for demonstration, repetitive asset/media nodes are summarized; elaborate as needed):

Notes:

Consider using more explicit shapes for key nodes (([ ... ]), { ... } etc) per syntax doc for further clarity.
“Other ...” nodes summarize repetitive entries; expand if detailed flows per asset/output are desired.
If you want to expose details per asset, use call-out subgraphs per media/job/asset.
Let me know which area you’d like to expand or stylize—for example, making key resources stand out with color/style, or adding tooltips for full names.


flowchart TD
  %% ------------------ Tenancy / Compartments ------------------
  subgraph TEN_ROOT["Tenancy / Compartments"]
    direction TB
    subgraph TEN_Ne102c0d30e5d["Compartment 7azpcggq"]
      EDGE_VM["edge-sandbox-vm<br>compute.Instance"]
      IGW["Internet gateway-sandbox<br>network.InternetGateway"]
      NATGW["NAT gateway-sandbox<br>network.NatGateway"]
      SGW["Service gateway-sandbox<br>network.ServiceGateway"]
      PUB_SN["public subnet-sandbox<br>network.Subnet"]
      PRIV_SN["private subnet-sandbox<br>network.Subnet"]
      VCN["sandbox<br>network.Vcn"]
      BUCKET["bucket-20251201-1228<br>Bucket"]
    end
    %% Key resource relationships
    EDGE_VM -->|uses network| VCN
    EDGE_VM -->|storage| BUCKET
  end

  %% ------------------ Network Topology ------------------
  subgraph NET_sandbox_ROOT["Network Topology: sandbox"]
    direction LR
    NET_INTERNET["Internet"]
    subgraph NET_VCN["VCN: sandbox (10.75.0.0/16)"]
      IGW2["Internet gateway"]
      NATGW2["NAT gateway"]
      SGW2["Service gateway"]
      NET_PSN["Subnet: private (10.75.20.0/24)"]
      NET_PUBSN["Subnet: public (10.75.100.0/24)"]
    end
    %% Routing relationships
    NET_INTERNET -->|ingress/egress| IGW2
    IGW2 -->|routes| NET_PUBSN
    NET_PSN -->|egress| NATGW2
    NET_PSN -->|OCI services| SGW2
  end

  %% ------------------ Workload View: Content ------------------
  subgraph WL_content_ROOT["Workload View: Content"]
    direction TB
    CONTENT_USERS["Users"]
    OCI_SERVICES_C["OCI Services"]
    subgraph CONTENT_COMPARTMENT["Compartment 7azpcggq"]
      %% Show only two representative assets, summarize remainder
      CONTENT_MEDIA1["Samsung_Landscape_4K_Demo.mp4<br>MediaAsset"]
      CONTENT_MEDIA2["big-buck-bunny.mp4<br>MediaAsset"]
      MORE_CONTENT["Other Media Assets..."]
    end
  end

  %% ------------------ Workload View: Edge ------------------
  subgraph WL_edge_ROOT["Workload View: Edge"]
    direction TB
    EDGE_USERS["Users"]
    OCI_SERVICES_E["OCI Services"]
    subgraph EDGE_COMPARTMENT["Compartment 7azpcggq"]
      LOGENTITY["edge-sandbox-vnic<br>LogAnalyticsEntity"]
      EDGE_VOL["edge-sandbox-block<br>Volume"]
      EDGE_VM2["edge-sandbox-vm<br>compute.Instance"]
    end
  end

  %% ------------------ Workload View: MediaService ------------------
  subgraph WL_mediaservice_ROOT["Workload View: MediaService"]
    direction TB
    MS_USERS["Users"]
    OCI_SERVICES_M["OCI Services"]
    subgraph MEDIA_COMPARTMENT["Compartment 7azpcggq"]
      POLICY_MM["Allow_read_media_metadata<br>Policy"]
      POLICY_OBJ["Allow_read_object_family<br>Policy"]
    end
  end

  %% ------------------ Workload View: Output ------------------
  subgraph WL_output_ROOT["Workload View: Output"]
    direction TB
    OUTPUT_USERS["Users"]
    OCI_SERVICES_O["OCI Services"]
    subgraph OUTPUT_COMPARTMENT["Compartment 7azpcggq"]
      OUTPUT_FMP4["output/filename-standardTranscode_1080_4900K.fmp4<br>MediaAsset"]
      OUTPUT_M3U8["output/filename-standardTranscode_1080_4900K.m3u8<br>MediaAsset"]
      MORE_OUTPUTS["Other Outputs..."]
    end
  end

  %% ------------- Connect High-Level Groups for Context -------------
  TEN_ROOT -.-> NET_sandbox_ROOT
  TEN_ROOT -.-> WL_content_ROOT
  TEN_ROOT -.-> WL_edge_ROOT
  TEN_ROOT -.-> WL_mediaservice_ROOT
  TEN_ROOT -.-> WL_output_ROOT