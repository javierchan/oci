/* Typed fetch wrapper for the OCI DIS Blueprint frontend. */

import type {
  AuditPage,
  CatalogIntegrationDetail,
  CatalogPage,
  CatalogParams,
  ConsolidatedMetrics,
  DictionaryOptionList,
  ImportBatch,
  ImportBatchList,
  ImportBatchListResponse,
  Integration,
  IntegrationPatch,
  PatternList,
  Project,
  ProjectList,
  ProjectListResponse,
  VolumetrySnapshot,
  VolumetrySnapshotList,
} from "@/lib/types";

const PUBLIC_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const INTERNAL_BASE = process.env.INTERNAL_API_URL ?? PUBLIC_BASE;

function resolveBase(): string {
  return typeof window === "undefined" ? INTERNAL_BASE : PUBLIC_BASE;
}

function withQuery(params: CatalogParams | Record<string, string | number | undefined>): string {
  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") {
      searchParams.set(key, String(value));
    }
  }
  const query = searchParams.toString();
  return query ? `?${query}` : "";
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  const hasFormDataBody = typeof FormData !== "undefined" && init?.body instanceof FormData;
  if (!hasFormDataBody && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${resolveBase()}${path}`, {
    ...init,
    cache: "no-store",
    headers,
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`API ${response.status} ${path}: ${body}`);
  }

  return (await response.json()) as T;
}

function normalizeProjects(response: ProjectListResponse): ProjectList {
  return {
    projects: response.projects,
    total: response.projects.length,
  };
}

function normalizeImports(response: ImportBatchListResponse): ImportBatchList {
  return {
    batches: response.import_batches,
    total: response.import_batches.length,
  };
}

function serializePatch(body: IntegrationPatch): string {
  return JSON.stringify({
    ...body,
    core_tools: body.core_tools?.join(", "),
  });
}

export const api = {
  listProjects: (): Promise<ProjectList> =>
    apiFetch<ProjectListResponse>("/api/v1/projects/").then(normalizeProjects),

  getProject: (projectId: string): Promise<Project> =>
    apiFetch<Project>(`/api/v1/projects/${projectId}`),

  createProject: (body: { name: string; owner_id: string }): Promise<Project> =>
    apiFetch<Project>("/api/v1/projects/", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  uploadWorkbook: async (projectId: string, file: File): Promise<ImportBatch> => {
    const formData = new FormData();
    formData.append("file", file);
    return apiFetch<ImportBatch>(`/api/v1/imports/${projectId}`, {
      method: "POST",
      body: formData,
    });
  },

  listImports: (projectId: string): Promise<ImportBatchList> =>
    apiFetch<ImportBatchListResponse>(`/api/v1/imports/${projectId}`).then(normalizeImports),

  listCatalog: (projectId: string, params: CatalogParams): Promise<CatalogPage> =>
    apiFetch<CatalogPage>(`/api/v1/catalog/${projectId}${withQuery(params)}`),

  getIntegration: (projectId: string, integrationId: string): Promise<CatalogIntegrationDetail> =>
    apiFetch<CatalogIntegrationDetail>(`/api/v1/catalog/${projectId}/${integrationId}`),

  patchIntegration: (projectId: string, integrationId: string, body: IntegrationPatch): Promise<Integration> =>
    apiFetch<Integration>(`/api/v1/catalog/${projectId}/${integrationId}`, {
      method: "PATCH",
      body: serializePatch(body),
    }),

  listPatterns: (): Promise<PatternList> =>
    apiFetch<PatternList>("/api/v1/patterns/"),

  listDictionaryOptions: (category: string): Promise<DictionaryOptionList> =>
    apiFetch<DictionaryOptionList>(`/api/v1/dictionaries/${category}`),

  recalculate: (projectId: string): Promise<VolumetrySnapshot> =>
    apiFetch<VolumetrySnapshot>(`/api/v1/recalculate/${projectId}`, {
      method: "POST",
    }),

  listSnapshots: (projectId: string): Promise<VolumetrySnapshotList> =>
    apiFetch<VolumetrySnapshotList>(`/api/v1/volumetry/${projectId}/snapshots`),

  getConsolidated: (projectId: string, snapshotId: string): Promise<ConsolidatedMetrics> =>
    apiFetch<ConsolidatedMetrics>(`/api/v1/volumetry/${projectId}/snapshots/${snapshotId}/consolidated`),

  listAudit: (
    projectId: string,
    params: Record<string, string | number | undefined> = {},
  ): Promise<AuditPage> =>
    apiFetch<AuditPage>(`/api/v1/audit/${projectId}${withQuery(params)}`),
};
