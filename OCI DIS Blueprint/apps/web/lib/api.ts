/* Typed fetch wrapper for the OCI DIS Blueprint frontend. */

import type {
  AssumptionList,
  AssumptionSet,
  AssumptionSetCreate,
  AuditPage,
  CatalogIntegrationDetail,
  CatalogIntegrationDeleteResponse,
  CatalogPage,
  CatalogParams,
  ConsolidatedMetrics,
  DictionaryCategoryList,
  DictOption,
  DictOptionCreate,
  DuplicateCheckParams,
  DictionaryOptionList,
  GraphParams,
  GraphResponse,
  ImportBatch,
  ImportBatchDeleteResponse,
  ImportBatchList,
  ImportBatchListResponse,
  Integration,
  IntegrationPatch,
  ManualIntegrationCreate,
  OICEstimateRequest,
  OICEstimateResponse,
  PatternDefinition,
  PatternDefinitionCreate,
  PatternList,
  Project,
  ProjectArchiveResponse,
  ProjectDeleteResponse,
  ProjectList,
  ProjectListResponse,
  SourceRowList,
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

function adminHeaders(): HeadersInit {
  return {
    "X-Actor-Id": "web-admin",
    "X-Actor-Role": "Admin",
  };
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

  if (response.status === 204) {
    return undefined as T;
  }

  const text = await response.text();
  if (!text) {
    return undefined as T;
  }

  return JSON.parse(text) as T;
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

type RawAssumptionSet = {
  id: string;
  version: string;
  label: string;
  is_default: boolean;
  assumptions: Record<string, number>;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

type RawAssumptionList = {
  assumption_sets: RawAssumptionSet[];
};

function normalizeAssumption(raw: RawAssumptionSet): AssumptionSet {
  return {
    id: raw.id,
    version: raw.version,
    is_default: raw.is_default,
    created_at: raw.created_at,
    updated_at: raw.updated_at,
    oic_billing_threshold_kb: Number(raw.assumptions.oic_billing_threshold_kb ?? 50),
    oic_pack_size_msgs_per_hour: Number(raw.assumptions.oic_pack_size_msgs_per_hour ?? 5000),
    month_days: Number(raw.assumptions.month_days ?? 30),
    oic_rest_max_payload_kb: Number(raw.assumptions.oic_rest_max_payload_kb ?? 50000),
    oic_ftp_max_payload_kb: Number(raw.assumptions.oic_ftp_max_payload_kb ?? 50000),
    oic_kafka_max_payload_kb: Number(raw.assumptions.oic_kafka_max_payload_kb ?? 10000),
    oic_timeout_s: Number(raw.assumptions.oic_timeout_s ?? 300),
    streaming_partition_throughput_mb_s: Number(
      raw.assumptions.streaming_partition_throughput_mb_s ?? 1,
    ),
    functions_default_duration_ms: Number(raw.assumptions.functions_default_duration_ms ?? 200),
    functions_default_memory_mb: Number(raw.assumptions.functions_default_memory_mb ?? 256),
    functions_default_concurrency: Number(raw.assumptions.functions_default_concurrency ?? 1),
  };
}

function normalizeAssumptionList(response: RawAssumptionList): AssumptionList {
  const assumptionSets = response.assumption_sets.map(normalizeAssumption);
  return {
    assumption_sets: assumptionSets,
    total: assumptionSets.length,
  };
}

function serializeAssumption(
  body: Partial<AssumptionSetCreate>,
  options: {
    includeVersion: boolean;
    label?: string;
  },
): string {
  const version = options.includeVersion ? body.version : undefined;
  return JSON.stringify({
    ...(version ? { version } : {}),
    ...(options.label ? { label: options.label } : {}),
    assumptions: {
      ...(body.oic_billing_threshold_kb !== undefined
        ? { oic_billing_threshold_kb: body.oic_billing_threshold_kb }
        : {}),
      ...(body.oic_pack_size_msgs_per_hour !== undefined
        ? { oic_pack_size_msgs_per_hour: body.oic_pack_size_msgs_per_hour }
        : {}),
      ...(body.month_days !== undefined ? { month_days: body.month_days } : {}),
      ...(body.oic_rest_max_payload_kb !== undefined
        ? { oic_rest_max_payload_kb: body.oic_rest_max_payload_kb }
        : {}),
      ...(body.oic_ftp_max_payload_kb !== undefined
        ? { oic_ftp_max_payload_kb: body.oic_ftp_max_payload_kb }
        : {}),
      ...(body.oic_kafka_max_payload_kb !== undefined
        ? { oic_kafka_max_payload_kb: body.oic_kafka_max_payload_kb }
        : {}),
      ...(body.oic_timeout_s !== undefined ? { oic_timeout_s: body.oic_timeout_s } : {}),
      ...(body.streaming_partition_throughput_mb_s !== undefined
        ? { streaming_partition_throughput_mb_s: body.streaming_partition_throughput_mb_s }
        : {}),
      ...(body.functions_default_duration_ms !== undefined
        ? { functions_default_duration_ms: body.functions_default_duration_ms }
        : {}),
      ...(body.functions_default_memory_mb !== undefined
        ? { functions_default_memory_mb: body.functions_default_memory_mb }
        : {}),
      ...(body.functions_default_concurrency !== undefined
        ? { functions_default_concurrency: body.functions_default_concurrency }
        : {}),
    },
  });
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

  archiveProject: (projectId: string): Promise<ProjectArchiveResponse> =>
    apiFetch<ProjectArchiveResponse>(`/api/v1/projects/${projectId}/archive`, {
      method: "POST",
    }),

  deleteProject: (projectId: string): Promise<ProjectDeleteResponse> =>
    apiFetch<ProjectDeleteResponse>(`/api/v1/projects/${projectId}`, {
      method: "DELETE",
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

  getImportBatch: (projectId: string, batchId: string): Promise<ImportBatch> =>
    apiFetch<ImportBatch>(`/api/v1/imports/${projectId}/${batchId}`),

  listImportRows: (
    projectId: string,
    batchId: string,
    params: { page?: number; page_size?: number } = {},
  ): Promise<SourceRowList> =>
    apiFetch<SourceRowList>(
      `/api/v1/imports/${projectId}/${batchId}/rows${withQuery(params)}`,
    ),

  deleteImport: (projectId: string, batchId: string): Promise<ImportBatchDeleteResponse> =>
    apiFetch<ImportBatchDeleteResponse>(`/api/v1/imports/${projectId}/${batchId}`, {
      method: "DELETE",
    }),

  listCatalog: (projectId: string, params: CatalogParams): Promise<CatalogPage> =>
    apiFetch<CatalogPage>(`/api/v1/catalog/${projectId}${withQuery(params)}`),

  getIntegration: (projectId: string, integrationId: string): Promise<CatalogIntegrationDetail> =>
    apiFetch<CatalogIntegrationDetail>(`/api/v1/catalog/${projectId}/${integrationId}`),

  createIntegration: (projectId: string, body: ManualIntegrationCreate): Promise<Integration> =>
    apiFetch<Integration>(`/api/v1/catalog/${projectId}`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  patchIntegration: (projectId: string, integrationId: string, body: IntegrationPatch): Promise<Integration> =>
    apiFetch<Integration>(`/api/v1/catalog/${projectId}/${integrationId}`, {
      method: "PATCH",
      body: serializePatch(body),
    }),

  deleteIntegration: (
    projectId: string,
    integrationId: string,
  ): Promise<CatalogIntegrationDeleteResponse> =>
    apiFetch<CatalogIntegrationDeleteResponse>(`/api/v1/catalog/${projectId}/${integrationId}`, {
      method: "DELETE",
    }),

  getSystems: (projectId: string): Promise<string[]> =>
    apiFetch<string[]>(`/api/v1/catalog/${projectId}/systems`),

  checkDuplicates: (projectId: string, params: DuplicateCheckParams): Promise<Integration[]> =>
    apiFetch<Integration[]>(`/api/v1/catalog/${projectId}/duplicates${withQuery(params)}`),

  estimateOIC: (projectId: string, body: OICEstimateRequest): Promise<OICEstimateResponse> =>
    apiFetch<OICEstimateResponse>(`/api/v1/catalog/${projectId}/estimate`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  getGraph: (projectId: string, params: GraphParams = {}): Promise<GraphResponse> =>
    apiFetch<GraphResponse>(`/api/v1/catalog/${projectId}/graph${withQuery(params)}`),

  listPatterns: (): Promise<PatternList> =>
    apiFetch<PatternList>("/api/v1/patterns/"),

  createPattern: (body: PatternDefinitionCreate): Promise<PatternDefinition> =>
    apiFetch<PatternDefinition>("/api/v1/patterns/", {
      method: "POST",
      headers: adminHeaders(),
      body: JSON.stringify(body),
    }),

  updatePattern: (
    patternId: string,
    body: Partial<PatternDefinitionCreate>,
  ): Promise<PatternDefinition> =>
    apiFetch<PatternDefinition>(`/api/v1/patterns/${encodeURIComponent(patternId)}`, {
      method: "PATCH",
      headers: adminHeaders(),
      body: JSON.stringify(body),
    }),

  deletePattern: (patternId: string): Promise<void> =>
    apiFetch<void>(`/api/v1/patterns/${encodeURIComponent(patternId)}`, {
      method: "DELETE",
      headers: adminHeaders(),
    }),

  listDictionaryCategories: (): Promise<DictionaryCategoryList> =>
    apiFetch<DictionaryCategoryList>("/api/v1/dictionaries/"),

  listDictionaryOptions: (category: string): Promise<DictionaryOptionList> =>
    apiFetch<DictionaryOptionList>(`/api/v1/dictionaries/${category}`),

  createDictOption: (category: string, body: DictOptionCreate): Promise<DictOption> =>
    apiFetch<DictOption>(`/api/v1/dictionaries/${category}`, {
      method: "POST",
      headers: adminHeaders(),
      body: JSON.stringify(body),
    }),

  updateDictOption: (
    category: string,
    optionId: string,
    body: Partial<DictOptionCreate>,
  ): Promise<DictOption> =>
    apiFetch<DictOption>(`/api/v1/dictionaries/${category}/${optionId}`, {
      method: "PATCH",
      headers: adminHeaders(),
      body: JSON.stringify(body),
    }),

  deleteDictOption: (category: string, optionId: string): Promise<void> =>
    apiFetch<void>(`/api/v1/dictionaries/${category}/${optionId}`, {
      method: "DELETE",
      headers: adminHeaders(),
    }),

  listAssumptions: (): Promise<AssumptionList> =>
    apiFetch<RawAssumptionList>("/api/v1/assumptions/").then(normalizeAssumptionList),

  getAssumption: (version: string): Promise<AssumptionSet> =>
    apiFetch<RawAssumptionSet>(`/api/v1/assumptions/${version}`).then(normalizeAssumption),

  createAssumption: (body: AssumptionSetCreate): Promise<AssumptionSet> =>
    apiFetch<RawAssumptionSet>("/api/v1/assumptions/", {
      method: "POST",
      headers: adminHeaders(),
      body: serializeAssumption(body, {
        includeVersion: true,
        label: `Assumption Set ${body.version}`,
      }),
    }).then(normalizeAssumption),

  updateAssumption: (version: string, body: Partial<AssumptionSetCreate>): Promise<AssumptionSet> =>
    apiFetch<RawAssumptionSet>(`/api/v1/assumptions/${version}`, {
      method: "PATCH",
      headers: adminHeaders(),
      body: serializeAssumption(body, { includeVersion: false }),
    }).then(normalizeAssumption),

  setDefaultAssumption: (version: string): Promise<AssumptionSet> =>
    apiFetch<RawAssumptionSet>(`/api/v1/assumptions/${version}/default`, {
      method: "POST",
      headers: adminHeaders(),
    }).then(normalizeAssumption),

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
