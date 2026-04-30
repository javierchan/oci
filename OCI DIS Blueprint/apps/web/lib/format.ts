/* Shared formatting helpers for dashboard and table views. */

const QA_STATUS_LABELS: Record<string, string> = {
  OK: "OK",
  REVISAR: "Needs Review",
  PENDING: "Pending",
};

const COMPLEXITY_LABELS: Record<string, string> = {
  Bajo: "Low",
  Medio: "Medium",
  Alto: "High",
};

const DISPLAY_VALUE_LABELS: Record<string, string> = {
  "Tiempo Real": "Real Time",
  "Tiempo real": "Real Time",
  "Cada 5 minutos": "Every 5 minutes",
  "Cada minuto": "Every minute",
  "Cada 15 minutos": "Every 15 minutes",
  "Cada 20 minutos": "Every 20 minutes",
  "Cada 30 minutos": "Every 30 minutes",
  "Cada 1 hora": "Every hour",
  "Cada hora": "Every hour",
  "Cada 2 horas": "Every 2 hours",
  "Cada 4 horas": "Every 4 hours",
  "Cada 6 horas": "Every 6 hours",
  "Cada 8 horas": "Every 8 hours",
  "Cada 12 horas": "Every 12 hours",
  "Una vez al día": "Once per day",
  "2 veces al día": "Twice per day",
  "4 veces al día": "4 times per day",
  Semanal: "Weekly",
  Quincenal: "Biweekly",
  Mensual: "Monthly",
  "Bajo demanda": "On demand",
  Bajo: "Low",
  Medio: "Medium",
  Alto: "High",
  "Definitiva (End-State)": "Target State",
  "En Revisión": "In Review",
  "En Progreso": "In Progress",
  "Pendiente": "Pending",
  Mapeado: "Mapped",
  "En análisis": "Under Analysis",
  "Ya existe": "Already Exists",
  "Duplicado 1": "Duplicate 1",
  "Duplicado 2": "Duplicate 2",
  Sí: "Yes",
  Válido: "Valid",
};

const SOURCE_FIELD_LABELS: Record<string, string> = {
  "#": "#",
  "ID de Interfaz": "Interface ID",
  "ID de interfaz": "Interface ID",
  Owner: "Owner",
  Marca: "Brand",
  "Proceso de Negocio": "Business Process",
  "Proceso Negocio": "Business Process",
  Interfaz: "Interface Name",
  Descripción: "Description",
  Descripcion: "Description",
  Estado: "Status",
  "Estado de Mapeo": "Mapping Status",
  "Alcance Inicial": "Initial Scope",
  Complejidad: "Complexity",
  Frecuencia: "Frequency",
  Tipo: "Type",
  Base: "Base",
  "Estado Interfaz": "Interface Status",
  "Tiempo Real": "Real Time",
  "Tiempo Real (Si/No)": "Real Time (Yes/No)",
  "Tipo Trigger OIC": "OIC Trigger Type",
  "Response Size (KB)": "Response Size (KB)",
  "Tamaño Respuesta KB": "Response Size KB",
  "Payload por ejecución (KB)": "Payload per Execution (KB)",
  "Payload por ejecucion (KB)": "Payload per Execution (KB)",
  "Payload por hora (KB)": "Payload per Hour (KB)",
  "Ejec /día": "Executions / Day",
  "Ejec /dia": "Executions / Day",
  "Fan-Out (Si/No)": "Fan-out (Yes/No)",
  "# Destinos": "# Destinations",
  "Sistema de Origen": "Source System",
  "Sistema Origen": "Source System",
  "Tecnología de Origen": "Source Technology",
  "Tecnologia de Origen": "Source Technology",
  "API Reference": "API Reference",
  "API Ref Origen": "Source API Reference",
  "Propietario de Origen": "Source Owner",
  "Sistema de Destino": "Destination System",
  "Sistema Destino": "Destination System",
  "Tecnología de Destino": "Destination Technology",
  "Tecnologia de Destino": "Destination Technology",
  "Tecnología de Destino #1": "Destination Technology #1",
  "Tecnologia de Destino #1": "Destination Technology #1",
  "Tecnología de Destino #2": "Destination Technology #2",
  "Tecnologia de Destino #2": "Destination Technology #2",
  "Propietario de Destino": "Destination Owner",
  Calendarización: "Scheduling",
  Calendarizacion: "Scheduling",
  Calendarization: "Scheduling",
  TBQ: "TBQ",
  "Patrón seleccionado (manual)": "Selected Pattern (Manual)",
  "Patrón Seleccionado (Manual)": "Selected Pattern (Manual)",
  "Patron seleccionado (manual)": "Selected Pattern (Manual)",
  "Patron Seleccionado (Manual)": "Selected Pattern (Manual)",
  Patrón: "Pattern",
  Patron: "Pattern",
  Patrones: "Patterns",
  "Racional del patrón (manual)": "Pattern Rationale (Manual)",
  "Racional del Patrón (Manual)": "Pattern Rationale (Manual)",
  "Racional del patron (manual)": "Pattern Rationale (Manual)",
  "Racional del Patron (Manual)": "Pattern Rationale (Manual)",
  "Racional del Patrón": "Pattern Rationale",
  "Racional del Patron": "Pattern Rationale",
  "Comentarios / Observaciones": "Comments / Observations",
  "Comentarios/Observaciones": "Comments / Observations",
  Comentarios: "Comments",
  Observaciones: "Observations",
  "Retry Policy": "Retry Policy",
  "Herramientas Core": "Core Tools",
  "Herramientas Core Cuantificables / Volumétricas": "Quantifiable / Volumetric Core Tools",
  "Herramientas Core Cuantificables / Volumetricas": "Quantifiable / Volumetric Core Tools",
  "Herramientas Adicionales": "Additional Tools",
  "Herramientas Adicionales / Overlays (complemento manual)": "Additional Tools / Overlays (Manual Complement)",
  "Herramientas Adicionales / Overlays (Complemento manual)": "Additional Tools / Overlays (Manual Complement)",
  Incertidumbre: "Uncertainty",
  QA: "QA",
};

function normalizeDisplayKey(value: string): string {
  return value
    .trim()
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase();
}

const NORMALIZED_DISPLAY_VALUE_LABELS: Record<string, string> = Object.fromEntries(
  Object.entries(DISPLAY_VALUE_LABELS).map(([key, label]) => [normalizeDisplayKey(key), label]),
);

const NORMALIZED_SOURCE_FIELD_LABELS: Record<string, string> = Object.fromEntries(
  Object.entries(SOURCE_FIELD_LABELS).map(([key, label]) => [normalizeDisplayKey(key), label]),
);

export function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(value));
}

export function formatNumber(value: number | null | undefined, maximumFractionDigits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits,
  }).format(value);
}

export function formatCompactNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }
  return new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}

export function titleCaseFromPath(pathname: string): string {
  const value = pathname.split("/").filter(Boolean).at(-1) ?? "projects";
  return value
    .replace(/\[|\]/g, "")
    .replace(/-/g, " ")
    .replace(/\b\w/g, (char: string) => char.toUpperCase());
}

export function displayQaStatus(value: string | null | undefined): string {
  if (!value) {
    return QA_STATUS_LABELS.PENDING;
  }
  return QA_STATUS_LABELS[value] ?? displayUiValue(value);
}

export function displayComplexity(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }
  return COMPLEXITY_LABELS[value] ?? value;
}

export function displayUiValue(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }
  return DISPLAY_VALUE_LABELS[value] ?? NORMALIZED_DISPLAY_VALUE_LABELS[normalizeDisplayKey(value)] ?? value;
}

export function displaySourceFieldLabel(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }
  return SOURCE_FIELD_LABELS[value] ?? NORMALIZED_SOURCE_FIELD_LABELS[normalizeDisplayKey(value)] ?? value;
}
