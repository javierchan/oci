"""Deterministic synthetic enterprise project generation helpers.

This module builds a governed, enterprise-scale synthetic dataset and seeds it
through the same service-layer flows used by the real product. It is designed to
be reusable from the current script-based entrypoint and from a future admin
router/worker slice without moving orchestration into the calc engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import random
from typing import Literal, cast

from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import CatalogIntegration, PatternDefinition, Project
from app.models.project import ProjectStatus
from app.schemas.catalog import CatalogIntegrationPatch, ManualIntegrationCreate
from app.schemas.export import ExportJobResponse
from app.services import (
    audit_service,
    catalog_service,
    dashboard_service,
    export_service,
    import_service,
    justification_service,
    recalc_service,
)
from app.services.serializers import sanitize_for_json

API_ROOT = Path(__file__).resolve().parents[2]
REPORT_ROOT = API_ROOT / "generated-reports"
UPLOAD_ROOT = API_ROOT / "uploads" / "synthetic"
SOURCE_SHEET_NAME = "Catálogo de Integraciones"
SYNTHETIC_ACTOR_ID = "synthetic-generator"

IMPORT_HEADER_ROW: list[str] = [
    "#",
    "ID de Interfaz",
    "Owner",
    "Marca",
    "Proceso de Negocio",
    "Interfaz",
    "Descripción",
    "Estado",
    "Estado de Mapeo",
    "Alcance Inicial",
    "Complejidad",
    "Frecuencia",
    "Tipo",
    "Base",
    "Estado Interfaz",
    "Tiempo Real (Si/No)",
    "Tipo Trigger OIC",
    "Response Size (KB)",
    "Payload por ejecución (KB)",
    "Fan-Out (Si/No)",
    "# Destinos",
    "Sistema de Origen",
    "Tecnología de Origen",
    "API Reference",
    "Propietario de Origen",
    "Sistema de Destino",
    "Tecnología de Destino #1",
    "Tecnología de Destino #2",
    "Propietario de Destino",
    "Calendarización",
    "TBQ",
    "Patrón seleccionado (manual)",
    "Racional del patrón (manual)",
    "Comentarios / Observaciones",
    "Retry Policy",
    "Herramientas Core Cuantificables / Volumétricas",
    "Herramientas Adicionales / Overlays (complemento manual)",
    "Incertidumbre",
]

BRANDS = [
    "Retail North",
    "Retail South",
    "Shared Services",
    "Digital Commerce",
    "Marketplace LATAM",
    "Corporate Finance",
]

BUSINESS_PROCESSES = [
    "Order to Cash",
    "Procure to Pay",
    "Inventory Synchronization",
    "Customer Service Resolution",
    "Partner Onboarding",
    "Store Replenishment",
    "Revenue Recognition",
    "Identity Provisioning",
    "Observability and Governance",
]

STATUS_VALUES = [
    "Definitiva (End-State)",
    "En Revisión",
    "En Progreso",
    "TBD",
]

MAPPING_STATUS_VALUES = [
    "Mapeado",
    "Pendiente",
    "En análisis",
]

CALENDARIZATION_VALUES = [
    "24x7",
    "Business hours",
    "Store close",
    "Month-end",
    "Quarter-end",
]

SHORT_TOOL_LABELS = {
    "OIC Gen3": "OIC",
    "OCI Streaming": "Stream",
    "OCI Queue": "Queue",
    "OCI Functions": "Fn",
    "OCI Data Integration": "DI",
    "Data Integrator": "DIx",
    "Oracle GoldenGate": "GG",
    "OCI API Gateway": "API GW",
    "Process Automation": "Proc",
    "OCI Events": "Events",
}

DESTINATION_TECHNOLOGIES = [
    None,
    None,
    "REST API",
    "Kafka",
    "Oracle DB",
    "SFTP",
]


@dataclass(frozen=True)
class SystemCapability:
    name: str
    technology: str
    owner_suffix: str


CAPABILITY_PROFILES: tuple[SystemCapability, ...] = (
    SystemCapability("Core ERP", "Oracle ERP Cloud", "ERP"),
    SystemCapability("Customer Hub", "Salesforce", "CX"),
    SystemCapability("Order Hub", "Oracle ATP", "Commerce"),
    SystemCapability("Inventory Service", "SAP S/4HANA", "Supply"),
    SystemCapability("Pricing Engine", "REST API", "Pricing"),
    SystemCapability("Billing Platform", "Oracle Revenue Management", "Billing"),
    SystemCapability("Warehouse System", "Manhattan WMS", "Logistics"),
    SystemCapability("Partner Gateway", "REST API", "Partners"),
    SystemCapability("Analytics Lake", "OCI Object Storage", "Data"),
)

DOMAINS = (
    "Retail",
    "Finance",
    "Supply Chain",
    "Logistics",
    "Human Capital",
    "Data Platform",
    "Identity",
    "Marketplace",
)


@dataclass(frozen=True)
class SystemProfile:
    name: str
    domain: str
    technology: str
    owner: str


@dataclass(frozen=True)
class PatternPlan:
    pattern_id: str
    route_core_tools: tuple[str, ...]
    route_overlays: tuple[str, ...]
    type_value: str
    base_value: str
    frequency_options: tuple[str, ...]
    complexity: str
    payload_range_kb: tuple[int, int]
    response_ratio: float
    fan_out_targets: tuple[int, ...] = ()
    uncertainty_ratio: int = 0


PATTERN_PLANS: dict[str, PatternPlan] = {
    "#01": PatternPlan("#01", ("OIC Gen3",), ("OCI API Gateway",), "REST", "Operational API", ("Cada 15 minutos", "Cada 1 hora", "Tiempo Real"), "Medio", (48, 2048), 0.35),
    "#02": PatternPlan("#02", ("OCI Streaming", "OIC Gen3"), ("OCI Events",), "Event", "Domain Event", ("Cada 5 minutos", "Cada 15 minutos", "Tiempo Real"), "Medio", (32, 768), 0.18, (2, 3, 4), 8),
    "#03": PatternPlan("#03", ("OCI Functions",), ("OCI API Gateway",), "REST", "Facade API", ("Cada 15 minutos", "Cada 1 hora", "Tiempo Real"), "Bajo", (16, 768), 0.25),
    "#04": PatternPlan("#04", ("OIC Gen3", "OCI Queue", "OCI Functions"), ("Process Automation",), "Scheduled", "Process Orchestration", ("Cada 1 hora", "Cada 4 horas", "Cada 12 horas"), "Alto", (128, 2048), 0.15),
    "#05": PatternPlan("#05", ("Oracle GoldenGate", "OCI Streaming"), (), "DB Polling", "CDC Feed", ("Cada 5 minutos", "Cada 15 minutos", "Cada 1 hora"), "Alto", (24, 512), 0.05, (), 10),
    "#06": PatternPlan("#06", ("OIC Gen3",), ("OCI API Gateway",), "REST", "Migration Bridge", ("Cada 1 hora", "Cada 4 horas", "Cada 12 horas"), "Medio", (64, 1536), 0.30),
    "#07": PatternPlan("#07", ("OIC Gen3",), ("OCI API Gateway",), "REST", "Parallel Aggregation", ("Cada 15 minutos", "Cada 1 hora", "Tiempo Real"), "Alto", (96, 2048), 0.55, (2, 3, 4)),
    "#08": PatternPlan("#08", ("OIC Gen3", "OCI Queue", "OCI Functions"), ("OCI API Gateway",), "REST", "Resilient API", ("Cada 15 minutos", "Cada 1 hora", "Tiempo Real"), "Alto", (64, 1536), 0.30),
    "#09": PatternPlan("#09", ("Oracle GoldenGate", "OCI Streaming", "OIC Gen3"), (), "Event", "Transactional Event", ("Cada 15 minutos", "Cada 1 hora", "Tiempo Real"), "Alto", (24, 384), 0.08),
    "#10": PatternPlan("#10", ("OCI Streaming", "OIC Gen3", "OCI Data Integration"), (), "Event", "Read Model Projection", ("Cada 15 minutos", "Cada 1 hora"), "Alto", (64, 1024), 0.12),
    "#11": PatternPlan("#11", ("OCI Functions",), ("OCI API Gateway",), "REST", "Channel API", ("Cada 15 minutos", "Cada 1 hora", "Tiempo Real"), "Medio", (16, 512), 0.20),
    "#12": PatternPlan("#12", ("OCI Data Integration", "Oracle GoldenGate"), (), "Scheduled", "Data Product Pipeline", ("Cada 4 horas", "Cada 12 horas", "Una vez al día"), "Alto", (256, 4096), 0.10, (), 12),
    "#13": PatternPlan("#13", ("OIC Gen3",), ("OCI API Gateway",), "REST", "Protected Integration", ("Cada 15 minutos", "Cada 1 hora", "Tiempo Real"), "Medio", (32, 1024), 0.22),
    "#14": PatternPlan("#14", ("OCI Streaming", "OIC Gen3"), ("OCI API Gateway",), "Event", "Governed Event API", ("Cada 15 minutos", "Cada 1 hora", "Tiempo Real"), "Medio", (32, 768), 0.12),
    "#15": PatternPlan("#15", ("OIC Gen3", "OCI Functions"), ("OCI API Gateway",), "REST", "AI-Assisted Orchestration", ("Cada 1 hora", "Cada 4 horas", "Bajo demanda"), "Alto", (64, 1024), 0.18, (), 6),
    "#16": PatternPlan("#16", ("OIC Gen3", "OCI Functions"), ("OCI API Gateway",), "REST", "Mesh Edge", ("Cada 15 minutos", "Cada 1 hora", "Tiempo Real"), "Alto", (48, 768), 0.20),
    "#17": PatternPlan("#17", ("OIC Gen3", "OCI Functions", "OCI Queue"), ("OCI API Gateway",), "Webhook", "Webhook Distribution", ("Cada 15 minutos", "Cada 1 hora", "Tiempo Real"), "Alto", (24, 640), 0.10, (2, 3, 4)),
}

PATTERN_WEIGHTS: dict[str, int] = {
    "#01": 120,
    "#02": 140,
    "#03": 10,
    "#04": 10,
    "#05": 80,
    "#06": 10,
    "#07": 10,
    "#08": 10,
    "#09": 10,
    "#10": 10,
    "#11": 10,
    "#12": 10,
    "#13": 10,
    "#14": 10,
    "#15": 10,
    "#16": 10,
    "#17": 10,
}


@dataclass(frozen=True)
class SyntheticProjectSpec:
    project_name: str = "Synthetic Enterprise Reference Project"
    owner_id: str = "synthetic-admin"
    description: str = (
        "Deterministic enterprise-scale synthetic OCI integration portfolio used "
        "to validate catalog, graph, volumetry, dashboard, justifications, audit, "
        "and export flows end to end."
    )
    seed: int = 20260416
    import_included_count: int = 420
    manual_count: int = 60
    excluded_import_count: int = 36
    minimum_distinct_systems: int = 70
    minimum_catalog_count: int = 480


DEFAULT_SYNTHETIC_SPEC = SyntheticProjectSpec()


@dataclass(frozen=True)
class SyntheticIntegrationSpec:
    sequence_number: int
    capture_mode: Literal["import", "manual"]
    interface_id: str
    owner: str
    brand: str
    business_process: str
    interface_name: str
    description: str
    status: str
    mapping_status: str
    initial_scope: str
    complexity: str
    frequency: str
    type_value: str
    base_value: str
    interface_status: str
    is_real_time: bool
    trigger_type: str
    response_size_kb: float
    payload_per_execution_kb: float
    is_fan_out: bool
    fan_out_targets: int | None
    source_system: str
    source_technology: str
    source_api_reference: str
    source_owner: str
    destination_system: str
    destination_technology_1: str
    destination_technology_2: str | None
    destination_owner: str
    calendarization: str
    selected_pattern: str
    pattern_rationale: str
    comments: str
    retry_policy: str
    core_tools: tuple[str, ...]
    overlay_keys: tuple[str, ...]
    uncertainty: str | None

    @property
    def core_tools_csv(self) -> str:
        return ", ".join(self.core_tools)

    @property
    def canvas_state(self) -> str:
        return build_canvas_state(self.core_tools, self.overlay_keys, self.payload_per_execution_kb)

    def to_workbook_row(self) -> list[object]:
        return [
            self.sequence_number,
            self.interface_id,
            self.owner,
            self.brand,
            self.business_process,
            self.interface_name,
            self.description,
            self.status,
            self.mapping_status,
            self.initial_scope,
            self.complexity,
            self.frequency,
            self.type_value,
            self.base_value,
            self.interface_status,
            "Sí" if self.is_real_time else "No",
            self.trigger_type,
            self.response_size_kb,
            self.payload_per_execution_kb,
            "Sí" if self.is_fan_out else "No",
            self.fan_out_targets,
            self.source_system,
            self.source_technology,
            self.source_api_reference,
            self.source_owner,
            self.destination_system,
            self.destination_technology_1,
            self.destination_technology_2,
            self.destination_owner,
            self.calendarization,
            "Y",
            self.selected_pattern,
            self.pattern_rationale,
            self.comments,
            self.retry_policy,
            self.core_tools_csv,
            self.canvas_state,
            self.uncertainty,
        ]

    def to_manual_request(self) -> ManualIntegrationCreate:
        return ManualIntegrationCreate(
            interface_id=self.interface_id,
            brand=self.brand,
            business_process=self.business_process,
            interface_name=self.interface_name,
            description=self.description,
            source_system=self.source_system,
            source_technology=self.source_technology,
            source_api_reference=self.source_api_reference,
            source_owner=self.source_owner,
            destination_system=self.destination_system,
            destination_technology=self.destination_technology_1,
            destination_owner=self.destination_owner,
            type=self.type_value,
            frequency=self.frequency,
            payload_per_execution_kb=self.payload_per_execution_kb,
            complexity=self.complexity,
            uncertainty=self.uncertainty,
            selected_pattern=self.selected_pattern,
            pattern_rationale=self.pattern_rationale,
            core_tools=list(self.core_tools),
            tbq="Y",
            initial_scope=self.initial_scope,
            owner=self.owner,
        )

    def to_follow_up_patch(self) -> CatalogIntegrationPatch:
        return CatalogIntegrationPatch(
            comments=self.comments,
            retry_policy=self.retry_policy,
            additional_tools_overlays=self.canvas_state,
        )


@dataclass(frozen=True)
class SyntheticDataset:
    import_rows: list[SyntheticIntegrationSpec]
    manual_rows: list[SyntheticIntegrationSpec]
    excluded_rows: list[list[object]]

    @property
    def included_rows(self) -> list[SyntheticIntegrationSpec]:
        return [*self.import_rows, *self.manual_rows]


@dataclass(frozen=True)
class SyntheticDatasetValidation:
    catalog_count: int
    distinct_systems: int
    covered_pattern_ids: list[str]
    max_canvas_state_length: int


@dataclass(frozen=True)
class SyntheticArtifactManifest:
    workbook_path: str
    report_json_path: str
    report_markdown_path: str
    export_jobs: dict[str, dict[str, str]]


@dataclass(frozen=True)
class SyntheticGenerationResult:
    project_id: str
    project_name: str
    import_batch_id: str
    imported_snapshot_id: str
    final_snapshot_id: str
    imported_dashboard_snapshot_id: str
    final_dashboard_snapshot_id: str
    catalog_count: int
    distinct_systems: int
    covered_pattern_ids: list[str]
    import_included_count: int
    manual_count: int
    excluded_import_count: int
    design_warning_rows: int
    approved_justifications: int
    artifacts: SyntheticArtifactManifest


def _slugify(value: str) -> str:
    return (
        value.lower()
        .replace(" ", "-")
        .replace("/", "-")
        .replace("(", "")
        .replace(")", "")
        .replace(".", "")
    )


def _build_system_catalog() -> list[SystemProfile]:
    systems: list[SystemProfile] = []
    for domain in DOMAINS:
        for capability in CAPABILITY_PROFILES:
            systems.append(
                SystemProfile(
                    name=f"{domain} {capability.name}",
                    domain=domain,
                    technology=capability.technology,
                    owner=f"{domain} {capability.owner_suffix} Team",
                )
            )
    return systems


def _pattern_name(pattern_id: str) -> str:
    return {
        "#01": "Request-Reply",
        "#02": "Event-Driven",
        "#03": "API Facade",
        "#04": "Saga Compensation",
        "#05": "Change Data Capture",
        "#06": "Strangler Runtime",
        "#07": "Scatter-Gather",
        "#08": "Circuit Breaker",
        "#09": "Transactional Outbox",
        "#10": "CQRS Event Sourcing",
        "#11": "Backend for Frontend",
        "#12": "Data Mesh",
        "#13": "Zero-Trust Integration",
        "#14": "AsyncAPI Event Catalog",
        "#15": "AI-Augmented Integration",
        "#16": "Integration Mesh",
        "#17": "Webhook Fanout",
    }[pattern_id]


def _pattern_sequence(total: int, seed: int) -> list[str]:
    pattern_ids: list[str] = []
    for pattern_id, weight in PATTERN_WEIGHTS.items():
        pattern_ids.extend([pattern_id] * weight)
    if len(pattern_ids) != total:
        raise ValueError(f"Expected weighted pattern sequence of {total}, found {len(pattern_ids)}")
    random.Random(seed).shuffle(pattern_ids)
    return pattern_ids


def _payload_value(
    pattern: PatternPlan,
    rng: random.Random,
    index: int,
) -> float:
    low, high = pattern.payload_range_kb
    value = round(rng.uniform(low, high), 1)
    if "OIC Gen3" in pattern.route_core_tools and index % 61 == 0:
        return 12288.0
    if "OCI Queue" in pattern.route_core_tools and index % 37 == 0:
        return 320.0
    if "OCI Streaming" in pattern.route_core_tools and index % 53 == 0:
        return 1536.0
    if "OCI Functions" in pattern.route_core_tools and index % 71 == 0:
        return 7168.0
    return value


def _response_size(payload_kb: float, ratio: float) -> float:
    return round(max(4.0, payload_kb * ratio), 1)


def _is_real_time(pattern: PatternPlan, frequency: str) -> bool:
    return pattern.type_value in {"REST", "Event", "Webhook", "SOAP"} or frequency == "Tiempo Real"


def _calendarization(pattern: PatternPlan, frequency: str, index: int) -> str:
    if pattern.type_value in {"REST", "Event", "Webhook"}:
        return "24x7"
    if "Mesh" in pattern.base_value or frequency == "Tiempo Real":
        return "24x7"
    return CALENDARIZATION_VALUES[index % len(CALENDARIZATION_VALUES)]


def _pattern_rationale(
    pattern_id: str,
    source: SystemProfile,
    destination: SystemProfile,
    core_tools: tuple[str, ...],
) -> str:
    return (
        f"{_pattern_name(pattern_id)} is used because {source.name} and {destination.name} "
        f"need a governed flow through {', '.join(core_tools)} with traceable enterprise ownership."
    )


def _comments(pattern_id: str, capture_mode: Literal["import", "manual"], index: int) -> str:
    return (
        f"Synthetic {capture_mode} row {index:03d} for {_pattern_name(pattern_id)} coverage, "
        "canvas validation, and downstream artifact generation."
    )


def _retry_policy(pattern: PatternPlan) -> str:
    if pattern.type_value in {"Event", "Webhook"}:
        return "Exponential backoff 5x with dead-letter handling."
    if "OCI Queue" in pattern.route_core_tools:
        return "Three retries plus operator review on final failure."
    return "Exponential backoff 3x within 10 minutes."


def _uncertainty(pattern: PatternPlan, index: int) -> str | None:
    if pattern.uncertainty_ratio and index % pattern.uncertainty_ratio == 0:
        return "Source payload estimate is modeled from historical batch evidence."
    return None


def _business_process(source: SystemProfile, destination: SystemProfile, index: int) -> str:
    base = BUSINESS_PROCESSES[index % len(BUSINESS_PROCESSES)]
    return f"{base} — {source.domain} to {destination.domain}"


def _interface_name(
    source: SystemProfile,
    destination: SystemProfile,
    pattern: PatternPlan,
    index: int,
) -> str:
    return f"{source.name} to {destination.name} {pattern.base_value} Flow {index:03d}"


def _destination_technology_2(index: int) -> str | None:
    return DESTINATION_TECHNOLOGIES[index % len(DESTINATION_TECHNOLOGIES)]


def build_canvas_state(core_tools: tuple[str, ...], overlay_keys: tuple[str, ...], payload_kb: float) -> str:
    route_nodes = [*overlay_keys[:1], *core_tools[:3]]
    nodes: list[dict[str, object]] = []
    edges: list[dict[str, object]] = []
    previous_id = "source-system"
    for index, tool_key in enumerate(route_nodes, start=1):
        instance_id = f"n{index}"
        label = SHORT_TOOL_LABELS.get(tool_key, tool_key)
        payload_note = f"{int(round(payload_kb / 1024))}MB" if index == 1 and payload_kb >= 1024 else ""
        nodes.append(
            {
                "instanceId": instance_id,
                "toolKey": tool_key,
                "label": label,
                "payloadNote": payload_note,
                "x": 200 + (index - 1) * 180,
                "y": 120 if index % 2 else 260,
            }
        )
        edges.append(
            {
                "edgeId": f"e{index}",
                "sourceInstanceId": previous_id,
                "targetInstanceId": instance_id,
                "label": "",
            }
        )
        previous_id = instance_id
    edges.append(
        {
            "edgeId": f"e{len(route_nodes) + 1}",
            "sourceInstanceId": previous_id,
            "targetInstanceId": "destination-system",
            "label": "",
        }
    )
    payload = {
        "v": 3,
        "nodes": nodes,
        "edges": edges,
        "coreToolKeys": sorted(set(core_tools)),
        "overlayKeys": sorted(set(overlay_keys)),
    }
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":"))


def generate_synthetic_dataset(spec: SyntheticProjectSpec) -> SyntheticDataset:
    rng = random.Random(spec.seed)
    systems = _build_system_catalog()
    excluded_positions = set(range(6, spec.import_included_count + spec.excluded_import_count + 1, 12))
    while len(excluded_positions) < spec.excluded_import_count:
        excluded_positions.add(len(excluded_positions) * 7 + 3)
    excluded_positions = set(sorted(excluded_positions)[: spec.excluded_import_count])

    pattern_ids = _pattern_sequence(spec.minimum_catalog_count, spec.seed)
    import_rows: list[SyntheticIntegrationSpec] = []
    manual_rows: list[SyntheticIntegrationSpec] = []
    excluded_rows: list[list[object]] = []

    import_position_limit = spec.import_included_count + spec.excluded_import_count
    pattern_cursor = 0

    for position in range(1, import_position_limit + 1):
        if position in excluded_positions:
            tbq_value = "N" if len(excluded_rows) % 2 == 0 else "Y"
            status_value = "Duplicado 2" if tbq_value == "Y" else "TBD"
            source = systems[(position - 1) % len(systems)]
            destination = systems[(position * 7 + 9) % len(systems)]
            excluded_rows.append(
                [
                    position,
                    f"INT-SYN-{position:04d}",
                    f"{source.domain} Integration Lead",
                    BRANDS[position % len(BRANDS)],
                    _business_process(source, destination, position),
                    f"{source.name} to {destination.name} deferred workbook row",
                    "Synthetic excluded workbook row kept to validate inclusion/exclusion lineage.",
                    status_value,
                    "Pendiente",
                    "Sí",
                    "Bajo",
                    "Cada 12 horas",
                    "Scheduled",
                    "Deferred Flow",
                    status_value,
                    "No",
                    "Scheduled",
                    12.0,
                    64.0,
                    "No",
                    None,
                    source.name,
                    source.technology,
                    f"/synthetic/excluded/{position:04d}",
                    source.owner,
                    destination.name,
                    destination.technology,
                    None,
                    destination.owner,
                    "Business hours",
                    tbq_value,
                    "#01",
                    "Excluded workbook evidence row.",
                    "Excluded for synthetic import-path validation.",
                    "No retry because row is excluded.",
                    "OIC Gen3",
                    build_canvas_state(("OIC Gen3",), ("OCI API Gateway",), 64.0),
                    "Excluded synthetic workbook row.",
                ]
            )
            continue

        pattern_id = pattern_ids[pattern_cursor]
        pattern_cursor += 1
        pattern = PATTERN_PLANS[pattern_id]
        source = systems[(position - 1) % len(systems)]
        destination = systems[(position * 11 + pattern_cursor * 3 + 7) % len(systems)]
        if destination.name == source.name:
            destination = systems[(systems.index(destination) + 1) % len(systems)]
        frequency = pattern.frequency_options[(position + pattern_cursor) % len(pattern.frequency_options)]
        payload_kb = _payload_value(pattern, rng, position)
        fan_out_targets = None
        if pattern.fan_out_targets:
            fan_out_targets = pattern.fan_out_targets[(position + pattern_cursor) % len(pattern.fan_out_targets)]
        spec_row = SyntheticIntegrationSpec(
            sequence_number=position,
            capture_mode="import",
            interface_id=f"INT-SYN-{position:04d}",
            owner=f"{source.domain} Architecture",
            brand=BRANDS[position % len(BRANDS)],
            business_process=_business_process(source, destination, position),
            interface_name=_interface_name(source, destination, pattern, position),
            description=(
                f"Synthetic import integration from {source.name} to {destination.name} "
                f"covering {_pattern_name(pattern_id)} with governed routing metadata."
            ),
            status=STATUS_VALUES[position % len(STATUS_VALUES)],
            mapping_status=MAPPING_STATUS_VALUES[position % len(MAPPING_STATUS_VALUES)],
            initial_scope="Sí",
            complexity=pattern.complexity,
            frequency=frequency,
            type_value=pattern.type_value,
            base_value=pattern.base_value,
            interface_status=STATUS_VALUES[(position + 1) % len(STATUS_VALUES)],
            is_real_time=_is_real_time(pattern, frequency),
            trigger_type=pattern.type_value,
            response_size_kb=_response_size(payload_kb, pattern.response_ratio),
            payload_per_execution_kb=payload_kb,
            is_fan_out=fan_out_targets is not None,
            fan_out_targets=fan_out_targets,
            source_system=source.name,
            source_technology=source.technology,
            source_api_reference=f"/synthetic/{_slugify(source.domain)}/{_slugify(source.name)}/{position:04d}",
            source_owner=source.owner,
            destination_system=destination.name,
            destination_technology_1=destination.technology,
            destination_technology_2=_destination_technology_2(position),
            destination_owner=destination.owner,
            calendarization=_calendarization(pattern, frequency, position),
            selected_pattern=pattern_id,
            pattern_rationale=_pattern_rationale(pattern_id, source, destination, pattern.route_core_tools),
            comments=_comments(pattern_id, "import", position),
            retry_policy=_retry_policy(pattern),
            core_tools=pattern.route_core_tools,
            overlay_keys=pattern.route_overlays,
            uncertainty=_uncertainty(pattern, position),
        )
        import_rows.append(spec_row)

    for offset in range(spec.manual_count):
        sequence_number = import_position_limit + offset + 1
        pattern_id = pattern_ids[pattern_cursor]
        pattern_cursor += 1
        pattern = PATTERN_PLANS[pattern_id]
        source = systems[(sequence_number - 1) % len(systems)]
        destination = systems[(sequence_number * 17 + offset * 5 + 11) % len(systems)]
        if destination.name == source.name:
            destination = systems[(systems.index(destination) + 2) % len(systems)]
        frequency = pattern.frequency_options[(sequence_number + offset) % len(pattern.frequency_options)]
        payload_kb = _payload_value(pattern, rng, sequence_number + offset)
        fan_out_targets = None
        if pattern.fan_out_targets:
            fan_out_targets = pattern.fan_out_targets[(sequence_number + offset) % len(pattern.fan_out_targets)]
        manual_rows.append(
            SyntheticIntegrationSpec(
                sequence_number=sequence_number,
                capture_mode="manual",
                interface_id=f"INT-SYN-{sequence_number:04d}",
                owner=f"{destination.domain} Architecture",
                brand=BRANDS[sequence_number % len(BRANDS)],
                business_process=_business_process(source, destination, sequence_number),
                interface_name=_interface_name(source, destination, pattern, sequence_number),
                description=(
                    f"Synthetic manual integration from {source.name} to {destination.name} "
                    f"covering {_pattern_name(pattern_id)} via governed capture."
                ),
                status=STATUS_VALUES[sequence_number % len(STATUS_VALUES)],
                mapping_status=MAPPING_STATUS_VALUES[sequence_number % len(MAPPING_STATUS_VALUES)],
                initial_scope="Sí",
                complexity=pattern.complexity,
                frequency=frequency,
                type_value=pattern.type_value,
                base_value=pattern.base_value,
                interface_status=STATUS_VALUES[(sequence_number + 1) % len(STATUS_VALUES)],
                is_real_time=_is_real_time(pattern, frequency),
                trigger_type=pattern.type_value,
                response_size_kb=_response_size(payload_kb, pattern.response_ratio),
                payload_per_execution_kb=payload_kb,
                is_fan_out=fan_out_targets is not None,
                fan_out_targets=fan_out_targets,
                source_system=source.name,
                source_technology=source.technology,
                source_api_reference=f"/synthetic/manual/{_slugify(source.domain)}/{sequence_number:04d}",
                source_owner=source.owner,
                destination_system=destination.name,
                destination_technology_1=destination.technology,
                destination_technology_2=_destination_technology_2(sequence_number),
                destination_owner=destination.owner,
                calendarization=_calendarization(pattern, frequency, sequence_number),
                selected_pattern=pattern_id,
                pattern_rationale=_pattern_rationale(pattern_id, source, destination, pattern.route_core_tools),
                comments=_comments(pattern_id, "manual", sequence_number),
                retry_policy=_retry_policy(pattern),
                core_tools=pattern.route_core_tools,
                overlay_keys=pattern.route_overlays,
                uncertainty=_uncertainty(pattern, sequence_number),
            )
        )

    return SyntheticDataset(import_rows=import_rows, manual_rows=manual_rows, excluded_rows=excluded_rows)


def validate_synthetic_dataset(dataset: SyntheticDataset) -> SyntheticDatasetValidation:
    systems = {
        system_name
        for row in dataset.included_rows
        for system_name in (row.source_system, row.destination_system)
        if system_name
    }
    covered_pattern_ids = sorted({row.selected_pattern for row in dataset.included_rows})
    max_canvas_state_length = max((len(row.canvas_state) for row in dataset.included_rows), default=0)
    return SyntheticDatasetValidation(
        catalog_count=len(dataset.included_rows),
        distinct_systems=len(systems),
        covered_pattern_ids=covered_pattern_ids,
        max_canvas_state_length=max_canvas_state_length,
    )


def _ensure_report_dirs() -> None:
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)


def _workbook_path(project_name: str, seed: int) -> Path:
    return UPLOAD_ROOT / f"{_slugify(project_name)}-{seed}.xlsx"


def write_synthetic_workbook(dataset: SyntheticDataset, destination: Path) -> Path:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = SOURCE_SHEET_NAME
    for _ in range(4):
        sheet.append([])
    sheet.append(IMPORT_HEADER_ROW)

    import_iter = iter(dataset.import_rows)
    excluded_map = {
        cast(int, row[0]): row for row in dataset.excluded_rows
    }
    max_position = len(dataset.import_rows) + len(dataset.excluded_rows)
    for position in range(1, max_position + 1):
        excluded = excluded_map.get(position)
        if excluded is not None:
            sheet.append(excluded)
            continue
        row = next(import_iter)
        sheet.append(row.to_workbook_row())

    destination.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(destination)
    return destination


async def _load_project_rows(project_id: str, db: AsyncSession) -> list[CatalogIntegration]:
    rows = await db.scalars(
        select(CatalogIntegration)
        .where(CatalogIntegration.project_id == project_id)
        .order_by(CatalogIntegration.seq_number, CatalogIntegration.created_at)
    )
    return list(rows.all())


async def _load_pattern_map(db: AsyncSession) -> dict[str, PatternDefinition]:
    patterns = await db.scalars(
        select(PatternDefinition).where(PatternDefinition.is_active.is_(True))
    )
    return {pattern.pattern_id: pattern for pattern in patterns.all()}


async def _apply_import_follow_up_patches(
    project_id: str,
    imported_rows: list[CatalogIntegration],
    dataset: SyntheticDataset,
    db: AsyncSession,
) -> None:
    patch_targets = imported_rows[:18]
    spec_by_id = {spec.interface_id: spec for spec in dataset.import_rows}
    for row in patch_targets:
        spec = spec_by_id.get(cast(str, row.interface_id))
        if spec is None:
            continue
        patch = CatalogIntegrationPatch(
            comments=f"{spec.comments} Reviewed by synthetic architect patch.",
            retry_policy=spec.retry_policy,
            additional_tools_overlays=spec.canvas_state,
        )
        await catalog_service.update_integration(project_id, row.id, patch, SYNTHETIC_ACTOR_ID, db)


async def _create_manual_rows(
    project_id: str,
    dataset: SyntheticDataset,
    db: AsyncSession,
) -> list[CatalogIntegration]:
    created_rows: list[CatalogIntegration] = []
    for spec in dataset.manual_rows:
        response = await catalog_service.manual_create_integration(
            project_id=project_id,
            data=spec.to_manual_request(),
            actor_id=SYNTHETIC_ACTOR_ID,
            db=db,
        )
        await catalog_service.update_integration(
            project_id=project_id,
            integration_id=response.id,
            patch=spec.to_follow_up_patch(),
            actor_id=SYNTHETIC_ACTOR_ID,
            db=db,
        )
        row = await db.scalar(
            select(CatalogIntegration).where(
                CatalogIntegration.project_id == project_id,
                CatalogIntegration.id == response.id,
            )
        )
        if row is not None:
            created_rows.append(row)
    return created_rows


async def _approve_all_justifications(project_id: str, db: AsyncSession) -> int:
    rows = await _load_project_rows(project_id, db)
    count = 0
    for row in rows:
        await justification_service.approve_justification(project_id, row.id, SYNTHETIC_ACTOR_ID, db)
        count += 1
    return count


async def _export_job_payload(
    job: ExportJobResponse,
) -> dict[str, str]:
    file_path, _ = export_service.get_export_file(job.project_id, job.job_id)
    return {
        "job_id": job.job_id,
        "filename": job.filename,
        "download_url": job.download_url,
        "file_path": str(file_path),
    }


async def create_synthetic_enterprise_project(
    db: AsyncSession,
    spec: SyntheticProjectSpec = DEFAULT_SYNTHETIC_SPEC,
) -> SyntheticGenerationResult:
    """Seed one deterministic enterprise-scale synthetic project through real services."""

    dataset = generate_synthetic_dataset(spec)
    validation = validate_synthetic_dataset(dataset)
    if validation.catalog_count < spec.minimum_catalog_count:
        raise ValueError("Synthetic dataset does not meet minimum catalog size.")
    if validation.distinct_systems < spec.minimum_distinct_systems:
        raise ValueError("Synthetic dataset does not meet minimum distinct-system coverage.")
    if len(validation.covered_pattern_ids) != 17:
        raise ValueError("Synthetic dataset does not cover all 17 patterns.")
    if validation.max_canvas_state_length >= 1000:
        raise ValueError("Synthetic dataset exceeded the current canvas column budget.")

    pattern_map = await _load_pattern_map(db)
    missing_patterns = sorted(set(validation.covered_pattern_ids) - set(pattern_map))
    if missing_patterns:
        raise ValueError(f"Reference seed is incomplete. Missing patterns: {', '.join(missing_patterns)}")

    _ensure_report_dirs()
    workbook_path = _workbook_path(spec.project_name, spec.seed)
    write_synthetic_workbook(dataset, workbook_path)

    project = Project(
        name=f"{spec.project_name} {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')}",
        description=spec.description,
        owner_id=spec.owner_id,
        status=ProjectStatus.ACTIVE,
        project_metadata=cast(
            dict[str, object],
            sanitize_for_json(
                {
                    "synthetic": True,
                    "seed_type": "synthetic-enterprise",
                    "seed_actor": SYNTHETIC_ACTOR_ID,
                    "generator": "enterprise-v1",
                    "seed": spec.seed,
                    "import_included_count": spec.import_included_count,
                    "manual_count": spec.manual_count,
                    "excluded_import_count": spec.excluded_import_count,
                }
            ),
        ),
    )
    db.add(project)
    await db.flush()
    await audit_service.emit(
        event_type="synthetic_project_created",
        entity_type="project",
        entity_id=project.id,
        actor_id=SYNTHETIC_ACTOR_ID,
        old_value=None,
        new_value={"project_name": project.name, "seed": spec.seed},
        project_id=project.id,
        db=db,
    )

    import_batch = await import_service.create_import_batch(project.id, workbook_path.name, db)
    await import_service.process_import(import_batch.id, str(workbook_path), db)

    imported_rows = await _load_project_rows(project.id, db)
    await _apply_import_follow_up_patches(project.id, imported_rows, dataset, db)

    imported_snapshot = await recalc_service.recalculate_project(project.id, SYNTHETIC_ACTOR_ID, db)
    imported_dashboard = await dashboard_service.get_snapshot(project.id, imported_snapshot.id, db)

    await _create_manual_rows(project.id, dataset, db)
    final_snapshot = await recalc_service.recalculate_project(project.id, SYNTHETIC_ACTOR_ID, db)
    final_dashboard = await dashboard_service.get_snapshot(project.id, final_snapshot.id, db)

    approved_justifications = await _approve_all_justifications(project.id, db)

    final_rows = await _load_project_rows(project.id, db)
    import_batch.loaded_count = len(final_rows)
    import_batch.source_row_count = len(final_rows)
    await db.flush()
    distinct_systems = len(
        {
            system_name
            for row in final_rows
            for system_name in (row.source_system, row.destination_system)
            if system_name
        }
    )
    covered_pattern_ids = sorted({row.selected_pattern for row in final_rows if row.selected_pattern})
    design_warning_rows = sum(
        1
        for row_metrics in final_snapshot.row_results.values()
        if cast(list[object], row_metrics.get("design_constraint_warnings", []))
    )

    await audit_service.emit(
        event_type="synthetic_project_seed_complete",
        entity_type="project",
        entity_id=project.id,
        actor_id=SYNTHETIC_ACTOR_ID,
        old_value=None,
        new_value={
            "catalog_count": len(final_rows),
            "distinct_systems": distinct_systems,
            "covered_pattern_ids": covered_pattern_ids,
        },
        project_id=project.id,
        db=db,
    )

    xlsx_job = await export_service.create_xlsx_export(project.id, final_snapshot.id, db)
    json_job = await export_service.create_json_export(project.id, final_snapshot.id, db)
    pdf_job = await export_service.create_pdf_export(project.id, final_snapshot.id, db)

    report_payload = cast(
        dict[str, object],
        sanitize_for_json(
            {
                "project_id": project.id,
                "project_name": project.name,
                "seed": spec.seed,
                "catalog_count": len(final_rows),
                "distinct_systems": distinct_systems,
                "covered_pattern_ids": covered_pattern_ids,
                "import_batch_id": import_batch.id,
                "import_included_count": len(dataset.import_rows),
                "manual_count": len(dataset.manual_rows),
                "excluded_import_count": len(dataset.excluded_rows),
                "design_warning_rows": design_warning_rows,
                "approved_justifications": approved_justifications,
                "snapshot_ids": {
                    "imported": imported_snapshot.id,
                    "final": final_snapshot.id,
                },
                "dashboard_snapshot_ids": {
                    "imported": imported_dashboard.snapshot_id,
                    "final": final_dashboard.snapshot_id,
                },
                "artifacts": {
                    "workbook_path": str(workbook_path),
                    "xlsx_export": await _export_job_payload(xlsx_job),
                    "json_export": await _export_job_payload(json_job),
                    "pdf_export": await _export_job_payload(pdf_job),
                },
                "smoke_routes": {
                    "project": f"/api/v1/projects/{project.id}",
                    "catalog": f"/api/v1/catalog/{project.id}",
                    "graph": f"/api/v1/catalog/{project.id}/graph",
                    "dashboard_snapshots": f"/api/v1/dashboard/{project.id}/snapshots",
                    "volumetry_snapshots": f"/api/v1/volumetry/{project.id}/snapshots",
                    "audit": f"/api/v1/audit/{project.id}",
                },
            }
        ),
    )

    report_json_path = REPORT_ROOT / f"synthetic-enterprise-{project.id}.json"
    report_markdown_path = REPORT_ROOT / f"synthetic-enterprise-{project.id}.md"
    report_json_path.write_text(json.dumps(report_payload, indent=2), encoding="utf-8")
    report_markdown_path.write_text(_report_markdown(report_payload), encoding="utf-8")

    return SyntheticGenerationResult(
        project_id=project.id,
        project_name=project.name,
        import_batch_id=import_batch.id,
        imported_snapshot_id=imported_snapshot.id,
        final_snapshot_id=final_snapshot.id,
        imported_dashboard_snapshot_id=imported_dashboard.snapshot_id,
        final_dashboard_snapshot_id=final_dashboard.snapshot_id,
        catalog_count=len(final_rows),
        distinct_systems=distinct_systems,
        covered_pattern_ids=covered_pattern_ids,
        import_included_count=len(dataset.import_rows),
        manual_count=len(dataset.manual_rows),
        excluded_import_count=len(dataset.excluded_rows),
        design_warning_rows=design_warning_rows,
        approved_justifications=approved_justifications,
        artifacts=SyntheticArtifactManifest(
            workbook_path=str(workbook_path),
            report_json_path=str(report_json_path),
            report_markdown_path=str(report_markdown_path),
            export_jobs={
                "xlsx": await _export_job_payload(xlsx_job),
                "json": await _export_job_payload(json_job),
                "pdf": await _export_job_payload(pdf_job),
            },
        ),
    )


def _report_markdown(payload: dict[str, object]) -> str:
    artifacts = cast(dict[str, object], payload["artifacts"])
    smoke_routes = cast(dict[str, str], payload["smoke_routes"])
    lines = [
        "# Synthetic Enterprise Project Report",
        "",
        f"- Project ID: `{payload['project_id']}`",
        f"- Project Name: {payload['project_name']}",
        f"- Seed: `{payload['seed']}`",
        f"- Catalog Count: `{payload['catalog_count']}`",
        f"- Distinct Systems: `{payload['distinct_systems']}`",
        f"- Covered Patterns: {', '.join(cast(list[str], payload['covered_pattern_ids']))}",
        f"- Import Batch ID: `{payload['import_batch_id']}`",
        f"- Import Included Rows: `{payload['import_included_count']}`",
        f"- Manual Rows: `{payload['manual_count']}`",
        f"- Excluded Import Rows: `{payload['excluded_import_count']}`",
        f"- Design Warning Rows: `{payload['design_warning_rows']}`",
        f"- Approved Justifications: `{payload['approved_justifications']}`",
        "",
        "## Artifacts",
        "",
        f"- Workbook: `{artifacts['workbook_path']}`",
        f"- XLSX Export: `{cast(dict[str, str], artifacts['xlsx_export'])['file_path']}`",
        f"- JSON Export: `{cast(dict[str, str], artifacts['json_export'])['file_path']}`",
        f"- PDF Export: `{cast(dict[str, str], artifacts['pdf_export'])['file_path']}`",
        "",
        "## Smoke Routes",
        "",
    ]
    lines.extend(f"- `{label}`: `{path}`" for label, path in smoke_routes.items())
    lines.append("")
    return "\n".join(lines)
