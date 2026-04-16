/* Shared formatting helpers for dashboard and table views. */

const QA_STATUS_LABELS: Record<string, string> = {
  OK: "OK",
  REVISAR: "REVIEW",
  REVIEW: "REVIEW",
  PENDING: "PENDING",
};

const COMPLEXITY_LABELS: Record<string, string> = {
  Bajo: "Low",
  Low: "Low",
  Medio: "Medium",
  Medium: "Medium",
  Alto: "High",
  High: "High",
};

const PATTERN_CATEGORY_LABELS: Record<string, string> = {
  "SÍNCRONO": "Synchronous",
  "ASÍNCRONO": "Asynchronous",
  "SÍNCRONO + ASÍNCRONO": "Synchronous + Asynchronous",
  Synchronous: "Synchronous",
  Asynchronous: "Asynchronous",
  "Synchronous + Asynchronous": "Synchronous + Asynchronous",
};

const FREQUENCY_LABELS: Record<string, string> = {
  "Una vez al día": "Once Daily",
  "2 veces al día": "Twice Daily",
  "4 veces al día": "4 Times Daily",
  "Cada hora": "Hourly",
  "Cada 30 minutos": "Every 30 Minutes",
  "Cada 15 minutos": "Every 15 Minutes",
  "Cada 5 minutos": "Every 5 Minutes",
  "Cada minuto": "Every Minute",
  "Tiempo real": "Real Time",
  Semanal: "Weekly",
  Mensual: "Monthly",
  "Bajo demanda": "On Demand",
  TBD: "TBD",
  "Once Daily": "Once Daily",
  "Twice Daily": "Twice Daily",
  "4 Times Daily": "4 Times Daily",
  Hourly: "Hourly",
  "Every 30 Minutes": "Every 30 Minutes",
  "Every 15 Minutes": "Every 15 Minutes",
  "Every 5 Minutes": "Every 5 Minutes",
  "Every Minute": "Every Minute",
  "Real Time": "Real Time",
  Weekly: "Weekly",
  Monthly: "Monthly",
  "On Demand": "On Demand",
};

const INTEGRATION_STATUS_LABELS: Record<string, string> = {
  "Ya existe": "Already Exists",
  "Definitiva (End-State)": "Definitive (End State)",
  "En Revisión": "Under Review",
  TBD: "TBD",
  "Duplicado 1": "Duplicate 1",
  "Duplicado 2": "Duplicate 2",
};

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

export function formatQaStatus(value: string | null | undefined): string {
  if (!value) {
    return "PENDING";
  }
  return QA_STATUS_LABELS[value] ?? value;
}

export function formatComplexity(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }
  return COMPLEXITY_LABELS[value] ?? value;
}

export function formatPatternCategory(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }
  return PATTERN_CATEGORY_LABELS[value] ?? value;
}

export function formatFrequency(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }
  return FREQUENCY_LABELS[value] ?? value;
}

export function formatIntegrationStatus(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }
  return INTEGRATION_STATUS_LABELS[value] ?? value;
}

export function formatExclusionReason(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }
  return value
    .replace("Estado = Duplicado 2", "Status = Duplicate 2")
    .replace("Duplicado 2", "Duplicate 2");
}

export function titleCaseFromPath(pathname: string): string {
  const value = pathname.split("/").filter(Boolean).at(-1) ?? "projects";
  return value
    .replace(/\[|\]/g, "")
    .replace(/-/g, " ")
    .replace(/\b\w/g, (char: string) => char.toUpperCase());
}
