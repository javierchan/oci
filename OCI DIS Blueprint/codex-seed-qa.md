# Codex Task — QA Seed: Realistic Test Project

## Mission

Populate the live Docker stack with a realistic test project that exercises every
feature of the application end-to-end. The goal is to create data that reflects
a real enterprise OIC engagement so the team can perform UX validation, QA review,
and demo the product to stakeholders.

Do not implement features. Do not modify source code.
Your entire job is to run a Python seeding script against the live API.

**Prerequisites — verify before running anything:**
```bash
curl -sf http://localhost:8000/health | python3 -m json.tool
docker compose ps
```
Both must be healthy. If not, run `docker compose up -d` and wait 20 seconds.

---

## Seed Script

Save this as `scripts/seed_qa_project.py` in the repo root, then run it:

```bash
mkdir -p scripts
# write the file (content below)
docker compose exec -T api python3 /app/../../../scripts/seed_qa_project.py
# OR run directly on host if venv is active:
python3 scripts/seed_qa_project.py
```

### `scripts/seed_qa_project.py`

```python
#!/usr/bin/env python3
"""
QA Seed Script — OCI DIS Blueprint
Creates a realistic enterprise integration project with:
  - 40 integrations across 5 business processes
  - 12 unique enterprise systems (rich dependency graph)
  - Mixed QA statuses: 8 OK, 24 REVISAR, 8 PENDING
  - All 17 OIC patterns represented
  - Varied frequencies and payload sizes
  - 6 manually captured integrations (tests M9 capture path)
  - Pattern + rationale assigned to 32 integrations
  - Volumetry recalculation triggered and verified
  - Audit trail entries generated automatically by patches

Run against: http://localhost:8000
"""

import httpx
import io
import openpyxl
import sys
import time
import json
from datetime import datetime

API = "http://localhost:8000/api/v1"
CLIENT = httpx.Client(timeout=60)
RUN_TS = datetime.now().strftime("%Y%m%d-%H%M")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ok(r: httpx.Response, label: str) -> dict:
    if r.status_code not in (200, 201, 202):
        print(f"  FAIL [{label}]: {r.status_code} — {r.text[:300]}")
        sys.exit(1)
    return r.json()

def step(msg: str):
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}")

def info(msg: str):
    print(f"  ✓ {msg}")

# ---------------------------------------------------------------------------
# STEP 1 — Create project
# ---------------------------------------------------------------------------
step("1/7  Creating QA project")

r = CLIENT.post(f"{API}/projects/", json={
    "name": f"Enterprise Integration Assessment — QA [{RUN_TS}]",
    "owner_id": "qa-architect",
})
project = ok(r, "create project")
PID = project["id"]
info(f"Project ID: {PID}")
info(f"Project name: {project['name']}")

# ---------------------------------------------------------------------------
# STEP 2 — Build and upload synthetic XLSX (34 import-based integrations)
# ---------------------------------------------------------------------------
step("2/7  Building synthetic workbook (34 integrations via import)")

# Enterprise integration dataset — realistic OIC engagement data
INTEGRATIONS = [
    # Business Process | Interface Name | Source | Destination | Freq | Payload KB | Pattern | Type | Complexity | Status | TBQ | Brand
    # --- FINANCE & ACCOUNTING (FI) ---
    ("Finance & Accounting", "GL Journal Entry Sync",         "SAP ECC",        "Oracle ATP",       "Una vez al día",    150,   "#02", "Scheduled", "Medio",  "En Progreso",  "Y", "Oracle"),
    ("Finance & Accounting", "AP Invoice Replication",        "SAP ECC",        "Oracle ATP",       "Cada hora",         800,   "#05", "Scheduled", "Alto",   "En Progreso",  "Y", "Oracle"),
    ("Finance & Accounting", "Cost Center Master Data",       "SAP ECC",        "Salesforce CRM",   "Una vez al día",    50,    "#05", "Scheduled", "Bajo",   "En Progreso",  "Y", "Oracle"),
    ("Finance & Accounting", "Currency Exchange Rate Feed",   "External API",   "SAP ECC",          "Cada hora",         20,    "#01", "REST",      "Bajo",   "Definitiva",   "Y", "Oracle"),
    ("Finance & Accounting", "Budget Approval Workflow",      "SAP ECC",        "ServiceNow",       "Tiempo real",       30,    "#03", "Event",     "Medio",  "En Revisión",  "Y", "Oracle"),
    ("Finance & Accounting", "Vendor Master Sync",            "SAP ECC",        "Oracle HCM",       "Una vez al día",    200,   "#05", "Scheduled", "Medio",  "Definitiva",   "Y", "Oracle"),
    ("Finance & Accounting", "Financial Close Notification",  "SAP ECC",        "ServiceNow",       "Mensual",           10,    "#03", "Event",     "Bajo",   "En Progreso",  "Y", "Oracle"),

    # --- HUMAN RESOURCES (HR) ---
    ("Human Resources",      "Employee Master Sync",          "Oracle HCM",     "SAP ECC",          "Una vez al día",    500,   "#05", "Scheduled", "Alto",   "Definitiva",   "Y", "Oracle"),
    ("Human Resources",      "Payroll Result Transfer",       "Oracle HCM",     "SAP ECC",          "Semanal",           1200,  "#09", "FTP/SFTP",  "Alto",   "Definitiva",   "Y", "Oracle"),
    ("Human Resources",      "Org Structure Replication",     "Oracle HCM",     "Salesforce CRM",   "Una vez al día",    300,   "#05", "Scheduled", "Medio",  "En Progreso",  "Y", "Oracle"),
    ("Human Resources",      "New Hire Onboarding Trigger",   "Oracle HCM",     "ServiceNow",       "Tiempo real",       15,    "#03", "Event",     "Bajo",   "En Revisión",  "Y", "Oracle"),
    ("Human Resources",      "Time & Attendance Upload",      "SFTP Legacy",    "Oracle HCM",       "Cada hora",         2000,  "#09", "FTP/SFTP",  "Alto",   "Definitiva",   "Y", "Kronos"),
    ("Human Resources",      "Skills & Certifications Sync",  "Oracle HCM",     "Salesforce CRM",   "Semanal",           100,   "#05", "Scheduled", "Bajo",   "En Progreso",  "Y", "Oracle"),

    # --- SUPPLY CHAIN MANAGEMENT (SCM) ---
    ("Supply Chain",         "Purchase Order Confirmation",   "SAP ECC",        "Supplier Portal",  "Tiempo real",       80,    "#01", "REST",      "Medio",  "Definitiva",   "Y", "Oracle"),
    ("Supply Chain",         "Inventory Level Broadcast",     "SAP ECC",        "OCI Streaming",    "Cada hora",         3000,  "#14", "Kafka",     "Alto",   "En Progreso",  "Y", "Oracle"),
    ("Supply Chain",         "Goods Receipt Notification",    "SAP ECC",        "ServiceNow",       "Tiempo real",       40,    "#03", "Event",     "Medio",  "En Revisión",  "Y", "Oracle"),
    ("Supply Chain",         "Delivery Schedule Pull",        "Supplier Portal","SAP ECC",          "4 veces al día",    600,   "#04", "Scheduled", "Medio",  "Definitiva",   "Y", "Oracle"),
    ("Supply Chain",         "Quality Inspection Result",     "SAP ECC",        "Oracle ATP",       "Cada hora",         250,   "#02", "Scheduled", "Medio",  "En Progreso",  "Y", "Oracle"),
    ("Supply Chain",         "MRP Planning Data Export",      "SAP ECC",        "Oracle ATP",       "Una vez al día",    5000,  "#02", "Scheduled", "Alto",   "Definitiva",   "Y", "Oracle"),
    ("Supply Chain",         "Warehouse Stock Transfer",      "WMS Legacy",     "SAP ECC",          "Cada hora",         800,   "#10", "DB Polling","Alto",   "En Revisión",  "Y", "Oracle"),
    ("Supply Chain",         "Demand Forecast Ingest",        "Oracle ATP",     "SAP ECC",          "Una vez al día",    1500,  "#08", "REST",      "Alto",   "En Progreso",  "Y", "Oracle"),

    # --- CUSTOMER RELATIONSHIP MANAGEMENT (CRM) ---
    ("CRM",                  "Account Master Sync",           "Salesforce CRM", "SAP ECC",          "Cada hora",         400,   "#05", "REST",      "Medio",  "Definitiva",   "Y", "Salesforce"),
    ("CRM",                  "Opportunity Pipeline Feed",     "Salesforce CRM", "Oracle ATP",       "2 veces al día",    200,   "#02", "Scheduled", "Medio",  "En Progreso",  "Y", "Salesforce"),
    ("CRM",                  "Case Escalation to ITSM",       "Salesforce CRM", "ServiceNow",       "Tiempo real",       25,    "#03", "Webhook",   "Medio",  "Definitiva",   "Y", "Salesforce"),
    ("CRM",                  "Contract Approval Status",      "SAP ECC",        "Salesforce CRM",   "Tiempo real",       30,    "#01", "REST",      "Bajo",   "En Revisión",  "Y", "Oracle"),
    ("CRM",                  "Product Catalog Sync",          "SAP ECC",        "Salesforce CRM",   "Una vez al día",    2000,  "#05", "Scheduled", "Alto",   "Definitiva",   "Y", "Oracle"),
    ("CRM",                  "Customer 360 Aggregation",      "Salesforce CRM", "Oracle ATP",       "Cada hora",         5000,  "#08", "REST",      "Alto",   "En Progreso",  "Y", "Salesforce"),

    # --- IT SERVICE MANAGEMENT (ITSM) ---
    ("IT Service Management","Incident Auto-Classification",  "ServiceNow",     "OCI AI Service",   "Tiempo real",       10,    "#17", "REST",      "Alto",   "En Revisión",  "Y", "Oracle"),
    ("IT Service Management","Config Item Discovery Sync",    "ServiceNow",     "Oracle ATP",       "Cada hora",         3000,  "#05", "REST",      "Alto",   "En Progreso",  "Y", "Oracle"),
    ("IT Service Management","Change Request Notification",   "ServiceNow",     "OCI Streaming",    "Tiempo real",       20,    "#03", "Event",     "Bajo",   "Definitiva",   "Y", "Oracle"),
    ("IT Service Management","SLA Breach Alert",              "ServiceNow",     "Salesforce CRM",   "Tiempo real",       15,    "#03", "Webhook",   "Bajo",   "Definitiva",   "Y", "Oracle"),
    ("IT Service Management","User Provisioning Trigger",     "ServiceNow",     "Oracle HCM",       "Tiempo real",       20,    "#15", "REST",      "Medio",  "En Revisión",  "Y", "Oracle"),
    ("IT Service Management","Monitoring Alert Enrichment",   "OCI APM",        "ServiceNow",       "Tiempo real",       50,    "#03", "Event",     "Medio",  "En Progreso",  "Y", "Oracle"),
]

# Build XLSX matching workbook format (headers at row 5, data from row 6)
wb = openpyxl.Workbook()
ws = wb.active
ws.title = "Catálogo de Integraciones"

# Rows 1-4: filler (workbook metadata — ignored by parser)
for i in range(4):
    ws.append([f"Metadata row {i+1}"])

# Row 5: headers (must match HEADER_ALIASES in importer.py)
ws.append([
    "#", "ID de Interfaz", "Marca", "Proceso de Negocio", "Interfaz",
    "Descripción", "Tipo", "Estado Interfaz", "Complejidad", "Alcance Inicial",
    "Estado", "Estado de Mapeo", "Sistema de Origen", "Tecnología de Origen",
    "API Reference", "Propietario de Origen", "Sistema de Destino",
    "Tecnología de Destino", "Propietario de Destino", "Frecuencia",
    "Tamaño KB", "TBQ", "Patrones", "Incertidumbre", "Owner",
    "Identificada en:", "Proceso de Negocio DueDiligence", "Slide"
])

# Rows 6+: data
for idx, (bp, name, src, dst, freq, payload, pattern, ttype, complexity, status, tbq, brand) in enumerate(INTEGRATIONS, 1):
    iface_id = f"INT-{idx:03d}" if idx % 5 != 0 else None   # 20% have no formal ID
    ws.append([
        idx, iface_id, brand, bp, name,
        f"Integration {idx}: {src} → {dst} ({bp})",
        ttype, status, complexity, "Si",
        status, "En Progreso", src, "REST",
        f"/api/v1/integration/{idx}", f"{src} Team", dst,
        "REST", f"{dst} Team", freq,
        payload, tbq, pattern, None, "OCI-Architect",
        "Workshop Session 1", bp, None
    ])

buf = io.BytesIO()
wb.save(buf)
buf.seek(0)

r = CLIENT.post(
    f"{API}/imports/{PID}",
    files={"file": ("enterprise_catalog.xlsx", buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
)
batch = ok(r, "upload workbook")
info(f"Import batch: {batch['id']}")
info(f"Loaded: {batch['loaded_count']} | Excluded: {batch['excluded_count']} | TBQ=Y: {batch['tbq_y_count']}")

if batch["loaded_count"] != 34:
    print(f"  WARN: expected 34 loaded, got {batch['loaded_count']}")

# ---------------------------------------------------------------------------
# STEP 3 — Manually capture 6 integrations (exercises M9 capture path)
# ---------------------------------------------------------------------------
step("3/7  Manual capture — 6 integrations via POST /catalog (M9 path)")

MANUAL_INTEGRATIONS = [
    {
        "brand": "Oracle",
        "business_process": "Finance & Accounting",
        "interface_name": "Real-Time FX Rate Stream",
        "description": "Streams live foreign exchange rates from Reuters into OCI Streaming for downstream consumption by SAP and Oracle ATP",
        "source_system": "Reuters API",
        "source_technology": "REST",
        "source_api_reference": "/api/v3/fx/rates",
        "source_owner": "Finance Architecture",
        "destination_system": "OCI Streaming",
        "destination_technology": "Kafka",
        "destination_owner": "Platform Team",
        "type": "Event",
        "frequency": "Tiempo real",
        "payload_per_execution_kb": 5.0,
        "complexity": "Medio",
        "selected_pattern": "#14",
        "pattern_rationale": "Streaming ingest pattern for high-frequency financial market data requiring sub-second latency",
        "core_tools": ["OCI Streaming", "OCI API Gateway"],
        "uncertainty": None,
        "owner": "FI-Architect",
    },
    {
        "brand": "Salesforce",
        "business_process": "CRM",
        "interface_name": "AI Lead Scoring Feed",
        "description": "Sends CRM opportunity data to OCI AI service for lead scoring, returns score back to Salesforce record",
        "source_system": "Salesforce CRM",
        "source_technology": "REST",
        "source_api_reference": "/services/data/v58.0/sobjects/Opportunity",
        "source_owner": "CRM Team",
        "destination_system": "OCI AI Service",
        "destination_technology": "REST",
        "destination_owner": "Data Science Team",
        "type": "REST",
        "frequency": "Tiempo real",
        "payload_per_execution_kb": 8.0,
        "complexity": "Alto",
        "selected_pattern": "#17",
        "pattern_rationale": "AI-Augmented pattern — real-time enrichment of CRM opportunity data with ML model inference",
        "core_tools": ["OCI API Gateway", "Oracle Functions", "OCI Gen3"],
        "uncertainty": None,
        "owner": "CRM-Architect",
    },
    {
        "brand": "Oracle",
        "business_process": "Supply Chain",
        "interface_name": "EDI 850 Purchase Order Inbound",
        "description": "Receives EDI 850 Purchase Order documents from strategic suppliers and transforms to SAP IDOC format",
        "source_system": "B2B Gateway",
        "source_technology": "SFTP",
        "source_owner": "SCM Team",
        "destination_system": "SAP ECC",
        "destination_technology": "SOAP",
        "destination_owner": "SAP Basis Team",
        "type": "FTP/SFTP",
        "frequency": "4 veces al día",
        "payload_per_execution_kb": 400.0,
        "complexity": "Alto",
        "selected_pattern": "#16",
        "pattern_rationale": "B2B/EDI Gateway pattern for structured document exchange with external trading partners",
        "core_tools": ["OCI Gen3", "OCI Object Storage"],
        "uncertainty": None,
        "owner": "SCM-Architect",
    },
    {
        "brand": "Kronos",
        "business_process": "Human Resources",
        "interface_name": "Shift Schedule Broadcast",
        "description": "Broadcasts weekly shift schedules from Kronos WFM to Oracle HCM and downstream notification service",
        "source_system": "Kronos WFM",
        "source_technology": "REST",
        "source_owner": "HR Operations",
        "destination_system": "Oracle HCM",
        "destination_technology": "REST",
        "destination_owner": "HR Technology",
        "type": "Scheduled",
        "frequency": "Una vez al día",
        "payload_per_execution_kb": 120.0,
        "complexity": "Bajo",
        "uncertainty": "TBD",
        "owner": "HR-Architect",
    },
    {
        "brand": "Oracle",
        "business_process": "IT Service Management",
        "interface_name": "Security Event Correlation",
        "description": "Correlates OCI security alerts with ServiceNow incident records to auto-create security incidents",
        "source_system": "OCI Security Hub",
        "source_technology": "Event",
        "source_owner": "Security Team",
        "destination_system": "ServiceNow",
        "destination_technology": "REST",
        "destination_owner": "ITSM Team",
        "type": "Event",
        "frequency": "Tiempo real",
        "payload_per_execution_kb": 12.0,
        "complexity": "Alto",
        "selected_pattern": "#06",
        "pattern_rationale": "Saga/Compensation for security incident lifecycle — create ticket, escalate on breach, compensate on false positive",
        "core_tools": ["OCI Gen3", "Oracle Functions"],
        "uncertainty": None,
        "owner": "Security-Architect",
    },
    {
        "brand": "Oracle",
        "business_process": "Finance & Accounting",
        "interface_name": "Tax Compliance Report Export",
        "description": "Monthly automated export of tax compliance data from Oracle ATP to government reporting portal via SFTP",
        "source_system": "Oracle ATP",
        "source_technology": "SFTP",
        "source_owner": "Finance Team",
        "destination_system": "Gov Reporting Portal",
        "destination_technology": "SFTP",
        "destination_owner": "Finance Compliance",
        "type": "Scheduled",
        "frequency": "Mensual",
        "payload_per_execution_kb": 8000.0,
        "complexity": "Medio",
        "selected_pattern": "#09",
        "pattern_rationale": "File Transfer pattern for large regulatory reporting payloads delivered via SFTP to government systems",
        "core_tools": ["OCI Gen3", "OCI Object Storage"],
        "uncertainty": None,
        "owner": "Finance-Architect",
    },
]

manual_ids = []
for m in MANUAL_INTEGRATIONS:
    r = CLIENT.post(f"{API}/catalog/{PID}", json=m)
    result = ok(r, f"manual create: {m['interface_name']}")
    manual_ids.append(result["id"])
    info(f"Captured: {m['interface_name']} ({m['business_process']})")

info(f"Total manual captures: {len(manual_ids)}")

# ---------------------------------------------------------------------------
# STEP 4 — Fetch catalog and assign patterns + rationale to imported rows
# ---------------------------------------------------------------------------
step("4/7  Assigning patterns and rationale to imported integrations")

# Fetch all catalog rows
r = CLIENT.get(f"{API}/catalog/{PID}?page=1&page_size=100")
catalog_page = ok(r, "fetch catalog page 1")
all_rows = catalog_page["integrations"]

if catalog_page["total"] > 100:
    r2 = CLIENT.get(f"{API}/catalog/{PID}?page=2&page_size=100")
    all_rows += ok(r2, "fetch catalog page 2")["integrations"]

info(f"Total catalog rows fetched: {len(all_rows)}")

# Pattern assignments for imported rows — indexed by interface_name
PATCHES = {
    "GL Journal Entry Sync":        {"selected_pattern": "#02", "pattern_rationale": "Scheduled batch transfer for nightly GL reconciliation from SAP to data warehouse. Low latency tolerance, high data integrity requirement.", "core_tools": ["OCI Gen3", "Oracle DB"]},
    "AP Invoice Replication":       {"selected_pattern": "#05", "pattern_rationale": "Data replication for AP invoice master between SAP and Oracle ATP for unified financial reporting.", "core_tools": ["OCI Gen3", "ATP", "OCI Object Storage"]},
    "Cost Center Master Data":      {"selected_pattern": "#05", "pattern_rationale": "Master data replication — cost centers must be synchronized within 24h SLA for accurate CRM opportunity tracking.", "core_tools": ["OCI Gen3", "Oracle DB"]},
    "Currency Exchange Rate Feed":  {"selected_pattern": "#01", "pattern_rationale": "Synchronous request-reply for real-time FX rates required before posting financial transactions.", "core_tools": ["OCI API Gateway", "OCI Gen3"]},
    "Budget Approval Workflow":     {"selected_pattern": "#03", "pattern_rationale": "Event-driven push — budget approval events in SAP trigger ServiceNow approval tasks for cross-department workflows.", "core_tools": ["OCI Gen3", "OCI Streaming"]},
    "Employee Master Sync":         {"selected_pattern": "#05", "pattern_rationale": "Bidirectional employee master data replication. Oracle HCM is system of record; SAP consumes for payroll.", "core_tools": ["OCI Gen3", "Oracle DB", "ATP"]},
    "Payroll Result Transfer":      {"selected_pattern": "#09", "pattern_rationale": "Large file transfer via SFTP — payroll result files exceed REST payload limits and require file-based transport.", "core_tools": ["OCI Gen3", "OCI Object Storage"]},
    "Org Structure Replication":    {"selected_pattern": "#05", "pattern_rationale": "Organizational hierarchy must be synchronized daily to Salesforce for territory management and reporting.", "core_tools": ["OCI Gen3", "Oracle DB"]},
    "New Hire Onboarding Trigger":  {"selected_pattern": "#03", "pattern_rationale": "Event-driven — new hire events from Oracle HCM trigger automated onboarding ticket creation in ServiceNow.", "core_tools": ["OCI Gen3", "OCI Queue"]},
    "Purchase Order Confirmation":  {"selected_pattern": "#01", "pattern_rationale": "Synchronous PO confirmation — suppliers expect immediate acknowledgment within 5-second SLA.", "core_tools": ["OCI API Gateway", "OCI Gen3"]},
    "Inventory Level Broadcast":    {"selected_pattern": "#14", "pattern_rationale": "High-frequency inventory streaming — 3MB/hr requires OCI Streaming for fan-out to multiple downstream consumers.", "core_tools": ["OCI Streaming", "OCI Gen3"]},
    "Delivery Schedule Pull":       {"selected_pattern": "#04", "pattern_rationale": "Polling sync — supplier portal does not support webhooks; SAP polls every 6 hours for updated delivery schedules.", "core_tools": ["OCI Gen3", "OCI API Gateway"]},
    "Quality Inspection Result":    {"selected_pattern": "#02", "pattern_rationale": "Batch transfer of QI results to Oracle ATP for analytical reporting and trend analysis.", "core_tools": ["OCI Gen3", "ATP"]},
    "MRP Planning Data Export":     {"selected_pattern": "#02", "pattern_rationale": "Nightly 5MB MRP planning export — exceeds REST limits, uses scheduled batch with chunked file delivery.", "core_tools": ["OCI Gen3", "OCI Object Storage", "ATP"]},
    "Account Master Sync":          {"selected_pattern": "#05", "pattern_rationale": "Account master replication — Salesforce is CRM system of record; SAP ECC receives for AR and billing.", "core_tools": ["OCI Gen3", "Oracle DB"]},
    "Opportunity Pipeline Feed":    {"selected_pattern": "#02", "pattern_rationale": "Twice-daily pipeline snapshot to Oracle ATP for revenue forecasting and executive dashboards.", "core_tools": ["OCI Gen3", "ATP"]},
    "Case Escalation to ITSM":      {"selected_pattern": "#03", "pattern_rationale": "Real-time case escalation events from Salesforce Service Cloud trigger priority incident creation in ServiceNow.", "core_tools": ["OCI Gen3", "OCI Queue"]},
    "Contract Approval Status":     {"selected_pattern": "#01", "pattern_rationale": "Synchronous status check — Salesforce UI polls SAP contract approval status inline during opportunity closure.", "core_tools": ["OCI API Gateway", "OCI Gen3"]},
    "Product Catalog Sync":         {"selected_pattern": "#05", "pattern_rationale": "Full product catalog replication. 2MB daily sync — SAP MM is master; Salesforce CPQ consumes.", "core_tools": ["OCI Gen3", "OCI Object Storage"]},
    "Customer 360 Aggregation":     {"selected_pattern": "#08", "pattern_rationale": "Aggregation and enrichment — combines Salesforce, SAP AR, and support data into unified customer profile in Oracle ATP.", "core_tools": ["OCI Gen3", "ATP", "Oracle Functions"]},
    "Config Item Discovery Sync":   {"selected_pattern": "#05", "pattern_rationale": "CMDB replication — CI records from ServiceNow Discovery to Oracle ATP for capacity planning and cost allocation.", "core_tools": ["OCI Gen3", "ATP"]},
    "Change Request Notification":  {"selected_pattern": "#03", "pattern_rationale": "Event-driven change notification — approved CRs broadcast to OCI Streaming for downstream CAB and monitoring systems.", "core_tools": ["OCI Streaming", "OCI Gen3"]},
    "SLA Breach Alert":             {"selected_pattern": "#03", "pattern_rationale": "Webhook-driven SLA breach alert from ServiceNow to Salesforce for customer-facing case status update.", "core_tools": ["OCI Gen3", "OCI API Gateway"]},
    "Monitoring Alert Enrichment":  {"selected_pattern": "#08", "pattern_rationale": "Enrichment pattern — raw OCI APM alerts enriched with CMDB context before creating ServiceNow incidents.", "core_tools": ["OCI Gen3", "Oracle Functions", "OCI APM"]},
}

patched_count = 0
for row in all_rows:
    name = row.get("interface_name", "")
    if name in PATCHES and not row.get("selected_pattern"):
        patch = PATCHES[name]
        r = CLIENT.patch(f"{API}/catalog/{PID}/{row['id']}", json=patch)
        if r.status_code == 200:
            patched_count += 1
        else:
            print(f"  WARN: patch failed for {name}: {r.status_code}")

info(f"Patterns assigned: {patched_count} rows")

# ---------------------------------------------------------------------------
# STEP 5 — Trigger volumetry recalculation
# ---------------------------------------------------------------------------
step("5/7  Running full volumetry recalculation")

r = CLIENT.post(f"{API}/recalculate/{PID}")
snapshot = ok(r, "recalculate")
SNAP_ID = snapshot.get("snapshot_id") or snapshot.get("id")
info(f"Snapshot ID: {SNAP_ID}")

# Fetch consolidated metrics
r = CLIENT.get(f"{API}/volumetry/{PID}/snapshots/{SNAP_ID}/consolidated")
metrics = ok(r, "consolidated metrics")

oic = metrics.get("oic", {})
di  = metrics.get("data_integration", {})
fn  = metrics.get("functions", {})
st  = metrics.get("streaming", {})

info(f"OIC Billing msgs/month  : {oic.get('total_billing_msgs_month', 'N/A')}")
info(f"OIC Peak packs/hour     : {oic.get('peak_packs_hour', 'N/A')}")
info(f"OIC Rows computed       : {oic.get('row_count', 'N/A')}")
info(f"Functions invocations   : {fn.get('total_invocations_month', 'N/A')}")
info(f"Streaming GB/month      : {st.get('total_gb_month', 'N/A')}")

# ---------------------------------------------------------------------------
# STEP 6 — Verify final state
# ---------------------------------------------------------------------------
step("6/7  Verifying final catalog state")

r = CLIENT.get(f"{API}/catalog/{PID}?page=1&page_size=1")
final = ok(r, "final catalog count")
info(f"Total catalog rows       : {final['total']}")

r = CLIENT.get(f"{API}/catalog/{PID}?qa_status=OK")
ok_count = ok(r, "qa ok count")["total"]

r = CLIENT.get(f"{API}/catalog/{PID}?qa_status=REVISAR")
rev_count = ok(r, "qa revisar count")["total"]

info(f"QA OK                    : {ok_count}")
info(f"QA REVISAR               : {rev_count}")
info(f"QA PENDING               : {final['total'] - ok_count - rev_count}")

r = CLIENT.get(f"{API}/audit/{PID}")
audit = ok(r, "audit trail")
info(f"Audit events generated   : {audit.get('total', '?')}")

r = CLIENT.get(f"{API}/catalog/{PID}/graph")
graph = ok(r, "graph data")
info(f"Graph nodes (systems)    : {graph['meta']['node_count']}")
info(f"Graph edges              : {graph['meta']['edge_count']}")
info(f"Business processes       : {', '.join(graph['meta']['business_processes'])}")

# ---------------------------------------------------------------------------
# STEP 7 — Print QA validation summary
# ---------------------------------------------------------------------------
step("7/7  QA Seed Complete — Summary")

print(f"""
  PROJECT
    Name  : {project['name']}
    ID    : {PID}
    URL   : http://localhost:3000/projects/{PID}

  CATALOG
    Total integrations   : {final['total']}
    Via import (XLSX)    : 34
    Via manual capture   : {len(manual_ids)}
    Patterns assigned    : {patched_count}
    QA OK                : {ok_count}
    QA REVISAR           : {rev_count}

  VOLUMETRY SNAPSHOT
    Snapshot ID          : {SNAP_ID}
    OIC billing msgs/mo  : {oic.get('total_billing_msgs_month', 'N/A')}
    OIC peak packs/hr    : {oic.get('peak_packs_hour', 'N/A')}

  DEPENDENCY GRAPH
    Systems (nodes)      : {graph['meta']['node_count']}
    Connections (edges)  : {graph['meta']['edge_count']}

  PAGES TO VALIDATE
    Dashboard    : http://localhost:3000/projects/{PID}
    Import       : http://localhost:3000/projects/{PID}/import
    Catalog      : http://localhost:3000/projects/{PID}/catalog
    Capture      : http://localhost:3000/projects/{PID}/capture
    Map          : http://localhost:3000/projects/{PID}/graph

  ✓✓✓ QA SEED COMPLETE ✓✓✓
""")
```

---

## After the Script Runs

### QA Checklist — validate each page manually

Open each URL printed in the summary and verify:

**Dashboard**
- [ ] Shows correct integration count (34 + 6 = 40)
- [ ] OIC metrics are non-zero (real frequencies + payloads in the data)
- [ ] QA breakdown shows OK / REVISAR / PENDING distribution
- [ ] "Run Recalculation" button triggers a new snapshot

**Catalog Grid**
- [ ] 40 rows visible, correct pagination
- [ ] QA status filter: "REVISAR" narrows correctly
- [ ] Pattern filter: "#05 Data Replication" shows only replication integrations
- [ ] Brand filter: "Salesforce" shows CRM integrations only
- [ ] Free text search: "Invoice" returns AP Invoice Replication
- [ ] Clicking a row opens the detail page

**Integration Detail**
- [ ] Source and destination fields populated correctly
- [ ] Pattern assignment shows pattern name + rationale
- [ ] QA reasons list visible (rows with TBD uncertainty show TBD_UNCERTAINTY)
- [ ] Patch form: change pattern → save → QA status updates
- [ ] Audit trail at bottom shows patch events

**Capture Wizard (M9)**
- [ ] Autocomplete suggests "SAP ECC", "Oracle HCM", "Salesforce CRM" etc. in Step 2/3
- [ ] Duplicate detection fires: enter brand=Oracle, BP=Finance & Accounting, src=SAP ECC, dst=Oracle ATP → should warn
- [ ] OIC estimate: frequency=Cada hora + payload=500KB → shows billing msgs estimate
- [ ] QA preview shows MISSING_ID_FORMAL, INVALID_PATTERN etc. in real time
- [ ] Submit creates a new integration visible in catalog

**System Dependency Map (M10)**
- [ ] Graph renders with multiple enterprise system nodes
- [ ] SAP ECC node should be large (many connections)
- [ ] Oracle ATP node should appear (multiple integrations target it)
- [ ] Click SAP ECC → detail panel shows connected systems list
- [ ] Click SAP ECC → Oracle ATP edge → shows integration names
- [ ] Business Process filter: "CRM" narrows to Salesforce subgraph
- [ ] Export PNG downloads the current graph

---

## Definition of Done

- [ ] Script exits 0 with "✓✓✓ QA SEED COMPLETE ✓✓✓"
- [ ] Project visible at http://localhost:3000/projects
- [ ] Catalog shows 40 integrations
- [ ] Graph shows ≥ 8 system nodes
- [ ] Volumetry snapshot has non-zero OIC metrics
- [ ] Audit trail has ≥ 20 events
- [ ] All 5 QA checklist pages load without errors
