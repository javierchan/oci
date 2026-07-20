/* Typed fetch wrapper for the OCI DIS Blueprint frontend. */

import type {
  AgentDefinition,
  AgentProviderStatus,
  AgentProviderMetrics,
  AgentRun,
  AgentRunList,
  AgentRunRequest,
  AgentValueMetrics,
  AssumptionList,
  AssumptionSet,
  AssumptionSetCreate,
  AiReviewBaseline,
  AiReviewBaselineList,
  AiReviewBaselineLookup,
  AiReviewBaselineRequest,
  AiReviewDraftSimulation,
  AiReviewJob,
  AiReviewJobCompare,
  AiReviewApplyPatchResponse,
  AiReviewJobList,
  AiReviewJobRequest,
  AiReviewProviderStatus,
  AiReviewSelectDraftResponse,
  AiReviewScope,
  AuditPage,
  BomJob,
  BomJobList,
  BomComparison,
  BomSnapshot,
  BomSnapshotList,
  CanvasGovernance,
  CaptureTemplateMetadata,
  CatalogIntegrationDetail,
  CatalogIntegrationDeleteResponse,
  CatalogFacets,
  CatalogPage,
  CatalogParams,
  ConsolidatedMetrics,
  CommercialCatalogFinalizeRequest,
  CommercialCandidateReviewRequest,
  CommercialExceptionReviewRequest,
  CommercialWorkspace,
  DashboardSnapshot,
  DashboardSnapshotList,
  DictionaryCategoryList,
  DictOption,
  DictOptionCreate,
  DuplicateCheckParams,
  DictionaryOptionList,
  DeploymentScenario,
  DeploymentScenarioCreate,
  DeploymentScenarioList,
  GraphParams,
  GraphResponse,
  GovernanceChangeSet,
  GovernanceChangeSetList,
  ImportBatch,
  ImportBatchDeleteResponse,
  ImportBatchList,
  ImportBatchListResponse,
  ImportMappingProfileListResponse,
  ImportMappingReviewApprovalRequest,
  ImportMappingReviewRequest,
  ImportQualityAssistant,
  Integration,
  IntegrationPatch,
  ManualIntegrationCreate,
  OICEstimateRequest,
  OICEstimateResponse,
  PatternDefinition,
  PatternDefinitionCreate,
  PatternList,
  PriceCatalogSnapshot,
  PriceCatalogSnapshotList,
  PriceItemList,
  PriceSourceList,
  PriceSyncJob,
  PriceSyncJobList,
  Project,
  ProjectArchiveResponse,
  ProjectDeleteResponse,
  ProjectList,
  ProjectListResponse,
  RecalculationJobStatus,
  ServiceVerificationAlertList,
  ServiceVerificationFinding,
  ServiceVerificationFindingReviewRequest,
  ServiceInteroperabilityMatrix,
  ServiceProductDetail,
  ServiceProductList,
  ServiceVerificationJobList,
  ServiceVerificationJob,
  ServiceVerificationRunRequest,
  ScenarioAssistant,
  SkuMapping,
  SkuMappingList,
  SkuMappingPatch,
  SourceRowList,
  SupportConversation,
  SupportMessageInput,
  SyntheticGenerationJob,
  SyntheticGenerationJobList,
  SyntheticGenerationJobRequest,
  SyntheticGenerationPresetList,
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

function supportHeaders(sessionId: string): HeadersInit {
  return {
    ...adminHeaders(),
    "X-Support-Session-Id": sessionId,
  };
}

type ApiErrorPayload = {
  detail?: string | { detail?: string; [key: string]: unknown } | Array<{ msg?: string; [key: string]: unknown }>;
  error_code?: string;
};

type ParsedApiError = {
  message: string;
  errorCode?: string;
  detail?: unknown;
};

export class ApiError extends Error {
  readonly status: number;
  readonly path: string;
  readonly errorCode?: string;
  readonly detail?: unknown;

  constructor({
    status,
    path,
    message,
    errorCode,
    detail,
  }: {
    status: number;
    path: string;
    message: string;
    errorCode?: string;
    detail?: unknown;
  }) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.path = path;
    this.errorCode = errorCode;
    this.detail = detail;
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

export function isApiError(error: unknown): error is ApiError {
  if (error instanceof ApiError) {
    return true;
  }
  return (
    typeof error === "object" &&
    error !== null &&
    typeof (error as { message?: unknown }).message === "string" &&
    ("status" in error || "path" in error || "errorCode" in error || "detail" in error)
  );
}

export function isApiErrorCode(error: unknown, errorCode: string): boolean {
  if (
    typeof error === "object" &&
    error !== null &&
    "errorCode" in error &&
    typeof (error as { errorCode?: unknown }).errorCode === "string"
  ) {
    return (error as { errorCode: string }).errorCode === errorCode;
  }

  if (errorCode === "PROJECT_NOT_FOUND" && error instanceof Error) {
    return error.message.trim() === "Project not found";
  }

  return false;
}

export function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

export function apiDownloadUrl(path: string): string {
  return `${PUBLIC_BASE}${path}`;
}

export async function apiDownloadBlob(path: string): Promise<{ blob: Blob; filename: string | null }> {
  const response = await fetch(`${PUBLIC_BASE}${path}`, {
    cache: "no-store",
    headers: adminHeaders(),
  });
  if (!response.ok) {
    const body = await response.text();
    const parsed = parseApiError(response.status, path, body);
    throw new ApiError({
      status: response.status,
      path,
      message: parsed.message,
      errorCode: parsed.errorCode,
      detail: parsed.detail,
    });
  }
  const disposition = response.headers.get("content-disposition") ?? "";
  const match = disposition.match(/filename\*?=(?:UTF-8''|\")?([^";]+)/i);
  return {
    blob: await response.blob(),
    filename: match ? decodeURIComponent(match[1].trim()) : null,
  };
}

function parseApiError(status: number, path: string, body: string): ParsedApiError {
  if (!body.trim()) {
    return {
      message: `API ${status} ${path}`,
    };
  }

  try {
    const parsed = JSON.parse(body) as ApiErrorPayload;
    const errorCode = typeof parsed.error_code === "string" ? parsed.error_code : undefined;
    if (typeof parsed.detail === "string") {
      return {
        message: parsed.detail,
        errorCode,
        detail: parsed.detail,
      };
    }
    if (parsed.detail && typeof parsed.detail === "object" && !Array.isArray(parsed.detail)) {
      if (typeof parsed.detail.detail === "string") {
        return {
          message: parsed.detail.detail,
          errorCode,
          detail: parsed.detail,
        };
      }
      return {
        message: JSON.stringify(parsed.detail),
        errorCode,
        detail: parsed.detail,
      };
    }
    if (Array.isArray(parsed.detail) && parsed.detail.length > 0) {
      const messages = parsed.detail
        .map((entry) => entry.msg)
        .filter((message): message is string => Boolean(message));
      if (messages.length > 0) {
        return {
          message: messages.join("; "),
          errorCode,
          detail: parsed.detail,
        };
      }
    }
  } catch {}

  return {
    message: `API ${status} ${path}: ${body}`,
    detail: body,
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
    const parsed = parseApiError(response.status, path, body);
    throw new ApiError({
      status: response.status,
      path,
      message: parsed.message,
      errorCode: parsed.errorCode,
      detail: parsed.detail,
    });
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
    month_days: readAssumptionNumber(raw.assumptions.month_days, 31),
    streaming_default_partitions: readAssumptionNumber(raw.assumptions.streaming_default_partitions, 200),
    functions_default_duration_ms: readAssumptionNumber(raw.assumptions.functions_default_duration_ms, 2000),
    functions_default_memory_mb: readAssumptionNumber(raw.assumptions.functions_default_memory_mb, 256),
    functions_default_concurrency: readAssumptionNumber(raw.assumptions.functions_default_concurrency, 1),
    functions_batch_size_records: readAssumptionNumber(raw.assumptions.functions_batch_size_records, 500),
    queue_throughput_soft_limit_msgs_per_second: readAssumptionNumber(
      raw.assumptions.queue_throughput_soft_limit_msgs_per_second,
      10,
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
      ...(body.month_days !== undefined ? { month_days: body.month_days } : {}),
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
      ...(body.functions_batch_size_records !== undefined
        ? { functions_batch_size_records: body.functions_batch_size_records }
        : {}),
      ...(body.queue_throughput_soft_limit_msgs_per_second !== undefined
        ? {
            queue_throughput_soft_limit_msgs_per_second:
              body.queue_throughput_soft_limit_msgs_per_second,
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
  listAgents: (): Promise<AgentDefinition[]> =>
    apiFetch<AgentDefinition[]>("/api/v1/agents", { headers: adminHeaders() }),

  getAgentProviderStatus: (): Promise<AgentProviderStatus> =>
    apiFetch<AgentProviderStatus>("/api/v1/agents/provider-status", { headers: adminHeaders() }),

  getAgentProviderMetrics: (): Promise<AgentProviderMetrics> =>
    apiFetch<AgentProviderMetrics>("/api/v1/agents/provider-metrics", { headers: adminHeaders() }),

  getAgentValueMetrics: (): Promise<AgentValueMetrics> =>
    apiFetch<AgentValueMetrics>("/api/v1/agents/value-metrics", { headers: adminHeaders() }),

  listAgentRuns: (params: { project_id?: string; limit?: number } = {}): Promise<AgentRunList> =>
    apiFetch<AgentRunList>(`/api/v1/agents/runs${withQuery(params)}`, { headers: adminHeaders() }),

  getAgentRun: (runId: string): Promise<AgentRun> =>
    apiFetch<AgentRun>(`/api/v1/agents/runs/${encodeURIComponent(runId)}`, { headers: adminHeaders() }),

  runAgent: (body: AgentRunRequest): Promise<AgentRun> =>
    apiFetch<AgentRun>("/api/v1/agents/runs", {
      method: "POST",
      headers: adminHeaders(),
      body: JSON.stringify(body),
    }),

  cancelAgentRun: (runId: string): Promise<AgentRun> =>
    apiFetch<AgentRun>(`/api/v1/agents/runs/${encodeURIComponent(runId)}/cancel`, {
      method: "POST",
      headers: adminHeaders(),
    }),

  decideAgentApproval: (runId: string, approvalId: string, decision: "approved" | "rejected", note?: string): Promise<AgentRun> =>
    apiFetch<AgentRun>(`/api/v1/agents/runs/${encodeURIComponent(runId)}/approvals/${encodeURIComponent(approvalId)}`, {
      method: "POST",
      headers: adminHeaders(),
      body: JSON.stringify({ decision, note }),
    }),

  executeAgentApproval: (runId: string, approvalId: string): Promise<AgentRun> =>
    apiFetch<AgentRun>(`/api/v1/agents/runs/${encodeURIComponent(runId)}/approvals/${encodeURIComponent(approvalId)}/execute`, {
      method: "POST",
      headers: adminHeaders(),
    }),

  getOrCreateSupportConversation: (sessionId: string): Promise<SupportConversation> =>
    apiFetch<SupportConversation>("/api/v1/support/conversations/current", {
      method: "POST",
      headers: supportHeaders(sessionId),
    }),

  getSupportConversation: (conversationId: string, sessionId: string): Promise<SupportConversation> =>
    apiFetch<SupportConversation>(
      `/api/v1/support/conversations/${encodeURIComponent(conversationId)}`,
      { headers: supportHeaders(sessionId) },
    ),

  clearSupportConversationHistory: (
    conversationId: string,
    sessionId: string,
  ): Promise<SupportConversation> =>
    apiFetch<SupportConversation>(
      `/api/v1/support/conversations/${encodeURIComponent(conversationId)}/messages`,
      {
        method: "DELETE",
        headers: supportHeaders(sessionId),
      },
    ),

  sendSupportMessage: (
    conversationId: string,
    sessionId: string,
    body: SupportMessageInput,
  ): Promise<SupportConversation> =>
    apiFetch<SupportConversation>(
      `/api/v1/support/conversations/${encodeURIComponent(conversationId)}/messages`,
      {
        method: "POST",
        headers: supportHeaders(sessionId),
        body: JSON.stringify(body),
      },
    ),

  listProjects: (): Promise<ProjectList> =>
    apiFetch<ProjectListResponse>("/api/v1/projects/").then(normalizeProjects),

  getAiReviewProviderStatus: (): Promise<AiReviewProviderStatus> =>
    apiFetch<AiReviewProviderStatus>("/api/v1/ai-reviews/provider-status", {
      headers: adminHeaders(),
    }),

  runAiReview: (projectId: string, body: AiReviewJobRequest = {}): Promise<AiReviewJob> =>
    apiFetch<AiReviewJob>(`/api/v1/ai-reviews/projects/${projectId}`, {
      method: "POST",
      headers: adminHeaders(),
      body: JSON.stringify(body),
    }),

  getAiReviewBaseline: (
    projectId: string,
    params: { scope?: AiReviewScope; integration_id?: string } = {},
  ): Promise<AiReviewBaselineLookup> =>
    apiFetch<AiReviewBaselineLookup>(`/api/v1/ai-reviews/projects/${projectId}/baseline${withQuery(params)}`),

  listAiReviewBaselines: (
    projectId: string,
    params: { scope?: AiReviewScope; integration_id?: string; limit?: number } = {},
  ): Promise<AiReviewBaselineList> =>
    apiFetch<AiReviewBaselineList>(`/api/v1/ai-reviews/projects/${projectId}/baselines${withQuery(params)}`),

  createAiReviewBaseline: (projectId: string, body: AiReviewBaselineRequest = {}): Promise<AiReviewBaseline> =>
    apiFetch<AiReviewBaseline>(`/api/v1/ai-reviews/projects/${projectId}/baseline`, {
      method: "POST",
      headers: adminHeaders(),
      body: JSON.stringify(body),
    }),

  getAiReviewJob: (jobId: string): Promise<AiReviewJob> =>
    apiFetch<AiReviewJob>(`/api/v1/ai-reviews/${jobId}`),

  listAiReviewJobs: (projectId: string): Promise<AiReviewJobList> =>
    apiFetch<AiReviewJobList>(`/api/v1/ai-reviews/projects/${projectId}/jobs`, {
      headers: adminHeaders(),
    }),

  compareAiReviewJobs: (
    projectId: string,
    params: { base_job_id: string; target_job_id: string },
  ): Promise<AiReviewJobCompare> =>
    apiFetch<AiReviewJobCompare>(`/api/v1/ai-reviews/projects/${projectId}/jobs/compare${withQuery(params)}`, {
      headers: adminHeaders(),
    }),

  acceptAiReviewFinding: (jobId: string, findingId: string, note?: string): Promise<AiReviewJob> =>
    apiFetch<AiReviewJob>(`/api/v1/ai-reviews/${jobId}/findings/${findingId}/accept`, {
      method: "POST",
      headers: adminHeaders(),
      body: JSON.stringify({ note }),
    }),

  applyAiReviewFindingPatch: (
    jobId: string,
    findingId: string,
    note?: string,
  ): Promise<AiReviewApplyPatchResponse> =>
    apiFetch<AiReviewApplyPatchResponse>(`/api/v1/ai-reviews/${jobId}/findings/${findingId}/apply-patch`, {
      method: "POST",
      headers: adminHeaders(),
      body: JSON.stringify({ note }),
    }),

  selectAiReviewCandidateForDraft: (
    jobId: string,
    candidateId: string,
    note?: string,
  ): Promise<AiReviewSelectDraftResponse> =>
    apiFetch<AiReviewSelectDraftResponse>(
      `/api/v1/ai-reviews/${jobId}/recommendations/${candidateId}/select-draft`,
      {
        method: "POST",
        headers: adminHeaders(),
        body: JSON.stringify({ note }),
      },
    ),

  simulateAiReviewCanvasDraft: (
    projectId: string,
    integrationId: string,
    body: { core_tools: string[]; canvas_state: string; deployment_scenario_id?: string },
  ): Promise<AiReviewDraftSimulation> =>
    apiFetch<AiReviewDraftSimulation>(
      `/api/v1/ai-reviews/projects/${projectId}/integrations/${integrationId}/simulate-draft`,
      {
        method: "POST",
        headers: adminHeaders(),
        body: JSON.stringify(body),
      },
    ),

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

  saveImportMappingReview: (
    projectId: string,
    batchId: string,
    body: ImportMappingReviewRequest,
  ): Promise<ImportBatch> =>
    apiFetch<ImportBatch>(`/api/v1/imports/${projectId}/${batchId}/mapping-review`, {
      method: "PATCH",
      headers: adminHeaders(),
      body: JSON.stringify(body),
    }),

  approveImportMappingReview: (
    projectId: string,
    batchId: string,
    body: ImportMappingReviewApprovalRequest,
  ): Promise<ImportBatch> =>
    apiFetch<ImportBatch>(`/api/v1/imports/${projectId}/${batchId}/mapping-review/approve`, {
      method: "POST",
      headers: adminHeaders(),
      body: JSON.stringify(body),
    }),

  listImportMappingProfiles: (projectId: string): Promise<ImportMappingProfileListResponse> =>
    apiFetch<ImportMappingProfileListResponse>(`/api/v1/imports/${projectId}/mapping-profiles`),

  getImportQualityAssistant: (projectId: string, batchId: string): Promise<ImportQualityAssistant> =>
    apiFetch<ImportQualityAssistant>(`/api/v1/imports/${projectId}/${batchId}/quality-assistant`),

  runImportQualityAgent: (projectId: string, batchId: string): Promise<AgentRun> =>
    apiFetch<AgentRun>(`/api/v1/imports/${projectId}/${batchId}/quality-agent`, {
      method: "POST",
      headers: adminHeaders(),
    }),

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

  getCatalogFacets: (projectId: string): Promise<CatalogFacets> =>
    apiFetch<CatalogFacets>(`/api/v1/catalog/${projectId}/facets`),

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

  getCaptureTemplateMetadata: (): Promise<CaptureTemplateMetadata> =>
    apiFetch<CaptureTemplateMetadata>("/api/v1/exports/template/metadata"),

  listServiceProducts: (): Promise<ServiceProductList> =>
    apiFetch<ServiceProductList>("/api/v1/service-products"),

  getServiceProduct: (serviceId: string): Promise<ServiceProductDetail> =>
    apiFetch<ServiceProductDetail>(`/api/v1/service-products/${encodeURIComponent(serviceId)}`),

  getServiceInteroperabilityMatrix: (): Promise<ServiceInteroperabilityMatrix> =>
    apiFetch<ServiceInteroperabilityMatrix>("/api/v1/service-products/matrix"),

  listServiceVerificationJobs: (params: { limit?: number } = {}): Promise<ServiceVerificationJobList> =>
    apiFetch<ServiceVerificationJobList>(`/api/v1/service-products/verification-jobs${withQuery(params)}`),

  getServiceVerificationJob: (jobId: string): Promise<ServiceVerificationJob> =>
    apiFetch<ServiceVerificationJob>(`/api/v1/service-products/verification-jobs/${encodeURIComponent(jobId)}`),

  listServiceVerificationAlerts: (params: { limit?: number } = {}): Promise<ServiceVerificationAlertList> =>
    apiFetch<ServiceVerificationAlertList>(`/api/v1/service-products/verification-alerts${withQuery(params)}`),

  runServiceVerificationJob: (body: ServiceVerificationRunRequest = {}): Promise<ServiceVerificationJob> =>
    apiFetch<ServiceVerificationJob>("/api/v1/service-products/verification-jobs", {
      method: "POST",
      headers: adminHeaders(),
      body: JSON.stringify(body),
    }),

  listServiceVerificationFindings: (jobId: string): Promise<ServiceVerificationFinding[]> =>
    apiFetch<ServiceVerificationFinding[]>(
      `/api/v1/service-products/verification-jobs/${encodeURIComponent(jobId)}/findings`,
    ),

  reviewServiceVerificationFinding: (
    jobId: string,
    findingId: string,
    body: ServiceVerificationFindingReviewRequest,
  ): Promise<ServiceVerificationFinding> =>
    apiFetch<ServiceVerificationFinding>(
      `/api/v1/service-products/verification-jobs/${encodeURIComponent(jobId)}/findings/${encodeURIComponent(findingId)}/review`,
      {
        method: "POST",
        headers: adminHeaders(),
        body: JSON.stringify(body),
      },
    ),

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

  listDictionaryOptions: (category: string, includeInactive = false): Promise<DictionaryOptionList> =>
    apiFetch<DictionaryOptionList>(
      `/api/v1/dictionaries/${category}${includeInactive ? "?include_inactive=true" : ""}`,
    ),

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

  listSyntheticPresets: (): Promise<SyntheticGenerationPresetList> =>
    apiFetch<SyntheticGenerationPresetList>("/api/v1/admin/synthetic/presets", {
      headers: adminHeaders(),
    }),

  listSyntheticJobs: (params: { limit?: number } = {}): Promise<SyntheticGenerationJobList> =>
    apiFetch<SyntheticGenerationJobList>(`/api/v1/admin/synthetic/jobs${withQuery(params)}`, {
      headers: adminHeaders(),
    }),

  createSyntheticJob: (body: SyntheticGenerationJobRequest): Promise<SyntheticGenerationJob> =>
    apiFetch<SyntheticGenerationJob>("/api/v1/admin/synthetic/jobs", {
      method: "POST",
      headers: adminHeaders(),
      body: JSON.stringify(body),
    }),

  getSyntheticJob: (jobId: string): Promise<SyntheticGenerationJob> =>
    apiFetch<SyntheticGenerationJob>(`/api/v1/admin/synthetic/jobs/${jobId}`, {
      headers: adminHeaders(),
    }),

  retrySyntheticJob: (jobId: string): Promise<SyntheticGenerationJob> =>
    apiFetch<SyntheticGenerationJob>(`/api/v1/admin/synthetic/jobs/${jobId}/retry`, {
      method: "POST",
      headers: adminHeaders(),
    }),

  cleanupSyntheticJob: (jobId: string): Promise<SyntheticGenerationJob> =>
    apiFetch<SyntheticGenerationJob>(`/api/v1/admin/synthetic/jobs/${jobId}/cleanup`, {
      method: "POST",
      headers: adminHeaders(),
    }),

  listPriceSources: (): Promise<PriceSourceList> =>
    apiFetch<PriceSourceList>("/api/v1/pricing/sources", { headers: adminHeaders() }),

  getCommercialCatalog: (
    params: { document_id?: string; search?: string; limit?: number } = {},
  ): Promise<CommercialWorkspace> =>
    apiFetch<CommercialWorkspace>(`/api/v1/pricing/commercial-catalog${withQuery(params)}`, {
      headers: adminHeaders(),
    }),

  importCommercialDocument: async (file: File): Promise<CommercialWorkspace> => {
    const formData = new FormData();
    formData.append("file", file);
    return apiFetch<CommercialWorkspace>("/api/v1/pricing/commercial-documents", {
      method: "POST",
      headers: adminHeaders(),
      body: formData,
    });
  },

  approveCommercialDocument: (documentId: string): Promise<CommercialWorkspace> =>
    apiFetch<CommercialWorkspace>(
      `/api/v1/pricing/commercial-documents/${encodeURIComponent(documentId)}/approve`,
      { method: "POST", headers: adminHeaders() },
    ),

  finalizeCommercialCatalogReview: (
    documentId: string,
    body: CommercialCatalogFinalizeRequest,
  ): Promise<CommercialWorkspace> =>
    apiFetch<CommercialWorkspace>(
      `/api/v1/pricing/commercial-documents/${encodeURIComponent(documentId)}/finalize-review`,
      { method: "POST", headers: adminHeaders(), body: JSON.stringify(body) },
    ),

  reviewCommercialCandidate: (
    candidateId: string,
    body: CommercialCandidateReviewRequest,
  ): Promise<CommercialWorkspace> =>
    apiFetch<CommercialWorkspace>(
      `/api/v1/pricing/commercial-candidates/${encodeURIComponent(candidateId)}/review`,
      { method: "POST", headers: adminHeaders(), body: JSON.stringify(body) },
    ),

  revalidateCommercialCandidate: (candidateId: string): Promise<CommercialWorkspace> =>
    apiFetch<CommercialWorkspace>(
      `/api/v1/pricing/commercial-candidates/${encodeURIComponent(candidateId)}/revalidate`,
      { method: "POST", headers: adminHeaders() },
    ),

  reviewCommercialException: (
    exceptionId: string,
    body: CommercialExceptionReviewRequest,
  ): Promise<CommercialWorkspace> =>
    apiFetch<CommercialWorkspace>(
      `/api/v1/pricing/commercial-exceptions/${encodeURIComponent(exceptionId)}/review`,
      { method: "POST", headers: adminHeaders(), body: JSON.stringify(body) },
    ),

  promoteCommercialRelease: (documentId: string): Promise<CommercialWorkspace> =>
    apiFetch<CommercialWorkspace>(
      `/api/v1/pricing/commercial-documents/${encodeURIComponent(documentId)}/releases`,
      { method: "POST", headers: adminHeaders() },
    ),

  createPriceSyncJob: (body: { source_id?: string; currency: string }): Promise<PriceSyncJob> =>
    apiFetch<PriceSyncJob>("/api/v1/pricing/sync-jobs", {
      method: "POST",
      headers: adminHeaders(),
      body: JSON.stringify(body),
    }),

  listPriceSyncJobs: (limit = 20): Promise<PriceSyncJobList> =>
    apiFetch<PriceSyncJobList>(`/api/v1/pricing/sync-jobs${withQuery({ limit })}`, {
      headers: adminHeaders(),
    }),

  getPriceSyncJob: (jobId: string): Promise<PriceSyncJob> =>
    apiFetch<PriceSyncJob>(`/api/v1/pricing/sync-jobs/${encodeURIComponent(jobId)}`, {
      headers: adminHeaders(),
    }),

  listGovernanceChangeSets: (limit = 20): Promise<GovernanceChangeSetList> =>
    apiFetch<GovernanceChangeSetList>(
      `/api/v1/pricing/governance-change-sets${withQuery({ limit })}`,
      { headers: adminHeaders() },
    ),

  getGovernanceChangeSet: (changeSetId: string): Promise<GovernanceChangeSet> =>
    apiFetch<GovernanceChangeSet>(
      `/api/v1/pricing/governance-change-sets/${encodeURIComponent(changeSetId)}`,
      { headers: adminHeaders() },
    ),

  listPriceCatalogSnapshots: (limit = 20): Promise<PriceCatalogSnapshotList> =>
    apiFetch<PriceCatalogSnapshotList>(`/api/v1/pricing/catalog-snapshots${withQuery({ limit })}`, {
      headers: adminHeaders(),
    }),

  approvePriceCatalogSnapshot: (snapshotId: string): Promise<PriceCatalogSnapshot> =>
    apiFetch<PriceCatalogSnapshot>(
      `/api/v1/pricing/catalog-snapshots/${encodeURIComponent(snapshotId)}/approve`,
      { method: "POST", headers: adminHeaders() },
    ),

  listPriceItems: (
    snapshotId: string,
    params: { search?: string; page?: number; page_size?: number } = {},
  ): Promise<PriceItemList> =>
    apiFetch<PriceItemList>(
      `/api/v1/pricing/catalog-snapshots/${encodeURIComponent(snapshotId)}/items${withQuery(params)}`,
      { headers: adminHeaders() },
    ),

  importPriceRateCard: async (file: File, name: string, currency: string): Promise<PriceCatalogSnapshot> => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("name", name);
    formData.append("currency", currency);
    return apiFetch<PriceCatalogSnapshot>("/api/v1/pricing/rate-card-imports", {
      method: "POST",
      headers: adminHeaders(),
      body: formData,
    });
  },

  listSkuMappings: (): Promise<SkuMappingList> =>
    apiFetch<SkuMappingList>("/api/v1/pricing/sku-mappings", { headers: adminHeaders() }),

  patchSkuMapping: (mappingId: string, body: SkuMappingPatch): Promise<SkuMapping> =>
    apiFetch<SkuMapping>(`/api/v1/pricing/sku-mappings/${encodeURIComponent(mappingId)}`, {
      method: "PATCH",
      headers: adminHeaders(),
      body: JSON.stringify(body),
    }),

  listDeploymentScenarios: (projectId: string): Promise<DeploymentScenarioList> =>
    apiFetch<DeploymentScenarioList>(`/api/v1/projects/${projectId}/deployment-scenarios`, {
      headers: adminHeaders(),
    }),

  getDeploymentScenarioAssistant: (projectId: string, includeLlm = false): Promise<ScenarioAssistant> =>
    apiFetch<ScenarioAssistant>(
      `/api/v1/projects/${projectId}/deployment-scenarios/assistant${withQuery({ include_llm: String(includeLlm) })}`,
      { headers: adminHeaders() },
    ),

  runBomScenarioAgent: (projectId: string): Promise<AgentRun> =>
    apiFetch<AgentRun>(`/api/v1/projects/${projectId}/deployment-scenarios/agent`, {
      method: "POST",
      headers: adminHeaders(),
    }),

  createDeploymentScenario: (
    projectId: string,
    body: DeploymentScenarioCreate,
  ): Promise<DeploymentScenario> =>
    apiFetch<DeploymentScenario>(`/api/v1/projects/${projectId}/deployment-scenarios`, {
      method: "POST",
      headers: adminHeaders(),
      body: JSON.stringify(body),
    }),

  approveDeploymentScenario: (projectId: string, scenarioId: string): Promise<DeploymentScenario> =>
    apiFetch<DeploymentScenario>(
      `/api/v1/projects/${projectId}/deployment-scenarios/${encodeURIComponent(scenarioId)}/approve`,
      { method: "POST", headers: adminHeaders() },
    ),

  createBomJob: (projectId: string, scenarioId: string): Promise<BomJob> =>
    apiFetch<BomJob>(`/api/v1/projects/${projectId}/bom-jobs`, {
      method: "POST",
      headers: adminHeaders(),
      body: JSON.stringify({ scenario_id: scenarioId }),
    }),

  listBomJobs: (projectId: string, limit = 20): Promise<BomJobList> =>
    apiFetch<BomJobList>(`/api/v1/projects/${projectId}/bom-jobs${withQuery({ limit })}`, {
      headers: adminHeaders(),
    }),

  getBomJob: (projectId: string, jobId: string): Promise<BomJob> =>
    apiFetch<BomJob>(`/api/v1/projects/${projectId}/bom-jobs/${encodeURIComponent(jobId)}`, {
      headers: adminHeaders(),
    }),

  listBomSnapshots: (projectId: string, limit = 20): Promise<BomSnapshotList> =>
    apiFetch<BomSnapshotList>(`/api/v1/projects/${projectId}/bom-snapshots${withQuery({ limit })}`, {
      headers: adminHeaders(),
    }),

  getBomSnapshot: (projectId: string, snapshotId: string): Promise<BomSnapshot> =>
    apiFetch<BomSnapshot>(
      `/api/v1/projects/${projectId}/bom-snapshots/${encodeURIComponent(snapshotId)}`,
      { headers: adminHeaders() },
    ),

  compareBomSnapshots: (
    projectId: string,
    baselineId: string,
    comparisonId: string,
  ): Promise<BomComparison> =>
    apiFetch<BomComparison>(
      `/api/v1/projects/${projectId}/bom-snapshots/compare${withQuery({ baseline_id: baselineId, comparison_id: comparisonId })}`,
      { headers: adminHeaders() },
    ),

  reviewBomSnapshot: (
    projectId: string,
    snapshotId: string,
    publicationStatus: "approved" | "published",
    note?: string,
  ): Promise<BomSnapshot> =>
    apiFetch<BomSnapshot>(
      `/api/v1/projects/${projectId}/bom-snapshots/${encodeURIComponent(snapshotId)}/review`,
      {
        method: "POST",
        headers: adminHeaders(),
        body: JSON.stringify({ publication_status: publicationStatus, note }),
      },
    ),
};
