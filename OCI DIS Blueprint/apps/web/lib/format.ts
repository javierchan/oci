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
