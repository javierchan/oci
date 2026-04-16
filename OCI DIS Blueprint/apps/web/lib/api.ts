/* Typed fetch wrapper for the OCI DIS Blueprint frontend. */

import type {
  AssumptionList,
  AssumptionSet,
  AssumptionSetCreate,
  AuditPage,
  CanvasGovernance,
  CatalogIntegrationDetail,
  CatalogIntegrationDeleteResponse,
  CatalogPage,
  CatalogParams,
  ConsolidatedMetrics,
  DashboardSnapshot,
  DashboardSnapshotList,
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
  RecalculationJobStatus,
  ServiceCapabilityProfileList,
  SourceRowList,
  VolumetrySnapshotList,
} from "@/lib/types";

function normalizeBase(value: string): string {
  return value.replace(/\/api\/v1\/?$/, "");
}

const PUBLIC_BASE = normalizeBase(process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000");
const INTERNAL_BASE = normalizeBase(process.env.INTERNAL_API_URL ?? PUBLIC_BASE);
const DOCKER_INTERNAL_BASE = "http://api:8000";

function resolveBases(): string[] {
  if (typeof window !== "undefined") {
    return [PUBLIC_BASE];
  }

  const bases = new Set<string>([INTERNAL_BASE, PUBLIC_BASE]);
  if (INTERNAL_BASE.includes("localhost") || INTERNAL_BASE.includes("127.0.0.1")) {
    bases.add(DOCKER_INTERNAL_BASE);
  }
  return Array.from(bases);
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

  let response: Response | null = null;
  let lastError: unknown = null;
  for (const base of resolveBases()) {
    try {
      response = await fetch(`${base}${path}`, {
        ...init,
        cache: "no-store",
        headers,
      });
      break;
    } catch (error) {
      lastError = error;
    }
  }

  if (response === null) {
    throw lastError instanceof Error ? lastError : new Error(`API request failed for ${path}`);
  }

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
  assumptions: Record<string, unknown>;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

type RawAssumptionList = {
  assumption_sets: RawAssumptionSet[];
};

function readAssumptionNumber(value: unknown, fallback: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function normalizeAssumption(raw: RawAssumptionSet): AssumptionSet {
  return {
    id: raw.id,
    version: raw.version,
    is_default: raw.is_default,
    created_at: raw.created_at,
    updated_at: raw.updated_at,
    oic_billing_threshold_kb: readAssumptionNumber(raw.assumptions.oic_billing_threshold_kb, 50),
    oic_pack_size_msgs_per_hour: readAssumptionNumber(raw.assumptions.oic_pack_size_msgs_per_hour, 5000),
    oic_byol_pack_size_msgs_per_hour: readAssumptionNumber(
      raw.assumptions.oic_byol_pack_size_msgs_per_hour,
      20000,
    ),
    month_days: readAssumptionNumber(raw.assumptions.month_days, 31),
    oic_rest_max_payload_kb: readAssumptionNumber(raw.assumptions.oic_rest_max_payload_kb, 10240),
    oic_ftp_max_payload_kb: readAssumptionNumber(raw.assumptions.oic_ftp_max_payload_kb, 10240),
    oic_kafka_max_payload_kb: readAssumptionNumber(raw.assumptions.oic_kafka_max_payload_kb, 10240),
    oic_timeout_s: readAssumptionNumber(raw.assumptions.oic_timeout_s, 300),
    streaming_partition_throughput_mb_s: readAssumptionNumber(
      raw.assumptions.streaming_partition_throughput_mb_s,
      1,
    ),
    streaming_read_throughput_mb_s: readAssumptionNumber(
      raw.assumptions.streaming_read_throughput_mb_s,
      2,
    ),
    streaming_max_message_size_mb: readAssumptionNumber(
      raw.assumptions.streaming_max_message_size_mb,
      1,
    ),
    streaming_retention_days: readAssumptionNumber(raw.assumptions.streaming_retention_days, 7),
    streaming_default_partitions: readAssumptionNumber(raw.assumptions.streaming_default_partitions, 200),
    functions_default_duration_ms: readAssumptionNumber(raw.assumptions.functions_default_duration_ms, 2000),
    functions_default_memory_mb: readAssumptionNumber(raw.assumptions.functions_default_memory_mb, 256),
    functions_default_concurrency: readAssumptionNumber(raw.assumptions.functions_default_concurrency, 1),
    functions_max_timeout_s: readAssumptionNumber(raw.assumptions.functions_max_timeout_s, 300),
    functions_batch_size_records: readAssumptionNumber(raw.assumptions.functions_batch_size_records, 500),
    queue_billing_unit_kb: readAssumptionNumber(raw.assumptions.queue_billing_unit_kb, 64),
    queue_max_message_kb: readAssumptionNumber(raw.assumptions.queue_max_message_kb, 256),
    queue_retention_days: readAssumptionNumber(raw.assumptions.queue_retention_days, 7),
    queue_throughput_soft_limit_msgs_per_second: readAssumptionNumber(
      raw.assumptions.queue_throughput_soft_limit_msgs_per_second,
      10,
    ),
    data_integration_workspaces_per_region: readAssumptionNumber(
      raw.assumptions.data_integration_workspaces_per_region,
      5,
    ),
    data_integration_deleted_workspace_retention_days: readAssumptionNumber(
      raw.assumptions.data_integration_deleted_workspace_retention_days,
      15,
    ),
    raw_assumptions: raw.assumptions,
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
      ...(body.raw_assumptions ?? {}),
      ...(body.oic_billing_threshold_kb !== undefined
        ? { oic_billing_threshold_kb: body.oic_billing_threshold_kb }
        : {}),
      ...(body.oic_pack_size_msgs_per_hour !== undefined
        ? { oic_pack_size_msgs_per_hour: body.oic_pack_size_msgs_per_hour }
        : {}),
      ...(body.oic_byol_pack_size_msgs_per_hour !== undefined
        ? { oic_byol_pack_size_msgs_per_hour: body.oic_byol_pack_size_msgs_per_hour }
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
      ...(body.streaming_read_throughput_mb_s !== undefined
        ? { streaming_read_throughput_mb_s: body.streaming_read_throughput_mb_s }
        : {}),
      ...(body.streaming_max_message_size_mb !== undefined
        ? { streaming_max_message_size_mb: body.streaming_max_message_size_mb }
        : {}),
      ...(body.streaming_retention_days !== undefined
        ? { streaming_retention_days: body.streaming_retention_days }
        : {}),
      ...(body.streaming_default_partitions !== undefined
        ? { streaming_default_partitions: body.streaming_default_partitions }
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
      ...(body.functions_max_timeout_s !== undefined
        ? { functions_max_timeout_s: body.functions_max_timeout_s }
        : {}),
      ...(body.functions_batch_size_records !== undefined
        ? { functions_batch_size_records: body.functions_batch_size_records }
        : {}),
      ...(body.queue_billing_unit_kb !== undefined
        ? { queue_billing_unit_kb: body.queue_billing_unit_kb }
        : {}),
      ...(body.queue_max_message_kb !== undefined
        ? { queue_max_message_kb: body.queue_max_message_kb }
        : {}),
      ...(body.queue_retention_days !== undefined
        ? { queue_retention_days: body.queue_retention_days }
        : {}),
      ...(body.queue_throughput_soft_limit_msgs_per_second !== undefined
        ? {
            queue_throughput_soft_limit_msgs_per_second:
              body.queue_throughput_soft_limit_msgs_per_second,
          }
        : {}),
      ...(body.data_integration_workspaces_per_region !== undefined
        ? { data_integration_workspaces_per_region: body.data_integration_workspaces_per_region }
        : {}),
      ...(body.data_integration_deleted_workspace_retention_days !== undefined
        ? {
            data_integration_deleted_workspace_retention_days:
              body.data_integration_deleted_workspace_retention_days,
          }
        : {}),
    },
  });
}

function serializePatch(body: IntegrationPatch): string {
  return JSON.stringify({
    ...body,
    core_tools: body.core_tools ? body.core_tools.join(", ") : undefined,
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

  listServices: (): Promise<ServiceCapabilityProfileList> =>
    apiFetch<ServiceCapabilityProfileList>("/api/v1/services/"),

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

  getCanvasGovernance: (): Promise<CanvasGovernance> =>
    apiFetch<CanvasGovernance>("/api/v1/dictionaries/canvas-governance"),

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

  recalculate: (projectId: string): Promise<RecalculationJobStatus> =>
    apiFetch<RecalculationJobStatus>(`/api/v1/recalculate/${projectId}`, {
      method: "POST",
    }),

  getRecalculationJob: (projectId: string, jobId: string): Promise<RecalculationJobStatus> =>
    apiFetch<RecalculationJobStatus>(`/api/v1/recalculate/${projectId}/jobs/${jobId}`),

  listSnapshots: (projectId: string): Promise<VolumetrySnapshotList> =>
    apiFetch<VolumetrySnapshotList>(`/api/v1/volumetry/${projectId}/snapshots`),

  listDashboardSnapshots: (projectId: string): Promise<DashboardSnapshotList> =>
    apiFetch<DashboardSnapshotList>(`/api/v1/dashboard/${projectId}/snapshots`),

  getDashboardSnapshot: (projectId: string, snapshotId: string): Promise<DashboardSnapshot> =>
    apiFetch<DashboardSnapshot>(`/api/v1/dashboard/${projectId}/snapshots/${snapshotId}`),

  getConsolidated: (projectId: string, snapshotId: string): Promise<ConsolidatedMetrics> =>
    apiFetch<ConsolidatedMetrics>(`/api/v1/volumetry/${projectId}/snapshots/${snapshotId}/consolidated`),

  listAudit: (
    projectId: string,
    params: Record<string, string | number | undefined> = {},
  ): Promise<AuditPage> =>
    apiFetch<AuditPage>(`/api/v1/audit/${projectId}${withQuery(params)}`),
};
