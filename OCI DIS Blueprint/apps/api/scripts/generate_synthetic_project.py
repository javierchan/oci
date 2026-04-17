"""Generate a deterministic NovaBrand synthetic enterprise integration project."""

from __future__ import annotations

import asyncio
import os
import random
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.db import AsyncSessionLocal, get_sync_database_url
from app.models import (
    AuditEvent,
    CatalogIntegration,
    DashboardSnapshot,
    DictionaryOption,
    ImportBatch,
    JustificationRecord,
    PatternDefinition,
    Project,
    SourceIntegrationRow,
    VolumetrySnapshot,
)
from app.models.project import ImportStatus, IntegrationStatus, ProjectStatus, QAStatus
from app.services import dashboard_service, export_service, justification_service, recalc_service

PROJECT_NAME = "NovaBrand Group — OCI Integration Program FY26"
PROJECT_DESCRIPTION = (
    "Enterprise integration catalog for NovaBrand Group's OCI migration program. "
    "Covers 6 business domains, 5 brand units, and 77 source systems. Designed to "
    "validate all 17 OCI integration patterns and service capability constraints."
)
PROJECT_OWNER_ID = "architect-lead-001"
PROJECT_METADATA = {
    "seed_type": "synthetic-enterprise",
    "scenario": "novabrand-fy26",
    "brand_units": 5,
    "business_processes": 12,
    "systems": 77,
}

OWNERS = [
    "María González",
    "Carlos Mendoza",
    "Ana Reyes",
    "Luis Herrera",
    "Patricia Soto",
    "Roberto Díaz",
    "Elena Vásquez",
    "Miguel Torres",
]

BRANDS = {
    "NOVA_CORE": "NovaBrand Core (corporate & shared services)",
    "NOVA_CONSUMER": "NovaBrand Consumer (mass-market products)",
    "NOVA_PREMIUM": "NovaBrand Premium (luxury & specialty)",
    "NOVA_FOOD": "NovaBrand Food & Beverage",
    "NOVA_DIGITAL": "NovaBrand Digital (e-commerce & digital channels)",
}

BUSINESS_PROCESSES = {
    "O2C": "Order-to-Cash",
    "P2P": "Procure-to-Pay",
    "H2R": "Hire-to-Retire",
    "M2D": "Make-to-Deliver",
    "R2R": "Record-to-Report",
    "P2I": "Plan-to-Inventory",
    "CX": "Customer Experience & Loyalty",
    "SCV": "Supply Chain Visibility",
    "PLM": "Product Lifecycle Management",
    "DCM": "Digital Commerce & Marketing",
    "COM": "Compliance, Risk & Reporting",
    "IOT": "IoT & Smart Manufacturing",
}


def system(
    name: str,
    technology: str,
    category: str,
    owner: str,
) -> dict[str, str]:
    """Create a normalized system entry."""

    return {
        "name": name,
        "technology": technology,
        "category": category,
        "owner": owner,
    }


SYSTEMS: dict[str, dict[str, str]] = {
    "SAP_S4_CORE": system(
        "SAP S/4HANA 2023 — Finance & Core Logistics",
        "SAP S/4HANA 2023",
        "ERP",
        "Finance Platforms",
    ),
    "SAP_S4_DIST": system(
        "SAP S/4HANA Distribution — Sales & Distribution",
        "SAP S/4HANA Distribution",
        "ERP",
        "Commercial Platforms",
    ),
    "ORACLE_EBS_FIN": system(
        "Oracle EBS R12.2 — Finance & AR/AP",
        "Oracle EBS R12.2",
        "ERP_LEGACY",
        "Finance Platforms",
    ),
    "SAP_BW": system(
        "SAP BW/4HANA — Corporate Analytics & Reporting",
        "SAP BW/4HANA",
        "ANALYTICS",
        "Enterprise Analytics",
    ),
    "KYRIBA": system(
        "Kyriba Treasury Management — Treasury & Cash",
        "Kyriba",
        "FINANCE",
        "Treasury Platforms",
    ),
    "BLACKLINE": system(
        "BlackLine Reconciliation — Period-Close & Reconciliation",
        "BlackLine",
        "FINANCE",
        "Finance Operations",
    ),
    "CONCUR": system(
        "SAP Concur T&E — Travel & Expenses",
        "SAP Concur",
        "FINANCE",
        "People Platforms",
    ),
    "ORACLE_AR": system(
        "Oracle AR Cloud — Accounts Receivable",
        "Oracle AR Cloud",
        "FINANCE",
        "Finance Platforms",
    ),
    "SFDC_SALES": system(
        "Salesforce Sales Cloud — Sales Pipeline & Accounts",
        "Salesforce Sales Cloud",
        "CRM",
        "Customer Platforms",
    ),
    "SFDC_SERVICE": system(
        "Salesforce Service Cloud — Customer Service & Cases",
        "Salesforce Service Cloud",
        "CRM",
        "Customer Platforms",
    ),
    "ORACLE_CX": system(
        "Oracle CX Sales — Configure-Price-Quote",
        "Oracle CX Sales",
        "CRM",
        "Commercial Platforms",
    ),
    "BRIERLEY": system(
        "Brierley Loyalty Platform — Loyalty Points & Rewards",
        "Brierley Loyalty Platform",
        "LOYALTY",
        "Customer Loyalty",
    ),
    "EMARSYS": system(
        "SAP Emarsys — Email & Omnichannel Marketing",
        "SAP Emarsys",
        "MARKETING",
        "Digital Marketing",
    ),
    "TWILIO": system(
        "Twilio Engage — SMS, WhatsApp & Push",
        "Twilio Engage",
        "MESSAGING",
        "Digital Marketing",
    ),
    "ADOBE_AEP": system(
        "Adobe Experience Platform — CDP & Audience Activation",
        "Adobe Experience Platform",
        "CDP",
        "Customer Data Platforms",
    ),
    "SFDC_COMMERCE": system(
        "Salesforce Commerce Cloud B2C — B2C Storefront",
        "Salesforce Commerce Cloud B2C",
        "ECOMMERCE",
        "Digital Commerce",
    ),
    "SAP_COMMERCE": system(
        "SAP Commerce Cloud B2B — B2B Portal & Order Entry",
        "SAP Commerce Cloud B2B",
        "ECOMMERCE",
        "Digital Commerce",
    ),
    "MAGENTO": system(
        "Adobe Commerce (Magento) — Wholesale & Reseller",
        "Adobe Commerce",
        "ECOMMERCE",
        "Digital Commerce",
    ),
    "AMAZON_SC": system(
        "Amazon Seller Central — Marketplace Listings & Orders",
        "Amazon Seller Central",
        "MARKETPLACE",
        "Marketplace Operations",
    ),
    "GOOGLE_MERCHANT": system(
        "Google Merchant Center — Product Feed & Shopping Ads",
        "Google Merchant Center",
        "MARKETPLACE",
        "Digital Marketing",
    ),
    "TIKTOK_SHOP": system(
        "TikTok Shop — Social Commerce & Live Orders",
        "TikTok Shop",
        "MARKETPLACE",
        "Marketplace Operations",
    ),
    "ORACLE_WMS": system(
        "Oracle WMS Cloud — Warehouse Management",
        "Oracle WMS Cloud",
        "WMS",
        "Supply Chain Platforms",
    ),
    "BLUE_YONDER_WMS": system(
        "Blue Yonder WMS — Cold Chain & Perishables",
        "Blue Yonder WMS",
        "WMS",
        "Supply Chain Platforms",
    ),
    "ORACLE_TMS": system(
        "Oracle Transportation Management — Domestic Transport",
        "Oracle Transportation Management",
        "TMS",
        "Logistics Platforms",
    ),
    "BY_TMS": system(
        "Blue Yonder TMS — International & Cross-Border",
        "Blue Yonder TMS",
        "TMS",
        "Logistics Platforms",
    ),
    "ORACLE_SCM_DP": system(
        "Oracle SCM Demand Planning — S&OP & Forecasting",
        "Oracle SCM Demand Planning",
        "SCM",
        "Supply Chain Platforms",
    ),
    "ORACLE_INVENTORY": system(
        "Oracle Inventory Cloud — Inventory Visibility & Transfers",
        "Oracle Inventory Cloud",
        "SCM",
        "Supply Chain Platforms",
    ),
    "DHL_PORTAL": system(
        "DHL Logistics Portal — Carrier Booking & Tracking",
        "DHL Logistics Portal",
        "CARRIER",
        "Logistics Platforms",
    ),
    "FLEXPORT": system(
        "Flexport Ocean & Air — Freight Forwarding",
        "Flexport",
        "CARRIER",
        "Logistics Platforms",
    ),
    "ORACLE_MES": system(
        "Oracle MES — Shop Floor Execution & Work Orders",
        "Oracle MES",
        "MES",
        "Manufacturing Technology",
    ),
    "SCADA_PLANT_MX": system(
        "SCADA / HMI Mexico Plants — PLC & Sensor Data",
        "SCADA / HMI",
        "SCADA",
        "Manufacturing Technology",
    ),
    "SCADA_PLANT_BR": system(
        "SCADA / HMI Brazil Plants — PLC & Sensor Data",
        "SCADA / HMI",
        "SCADA",
        "Manufacturing Technology",
    ),
    "ORACLE_QMS": system(
        "Oracle Quality Management — QA Inspections & NCRs",
        "Oracle Quality Management",
        "QUALITY",
        "Quality Platforms",
    ),
    "LABELVANTAGE": system(
        "LabelVantage LIMS — Label Compliance & Artwork",
        "LabelVantage LIMS",
        "QUALITY",
        "Quality Platforms",
    ),
    "OSI_PI": system(
        "OSIsoft PI System (Plant Historian) — Process Data Archive",
        "OSIsoft PI System",
        "HISTORIAN",
        "Manufacturing Technology",
    ),
    "COLD_CHAIN": system(
        "Cold Chain IoT Monitor — Temperature & Humidity",
        "Cold Chain IoT Monitor",
        "IOT",
        "Manufacturing Technology",
    ),
    "ORACLE_HCM": system(
        "Oracle HCM Cloud — Core HR, Benefits & Performance",
        "Oracle HCM Cloud",
        "HCM",
        "People Platforms",
    ),
    "WORKDAY": system(
        "Workday HCM — Compensation & Advanced HR",
        "Workday HCM",
        "HCM",
        "People Platforms",
    ),
    "ADP_PAYROLL": system(
        "ADP Workforce Now — Payroll MX, BR, CO",
        "ADP Workforce Now",
        "PAYROLL",
        "People Platforms",
    ),
    "KRONOS": system(
        "UKG Kronos Workforce — Time & Attendance",
        "UKG Kronos Workforce",
        "WORKFORCE",
        "People Platforms",
    ),
    "CORNERSTONE": system(
        "Cornerstone OnDemand — Learning & Talent",
        "Cornerstone OnDemand",
        "LMS",
        "People Platforms",
    ),
    "ORACLE_PROC": system(
        "Oracle Procurement Cloud — Purchase Orders & Suppliers",
        "Oracle Procurement Cloud",
        "PROCUREMENT",
        "Procurement Platforms",
    ),
    "COUPA": system(
        "Coupa Procurement — Guided Buying & Invoices",
        "Coupa",
        "PROCUREMENT",
        "Procurement Platforms",
    ),
    "ARIBA": system(
        "SAP Ariba Network — Supplier Collaboration & RFQ",
        "SAP Ariba Network",
        "SUPPLIER_NETWORK",
        "Procurement Platforms",
    ),
    "GEP_SMART": system(
        "GEP SMART — Contract Management & Spend Analytics",
        "GEP SMART",
        "PROCUREMENT",
        "Procurement Platforms",
    ),
    "VEEVA_VAULT": system(
        "Veeva Vault RIM — Regulatory & Quality Docs",
        "Veeva Vault RIM",
        "COMPLIANCE",
        "Compliance Platforms",
    ),
    "ORACLE_MDM": system(
        "Oracle MDM — Customer & Supplier Master Data",
        "Oracle MDM",
        "MDM",
        "Data Governance",
    ),
    "AKENEO": system(
        "Akeneo PIM — Product Information & Attributes",
        "Akeneo PIM",
        "PIM",
        "Product Data Platforms",
    ),
    "SALSIFY": system(
        "Salsify PIM — Digital Shelf & Retailer Syndication",
        "Salsify PIM",
        "PIM",
        "Product Data Platforms",
    ),
    "INFORMATICA_MDM": system(
        "Informatica MDM — Item Master & Hierarchy",
        "Informatica MDM",
        "MDM",
        "Data Governance",
    ),
    "ORACLE_CONTENT": system(
        "Oracle Content Management — Digital Assets & Documents",
        "Oracle Content Management",
        "DAM",
        "Digital Experience Platforms",
    ),
    "SHAREPOINT": system(
        "Microsoft SharePoint Online — Collaboration & Portals",
        "Microsoft SharePoint Online",
        "COLLABORATION",
        "Digital Workplace",
    ),
    "ORACLE_OAC": system(
        "Oracle Analytics Cloud — Enterprise BI & Dashboards",
        "Oracle Analytics Cloud",
        "BI",
        "Enterprise Analytics",
    ),
    "POWER_BI": system(
        "Microsoft Power BI — Self-Service Analytics",
        "Microsoft Power BI",
        "BI",
        "Enterprise Analytics",
    ),
    "TABLEAU": system(
        "Tableau Online — Operations & Sales Analytics",
        "Tableau Online",
        "BI",
        "Enterprise Analytics",
    ),
    "GOOGLE_ANALYTICS": system(
        "Google Analytics 4 — Web & App Behavior",
        "Google Analytics 4",
        "ANALYTICS",
        "Digital Analytics",
    ),
    "ORACLE_ESSBASE": system(
        "Oracle Essbase — Financial Planning & Consolidation",
        "Oracle Essbase",
        "EPM",
        "Finance Platforms",
    ),
    "STERLING_B2B": system(
        "IBM Sterling B2B Integrator — EDI X12 & EDIFACT",
        "IBM Sterling B2B Integrator",
        "EDI",
        "B2B Platforms",
    ),
    "OPENTEXT_EDI": system(
        "OpenText Trading Grid — Supplier EDI & e-Invoicing",
        "OpenText Trading Grid",
        "EDI",
        "B2B Platforms",
    ),
    "TRUECOMMERCE": system(
        "TrueCommerce EDI — Retail Compliance & ASN",
        "TrueCommerce EDI",
        "EDI",
        "B2B Platforms",
    ),
    "METRICSTREAM": system(
        "MetricStream GRC — Risk, Audit & Controls",
        "MetricStream GRC",
        "GRC",
        "Compliance Platforms",
    ),
    "CCH_WOLTERS": system(
        "Wolters Kluwer CCH — Tax Compliance & Filing",
        "Wolters Kluwer CCH",
        "TAX",
        "Compliance Platforms",
    ),
    "OCI_STREAMING": system(
        "OCI Streaming — Kafka-compatible Event Backbone",
        "OCI Streaming",
        "OCI_PLATFORM",
        "OCI Platform Team",
    ),
    "OCI_QUEUE": system(
        "OCI Queue — Durable Work Queue & DLQ",
        "OCI Queue",
        "OCI_PLATFORM",
        "OCI Platform Team",
    ),
    "OCI_FUNCTIONS": system(
        "OCI Functions — Serverless Compute & Transformation",
        "OCI Functions",
        "OCI_PLATFORM",
        "OCI Platform Team",
    ),
    "OCI_API_GW": system(
        "OCI API Gateway — North-South API Ingress",
        "OCI API Gateway",
        "OCI_PLATFORM",
        "OCI Platform Team",
    ),
    "OCI_OBJECT_STORE": system(
        "OCI Object Storage — Blob, File & Data Lake",
        "OCI Object Storage",
        "OCI_PLATFORM",
        "OCI Platform Team",
    ),
    "OCI_GOLDENGATE": system(
        "Oracle GoldenGate — CDC & Real-Time Replication",
        "Oracle GoldenGate",
        "OCI_PLATFORM",
        "OCI Platform Team",
    ),
    "OCI_DATA_INT": system(
        "OCI Data Integration — ETL/ELT Pipelines",
        "OCI Data Integration",
        "OCI_PLATFORM",
        "OCI Platform Team",
    ),
    "OCI_GEN_AI": system(
        "OCI Generative AI — LLM & AI Services",
        "OCI Generative AI",
        "OCI_PLATFORM",
        "OCI Innovation Team",
    ),
    "IBM_MQ": system(
        "IBM MQ 9.3 — Legacy Message Broker",
        "IBM MQ 9.3",
        "LEGACY_MW",
        "Legacy Modernization",
    ),
    "TIBCO_EMS": system(
        "TIBCO Enterprise Message Service — Legacy Topics/Queues",
        "TIBCO EMS",
        "LEGACY_MW",
        "Legacy Modernization",
    ),
    "ORACLE_SOA": system(
        "Oracle SOA Suite 12c — Legacy Orchestration & BPEL",
        "Oracle SOA Suite 12c",
        "LEGACY_MW",
        "Legacy Modernization",
    ),
    "WEBMETHODS": system(
        "Software AG webMethods — Legacy API Gateway",
        "Software AG webMethods",
        "LEGACY_MW",
        "Legacy Modernization",
    ),
    "MULESOFT": system(
        "MuleSoft Anypoint — Hybrid Integration",
        "MuleSoft Anypoint",
        "INTEGRATION_PLATFORM",
        "Integration CoE",
    ),
    "BOOMI": system(
        "Dell Boomi AtomSphere — Cloud iPaaS Legacy",
        "Dell Boomi AtomSphere",
        "INTEGRATION_PLATFORM",
        "Integration CoE",
    ),
    "SNAPLOGIC": system(
        "SnapLogic — Data & App Integration Legacy",
        "SnapLogic",
        "INTEGRATION_PLATFORM",
        "Integration CoE",
    ),
}

PATTERN_DISTRIBUTION: dict[str, dict[str, int]] = {
    "#01": {"O2C": 30, "P2P": 20, "H2R": 15, "CX": 15},
    "#02": {"DCM": 20, "SCV": 15, "CX": 10, "IOT": 5},
    "#03": {"O2C": 15, "CX": 15, "DCM": 10},
    "#04": {"O2C": 10, "P2P": 10, "M2D": 5},
    "#05": {"R2R": 15, "P2I": 10, "M2D": 5},
    "#06": {
        "O2C": 4,
        "P2P": 3,
        "H2R": 2,
        "M2D": 3,
        "R2R": 3,
        "P2I": 2,
        "CX": 4,
        "SCV": 3,
        "PLM": 4,
        "DCM": 3,
        "COM": 2,
        "IOT": 2,
    },
    "#07": {"O2C": 10, "SCV": 10},
    "#08": {"O2C": 10, "P2P": 10, "CX": 5},
    "#09": {"R2R": 10, "M2D": 10},
    "#10": {"R2R": 8, "SCV": 7},
    "#11": {"DCM": 10, "CX": 10},
    "#12": {"R2R": 8, "P2I": 7},
    "#13": {"COM": 10, "O2C": 10},
    "#14": {"DCM": 8, "SCV": 7},
    "#15": {"CX": 10, "COM": 5, "DCM": 5},
    "#16": {"M2D": 8, "IOT": 7},
    "#17": {"DCM": 15, "CX": 10, "O2C": 10},
}

TRIGGER_BY_PATTERN = {
    "#01": "REST",
    "#02": "Kafka",
    "#03": "REST",
    "#04": "REST",
    "#05": "DB Polling",
    "#06": "REST",
    "#07": "REST",
    "#08": "REST",
    "#09": "Kafka",
    "#10": "Event",
    "#11": "REST",
    "#12": "Scheduled",
    "#13": "REST",
    "#14": "Kafka",
    "#15": "Webhook",
    "#16": "REST",
    "#17": "Webhook",
}

TYPE_BY_TRIGGER = {
    "REST": "API",
    "Webhook": "Event-Driven",
    "Kafka": "Event-Driven",
    "Event": "Event-Driven",
    "Scheduled": "Batch",
    "DB Polling": "Batch",
}

PAYLOAD_RANGE_BY_PATTERN = {
    "#01": (5.0, 200.0),
    "#02": (1.0, 800.0),
    "#03": (10.0, 5000.0),
    "#04": (40.0, 240.0),
    "#05": (50.0, 500.0),
    "#06": (20.0, 1800.0),
    "#07": (20.0, 250.0),
    "#08": (20.0, 220.0),
    "#09": (10.0, 900.0),
    "#10": (1.0, 50.0),
    "#11": (20.0, 1800.0),
    "#12": (150.0, 2500.0),
    "#13": (10.0, 400.0),
    "#14": (10.0, 800.0),
    "#15": (30.0, 2200.0),
    "#16": (20.0, 900.0),
    "#17": (5.0, 220.0),
}

ASYNC_PATTERNS = {"#02", "#04", "#05", "#09", "#10", "#12", "#14", "#17"}

FAN_OUT_PATTERNS = {"#02", "#07", "#17"}

PROCESS_BRAND_MAP = {
    "O2C": ["NOVA_CORE", "NOVA_CONSUMER"],
    "P2P": ["NOVA_CORE", "NOVA_CONSUMER"],
    "H2R": ["NOVA_CORE", "NOVA_PREMIUM"],
    "M2D": ["NOVA_FOOD"],
    "R2R": ["NOVA_CORE", "NOVA_CONSUMER"],
    "P2I": ["NOVA_CORE", "NOVA_FOOD"],
    "CX": ["NOVA_CONSUMER", "NOVA_DIGITAL", "NOVA_PREMIUM"],
    "SCV": ["NOVA_CORE", "NOVA_FOOD"],
    "PLM": ["NOVA_PREMIUM", "NOVA_FOOD"],
    "DCM": ["NOVA_DIGITAL", "NOVA_PREMIUM"],
    "COM": ["NOVA_CORE", "NOVA_PREMIUM"],
    "IOT": ["NOVA_FOOD"],
}

PROCESS_FREQUENCY_CANDIDATES = {
    "O2C": ["Tiempo Real", "Tiempo real", "Cada 5 minutos"],
    "P2P": ["Una vez al día", "2 veces al día", "Cada 1 hora", "Cada hora"],
    "H2R": ["Una vez al día", "2 veces al día", "Cada 1 hora", "Cada hora"],
    "M2D": ["Cada minuto", "Tiempo Real", "Tiempo real"],
    "R2R": ["Una vez al día", "2 veces al día", "Cada 1 hora", "Cada hora"],
    "P2I": ["Cada 15 minutos", "Cada 30 minutos"],
    "CX": ["Tiempo Real", "Tiempo real", "Cada 5 minutos"],
    "SCV": ["Cada 15 minutos", "Cada 30 minutos"],
    "PLM": ["Cada 4 horas", "Una vez al día"],
    "DCM": ["Tiempo Real", "Tiempo real", "Cada 5 minutos"],
    "COM": ["Semanal", "Una vez al día"],
    "IOT": ["Cada minuto", "Tiempo Real", "Tiempo real"],
}

PROCESS_ACTIONS = {
    "O2C": [
        "Sales Order Release and Warehouse Dispatch",
        "Order Confirmation and Invoice Alignment",
        "Marketplace Order Intake and Fulfillment Update",
    ],
    "P2P": [
        "Purchase Order Approval and Supplier Sync",
        "Invoice Match and Exception Routing",
        "Supplier Onboarding and Contract Validation",
    ],
    "H2R": [
        "Employee Master Synchronization",
        "Payroll Event Publication",
        "Learning Completion and Workforce Status Update",
    ],
    "M2D": [
        "Production Order Release and Quality Dispatch",
        "Batch Genealogy and Warehouse Handoff",
        "Plant Execution Update and Material Availability Sync",
    ],
    "R2R": [
        "Journal Posting and Close Reconciliation Feed",
        "Treasury Position Publication",
        "Financial Forecast and Consolidation Refresh",
    ],
    "P2I": [
        "Inventory Position Synchronization",
        "Demand Plan Refresh and Exception Broadcast",
        "Stock Transfer and Safety Threshold Update",
    ],
    "CX": [
        "Loyalty Profile Enrichment",
        "Case Resolution Update and Notification",
        "Customer Preference Activation",
    ],
    "SCV": [
        "Shipment Milestone Broadcast",
        "Carrier Tracking Normalization",
        "Inventory Risk Visibility Update",
    ],
    "PLM": [
        "Product Specification Approval and Distribution",
        "Artwork Compliance Review Sync",
        "Master Product Attribute Propagation",
    ],
    "DCM": [
        "Campaign Activation and Audience Sync",
        "Storefront Content Publication",
        "Marketplace Feed and Offer Syndication",
    ],
    "COM": [
        "Policy Evidence Collection and Audit Handshake",
        "Tax Compliance Filing Support",
        "Risk Control Exception Escalation",
    ],
    "IOT": [
        "Sensor Threshold Event Publication",
        "Plant Condition Monitoring Update",
        "Cold Chain Alert and Recovery Workflow",
    ],
}

RATIONALE_SNIPPETS = {
    "#01": "the caller needs an immediate response before the business user can continue",
    "#02": "the event must fan out to independent consumers without coupling the producer",
    "#03": "the public API contract needs a controlled facade in front of heterogeneous backends",
    "#04": "the workflow spans multiple systems and needs compensation if a downstream step fails",
    "#05": "database changes must move downstream in near real time without polling spikes",
    "#06": "legacy and target runtimes need to coexist while traffic shifts safely",
    "#07": "parallel lookups reduce end-to-end latency for a composite response",
    "#08": "the integration must degrade safely when a dependency becomes unstable",
    "#09": "transactional data and event publication need a single reliable commit boundary",
    "#10": "the write model and read projections need to evolve independently",
    "#11": "channel-specific clients need a thin backend optimized for their experience",
    "#12": "data products need scheduled propagation into governed analytical targets",
    "#13": "the flow needs explicit zero-trust controls before traffic reaches core systems",
    "#14": "event contracts need discoverability and schema governance across teams",
    "#15": "AI enrichment adds business value but must remain inside a governed integration path",
    "#16": "mesh-style controls are needed across distributed plant and edge services",
    "#17": "one inbound webhook must drive multiple internal subscriber actions safely",
}

DESCRIPTION_TEMPLATES = {
    "O2C": (
        "Supports order-to-cash execution between {source} and {destination}, ensuring that "
        "{action_lower} stays aligned for NovaBrand's FY26 operating model."
    ),
    "P2P": (
        "Coordinates procure-to-pay data between {source} and {destination} so supplier, "
        "approval, and invoice events remain governed and auditable."
    ),
    "H2R": (
        "Keeps hire-to-retire information synchronized between {source} and {destination} "
        "for workforce administration, payroll, and compliance reporting."
    ),
    "M2D": (
        "Carries make-to-deliver execution data between {source} and {destination} to keep "
        "plant operations, quality, and fulfillment synchronized."
    ),
    "R2R": (
        "Moves record-to-report signals from {source} to {destination} so finance closes, "
        "treasury updates, and reporting cycles remain predictable."
    ),
    "P2I": (
        "Supports plan-to-inventory coordination between {source} and {destination}, linking "
        "forecast, inventory, and replenishment decisions."
    ),
    "CX": (
        "Connects customer experience platforms from {source} to {destination} so service, "
        "loyalty, and engagement workflows react quickly to customer changes."
    ),
    "SCV": (
        "Improves supply chain visibility by moving milestone and exception data from {source} "
        "to {destination} for downstream operational decisions."
    ),
    "PLM": (
        "Propagates product lifecycle updates between {source} and {destination} to keep "
        "regulated product content, quality artifacts, and master attributes consistent."
    ),
    "DCM": (
        "Enables digital commerce and marketing activation between {source} and {destination}, "
        "keeping campaigns, offers, and storefront content synchronized."
    ),
    "COM": (
        "Supports compliance, risk, and reporting flows between {source} and {destination} "
        "so evidence and control data remain traceable."
    ),
    "IOT": (
        "Streams smart manufacturing and telemetry context from {source} to {destination} to "
        "improve operational responsiveness across plants and cold-chain assets."
    ),
}

RETRY_POLICIES = {
    "sync": "3 retries, exponential backoff 1s/2s/4s, circuit breaker after 5 failures",
    "async": "DLQ after 3 delivery attempts, visibility timeout 300s",
    "cdc": "GoldenGate trail guarantees at-least-once; consumer idempotent by event_id",
    "batch": "Manual rerun via SFTP retry folder after ops review",
}

QA_REASON_POOL = [
    "Missing payload size estimate — cannot compute OIC billing message count",
    "Source system owner not confirmed — integration scope may change",
    "Pattern selection requires architecture board review",
    "Trigger type inconsistent with stated integration category",
    "Fan-out target count exceeds OIC parallel branch limit of 5",
    "Payload exceeds OCI Functions invoke body limit (6 MB)",
    "Frequency not aligned with stated business requirement",
    "No retry policy defined for critical business process",
    "Dependency on legacy system with no confirmed decommission date",
    "CDC pattern requires GoldenGate license — cost approval pending",
]

@dataclass(frozen=True)
class ViolationSpec:
    """Primary intentional service-limit violation for one generated row."""

    payload: float
    reason: str


VIOLATION_SPECS: dict[tuple[str, int], ViolationSpec] = {
    ("#03", 0): ViolationSpec(
        payload=6500.0,
        reason="Payload exceeds OCI Functions invoke body limit (6 MB)",
    ),
    ("#06", 0): ViolationSpec(
        payload=21000.0,
        reason="Trigger type inconsistent with stated integration category",
    ),
    ("#02", 0): ViolationSpec(
        payload=1100.0,
        reason="Pattern selection requires architecture board review",
    ),
    ("#17", 0): ViolationSpec(
        payload=300.0,
        reason="Frequency not aligned with stated business requirement",
    ),
    ("#01", 0): ViolationSpec(
        payload=10500.0,
        reason="Pattern selection requires architecture board review",
    ),
}

EXPECTED_PATTERN_COUNTS = {
    pattern_id: sum(domain_counts.values())
    for pattern_id, domain_counts in PATTERN_DISTRIBUTION.items()
}


@dataclass(frozen=True)
class BuildContext:
    """Runtime context for deterministic row generation."""

    rng: random.Random
    patterns: dict[str, str]
    frequency_execs: dict[str, float | None]
    tool_names: dict[str, str]
    status_sequence: list[str]
    complexity_sequence: list[str]
    qa_sequence: list[str]


@dataclass(frozen=True)
class ValidationMetrics:
    """Verification summary returned after dataset construction."""

    pattern_counts: Counter[str]
    distinct_sources: int
    distinct_destinations: int
    qa_counts: Counter[str]
    violation_counts: dict[str, int]


@dataclass(frozen=True)
class ArtifactMetrics:
    """Identifiers for downstream governed artifacts generated for the project."""

    volumetry_snapshot_id: str
    dashboard_snapshot_id: str
    approved_justifications: int
    export_job_ids: dict[str, str]


def normalize(value: str) -> str:
    """Normalize reference values for safe lookups."""

    return " ".join(value.strip().lower().split())


def build_sequence(counts: dict[str, int], rng: random.Random) -> list[str]:
    """Build a deterministic shuffled sequence from exact counts."""

    values: list[str] = []
    for item, count in counts.items():
        values.extend([item] * count)
    rng.shuffle(values)
    return values


def require_option(options: Sequence[str], candidates: Sequence[str]) -> str:
    """Return the first available option matching one of the candidate labels."""

    normalized_options = {normalize(option): option for option in options}
    for candidate in candidates:
        match = normalized_options.get(normalize(candidate))
        if match is not None:
            return match
    raise SystemExit(
        f"ABORT: none of the expected governed values were found: {', '.join(candidates)}"
    )


def resolve_frequencies(
    frequency_options: Sequence[str],
    frequency_execs: dict[str, float | None],
) -> dict[str, list[str]]:
    """Resolve process-level frequency labels against governed DB options."""

    resolved: dict[str, list[str]] = {}
    for process_code, candidates in PROCESS_FREQUENCY_CANDIDATES.items():
        process_values: list[str] = []
        for candidate in candidates:
            process_values.append(require_option(frequency_options, [candidate]))
        deduped = list(dict.fromkeys(process_values))
        if not deduped:
            raise SystemExit(f"ABORT: no frequency values resolved for process {process_code}")
        if all(frequency_execs.get(value) is None for value in deduped):
            raise SystemExit(
                f"ABORT: resolved frequencies for {process_code} have no executions/day metadata"
            )
        resolved[process_code] = deduped
    return resolved


def delete_existing_novabrand_projects(session: Session) -> list[str]:
    """Delete any existing NovaBrand project and its dependent rows."""

    projects = session.scalars(
        select(Project).where(Project.name.like("%NovaBrand%"))
    ).all()
    if not projects:
        return []

    project_ids = [project.id for project in projects]
    import_batch_ids = session.scalars(
        select(ImportBatch.id).where(ImportBatch.project_id.in_(project_ids))
    ).all()
    source_row_ids = session.scalars(
        select(SourceIntegrationRow.id).where(
            SourceIntegrationRow.import_batch_id.in_(import_batch_ids)
        )
    ).all()
    integration_ids = session.scalars(
        select(CatalogIntegration.id).where(CatalogIntegration.project_id.in_(project_ids))
    ).all()
    volumetry_ids = session.scalars(
        select(VolumetrySnapshot.id).where(VolumetrySnapshot.project_id.in_(project_ids))
    ).all()

    if integration_ids:
        justification_rows = session.scalars(
            select(JustificationRecord).where(
                JustificationRecord.integration_id.in_(integration_ids)
            )
        ).all()
        for justification_row in justification_rows:
            session.delete(justification_row)

    audit_rows = session.scalars(
        select(AuditEvent).where(AuditEvent.project_id.in_(project_ids))
    ).all()
    for audit_row in audit_rows:
        session.delete(audit_row)

    dashboard_rows_by_snapshot = session.scalars(
        select(DashboardSnapshot).where(
            DashboardSnapshot.volumetry_snapshot_id.in_(volumetry_ids)
        )
    ).all()
    for dashboard_row in dashboard_rows_by_snapshot:
        session.delete(dashboard_row)

    dashboard_rows_by_project = session.scalars(
        select(DashboardSnapshot).where(DashboardSnapshot.project_id.in_(project_ids))
    ).all()
    for dashboard_row in dashboard_rows_by_project:
        session.delete(dashboard_row)

    volumetry_rows = session.scalars(
        select(VolumetrySnapshot).where(VolumetrySnapshot.project_id.in_(project_ids))
    ).all()
    for volumetry_row in volumetry_rows:
        session.delete(volumetry_row)

    catalog_rows = session.scalars(
        select(CatalogIntegration).where(CatalogIntegration.project_id.in_(project_ids))
    ).all()
    for catalog_row in catalog_rows:
        session.delete(catalog_row)

    if source_row_ids:
        source_rows = session.scalars(
            select(SourceIntegrationRow).where(SourceIntegrationRow.id.in_(source_row_ids))
        ).all()
        for source_row in source_rows:
            session.delete(source_row)

    if import_batch_ids:
        import_batch_rows = session.scalars(
            select(ImportBatch).where(ImportBatch.id.in_(import_batch_ids))
        ).all()
        for import_batch_row in import_batch_rows:
            session.delete(import_batch_row)

    for project in projects:
        session.delete(project)

    session.flush()
    return project_ids


def choose_brand(process_code: str, seq_number: int) -> str:
    """Select a brand code deterministically for the business process."""

    options = PROCESS_BRAND_MAP[process_code]
    return options[(seq_number - 1) % len(options)]


def choose_owner(seq_number: int) -> str:
    """Rotate integration owners deterministically."""

    return OWNERS[(seq_number - 1) % len(OWNERS)]


def choose_frequency(
    process_code: str,
    pattern_id: str,
    seq_number: int,
    resolved_frequencies: dict[str, list[str]],
) -> str:
    """Select a governed frequency label for the process."""

    options = resolved_frequencies[process_code]
    if pattern_id in {"#12", "#04"} and len(options) > 1:
        return options[-1]
    return options[(seq_number - 1) % len(options)]


def choose_payload(
    ctx: BuildContext,
    pattern_id: str,
    occurrence_index: int,
) -> float:
    """Choose a deterministic payload, including the required limit violations."""

    violation = VIOLATION_SPECS.get((pattern_id, occurrence_index))
    if violation is not None:
        return violation.payload

    lower, upper = PAYLOAD_RANGE_BY_PATTERN[pattern_id]
    return round(ctx.rng.uniform(lower, upper), 1)


def choose_response_size(
    rng: random.Random,
    pattern_id: str,
    payload_kb: float,
) -> float | None:
    """Choose a response size for synchronous patterns."""

    if pattern_id in ASYNC_PATTERNS:
        return None
    ratio = rng.uniform(0.1, 0.5)
    return round(payload_kb * ratio, 1)


def choose_fan_out(
    rng: random.Random,
    pattern_id: str,
    occurrence_index: int,
) -> tuple[bool, int | None]:
    """Choose fan-out details for fan-out patterns."""

    if pattern_id not in FAN_OUT_PATTERNS:
        return False, None

    if pattern_id == "#07" and occurrence_index % 5 == 0:
        return True, 6 + (occurrence_index % 3)
    return True, 2 + (occurrence_index % 5)


def choose_system_pair(
    system_ids: Sequence[str],
    seq_number: int,
    pattern_id: str,
    process_code: str,
) -> tuple[str, str]:
    """Choose a deterministic source and destination pair with wide coverage."""

    pattern_offset = int(pattern_id[1:])
    source_index = (seq_number - 1) % len(system_ids)
    destination_index = (
        source_index * 3
        + pattern_offset
        + list(BUSINESS_PROCESSES).index(process_code)
        + 11
    ) % len(system_ids)
    if destination_index == source_index:
        destination_index = (destination_index + 1) % len(system_ids)
    return system_ids[source_index], system_ids[destination_index]


def choose_core_tools(tool_names: dict[str, str], pattern_id: str) -> str:
    """Choose the governed core tool stack for the pattern."""

    stacks = {
        "#01": [[tool_names["OIC Gen3"]], [tool_names["OIC Gen3"], tool_names["OCI API Gateway"]]],
        "#02": [[tool_names["OCI Streaming"], tool_names["OIC Gen3"]], [tool_names["OCI Streaming"], tool_names["Oracle Functions"]]],
        "#03": [[tool_names["OCI API Gateway"], tool_names["Oracle Functions"]]],
        "#04": [[tool_names["OIC Gen3"], tool_names["OCI Queue"]]],
        "#05": [[tool_names["OCI Data Integration"], tool_names["OCI Streaming"]]],
        "#06": [[tool_names["OCI API Gateway"], tool_names["OIC Gen3"]]],
        "#07": [[tool_names["OIC Gen3"]]],
        "#08": [[tool_names["OIC Gen3"], tool_names["OCI APM"]]],
        "#09": [[tool_names["Oracle DB"], tool_names["OCI Streaming"]]],
        "#10": [[tool_names["OCI Streaming"], tool_names["ATP"]]],
        "#11": [[tool_names["OCI API Gateway"], tool_names["Oracle Functions"], tool_names["OIC Gen3"]]],
        "#12": [[tool_names["OCI Data Integration"], tool_names["OCI Object Storage"]]],
        "#13": [[tool_names["OCI API Gateway"], tool_names["OIC Gen3"]]],
        "#14": [[tool_names["OCI Streaming"], tool_names["OIC Gen3"]]],
        "#15": [[tool_names["OIC Gen3"], tool_names["Oracle Functions"]]],
        "#16": [[tool_names["OCI API Gateway"], tool_names["OIC Gen3"]]],
        "#17": [[tool_names["OCI API Gateway"], tool_names["OIC Gen3"], tool_names["OCI Queue"]]],
    }
    return ", ".join(stacks[pattern_id][0])


def choose_retry_policy(pattern_id: str, trigger_type: str) -> str:
    """Select the retry policy text required by the prompt."""

    if pattern_id == "#05":
        return RETRY_POLICIES["cdc"]
    if trigger_type in {"Kafka", "Event", "Webhook"} or pattern_id in {"#04", "#17"}:
        return RETRY_POLICIES["async"]
    if trigger_type in {"Scheduled", "DB Polling"}:
        return RETRY_POLICIES["batch"]
    return RETRY_POLICIES["sync"]


def choose_calendarization(trigger_type: str, frequency: str) -> str | None:
    """Return a deterministic schedule string for batch-style integrations."""

    if trigger_type not in {"Scheduled", "DB Polling"}:
        return None
    if normalize(frequency) == normalize("Semanal"):
        return "Semanal los domingos a las 03:00 MX"
    if normalize(frequency) in {normalize("Una vez al día"), normalize("2 veces al día")}:
        return "Diario a las 02:00 MX"
    if normalize(frequency) in {normalize("Cada 12 horas"), normalize("Cada 6 horas")}:
        return "00:00 / 12:00 MX"
    return "Ventana batch cada 4 horas"


def choose_mapping_status(status_value: str) -> str:
    """Infer a light-weight mapping status."""

    if status_value == IntegrationStatus.DEFINITIVA.value:
        return "Mapeado"
    if status_value == IntegrationStatus.YA_EXISTE.value:
        return "Activo"
    return "Pendiente"


def choose_interface_status(status_value: str) -> str:
    """Infer a UI-facing interface status string."""

    if status_value == IntegrationStatus.YA_EXISTE.value:
        return "Operando"
    if status_value == IntegrationStatus.DEFINITIVA.value:
        return "Objetivo FY26"
    if status_value == IntegrationStatus.DUPLICADO_1.value:
        return "Duplicado controlado"
    return "En diseño"


def choose_complexity(
    pattern_id: str,
    seq_index: int,
    complexity_sequence: Sequence[str],
) -> str:
    """Choose complexity while biasing certain patterns upward."""

    if pattern_id in {"#04", "#05", "#09", "#10", "#12", "#16"}:
        return "Alto" if seq_index % 2 == 0 else "Medio"
    return complexity_sequence[seq_index]


def choose_qa_reasons(
    qa_status: str,
    pattern_id: str,
    core_tools: str,
    fan_out_targets: int | None,
    source_system_id: str,
    payload_kb: float,
    occurrence_index: int,
    rng: random.Random,
) -> list[str]:
    """Choose deterministic QA reasons consistent with the generated row."""

    if qa_status == QAStatus.OK.value:
        return []

    violation = VIOLATION_SPECS.get((pattern_id, occurrence_index))
    if violation is not None:
        if pattern_id == "#03":
            return [
                "Payload exceeds OCI Functions invoke body limit (6 MB)",
                "Pattern selection requires architecture board review",
            ]
        if pattern_id == "#02":
            return [
                "Pattern selection requires architecture board review",
                "Trigger type inconsistent with stated integration category",
            ]
        if pattern_id == "#17":
            return [
                "Frequency not aligned with stated business requirement",
                "Fan-out target count exceeds OIC parallel branch limit of 5",
            ]
        if pattern_id == "#06":
            return [
                "Trigger type inconsistent with stated integration category",
                "Dependency on legacy system with no confirmed decommission date",
            ]
        return [
            "Pattern selection requires architecture board review",
            "Payload exceeds OCI Functions invoke body limit (6 MB)"
            if "Oracle Functions" in core_tools
            else "Frequency not aligned with stated business requirement",
        ]

    reasons: list[str] = []
    if source_system_id in {"IBM_MQ", "TIBCO_EMS", "ORACLE_SOA", "WEBMETHODS"}:
        reasons.append("Dependency on legacy system with no confirmed decommission date")
    if pattern_id == "#05":
        reasons.append("CDC pattern requires GoldenGate license — cost approval pending")
    if fan_out_targets is not None and fan_out_targets > 5:
        reasons.append("Fan-out target count exceeds OIC parallel branch limit of 5")

    while len(reasons) < (2 if qa_status == QAStatus.PENDING.value else 1):
        reasons.append(QA_REASON_POOL[rng.randrange(len(QA_REASON_POOL))])
        reasons = list(dict.fromkeys(reasons))

    if qa_status == QAStatus.PENDING.value and payload_kb < 10:
        reasons.append("Missing payload size estimate — cannot compute OIC billing message count")
    return reasons[:2]


def choose_description(
    process_code: str,
    source_name: str,
    destination_name: str,
    action: str,
) -> str:
    """Create a specific integration description."""

    template = DESCRIPTION_TEMPLATES[process_code]
    return template.format(
        source=source_name,
        destination=destination_name,
        action_lower=action.lower(),
    )


def choose_rationale(
    pattern_name: str,
    pattern_id: str,
    process_code: str,
    source_name: str,
    destination_name: str,
    brand_code: str,
) -> str:
    """Create a unique pattern rationale string."""

    process_name = BUSINESS_PROCESSES[process_code]
    return (
        f"{pattern_name} ({pattern_id}) fits because {source_name} and {destination_name} "
        f"need a governed flow for {process_name.lower()} where {RATIONALE_SNIPPETS[pattern_id]}. "
        f"The design keeps the {brand_code} roadmap consistent with the FY26 modernization plan."
    )


def expand_pattern_processes(pattern_id: str) -> list[str]:
    """Expand the per-pattern process counts into a row-level ordered list."""

    processes: list[str] = []
    for process_code, count in PATTERN_DISTRIBUTION[pattern_id].items():
        processes.extend([process_code] * count)
    return processes


def build_integrations(
    project_id: str,
    import_batch_id: str,
    ctx: BuildContext,
    resolved_frequencies: dict[str, list[str]],
) -> list[CatalogIntegration]:
    """Build the deterministic synthetic integration set."""

    integrations: list[CatalogIntegration] = []
    system_ids = list(SYSTEMS)
    occurrence_by_pattern: Counter[str] = Counter()

    for pattern_id in sorted(PATTERN_DISTRIBUTION):
        if pattern_id not in ctx.patterns:
            raise SystemExit(f"ABORT: pattern {pattern_id} is not present in pattern_definitions")

        for process_code in expand_pattern_processes(pattern_id):
            seq_number = len(integrations) + 1
            occurrence_index = occurrence_by_pattern[pattern_id]
            occurrence_by_pattern[pattern_id] += 1

            owner = choose_owner(seq_number)
            brand_code = choose_brand(process_code, seq_number)
            source_system_id, destination_system_id = choose_system_pair(
                system_ids,
                seq_number,
                pattern_id,
                process_code,
            )
            source = SYSTEMS[source_system_id]
            destination = SYSTEMS[destination_system_id]
            action = PROCESS_ACTIONS[process_code][occurrence_index % len(PROCESS_ACTIONS[process_code])]
            frequency = choose_frequency(
                process_code,
                pattern_id,
                seq_number,
                resolved_frequencies,
            )
            payload_kb = choose_payload(ctx, pattern_id, occurrence_index)
            trigger_type = TRIGGER_BY_PATTERN[pattern_id]
            type_value = TYPE_BY_TRIGGER[trigger_type]
            response_size_kb = choose_response_size(ctx.rng, pattern_id, payload_kb)
            is_fan_out, fan_out_targets = choose_fan_out(ctx.rng, pattern_id, occurrence_index)
            status_value = ctx.status_sequence[seq_number - 1]
            complexity_value = choose_complexity(
                pattern_id,
                seq_number - 1,
                ctx.complexity_sequence,
            )
            qa_status = ctx.qa_sequence[seq_number - 1]
            if VIOLATION_SPECS.get((pattern_id, occurrence_index)) is not None:
                qa_status = QAStatus.REVISAR.value
            core_tools = choose_core_tools(ctx.tool_names, pattern_id)
            qa_reasons = choose_qa_reasons(
                qa_status,
                pattern_id,
                core_tools,
                fan_out_targets,
                source_system_id,
                payload_kb,
                occurrence_index,
                ctx.rng,
            )
            if qa_status == QAStatus.OK.value and qa_reasons:
                qa_status = QAStatus.REVISAR.value
            executions_per_day = ctx.frequency_execs.get(frequency)
            payload_per_hour_kb = (
                round(payload_kb * executions_per_day / 24.0, 2)
                if executions_per_day is not None
                else None
            )
            interface_id = f"NB-{process_code}-{pattern_id[1:]}-{seq_number:04d}"
            interface_name = (
                f"{source['name'].split(' — ')[0]} to {destination['name'].split(' — ')[0]} — {action}"
            )
            description = choose_description(
                process_code,
                source["name"],
                destination["name"],
                action,
            )
            rationale = choose_rationale(
                ctx.patterns[pattern_id],
                pattern_id,
                process_code,
                source["name"],
                destination["name"],
                brand_code,
            )
            retry_policy = choose_retry_policy(pattern_id, trigger_type)
            calendarization = choose_calendarization(trigger_type, frequency)
            uncertainty = (
                "Architecture and business assumptions pending final domain sign-off."
                if qa_status == QAStatus.PENDING.value
                else None
            )
            comments = (
                "Synthetic enterprise scenario row generated for milestone M24 validation."
                if qa_status != QAStatus.OK.value
                else None
            )
            source_reference = (
                f"/novabrand/{process_code.lower()}/{pattern_id[1:]}/{seq_number:04d}"
                if trigger_type == "REST"
                else f"novabrand.{process_code.lower()}.{pattern_id[1:]}.{seq_number:04d}"
            )

            raw_data = {
                "Interfaz": interface_name,
                "Sistema Origen": source["name"],
                "Sistema Destino": destination["name"],
                "Proceso de Negocio": process_code,
                "Frecuencia": frequency,
                "Patrón": pattern_id,
                "Herramientas": core_tools,
            }
            source_row = SourceIntegrationRow(
                import_batch_id=import_batch_id,
                source_row_number=seq_number,
                raw_data=raw_data,
                included=True,
                exclusion_reason=None,
                normalization_events=[],
            )
            integration = CatalogIntegration(
                project_id=project_id,
                source_row=source_row,
                seq_number=seq_number,
                interface_id=interface_id,
                owner=owner,
                brand=brand_code,
                business_process=process_code,
                interface_name=interface_name,
                description=description,
                status=status_value,
                mapping_status=choose_mapping_status(status_value),
                initial_scope=f"FY26 Wave {((seq_number - 1) % 4) + 1}",
                complexity=complexity_value,
                frequency=frequency,
                type=type_value,
                base="OCI Integration Program FY26",
                interface_status=choose_interface_status(status_value),
                is_real_time=trigger_type in {"REST", "Webhook", "Kafka"} or pattern_id in {"#05", "#09", "#14", "#17"},
                trigger_type=trigger_type,
                response_size_kb=response_size_kb,
                payload_per_execution_kb=payload_kb,
                is_fan_out=is_fan_out,
                fan_out_targets=fan_out_targets,
                source_system=source["name"],
                source_technology=source["technology"],
                source_api_reference=source_reference,
                source_owner=source["owner"],
                destination_system=destination["name"],
                destination_technology_1=destination["technology"],
                destination_technology_2=None,
                destination_owner=destination["owner"],
                executions_per_day=executions_per_day,
                payload_per_hour_kb=payload_per_hour_kb,
                selected_pattern=pattern_id,
                pattern_rationale=rationale,
                comments=comments,
                retry_policy=retry_policy,
                core_tools=core_tools,
                additional_tools_overlays=None,
                qa_status=qa_status,
                qa_reasons=qa_reasons,
                calendarization=calendarization,
                uncertainty=uncertainty,
            )
            integrations.append(integration)

    return integrations


def verify_integrations(
    integrations: Sequence[CatalogIntegration],
) -> ValidationMetrics:
    """Validate the generated dataset against the prompt's success criteria."""

    if len(integrations) != 480:
        raise SystemExit(f"ABORT: expected 480 integrations, found {len(integrations)}")

    selected_patterns: list[str] = []
    qa_status_values: list[str] = []
    for integration in integrations:
        if integration.selected_pattern is None:
            raise SystemExit("ABORT: generated integration missing selected_pattern")
        if integration.qa_status is None:
            raise SystemExit("ABORT: generated integration missing qa_status")
        selected_patterns.append(integration.selected_pattern)
        qa_status_values.append(integration.qa_status)

    by_pattern: Counter[str] = Counter(selected_patterns)
    if dict(by_pattern) != EXPECTED_PATTERN_COUNTS:
        raise SystemExit(
            f"ABORT: pattern distribution mismatch: {dict(sorted(by_pattern.items()))}"
        )

    distinct_sources = len({integration.source_system for integration in integrations})
    distinct_destinations = len({integration.destination_system for integration in integrations})
    if distinct_sources < 70:
        raise SystemExit(f"ABORT: only {distinct_sources} distinct source systems")
    if distinct_destinations < 70:
        raise SystemExit(f"ABORT: only {distinct_destinations} distinct destination systems")

    brands = {integration.brand for integration in integrations}
    if len(brands) != 5:
        raise SystemExit(f"ABORT: expected 5 brands, found {len(brands)}")

    processes = {integration.business_process for integration in integrations}
    if len(processes) != 12:
        raise SystemExit(f"ABORT: expected 12 business processes, found {len(processes)}")

    qa_counts: Counter[str] = Counter(qa_status_values)
    ok_pct = qa_counts[QAStatus.OK.value] / len(integrations)
    revisar_pct = qa_counts[QAStatus.REVISAR.value] / len(integrations)
    if ok_pct < 0.60 or revisar_pct < 0.15:
        raise SystemExit(
            f"ABORT: QA distribution invalid: OK={ok_pct:.2%}, REVISAR={revisar_pct:.2%}"
        )

    violation_counts = {
        "functions": sum(
            1
            for integration in integrations
            if integration.payload_per_execution_kb == 6500.0
            and integration.core_tools is not None
            and "Oracle Functions" in integration.core_tools
        ),
        "api_gw": sum(
            1
            for integration in integrations
            if integration.payload_per_execution_kb == 21000.0
            and integration.core_tools is not None
            and "OCI API Gateway" in integration.core_tools
        ),
        "streaming": sum(
            1
            for integration in integrations
            if integration.payload_per_execution_kb == 1100.0
            and integration.core_tools is not None
            and "OCI Streaming" in integration.core_tools
        ),
        "queue": sum(
            1
            for integration in integrations
            if integration.payload_per_execution_kb == 300.0
            and integration.core_tools is not None
            and "OCI Queue" in integration.core_tools
        ),
        "oic": sum(
            1
            for integration in integrations
            if integration.payload_per_execution_kb == 10500.0
            and integration.core_tools is not None
            and "OIC Gen3" in integration.core_tools
        ),
    }
    if sum(violation_counts.values()) != 5:
        raise SystemExit(
            f"ABORT: expected exactly 5 intentional limit violations, found {violation_counts}"
        )

    return ValidationMetrics(
        pattern_counts=by_pattern,
        distinct_sources=distinct_sources,
        distinct_destinations=distinct_destinations,
        qa_counts=qa_counts,
        violation_counts=violation_counts,
    )


def format_summary(
    project: Project,
    import_batch: ImportBatch,
    pattern_counts: Counter[str],
    distinct_sources: int,
    distinct_destinations: int,
    qa_counts: Counter[str],
    violation_counts: dict[str, int],
    patterns: dict[str, str],
) -> str:
    """Format the exact console summary block required by the prompt."""

    total = sum(pattern_counts.values())
    lines = [
        "=== Synthetic Project Generated ===",
        f"Project ID:   {project.id}",
        f"Project Name: {PROJECT_NAME}",
        "",
        "Integration counts by pattern:",
    ]
    for pattern_id in sorted(pattern_counts):
        lines.append(
            f"  {pattern_id} {patterns[pattern_id]:<27}: {pattern_counts[pattern_id]:>3}"
        )
    lines.extend(
        [
            f"  TOTAL                          : {total}",
            "",
            f"Distinct source_systems:         {distinct_sources}",
            f"Distinct destination_systems:    {distinct_destinations}",
            f"Distinct brands:                  {len(BRANDS)}",
            f"Distinct business processes:     {len(BUSINESS_PROCESSES)}",
            "",
            "QA distribution:",
            f"  OK      : {qa_counts[QAStatus.OK.value]:>3} ({qa_counts[QAStatus.OK.value] / total:.0%})",
            f"  REVISAR : {qa_counts[QAStatus.REVISAR.value]:>3} ({qa_counts[QAStatus.REVISAR.value] / total:.0%})",
            f"  PENDING : {qa_counts[QAStatus.PENDING.value]:>3} ({qa_counts[QAStatus.PENDING.value] / total:.0%})",
            "",
            f"Limit-violation integrations:    {sum(violation_counts.values())}",
            f"  - Functions body >6 MB: {violation_counts['functions']}",
            f"  - API GW body >20 MB: {violation_counts['api_gw']}",
            f"  - Streaming msg >1 MB: {violation_counts['streaming']}",
            f"  - Queue msg >256 KB: {violation_counts['queue']}",
            f"  - OIC msg >10 MB: {violation_counts['oic']}",
            "",
            f"Import batch ID: {import_batch.id}",
            "===================================",
        ]
    )
    return "\n".join(lines)


async def create_project_artifacts(project_id: str) -> ArtifactMetrics:
    """Generate governed snapshots, narratives, and exports for the project."""

    snapshot_id = await _recalculate_project(project_id)
    dashboard_snapshot_id = await _load_dashboard_snapshot(project_id, snapshot_id)
    approved_justifications = await _approve_project_justifications(project_id)
    export_job_ids = await _create_project_exports(project_id, snapshot_id)
    return ArtifactMetrics(
        volumetry_snapshot_id=snapshot_id,
        dashboard_snapshot_id=dashboard_snapshot_id,
        approved_justifications=approved_justifications,
        export_job_ids=export_job_ids,
    )


async def _recalculate_project(
    project_id: str,
)-> str:
    """Persist a fresh volumetry snapshot and its dashboard companion."""

    async with AsyncSessionLocal() as db:
        async with db.begin():
            snapshot = await recalc_service.recalculate_project(project_id, "synthetic-generator", db)
        return snapshot.id


async def _load_dashboard_snapshot(project_id: str, snapshot_id: str) -> str:
    """Load the dashboard snapshot ID generated during recalculation."""

    async with AsyncSessionLocal() as db:
        dashboard = await dashboard_service.get_snapshot(project_id, snapshot_id, db)
        return dashboard.snapshot_id


async def _approve_project_justifications(project_id: str) -> int:
    """Persist approved deterministic justifications for all project rows."""

    async with AsyncSessionLocal() as db:
        integration_ids = (
            await db.scalars(
                select(CatalogIntegration.id)
                .where(CatalogIntegration.project_id == project_id)
                .order_by(CatalogIntegration.seq_number, CatalogIntegration.created_at)
            )
        ).all()
        if not integration_ids:
            return 0

        for integration_id in integration_ids:
            await justification_service.approve_justification(
                project_id,
                integration_id,
                "synthetic-generator",
                db,
            )
        await db.commit()
        return len(integration_ids)


async def _create_project_exports(
    project_id: str,
    snapshot_id: str,
) -> dict[str, str]:
    """Generate the supported export artifacts for the final synthetic snapshot."""

    async with AsyncSessionLocal() as db:
        async with db.begin():
            xlsx_job = await export_service.create_xlsx_export(project_id, snapshot_id, db)
            json_job = await export_service.create_json_export(project_id, snapshot_id, db)
            pdf_job = await export_service.create_pdf_export(project_id, snapshot_id, db)
    return {
        "xlsx": xlsx_job.job_id,
        "json": json_job.job_id,
        "pdf": pdf_job.job_id,
    }


def main() -> None:
    """Generate the synthetic project against the live database."""

    if len(SYSTEMS) != 77:
        raise SystemExit(f"ABORT: expected 77 systems, found {len(SYSTEMS)}")

    engine = create_engine(get_sync_database_url())
    rng = random.Random(42)

    with Session(engine) as session:
        deleted_project_ids = delete_existing_novabrand_projects(session)
        if deleted_project_ids:
            print(f"Deleted existing NovaBrand projects: {deleted_project_ids}")

        pattern_rows = session.scalars(select(PatternDefinition)).all()
        patterns_in_db = {
            pattern.pattern_id: pattern.name for pattern in pattern_rows if pattern.is_active
        }
        frequency_rows = session.scalars(
            select(DictionaryOption).where(DictionaryOption.category == "FREQUENCY")
        ).all()
        tool_rows = session.scalars(
            select(DictionaryOption).where(DictionaryOption.category == "TOOLS")
        ).all()

        frequency_options = [row.value for row in frequency_rows]
        tool_options = [row.value for row in tool_rows]
        if len(patterns_in_db) < 17:
            raise SystemExit(f"ABORT: only {len(patterns_in_db)} patterns in DB — need 17")
        if len(frequency_options) < 5:
            raise SystemExit(
                f"ABORT: only {len(frequency_options)} FREQUENCY options in DB — need ≥5"
            )
        if len(tool_options) < 10:
            raise SystemExit(f"ABORT: only {len(tool_options)} TOOLS options in DB — need ≥10")

        frequency_execs = {row.value: row.executions_per_day for row in frequency_rows}
        resolved_frequencies = resolve_frequencies(frequency_options, frequency_execs)
        tool_names = {
            "OIC Gen3": require_option(tool_options, ["OIC Gen3"]),
            "OCI API Gateway": require_option(tool_options, ["OCI API Gateway"]),
            "OCI Streaming": require_option(tool_options, ["OCI Streaming"]),
            "OCI Queue": require_option(tool_options, ["OCI Queue"]),
            "Oracle Functions": require_option(tool_options, ["Oracle Functions"]),
            "OCI Data Integration": require_option(tool_options, ["OCI Data Integration"]),
            "ATP": require_option(tool_options, ["ATP"]),
            "Oracle DB": require_option(tool_options, ["Oracle DB"]),
            "OCI Object Storage": require_option(tool_options, ["OCI Object Storage"]),
            "OCI APM": require_option(tool_options, ["OCI APM"]),
        }

        ctx = BuildContext(
            rng=rng,
            patterns=patterns_in_db,
            frequency_execs=frequency_execs,
            tool_names=tool_names,
            status_sequence=build_sequence(
                {
                    IntegrationStatus.DEFINITIVA.value: 264,
                    IntegrationStatus.EN_REVISION.value: 96,
                    IntegrationStatus.YA_EXISTE.value: 72,
                    IntegrationStatus.TBD.value: 24,
                    IntegrationStatus.DUPLICADO_1.value: 24,
                },
                rng,
            ),
            complexity_sequence=build_sequence(
                {"Bajo": 168, "Medio": 216, "Alto": 96},
                rng,
            ),
            qa_sequence=build_sequence(
                {
                    QAStatus.OK.value: 312,
                    QAStatus.REVISAR.value: 120,
                    QAStatus.PENDING.value: 48,
                },
                rng,
            ),
        )

        project = Project(
            name=PROJECT_NAME,
            description=PROJECT_DESCRIPTION,
            status=ProjectStatus.ACTIVE,
            owner_id=PROJECT_OWNER_ID,
            project_metadata=PROJECT_METADATA,
        )
        session.add(project)
        session.flush()

        import_batch = ImportBatch(
            project_id=project.id,
            filename="synthetic_novabrand_fy26_v1.xlsx",
            parser_version="2.0.0",
            status=ImportStatus.COMPLETED,
            source_row_count=0,
            loaded_count=0,
            excluded_count=0,
            tbq_y_count=0,
            header_map={
                "Interfaz": "interface_name",
                "Sistema Origen": "source_system",
                "Sistema Destino": "destination_system",
                "Proceso de Negocio": "business_process",
                "Frecuencia": "frequency",
            },
        )
        session.add(import_batch)
        session.flush()

        integrations = build_integrations(
            project.id,
            import_batch.id,
            ctx,
            resolved_frequencies,
        )
        metrics = verify_integrations(integrations)

        session.add_all(integrations)
        import_batch.source_row_count = len(integrations)
        import_batch.loaded_count = len(integrations)
        import_batch.tbq_y_count = len(integrations)
        session.commit()

        artifact_metrics = asyncio.run(create_project_artifacts(project.id))

        summary = format_summary(
            project,
            import_batch,
            metrics.pattern_counts,
            metrics.distinct_sources,
            metrics.distinct_destinations,
            metrics.qa_counts,
            metrics.violation_counts,
            patterns_in_db,
        )
        print(summary)
        print(
            "\n".join(
                [
                    f"Volumetry snapshot ID: {artifact_metrics.volumetry_snapshot_id}",
                    f"Dashboard snapshot ID: {artifact_metrics.dashboard_snapshot_id}",
                    f"Approved justifications: {artifact_metrics.approved_justifications}",
                    f"Export job IDs: {artifact_metrics.export_job_ids}",
                ]
            )
        )


if __name__ == "__main__":
    main()
