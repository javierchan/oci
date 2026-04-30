"""Deterministic synthetic enterprise project generation helpers.

This module builds a governed, enterprise-scale synthetic dataset and seeds it
through the same service-layer flows used by the real product. It is designed to
be reusable from the current script-based entrypoint and from a future admin
router/worker slice without moving orchestration into the calc engine.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from fastapi import HTTPException
import json
from pathlib import Path
import random
from typing import Literal, cast

from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import CatalogIntegration, PatternDefinition, Project, SyntheticGenerationJob
from app.models.project import ProjectStatus
from app.schemas.catalog import CatalogIntegrationPatch, ManualIntegrationCreate
from app.schemas.export import ExportJobResponse
from app.schemas.synthetic import (
    SyntheticArtifactExportJobResponse,
    SyntheticArtifactManifestResponse,
    SyntheticGenerationJobCreateRequest,
    SyntheticGenerationJobListResponse,
    SyntheticGenerationJobResponse,
    SyntheticGenerationPresetListResponse,
    SyntheticGenerationPresetResponse,
)
from app.services import (
    audit_service,
    catalog_service,
    dashboard_service,
    export_service,
    import_service,
    justification_service,
    project_service,
    recalc_service,
)
from app.services.serializers import sanitize_for_json

API_ROOT = Path(__file__).resolve().parents[2]
REPORT_ROOT = API_ROOT / "generated-reports"
UPLOAD_ROOT = API_ROOT / "uploads" / "synthetic"
EXPORT_ROOT = API_ROOT / "uploads" / "exports"
SOURCE_SHEET_NAME = "Catálogo de Integraciones"
SYNTHETIC_ACTOR_ID = "synthetic-generator"
DEFAULT_PRESET_CODE = "enterprise-default"
SMOKE_PRESET_CODE = "ephemeral-smoke"
RETAINED_SMOKE_PRESET_CODE = "retained-smoke"
MINIMUM_SUPPORTED_CATALOG_SIZE = 480
MINIMUM_SUPPORTED_DISTINCT_SYSTEMS = 70
SYNTHETIC_JOBS_TABLE_NAME = "synthetic_generation_jobs"
SYNTHETIC_JOBS_REQUIRED_MIGRATION = "20260428_0007"

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
SUPPORTED_PATTERN_COUNT = len(PATTERN_WEIGHTS)
SMOKE_MINIMUM_SUPPORTED_CATALOG_SIZE = 18
SMOKE_MINIMUM_SUPPORTED_DISTINCT_SYSTEMS = 12


@dataclass(frozen=True)
class SyntheticProjectSpec:
    project_name: str = "Synthetic Enterprise Reference Project"
    owner_id: str = "synthetic-admin"
    description: str = (
        "Deterministic enterprise-scale synthetic OCI integration portfolio used "
        "to validate catalog, graph, volumetry, dashboard, justifications, audit, "
        "and export flows end to end."
    )
    seed_type: str = "synthetic-enterprise"
    generator_version: str = "enterprise-v1"
    seed: int = 20260416
    import_included_count: int = 420
    manual_count: int = 60
    excluded_import_count: int = 36
    minimum_distinct_systems: int = 70
    minimum_catalog_count: int = 480
    include_justifications: bool = True
    include_exports: bool = True
    include_design_warnings: bool = True


DEFAULT_SYNTHETIC_SPEC = SyntheticProjectSpec()
SMOKE_SYNTHETIC_SPEC = SyntheticProjectSpec(
    project_name="Synthetic Smoke Validation Project",
    description=(
        "Ephemeral synthetic smoke project used to validate the real admin "
        "synthetic job flow without leaving durable artifacts behind."
    ),
    seed_type="synthetic-smoke",
    generator_version="smoke-v1",
    seed=20260428,
    import_included_count=12,
    manual_count=6,
    excluded_import_count=2,
    minimum_distinct_systems=SMOKE_MINIMUM_SUPPORTED_DISTINCT_SYSTEMS,
    minimum_catalog_count=SMOKE_MINIMUM_SUPPORTED_CATALOG_SIZE,
    include_justifications=False,
    include_exports=False,
    include_design_warnings=False,
)
RETAINED_SMOKE_SYNTHETIC_SPEC = replace(
    SMOKE_SYNTHETIC_SPEC,
    project_name="Retained Smoke Validation Project",
    description=(
        "Retained synthetic smoke project used to validate the real admin "
        "synthetic cleanup flow before operators explicitly remove it."
    ),
    seed_type="synthetic-smoke-retained",
    generator_version="smoke-retained-v1",
)


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
    weighted_pattern_ids: list[str] = []
    for pattern_id, weight in PATTERN_WEIGHTS.items():
        weighted_pattern_ids.extend([pattern_id] * weight)

    if total == len(weighted_pattern_ids):
        pattern_ids = list(weighted_pattern_ids)
        random.Random(seed).shuffle(pattern_ids)
        return pattern_ids

    if total < SUPPORTED_PATTERN_COUNT:
        raise ValueError(
            f"Synthetic dataset needs at least {SUPPORTED_PATTERN_COUNT} included rows for full pattern coverage."
        )

    rng = random.Random(seed)
    extra_needed = total - SUPPORTED_PATTERN_COUNT
    extra_pattern_ids: list[str] = []
    while len(extra_pattern_ids) < extra_needed:
        batch = list(weighted_pattern_ids)
        rng.shuffle(batch)
        extra_pattern_ids.extend(batch)

    pattern_ids = [*PATTERN_WEIGHTS.keys(), *extra_pattern_ids[:extra_needed]]
    rng.shuffle(pattern_ids)
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
    route_start_x = 340
    route_gap_x = 260
    route_y = 220
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
                "x": route_start_x + (index - 1) * route_gap_x,
                "y": route_y,
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
        "job_file_path": str(export_service.JOBS_DIR / f"{job.job_id}.json"),
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
    if len(validation.covered_pattern_ids) != SUPPORTED_PATTERN_COUNT:
        raise ValueError(f"Synthetic dataset does not cover all {SUPPORTED_PATTERN_COUNT} patterns.")
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
        name=spec.project_name,
        description=spec.description,
        owner_id=spec.owner_id,
        status=ProjectStatus.ACTIVE,
        project_metadata=cast(
            dict[str, object],
            sanitize_for_json(
                {
                    "synthetic": True,
                    "seed_type": spec.seed_type,
                    "seed_actor": SYNTHETIC_ACTOR_ID,
                    "generator": spec.generator_version,
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

    approved_justifications = 0
    if spec.include_justifications:
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
    design_warning_rows = 0
    if spec.include_design_warnings:
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

    export_jobs_payload: dict[str, dict[str, str]] = {}
    if spec.include_exports:
        xlsx_job = await export_service.create_xlsx_export(project.id, final_snapshot.id, db)
        json_job = await export_service.create_json_export(project.id, final_snapshot.id, db)
        pdf_job = await export_service.create_pdf_export(project.id, final_snapshot.id, db)
        export_jobs_payload = {
            "xlsx": await _export_job_payload(xlsx_job),
            "json": await _export_job_payload(json_job),
            "pdf": await _export_job_payload(pdf_job),
        }

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
                    "xlsx_export": export_jobs_payload.get("xlsx"),
                    "json_export": export_jobs_payload.get("json"),
                    "pdf_export": export_jobs_payload.get("pdf"),
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
            export_jobs=export_jobs_payload,
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
    ]
    if artifacts.get("xlsx_export"):
        lines.append(f"- XLSX Export: `{cast(dict[str, str], artifacts['xlsx_export'])['file_path']}`")
    if artifacts.get("json_export"):
        lines.append(f"- JSON Export: `{cast(dict[str, str], artifacts['json_export'])['file_path']}`")
    if artifacts.get("pdf_export"):
        lines.append(f"- PDF Export: `{cast(dict[str, str], artifacts['pdf_export'])['file_path']}`")
    lines.extend(
        [
            "",
            "## Smoke Routes",
            "",
        ]
    )
    lines.extend(f"- `{label}`: `{path}`" for label, path in smoke_routes.items())
    lines.append("")
    return "\n".join(lines)


def _enterprise_preset_response() -> SyntheticGenerationPresetResponse:
    spec = DEFAULT_SYNTHETIC_SPEC
    return SyntheticGenerationPresetResponse(
        code=DEFAULT_PRESET_CODE,
        label="Enterprise Reference",
        description=(
            "Deterministic enterprise-scale governed dataset that exercises import, "
            "manual capture, snapshots, justifications, audit, graph, and exports."
        ),
        project_name=spec.project_name,
        seed_value=spec.seed,
        target_catalog_size=spec.minimum_catalog_count,
        min_distinct_systems=spec.minimum_distinct_systems,
        import_target=spec.import_included_count,
        manual_target=spec.manual_count,
        excluded_import_target=spec.excluded_import_count,
        include_justifications=spec.include_justifications,
        include_exports=spec.include_exports,
        include_design_warnings=spec.include_design_warnings,
        cleanup_policy="manual",
    )


def _smoke_preset_response() -> SyntheticGenerationPresetResponse:
    spec = SMOKE_SYNTHETIC_SPEC
    return SyntheticGenerationPresetResponse(
        code=SMOKE_PRESET_CODE,
        label="Ephemeral Smoke Validation",
        description=(
            "Small synthetic smoke run that exercises the real import, manual capture, "
            "snapshot, worker, and cleanup flow, then automatically removes its project and artifacts."
        ),
        project_name=spec.project_name,
        seed_value=spec.seed,
        target_catalog_size=spec.minimum_catalog_count,
        min_distinct_systems=spec.minimum_distinct_systems,
        import_target=spec.import_included_count,
        manual_target=spec.manual_count,
        excluded_import_target=spec.excluded_import_count,
        include_justifications=spec.include_justifications,
        include_exports=spec.include_exports,
        include_design_warnings=spec.include_design_warnings,
        cleanup_policy="ephemeral_auto_cleanup",
    )


def _retained_smoke_preset_response() -> SyntheticGenerationPresetResponse:
    spec = RETAINED_SMOKE_SYNTHETIC_SPEC
    return SyntheticGenerationPresetResponse(
        code=RETAINED_SMOKE_PRESET_CODE,
        label="Retained Smoke Validation",
        description=(
            "Small retained smoke run that exercises the real import, manual capture, "
            "snapshot, worker, and explicit cleanup flow without using the enterprise-scale preset."
        ),
        project_name=spec.project_name,
        seed_value=spec.seed,
        target_catalog_size=spec.minimum_catalog_count,
        min_distinct_systems=spec.minimum_distinct_systems,
        import_target=spec.import_included_count,
        manual_target=spec.manual_count,
        excluded_import_target=spec.excluded_import_count,
        include_justifications=spec.include_justifications,
        include_exports=spec.include_exports,
        include_design_warnings=spec.include_design_warnings,
        cleanup_policy="manual",
    )


def _preset_catalog() -> dict[str, SyntheticGenerationPresetResponse]:
    presets = (
        _enterprise_preset_response(),
        _smoke_preset_response(),
        _retained_smoke_preset_response(),
    )
    return {preset.code: preset for preset in presets}


def _preset_spec(preset_code: str) -> SyntheticProjectSpec:
    if preset_code == SMOKE_PRESET_CODE:
        return SMOKE_SYNTHETIC_SPEC
    if preset_code == RETAINED_SMOKE_PRESET_CODE:
        return RETAINED_SMOKE_SYNTHETIC_SPEC
    return DEFAULT_SYNTHETIC_SPEC


def list_synthetic_presets() -> SyntheticGenerationPresetListResponse:
    """Return the currently supported governed synthetic preset catalog."""

    return SyntheticGenerationPresetListResponse(presets=list(_preset_catalog().values()))


def _not_found(job_id: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={
            "detail": f"Synthetic generation job {job_id} not found.",
            "error_code": "SYNTHETIC_JOB_NOT_FOUND",
        },
    )


def _synthetic_schema_not_ready() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={
            "detail": (
                "Admin Synthetic Lab requires database migration "
                f"{SYNTHETIC_JOBS_REQUIRED_MIGRATION} before synthetic jobs can be queried or created."
            ),
            "error_code": "SYNTHETIC_SCHEMA_NOT_READY",
            "table": SYNTHETIC_JOBS_TABLE_NAME,
            "expected_migration": SYNTHETIC_JOBS_REQUIRED_MIGRATION,
            "recovery_hint": "Run 'alembic upgrade head' for the API service and retry.",
        },
    )


def is_synthetic_schema_not_ready_error(exc: ProgrammingError | OperationalError) -> bool:
    """Return true when the admin synthetic jobs table is missing from the DB schema."""

    combined_message = " ".join(
        part
        for part in (
            str(exc),
            str(getattr(exc, "orig", "")),
            str(getattr(getattr(exc, "orig", None), "args", "")),
        )
        if part
    ).lower()
    return SYNTHETIC_JOBS_TABLE_NAME in combined_message and (
        "does not exist" in combined_message or "no such table" in combined_message
    )


def raise_if_synthetic_schema_not_ready(exc: ProgrammingError | OperationalError) -> None:
    """Translate the known missing-table failure into a structured API response."""

    if is_synthetic_schema_not_ready_error(exc):
        raise _synthetic_schema_not_ready() from exc


def _serialize_artifact_manifest(
    manifest: dict[str, object] | None,
) -> SyntheticArtifactManifestResponse | None:
    if not manifest:
        return None

    export_jobs_raw = cast(dict[str, dict[str, object]], manifest.get("export_jobs", {}))
    return SyntheticArtifactManifestResponse(
        workbook_path=str(manifest.get("workbook_path", "")),
        report_json_path=str(manifest.get("report_json_path", "")),
        report_markdown_path=str(manifest.get("report_markdown_path", "")),
        export_jobs={
            key: SyntheticArtifactExportJobResponse(
                job_id=str(value["job_id"]),
                filename=str(value["filename"]),
                download_url=str(value["download_url"]),
                file_path=str(value["file_path"]),
                job_file_path=str(value["job_file_path"]) if value.get("job_file_path") else None,
            )
            for key, value in export_jobs_raw.items()
        },
    )


def serialize_synthetic_job(job: SyntheticGenerationJob) -> SyntheticGenerationJobResponse:
    """Convert a persisted synthetic-generation job into an API response."""

    return SyntheticGenerationJobResponse(
        id=job.id,
        requested_by=job.requested_by,
        status=job.status.value,
        preset_code=job.preset_code,
        input_payload=cast(dict[str, object], sanitize_for_json(job.input_payload)),
        normalized_payload=cast(dict[str, object], sanitize_for_json(job.normalized_payload)),
        project_id=job.project_id,
        project_name=job.project_name,
        seed_value=job.seed_value,
        catalog_target=job.catalog_target,
        manual_target=job.manual_target,
        import_target=job.import_target,
        excluded_import_target=job.excluded_import_target,
        result_summary=cast(dict[str, object] | None, sanitize_for_json(job.result_summary)),
        validation_results=cast(dict[str, object] | None, sanitize_for_json(job.validation_results)),
        artifact_manifest=_serialize_artifact_manifest(
            cast(dict[str, object] | None, sanitize_for_json(job.artifact_manifest))
        ),
        error_details=cast(dict[str, object] | None, sanitize_for_json(job.error_details)),
        started_at=job.started_at,
        finished_at=job.finished_at,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def should_auto_cleanup_payload(payload: dict[str, object] | None) -> bool:
    """Return true when the normalized payload requests ephemeral auto-cleanup."""

    if not payload:
        return False
    return str(payload.get("cleanup_policy", "manual")) == "ephemeral_auto_cleanup"


async def _load_job(job_id: str, db: AsyncSession) -> SyntheticGenerationJob:
    job = await db.get(SyntheticGenerationJob, job_id)
    if job is None:
        raise _not_found(job_id)
    return job


def _normalized_request_payload(body: SyntheticGenerationJobCreateRequest) -> dict[str, object]:
    presets = _preset_catalog()
    preset_code = body.preset_code.strip()
    preset = presets.get(preset_code)
    if preset is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Synthetic preset not found.", "error_code": "SYNTHETIC_PRESET_NOT_FOUND"},
        )

    target_catalog_size = body.target_catalog_size or preset.target_catalog_size
    import_target = body.import_target or preset.import_target
    manual_target = body.manual_target if body.manual_target is not None else preset.manual_target
    excluded_import_target = (
        body.excluded_import_target
        if body.excluded_import_target is not None
        else preset.excluded_import_target
    )
    min_distinct_systems = body.min_distinct_systems or preset.min_distinct_systems
    seed_value = body.seed_value or preset.seed_value
    project_name = (body.project_name or preset.project_name).strip()
    include_justifications = (
        preset.include_justifications if body.include_justifications is None else body.include_justifications
    )
    include_exports = preset.include_exports if body.include_exports is None else body.include_exports
    include_design_warnings = (
        preset.include_design_warnings if body.include_design_warnings is None else body.include_design_warnings
    )
    cleanup_policy = body.cleanup_policy or preset.cleanup_policy

    if import_target + manual_target != target_catalog_size:
        raise HTTPException(
            status_code=400,
            detail={
                "detail": "Import target plus manual target must equal the catalog target.",
                "error_code": "SYNTHETIC_TARGET_MISMATCH",
            },
        )
    if target_catalog_size < preset.target_catalog_size:
        raise HTTPException(
            status_code=400,
            detail={
                "detail": f"Catalog target is below the minimum supported size for preset {preset_code}.",
                "error_code": "SYNTHETIC_CATALOG_TARGET_TOO_SMALL",
            },
        )
    if min_distinct_systems < preset.min_distinct_systems:
        raise HTTPException(
            status_code=400,
            detail={
                "detail": f"Distinct-system target is below the supported governance minimum for preset {preset_code}.",
                "error_code": "SYNTHETIC_SYSTEM_TARGET_TOO_SMALL",
            },
        )
    if not project_name:
        raise HTTPException(
            status_code=400,
            detail={
                "detail": "Project name is required.",
                "error_code": "SYNTHETIC_PROJECT_NAME_REQUIRED",
            },
        )
    if cleanup_policy != preset.cleanup_policy:
        raise HTTPException(
            status_code=400,
            detail={
                "detail": f"Cleanup policy {cleanup_policy} is not supported for preset {preset_code}.",
                "error_code": "SYNTHETIC_CLEANUP_POLICY_INVALID",
            },
        )

    return cast(
        dict[str, object],
        sanitize_for_json(
            {
                "preset_code": preset_code,
                "project_name": project_name,
                "target_catalog_size": target_catalog_size,
                "min_distinct_systems": min_distinct_systems,
                "import_target": import_target,
                "manual_target": manual_target,
                "excluded_import_target": excluded_import_target,
                "include_justifications": include_justifications,
                "include_exports": include_exports,
                "include_design_warnings": include_design_warnings,
                "cleanup_policy": cleanup_policy,
                "seed_value": seed_value,
            }
        ),
    )


def _payload_int(payload: dict[str, object], key: str) -> int:
    value = payload[key]
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float, str)):
        return int(value)
    raise TypeError(f"Expected numeric synthetic payload value for {key}.")


def _spec_from_payload(payload: dict[str, object]) -> SyntheticProjectSpec:
    template = _preset_spec(str(payload["preset_code"]))
    return replace(
        template,
        project_name=str(payload["project_name"]),
        seed=_payload_int(payload, "seed_value"),
        import_included_count=_payload_int(payload, "import_target"),
        manual_count=_payload_int(payload, "manual_target"),
        excluded_import_count=_payload_int(payload, "excluded_import_target"),
        minimum_distinct_systems=_payload_int(payload, "min_distinct_systems"),
        minimum_catalog_count=_payload_int(payload, "target_catalog_size"),
        include_justifications=bool(payload["include_justifications"]),
        include_exports=bool(payload["include_exports"]),
        include_design_warnings=bool(payload["include_design_warnings"]),
    )


async def list_synthetic_jobs(
    db: AsyncSession,
    limit: int = 20,
) -> SyntheticGenerationJobListResponse:
    """List recent persisted synthetic-generation jobs."""

    total = int(
        await db.scalar(select(func.count()).select_from(SyntheticGenerationJob))
        or 0
    )
    result = await db.scalars(
        select(SyntheticGenerationJob)
        .order_by(SyntheticGenerationJob.created_at.desc())
        .limit(limit)
    )
    jobs = [serialize_synthetic_job(job) for job in result.all()]
    return SyntheticGenerationJobListResponse(jobs=jobs, total=total)


async def get_synthetic_job(job_id: str, db: AsyncSession) -> SyntheticGenerationJobResponse:
    """Return one persisted synthetic-generation job."""

    return serialize_synthetic_job(await _load_job(job_id, db))


async def create_synthetic_job(
    body: SyntheticGenerationJobCreateRequest,
    actor_id: str,
    db: AsyncSession,
) -> SyntheticGenerationJobResponse:
    """Persist a new synthetic-generation job request."""

    normalized_payload = _normalized_request_payload(body)
    job = SyntheticGenerationJob(
        requested_by=actor_id,
        preset_code=str(normalized_payload["preset_code"]),
        input_payload=cast(dict[str, object], sanitize_for_json(body.model_dump(exclude_none=True))),
        normalized_payload=normalized_payload,
        project_name=str(normalized_payload["project_name"]),
        seed_value=_payload_int(normalized_payload, "seed_value"),
        catalog_target=_payload_int(normalized_payload, "target_catalog_size"),
        manual_target=_payload_int(normalized_payload, "manual_target"),
        import_target=_payload_int(normalized_payload, "import_target"),
        excluded_import_target=_payload_int(normalized_payload, "excluded_import_target"),
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)
    await audit_service.emit(
        event_type="synthetic_job_created",
        entity_type="synthetic_generation_job",
        entity_id=job.id,
        actor_id=actor_id,
        old_value=None,
        new_value=serialize_synthetic_job(job).model_dump(mode="json"),
        project_id=None,
        db=db,
    )
    return serialize_synthetic_job(job)


async def retry_synthetic_job(
    job_id: str,
    actor_id: str,
    db: AsyncSession,
) -> SyntheticGenerationJobResponse:
    """Clone a failed job into a new pending job with the same governed inputs."""

    source_job = await _load_job(job_id, db)
    if source_job.status.value != "failed":
        raise HTTPException(
            status_code=409,
            detail={
                "detail": "Only failed synthetic jobs can be retried.",
                "error_code": "SYNTHETIC_JOB_RETRY_FORBIDDEN",
            },
        )

    new_job = SyntheticGenerationJob(
        requested_by=actor_id,
        preset_code=source_job.preset_code,
        input_payload=cast(dict[str, object], sanitize_for_json(source_job.input_payload)),
        normalized_payload=cast(dict[str, object], sanitize_for_json(source_job.normalized_payload)),
        project_name=source_job.project_name,
        seed_value=source_job.seed_value,
        catalog_target=source_job.catalog_target,
        manual_target=source_job.manual_target,
        import_target=source_job.import_target,
        excluded_import_target=source_job.excluded_import_target,
    )
    db.add(new_job)
    await db.flush()
    await db.refresh(new_job)
    await audit_service.emit(
        event_type="synthetic_job_retried",
        entity_type="synthetic_generation_job",
        entity_id=new_job.id,
        actor_id=actor_id,
        old_value={"retry_source_job_id": source_job.id},
        new_value=serialize_synthetic_job(new_job).model_dump(mode="json"),
        project_id=None,
        db=db,
    )
    return serialize_synthetic_job(new_job)


async def mark_synthetic_job_running(job_id: str, db: AsyncSession) -> SyntheticGenerationJobResponse:
    """Mark a queued synthetic-generation job as running."""

    job = await _load_job(job_id, db)
    if job.status.value == "cleaned_up":
        raise HTTPException(
            status_code=409,
            detail={
                "detail": "Cleaned-up synthetic jobs cannot run again.",
                "error_code": "SYNTHETIC_JOB_ALREADY_CLEANED",
            },
        )
    old_value: dict[str, object] = {"status": job.status.value}
    job.status = type(job.status).RUNNING
    job.started_at = datetime.now(UTC)
    job.finished_at = None
    job.error_details = None
    await db.flush()
    await db.refresh(job)
    await audit_service.emit(
        event_type="synthetic_job_started",
        entity_type="synthetic_generation_job",
        entity_id=job.id,
        actor_id=job.requested_by,
        old_value=old_value,
        new_value={"status": job.status.value, "started_at": job.started_at.isoformat()},
        project_id=None,
        db=db,
    )
    return serialize_synthetic_job(job)


async def mark_synthetic_job_failed(
    job_id: str,
    error_details: dict[str, object],
    db: AsyncSession,
) -> SyntheticGenerationJobResponse:
    """Persist a failed terminal state for a synthetic-generation job."""

    job = await _load_job(job_id, db)
    old_value: dict[str, object] = {"status": job.status.value, "error_details": job.error_details}
    job.status = type(job.status).FAILED
    job.finished_at = datetime.now(UTC)
    job.error_details = cast(dict[str, object], sanitize_for_json(error_details))
    await db.flush()
    await db.refresh(job)
    await audit_service.emit(
        event_type="synthetic_job_failed",
        entity_type="synthetic_generation_job",
        entity_id=job.id,
        actor_id=job.requested_by,
        old_value=old_value,
        new_value={"status": job.status.value, "error_details": job.error_details},
        project_id=None,
        db=db,
    )
    return serialize_synthetic_job(job)


async def run_synthetic_generation_job(
    job_id: str,
    db: AsyncSession,
) -> SyntheticGenerationJobResponse:
    """Execute one persisted synthetic-generation job through the real service flows."""

    job = await _load_job(job_id, db)
    normalized_payload = cast(dict[str, object], job.normalized_payload)
    result = await create_synthetic_enterprise_project(db, _spec_from_payload(normalized_payload))
    old_value: dict[str, object] = {"status": job.status.value}
    artifact_manifest = cast(
        dict[str, object],
        sanitize_for_json(
            {
                "workbook_path": result.artifacts.workbook_path,
                "report_json_path": result.artifacts.report_json_path,
                "report_markdown_path": result.artifacts.report_markdown_path,
                "export_jobs": result.artifacts.export_jobs,
            }
        ),
    )
    validation_results = cast(
        dict[str, object],
        sanitize_for_json(
            {
                "catalog_count": result.catalog_count,
                "catalog_target": job.catalog_target,
                "distinct_systems": result.distinct_systems,
                "min_distinct_systems": normalized_payload["min_distinct_systems"],
                "covered_pattern_ids": result.covered_pattern_ids,
                "design_warning_rows": result.design_warning_rows,
                "approved_justifications": result.approved_justifications,
                "import_included_count": result.import_included_count,
                "manual_count": result.manual_count,
                "excluded_import_count": result.excluded_import_count,
                "meets_catalog_target": result.catalog_count >= job.catalog_target,
                "meets_distinct_system_target": result.distinct_systems
                >= _payload_int(normalized_payload, "min_distinct_systems"),
            }
        ),
    )
    result_summary = cast(
        dict[str, object],
        sanitize_for_json(
            {
                "project_id": result.project_id,
                "project_name": result.project_name,
                "import_batch_id": result.import_batch_id,
                "imported_snapshot_id": result.imported_snapshot_id,
                "final_snapshot_id": result.final_snapshot_id,
                "imported_dashboard_snapshot_id": result.imported_dashboard_snapshot_id,
                "final_dashboard_snapshot_id": result.final_dashboard_snapshot_id,
            }
        ),
    )
    job.status = type(job.status).COMPLETED
    job.project_id = result.project_id
    job.project_name = result.project_name
    job.finished_at = datetime.now(UTC)
    job.result_summary = result_summary
    job.validation_results = validation_results
    job.artifact_manifest = artifact_manifest
    job.error_details = None
    await db.flush()
    await db.refresh(job)
    await audit_service.emit(
        event_type="synthetic_job_completed",
        entity_type="synthetic_generation_job",
        entity_id=job.id,
        actor_id=job.requested_by,
        old_value=old_value,
        new_value=serialize_synthetic_job(job).model_dump(mode="json"),
        project_id=job.project_id,
        db=db,
    )
    return serialize_synthetic_job(job)


def _resolve_artifact_path(path_value: str) -> Path:
    path = Path(path_value)
    return path.resolve() if path.is_absolute() else (API_ROOT / path).resolve()


def _artifact_roots() -> tuple[Path, ...]:
    return (
        REPORT_ROOT.resolve(),
        UPLOAD_ROOT.resolve(),
        EXPORT_ROOT.resolve(),
    )


def _remove_artifact_file(path_value: str, removed_paths: list[str]) -> None:
    resolved_path = _resolve_artifact_path(path_value)
    if not any(root == resolved_path or root in resolved_path.parents for root in _artifact_roots()):
        return
    if resolved_path.exists():
        resolved_path.unlink()
        removed_paths.append(str(resolved_path))


def _cleanup_artifact_manifest(manifest: dict[str, object] | None) -> list[str]:
    removed_paths: list[str] = []
    if not manifest:
        return removed_paths

    for key in ("workbook_path", "report_json_path", "report_markdown_path"):
        value = manifest.get(key)
        if isinstance(value, str) and value:
            _remove_artifact_file(value, removed_paths)

    export_jobs = cast(dict[str, dict[str, object]], manifest.get("export_jobs", {}))
    for payload in export_jobs.values():
        file_path = payload.get("file_path")
        job_file_path = payload.get("job_file_path")
        if isinstance(file_path, str) and file_path:
            _remove_artifact_file(file_path, removed_paths)
        if isinstance(job_file_path, str) and job_file_path:
            _remove_artifact_file(job_file_path, removed_paths)
    return removed_paths


async def cleanup_synthetic_job(
    job_id: str,
    actor_id: str,
    db: AsyncSession,
) -> SyntheticGenerationJobResponse:
    """Archive/delete a synthetic project and remove generated artifacts."""

    job = await _load_job(job_id, db)
    if job.status.value in {"pending", "running"}:
        raise HTTPException(
            status_code=409,
            detail={
                "detail": "Running synthetic jobs cannot be cleaned up.",
                "error_code": "SYNTHETIC_JOB_CLEANUP_FORBIDDEN",
            },
        )
    if job.status.value == "cleaned_up":
        return serialize_synthetic_job(job)

    old_value = serialize_synthetic_job(job).model_dump(mode="json")
    if job.project_id:
        project = await db.get(Project, job.project_id)
        if project is not None:
            project_metadata = cast(dict[str, object] | None, project.project_metadata)
            if not bool((project_metadata or {}).get("synthetic")):
                raise HTTPException(
                    status_code=409,
                    detail={
                        "detail": "Only synthetic projects can be cleaned up by this route.",
                        "error_code": "SYNTHETIC_PROJECT_METADATA_REQUIRED",
                    },
                )
            job.project_id = None
            if project.status != ProjectStatus.ARCHIVED:
                await project_service.archive_project(project.id, actor_id, db)
            await project_service.delete_project(project.id, actor_id, db)

    removed_paths = _cleanup_artifact_manifest(cast(dict[str, object] | None, job.artifact_manifest))
    job.status = type(job.status).CLEANED_UP
    job.finished_at = datetime.now(UTC)
    job.result_summary = cast(
        dict[str, object],
        sanitize_for_json(
            {
                **cast(dict[str, object], job.result_summary or {}),
                "cleanup_removed_paths": removed_paths,
                "cleaned_up_at": job.finished_at.isoformat(),
            }
        ),
    )
    await db.flush()
    await db.refresh(job)
    await audit_service.emit(
        event_type="synthetic_job_cleaned_up",
        entity_type="synthetic_generation_job",
        entity_id=job.id,
        actor_id=actor_id,
        old_value=old_value,
        new_value=serialize_synthetic_job(job).model_dump(mode="json"),
        project_id=None,
        db=db,
    )
    return serialize_synthetic_job(job)
