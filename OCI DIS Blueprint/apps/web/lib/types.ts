/* TypeScript contracts for the OCI DIS Blueprint frontend. */

export interface Project {
  id: string;
  name: string;
  owner_id: string;
  description: string | null;
  status: string;
  project_metadata: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectList {
  projects: Project[];
  total: number;
}

export interface ProjectListResponse {
  projects: Project[];
}

export interface ProjectArchiveResponse {
  project: Project;
  detail: string;
}

export interface ProjectDeleteResponse {
  project_id: string;
  detail: string;
  deleted_import_batches: number;
  deleted_source_rows: number;
  deleted_integrations: number;
  deleted_justifications: number;
  deleted_volumetry_snapshots: number;
  deleted_dashboard_snapshots: number;
  deleted_audit_events: number;
}

export type AgentType =
  | "architecture_review"
  | "service_verification"
  | "import_quality"
  | "integration_design"
  | "topology_investigation"
  | "bom_scenario"
  | "support_assistant";
export type AgentRunStatus = "pending" | "running" | "waiting_approval" | "completed" | "failed" | "cancelled";

export interface AgentDefinition {
  type: AgentType;
  version: string;
  name: string;
  description: string;
  location: string;
  tools: string[];
  allowed_roles: string[];
  mutates_data: boolean;
  requires_project: boolean;
}

export interface AgentProviderStatus {
  provider: "oci_genai";
  model: string;
  region: string;
  endpoint: string;
  api_key_configured: boolean;
  project_configured: boolean;
  function_calling_available: boolean;
  transport_strategy: string;
  responses_capability: string;
  guardrails_enabled: boolean;
  guardrails_version: string;
  max_retries: number;
  runtime: "docker_celery_agents_queue";
  status_message: string;
}

export interface AgentStep {
  id: string;
  sequence: number;
  step_type: string;
  tool_name: string | null;
  status: string;
  output_summary: string | null;
  opc_request_id: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface AgentApproval {
  id: string;
  action_type: string;
  status: string;
  proposed_payload: Record<string, unknown>;
  reviewed_by: string | null;
  review_note: string | null;
  reviewed_at: string | null;
}

export interface AgentRun {
  id: string;
  agent_type: AgentType;
  definition_version: string;
  project_id: string | null;
  integration_id: string | null;
  requested_by: string;
  status: AgentRunStatus;
  context: Record<string, unknown>;
  result: { summary?: string; evidence?: unknown; provider_status?: string; authority?: string } | null;
  error: Record<string, unknown> | null;
  model: string | null;
  provider_response_id: string | null;
  opc_request_id: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  step_count: number;
  max_steps: number;
  cancel_requested: boolean;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
  steps: AgentStep[];
  approvals: AgentApproval[];
}

export interface AgentRunList {
  runs: AgentRun[];
  total: number;
}

export interface AgentRunRequest {
  agent_type: AgentType;
  project_id?: string;
  integration_id?: string;
  context?: Record<string, unknown>;
  message?: string;
  include_provider?: boolean;
}

export type SupportAttachmentType =
  | "page"
  | "project"
  | "integration"
  | "catalog"
  | "topology"
  | "canvas"
  | "import"
  | "bom"
  | "admin";

export interface SupportAttachmentInput {
  attachment_type: SupportAttachmentType;
  label: string;
  entity_id?: string;
  href: string;
  context: Record<string, unknown>;
}

export interface SupportAttachment extends Omit<SupportAttachmentInput, "entity_id"> {
  id: string;
  entity_id: string | null;
}

export interface SupportMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  status: "pending" | "completed" | "failed" | "refused";
  agent_run_id: string | null;
  context: Record<string, unknown>;
  citations: Array<{ label: string; href: string }>;
  attachments: SupportAttachment[];
  created_at: string;
}

export interface SupportConversation {
  id: string;
  title: string;
  status: "active" | "archived";
  messages: SupportMessage[];
  created_at: string;
  updated_at: string;
}

export interface SupportMessageInput {
  content: string;
  route: string;
  page_title: string;
  project_id?: string;
  integration_id?: string;
  attachments: SupportAttachmentInput[];
}

export type AiReviewSeverity = "critical" | "high" | "medium" | "low" | "positive";
export type AiReviewScope = "project" | "integration";
export type AiReviewJobStatus = "pending" | "running" | "completed" | "failed";
export type AiReviewGraphContext =
  | { type: "node"; label: string; source?: never; target?: never }
  | { type: "edge"; source: string; target: string; label?: never };
export type AiReviewCategory =
  | "critical_blockers"
  | "high_confidence_fixes"
  | "needs_architect_decision"
  | "looks_production_ready";

export interface AiReviewMetric {
  label: string;
  value: string;
  detail: string;
}

export interface AiReviewQuotaState {
  daily_job_limit: number;
  actor_jobs_today: number;
  remaining_jobs_today: number;
  llm_daily_job_limit: number;
}

export interface AiReviewProviderStatus {
  provider: "oci_genai";
  configured: boolean;
  mode: "deterministic_only" | "llm_configured" | "llm_available" | "llm_degraded" | "misconfigured";
  model: string;
  transport: string;
  transport_strategy: {
    preferred: "responses";
    fallback: "chat_completions";
    configured_mode: string;
    responses_capability: "available" | "unavailable" | "unverified" | "disabled";
  };
  region: string;
  auth_mode: "api_key";
  endpoint: string;
  request_timeout_seconds: number;
  retry_policy: {
    max_retries: number;
    strategy: "exponential_full_jitter";
    retryable_status_codes: number[];
    respects_retry_after: boolean;
  };
  safety: {
    safety_identifier: "hmac_sha256";
    guardrails_enabled: boolean;
    guardrails_version: string;
    guardrails_failure_mode: string;
    input_protections: string[];
    output_protections: string[];
  };
  quota: AiReviewQuotaState;
  data_retention_policy: string;
  prompt_redaction_policy: string[];
  status_message: string;
}

export interface AiReviewDecisionBrief {
  signoff_status: "blocked" | "needs_review" | "ready_with_caveats" | "ready";
  headline: string;
  primary_risk: string;
  recommended_next_action: string;
  decision_points: string[];
  blockers: string[];
}

export interface AiReviewTopologyInsight {
  id: string;
  insight_type: "system_hotspot" | "edge_hotspot" | "payload_hotspot";
  severity: Exclude<AiReviewSeverity, "critical">;
  title: string;
  summary: string;
  metric: string;
  system_name: string | null;
  source_system: string | null;
  destination_system: string | null;
  action_href: string | null;
  integration_ids: string[];
}

export interface AiReviewStressScenario {
  id: string;
  name: string;
  multiplier: number;
  confidence: "high" | "medium" | "low";
  summary: string;
  projected_daily_payload_gb: number;
  top_integration_ids: string[];
  warnings: string[];
}

export interface AiReviewRemediationStep {
  id: string;
  priority: number;
  owner: "Architect" | "Analyst" | "Operations" | "Executive";
  title: string;
  action: string;
  expected_impact: string;
  action_href: string | null;
  finding_ids: string[];
  integration_ids: string[];
}

export interface AiReviewEvidence {
  id: string;
  label: string;
  detail: string;
  source: string;
  entity_type: string;
  entity_id: string | null;
  href: string | null;
}

export interface AiReviewFinding {
  id: string;
  severity: AiReviewSeverity;
  category: AiReviewCategory;
  review_area:
    | "data_quality"
    | "snapshot_freshness"
    | "canvas_consistency"
    | "oci_compatibility"
    | "stress_review"
    | "planned_drift"
    | "demo_readiness"
    | "red_team"
    | "governance";
  title: string;
  summary: string;
  evidence_ids: string[];
  evidence: string[];
  current_state: string;
  recommended_state: string;
  recommendation: string;
  action_label: string;
  action_href: string | null;
  integration_ids: string[];
  suggested_patch: AiReviewSuggestedPatch | null;
}

export interface AiReviewGroup {
  id: AiReviewCategory;
  title: string;
  description: string;
  finding_ids: string[];
  count: number;
  worst_severity: AiReviewSeverity | null;
}

export interface AiReviewPersonaSummary {
  persona: "architect" | "security" | "operations" | "executive";
  title: string;
  summary: string;
  focus: string[];
}

export interface AiReviewFieldDiff {
  field: string;
  current: string | null;
  recommended: string | null;
}

export interface AiReviewSuggestedPatch {
  integration_id: string;
  label: string;
  description: string;
  patch: Record<string, unknown>;
  field_diffs: AiReviewFieldDiff[];
  safe_to_apply: boolean;
  safety_note: string;
}

export type AiReviewDriftStatus =
  | "no_baseline"
  | "no_drift"
  | "minor_drift"
  | "material_drift"
  | "blocking_drift";

export interface AiReviewBaseline {
  id: string;
  project_id: string;
  scope: AiReviewScope;
  integration_id: string | null;
  created_by: string;
  label: string;
  note: string | null;
  row_count: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface AiReviewBaselineLookup {
  baseline: AiReviewBaseline | null;
}

export interface AiReviewBaselineList {
  baselines: AiReviewBaseline[];
  total: number;
}

export interface AiReviewBaselineRequest {
  scope?: AiReviewScope;
  integration_id?: string;
  label?: string;
  note?: string;
}

export interface AiReviewDriftItem {
  id: string;
  severity: Exclude<AiReviewSeverity, "positive">;
  entity_type: "project" | "integration";
  integration_id: string | null;
  field: string;
  label: string;
  planned: string | null;
  actual: string | null;
  detail: string;
  action_href: string | null;
}

export interface AiReviewDriftReport {
  status: AiReviewDriftStatus;
  baseline: AiReviewBaseline | null;
  item_count: number;
  worst_severity: Exclude<AiReviewSeverity, "positive"> | null;
  summary: string;
  items: AiReviewDriftItem[];
}

export interface AiReviewResponse {
  project_id: string;
  project_name: string;
  scope: AiReviewScope;
  integration_id: string | null;
  engine: string;
  generated_at: string;
  readiness_score: number;
  readiness_label: string;
  summary: string;
  llm_status: "not_configured" | "completed" | "failed" | "skipped";
  llm_model: string | null;
  llm_summary: string | null;
  graph_context: AiReviewGraphContext | null;
  metrics: AiReviewMetric[];
  decision_brief: AiReviewDecisionBrief;
  topology_insights: AiReviewTopologyInsight[];
  stress_scenarios: AiReviewStressScenario[];
  remediation_plan: AiReviewRemediationStep[];
  findings: AiReviewFinding[];
  groups: AiReviewGroup[];
  evidence: AiReviewEvidence[];
  evidence_pack: string[];
  reviewer_personas: AiReviewPersonaSummary[];
  drift: AiReviewDriftReport;
}

export interface AiReviewJobRequest {
  scope?: AiReviewScope;
  integration_id?: string;
  include_llm?: boolean;
  graph_context?: AiReviewGraphContext;
  reviewer_personas?: Array<"architect" | "security" | "operations" | "executive">;
}

export interface AiReviewRecommendationAcceptance {
  finding_id: string;
  accepted_by: string;
  accepted_at: string;
  note: string | null;
  applied_patch: AiReviewSuggestedPatch | null;
}

export interface AiReviewJob {
  id: string;
  project_id: string;
  requested_by: string;
  status: AiReviewJobStatus;
  scope: AiReviewScope;
  integration_id: string | null;
  input_payload: Record<string, unknown>;
  result: AiReviewResponse | null;
  accepted_recommendations: AiReviewRecommendationAcceptance[];
  error_details: Record<string, unknown> | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AiReviewJobList {
  jobs: AiReviewJob[];
  total: number;
}

export interface AiReviewJobCompare {
  project_id: string;
  base_job_id: string;
  target_job_id: string;
  base_readiness_score: number;
  target_readiness_score: number;
  readiness_score_delta: number;
  base_readiness_label: string;
  target_readiness_label: string;
  finding_count_delta: number;
  critical_high_delta: number;
  added_findings: string[];
  resolved_findings: string[];
  persistent_findings: string[];
  summary: string;
}

export interface AiReviewApplyPatchResponse {
  job: AiReviewJob;
  integration: Integration;
  applied_patch: AiReviewSuggestedPatch;
}

export interface SyntheticGenerationPreset {
  code: string;
  label: string;
  description: string;
  project_name: string;
  seed_value: number;
  target_catalog_size: number;
  min_distinct_systems: number;
  import_target: number;
  manual_target: number;
  excluded_import_target: number;
  include_justifications: boolean;
  include_exports: boolean;
  include_design_warnings: boolean;
  cleanup_policy: "manual" | "ephemeral_auto_cleanup";
}

export interface SyntheticGenerationPresetList {
  presets: SyntheticGenerationPreset[];
}

export interface SyntheticGenerationJobRequest {
  project_name?: string;
  preset_code?: string;
  target_catalog_size?: number;
  min_distinct_systems?: number;
  import_target?: number;
  manual_target?: number;
  excluded_import_target?: number;
  include_justifications?: boolean;
  include_exports?: boolean;
  include_design_warnings?: boolean;
  cleanup_policy?: "manual" | "ephemeral_auto_cleanup";
  seed_value?: number;
}

export interface SyntheticArtifactExportJob {
  job_id: string;
  filename: string;
  download_url: string;
  file_path: string;
  job_file_path?: string | null;
}

export interface SyntheticArtifactManifest {
  workbook_path: string;
  report_json_path: string;
  report_markdown_path: string;
  export_jobs: Record<string, SyntheticArtifactExportJob>;
}

export interface SyntheticGenerationJob {
  id: string;
  requested_by: string;
  status: string;
  preset_code: string;
  input_payload: Record<string, unknown>;
  normalized_payload: Record<string, unknown>;
  project_id: string | null;
  project_name: string | null;
  seed_value: number;
  catalog_target: number;
  manual_target: number;
  import_target: number;
  excluded_import_target: number;
  result_summary: Record<string, unknown> | null;
  validation_results: Record<string, unknown> | null;
  artifact_manifest: SyntheticArtifactManifest | null;
  error_details: Record<string, unknown> | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface SyntheticGenerationJobList {
  jobs: SyntheticGenerationJob[];
  total: number;
}

export interface ImportBatch {
  id: string;
  project_id: string;
  filename: string;
  parser_version: string;
  status: "pending" | "processing" | "completed" | "failed";
  loaded_count: number | null;
  excluded_count: number | null;
  tbq_y_count: number | null;
  source_row_count: number | null;
  header_map: Record<string, string> | null;
  error_details: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface ImportBatchListResponse {
  import_batches: ImportBatch[];
}

export interface ImportBatchList {
  batches: ImportBatch[];
  total: number;
}

export interface ImportBatchDeleteResponse {
  project_id: string;
  batch_id: string;
  detail: string;
  deleted_source_rows: number;
  deleted_integrations: number;
  deleted_justifications: number;
  recalculated_snapshot_id: string | null;
}

export interface NormalizationEvent {
  field: string;
  old_value: unknown;
  new_value: unknown;
  rule: string;
}

export interface SourceRow {
  id: string;
  source_row_number: number;
  included: boolean;
  exclusion_reason: string | null;
  raw_data: Record<string, unknown>;
  normalization_events: NormalizationEvent[];
}

export interface SourceRowList {
  rows: SourceRow[];
  total: number;
  page: number;
  page_size: number;
}

export interface ImportQualityMetric {
  label: string;
  value: string;
  detail: string;
}

export interface ImportQualityFinding {
  severity: string;
  title: string;
  summary: string;
  action_label: string;
  action_href: string;
}

export interface ImportQualityAssistant {
  project_id: string;
  batch_id: string;
  status: string;
  filename: string;
  row_count: number;
  included_count: number;
  excluded_count: number;
  normalization_event_count: number;
  recommended_next_action: string;
  metrics: ImportQualityMetric[];
  findings: ImportQualityFinding[];
}

export interface Integration {
  id: string;
  project_id: string;
  source_row_id: string | null;
  seq_number: number;
  interface_id: string | null;
  owner: string | null;
  brand: string | null;
  business_process: string | null;
  interface_name: string | null;
  description: string | null;
  status: string | null;
  mapping_status: string | null;
  initial_scope: string | null;
  complexity: string | null;
  frequency: string | null;
  type: string | null;
  base: string | null;
  interface_status: string | null;
  is_real_time: boolean | null;
  trigger_type: string | null;
  response_size_kb: number | null;
  payload_per_execution_kb: number | null;
  is_fan_out: boolean | null;
  fan_out_targets: number | null;
  source_system: string | null;
  source_technology: string | null;
  source_api_reference: string | null;
  source_owner: string | null;
  destination_system: string | null;
  destination_technology_1: string | null;
  destination_technology_2: string | null;
  destination_owner: string | null;
  executions_per_day: number | null;
  payload_per_hour_kb: number | null;
  selected_pattern: string | null;
  pattern_rationale: string | null;
  comments: string | null;
  retry_policy: string | null;
  core_tools: string | null;
  additional_tools_overlays: string | null;
  qa_status: "OK" | "REVISAR" | "PENDING" | string | null;
  qa_reasons: string[];
  calendarization: string | null;
  uncertainty: string | null;
  created_at: string;
  updated_at: string;
}

export interface LineageDetail {
  source_row_id: string;
  source_row_number: number;
  raw_data: Record<string, unknown>;
  column_names: Record<string, string>;
  included: boolean;
  exclusion_reason: string | null;
  normalization_events: NormalizationEvent[];
  import_batch_id: string;
  import_batch_date: string;
  import_filename: string;
}

export interface CatalogIntegrationDetail {
  integration: Integration;
  lineage: LineageDetail;
}

export interface IntegrationPatch {
  selected_pattern?: string;
  pattern_rationale?: string;
  comments?: string;
  retry_policy?: string;
  core_tools?: string[];
  additional_tools_overlays?: string;
  raw_column_values?: Record<string, unknown>;
}

export interface CatalogPage {
  integrations: Integration[];
  total: number;
  page: number;
  page_size: number;
}

export interface CatalogFacets {
  brands: string[];
}

export interface CatalogIntegrationDeleteResponse {
  project_id: string;
  integration_id: string;
  detail: string;
  deleted_source_row_id: string | null;
  deleted_import_batch_id: string | null;
  deleted_justification_id: string | null;
  recalculated_snapshot_id: string | null;
}

export interface CatalogParams {
  page?: number;
  page_size?: number;
  qa_status?: string;
  search?: string;
  pattern?: string;
  brand?: string;
  source_system?: string;
  destination_system?: string;
}

export interface PatternDefinition {
  id: string;
  pattern_id: string;
  name: string;
  category: string;
  description: string | null;
  oci_components: string | null;
  when_to_use: string | null;
  when_not_to_use: string | null;
  technical_flow: string | null;
  business_value: string | null;
  applicability_examples: string[];
  selection_questions: string[];
  required_inputs: string[];
  is_active: boolean;
  version: string;
  is_system: boolean;
  support: {
    level: "full" | "partial" | "reference";
    badge_label: string;
    summary: string;
    parity_ready: boolean;
    dimensions: {
      capture_selection: boolean;
      qa_validation: boolean;
      volumetry: boolean;
      dashboard: boolean;
      narratives: boolean;
      exports: boolean;
    };
  };
  created_at: string;
  updated_at: string;
}

export interface PatternList {
  patterns: PatternDefinition[];
  total: number;
}

export interface CanvasServiceProfile {
  id: string;
  service_id: string;
  name: string;
  category: string;
  sla_uptime_pct: number | null;
  pricing_model: string | null;
  limits: Record<string, unknown>;
  summary: string | null;
  architecture_role: string | null;
}

export interface ServiceProductVersion {
  id: string;
  version_label: string;
  description: string | null;
  capabilities: Record<string, unknown>;
  use_cases: unknown[];
  anti_patterns: unknown[];
  regional_availability: string | null;
  commercial_notes: string | null;
  security_notes: string | null;
  deprecation_notes: string | null;
  metadata: Record<string, unknown>;
  effective_from: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface ServiceLimit {
  id: string;
  limit_key: string;
  label: string;
  scope: string;
  limit_type: string;
  value: unknown;
  unit: string | null;
  default_value: unknown | null;
  can_request_increase: boolean;
  source_url: string | null;
  source_retrieved_at: string | null;
  confidence: number;
  notes: string | null;
  is_active: boolean;
  updated_at: string;
}

export interface ServiceEvidenceSource {
  id: string;
  source_type: string;
  url: string;
  title: string;
  publisher: string;
  trust_tier: string;
  retrieval_strategy: string;
  expected_update_frequency_days: number;
  last_checked_at: string | null;
  last_changed_at: string | null;
  content_hash: string | null;
  status: string;
  updated_at: string;
}

export interface ServiceInteroperabilityRule {
  id: string;
  source_service_id: string;
  source_service_name: string;
  target_service_id: string;
  target_service_name: string;
  relationship_type: string;
  supported: boolean;
  directionality: string;
  patterns: unknown[];
  required_components: unknown[];
  constraints: Record<string, unknown>;
  risk_notes: string | null;
  source_url: string | null;
  confidence: number;
  last_verified_at: string | null;
  is_active: boolean;
  updated_at: string;
}

export interface ServiceProductSummary {
  id: string;
  service_id: string;
  name: string;
  category: string;
  architecture_role: string | null;
  summary: string | null;
  pricing_model: string | null;
  sla_uptime_pct: number | null;
  version: string;
  is_active: boolean;
  limits_count: number;
  evidence_count: number;
  interoperability_count: number;
  verification_status: string;
  last_verified_at: string | null;
  updated_at: string;
}

export interface ServiceProductDetail extends ServiceProductSummary {
  architectural_fit: string | null;
  anti_patterns: string | null;
  interoperability_notes: string | null;
  oracle_docs_urls: string | null;
  current_version: ServiceProductVersion | null;
  limits: ServiceLimit[];
  evidence_sources: ServiceEvidenceSource[];
  interoperability_rules: ServiceInteroperabilityRule[];
}

export interface ServiceProductList {
  products: ServiceProductSummary[];
  total: number;
  stale_evidence_count: number;
  open_findings_count: number;
}

export interface ServiceInteroperabilityMatrix {
  services: ServiceProductSummary[];
  rules: ServiceInteroperabilityRule[];
  total_rules: number;
}

export interface ServiceVerificationJob {
  id: string;
  requested_by: string;
  scope: string;
  request_payload: Record<string, unknown> | null;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  services_checked: unknown[];
  sources_checked: number;
  changes_detected: number;
  findings: unknown[];
  recommendations: unknown[];
  error_details: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface ServiceVerificationJobList {
  jobs: ServiceVerificationJob[];
  total: number;
}

export interface ServiceVerificationFinding {
  id: string;
  job_id: string;
  service_profile_id: string | null;
  finding_type: string;
  severity: string;
  title: string;
  summary: string;
  old_value: unknown | null;
  new_value: unknown | null;
  source_url: string | null;
  evidence_excerpt: string | null;
  recommended_action: string | null;
  review_status: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ServiceVerificationAlert {
  id: string;
  alert_type: string;
  severity: string;
  title: string;
  summary: string;
  service_profile_id: string | null;
  service_id: string | null;
  source_url: string | null;
  finding_id: string | null;
  status: string;
  created_at: string;
}

export interface ServiceVerificationAlertList {
  alerts: ServiceVerificationAlert[];
  total: number;
  open_findings_count: number;
  stale_evidence_count: number;
}

export interface ServiceVerificationRunRequest {
  service_ids?: string[];
  max_sources?: number;
  force?: boolean;
}

export interface ServiceVerificationFindingReviewRequest {
  review_status: "accepted" | "dismissed" | "reviewed";
  note?: string;
}

export interface PatternDefinitionCreate {
  pattern_id: string;
  name: string;
  category: string;
  description?: string;
  oci_components?: string;
  when_to_use?: string;
  when_not_to_use?: string;
  technical_flow?: string;
  business_value?: string;
  applicability_examples?: string[];
  selection_questions?: string[];
  required_inputs?: string[];
}

export interface CaptureTemplateColumnMetadata {
  field: string;
  header: string;
  section: string;
  requirement: "Requerido" | "Recomendado" | "Opcional";
  data_type: string;
  description: string;
}

export interface CaptureTemplateMetadata {
  template_version: string;
  importer_min_version: string;
  filename: string;
  generated_at: string;
  capture_sheet: string;
  capture_row_limit: number;
  pattern_count: number;
  service_product_count: number;
  service_limit_count: number;
  interoperability_rule_count: number;
  evidence_source_count: number;
  stale_evidence_count: number;
  last_verified_at: string | null;
  columns: CaptureTemplateColumnMetadata[];
}

export interface DictionaryOption {
  id: string;
  category: string;
  code: string | null;
  value: string;
  description: string | null;
  executions_per_day: number | null;
  is_volumetric: boolean | null;
  sort_order: number;
  is_active: boolean;
  version: string;
  updated_at?: string;
}

export interface DictionaryOptionList {
  category: string;
  options: DictionaryOption[];
}

export interface CanvasCombination {
  code: string;
  name: string;
  capture_standard: string;
  supported_tool_keys: string[];
  compatible_pattern_ids: string[];
  activates_metrics: string[];
  activates_volumetric_metrics: boolean;
  recommended_overlays: string[];
  guidance: string;
  status: string;
}

export interface CanvasGovernance {
  tools: DictionaryOption[];
  overlays: DictionaryOption[];
  combinations: CanvasCombination[];
}

export interface DictionaryCategorySummary {
  category: string;
  option_count: number;
}

export interface DictionaryCategoryList {
  categories: DictionaryCategorySummary[];
}

export interface DictOptionCreate {
  code: string;
  value: string;
  description?: string;
  executions_per_day?: number | null;
  is_volumetric?: boolean | null;
  sort_order?: number;
  is_active?: boolean;
  version?: string;
}

export interface DictOption {
  id: string;
  category: string;
  code: string | null;
  value: string;
  description?: string | null;
  executions_per_day?: number | null;
  is_volumetric?: boolean | null;
  sort_order?: number;
  is_active?: boolean;
  version?: string;
  updated_at?: string;
}

export interface OICMetrics {
  total_billing_msgs_month: number;
  peak_billing_msgs_hour: number;
  peak_packs_hour: number;
  row_count: number;
}

export interface DIMetrics {
  workspace_active: boolean;
  row_count: number;
  data_processed_gb_month: number;
}

export interface FunctionsMetrics {
  total_invocations_month: number;
  total_execution_units_gb_s: number;
  row_count: number;
}

export interface StreamingMetrics {
  row_count: number;
  total_gb_month: number;
  partition_count: number;
}

export interface QueueMetrics {
  row_count: number;
}

export interface AssumptionSetCreate {
  version: string;
  month_days: number;
  streaming_default_partitions: number;
  functions_default_duration_ms: number;
  functions_default_memory_mb: number;
  functions_default_concurrency: number;
  functions_batch_size_records: number;
  queue_throughput_soft_limit_msgs_per_second: number;
  raw_assumptions?: Record<string, unknown>;
}

export interface AssumptionSet extends AssumptionSetCreate {
  id: string;
  is_default: boolean;
  created_at: string;
  updated_at?: string;
}

export interface AssumptionList {
  assumption_sets: AssumptionSet[];
  total: number;
}

export interface ConsolidatedMetrics {
  oic: OICMetrics;
  data_integration: DIMetrics;
  functions: FunctionsMetrics;
  streaming: StreamingMetrics;
  queue: QueueMetrics;
}

export interface VolumetrySnapshot {
  snapshot_id: string;
  project_id: string;
  assumption_set_version: string;
  triggered_by: string;
  row_results: Record<string, Record<string, unknown>>;
  consolidated: ConsolidatedMetrics;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

export interface VolumetrySnapshotSummary {
  snapshot_id: string;
  project_id: string;
  assumption_set_version: string;
  triggered_by: string;
  consolidated: ConsolidatedMetrics;
  metadata: Record<string, unknown> | null;
  row_result_count: number;
  created_at: string;
}

export interface VolumetrySnapshotList {
  snapshots: VolumetrySnapshotSummary[];
}

export interface RecalculationJobStatus {
  job_id: string;
  project_id: string;
  status: string;
  snapshot_id: string | null;
  scope: string;
  integration_ids: string[];
  created_at: string | null;
}

export interface AuditEvent {
  id: string;
  project_id: string | null;
  actor_id: string;
  event_type: string;
  entity_type: string;
  entity_id: string;
  correlation_id: string | null;
  old_value: Record<string, unknown> | null;
  new_value: Record<string, unknown> | null;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

export interface AuditPage {
  events: AuditEvent[];
  total: number;
  page: number;
  page_size: number;
}

export interface ManualIntegrationCreate {
  interface_id?: string;
  brand: string;
  business_process: string;
  interface_name: string;
  description?: string;
  source_system: string;
  source_technology?: string;
  source_api_reference?: string;
  source_owner?: string;
  destination_system: string;
  destination_technology?: string;
  destination_owner?: string;
  type?: string;
  frequency?: string;
  payload_per_execution_kb?: number;
  complexity?: string;
  uncertainty?: string;
  selected_pattern?: string;
  pattern_rationale?: string;
  core_tools?: string[];
  tbq?: string;
  initial_scope?: string;
  owner?: string;
}

export interface OICEstimateRequest {
  frequency?: string;
  payload_per_execution_kb?: number;
  response_kb?: number;
}

export interface OICEstimateResponse {
  billing_msgs_per_execution: number | null;
  billing_msgs_per_month: number | null;
  peak_packs_per_hour: number | null;
  executions_per_day: number | null;
  computable: boolean;
}

export interface DuplicateCheckParams {
  source_system: string;
  destination_system: string;
  business_process: string;
}

export interface GraphNode {
  id: string;
  label: string;
  integration_count: number;
  as_source_count: number;
  as_destination_count: number;
  brands: string[];
  business_processes: string[];
  owners: string[];
  technologies: string[];
}

export interface GraphIntegrationSummary {
  id: string;
  name: string;
  qa_status: string;
  owner: string | null;
  pattern: string | null;
  trigger_type: string | null;
  interaction_mode: "SYNCHRONOUS" | "ASYNCHRONOUS" | "MIXED" | "UNSPECIFIED";
  executions_per_day: number | null;
  payload_per_hour_kb: number | null;
  updated_at: string;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  integration_count: number;
  integration_ids: string[];
  integration_names: string[];
  integration_qa_statuses: string[];
  business_processes: string[];
  patterns: string[];
  qa_statuses: Record<string, number>;
  dominant_qa_status: string;
  risk_qa_status: string;
  risk_score: number;
  interaction_mode: "SYNCHRONOUS" | "ASYNCHRONOUS" | "MIXED" | "UNSPECIFIED";
  total_executions_per_day: number;
  total_payload_per_hour_kb: number;
  executions_coverage: number;
  payload_coverage: number;
  last_updated_at: string;
  integrations: GraphIntegrationSummary[];
}

export interface GraphMeta {
  node_count: number;
  edge_count: number;
  integration_count: number;
  business_processes: string[];
  business_process_families: string[];
  brands: string[];
  latest_updated_at: string | null;
  executions_coverage: number;
  payload_coverage: number;
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
  meta: GraphMeta;
}

export interface GraphParams {
  business_process?: string;
  business_process_family?: string;
  brand?: string;
  qa_status?: string;
  system?: string;
}

export interface DashboardKPIStrip {
  oic_msgs_month: number;
  peak_packs_hour: number;
  di_workspace_active: boolean;
  di_data_processed_gb_month: number;
  functions_execution_units_gb_s: number;
}

export interface DashboardCoverageMetric {
  complete: number;
  total: number;
  ratio: number;
}

export interface DashboardCoverage {
  total_integrations: number;
  formal_id: DashboardCoverageMetric;
  pattern: DashboardCoverageMetric;
  payload: DashboardCoverageMetric;
  trigger: DashboardCoverageMetric;
  source_destination: DashboardCoverageMetric;
  fan_out: DashboardCoverageMetric;
}

export interface DashboardCompleteness {
  qa_ok: number;
  qa_revisar: number;
  qa_pending: number;
  rationale_informed: number;
  core_tools_informed: number;
  comments_informed: number;
  retry_policy_informed: number;
}

export interface DashboardPatternMixEntry {
  pattern_id: string;
  name: string;
  count: number;
}

export interface DashboardPayloadDistributionBucket {
  label: string;
  count: number;
}

export interface DashboardForecastConfidence {
  level: string;
  title: string;
  message: string;
  payload_coverage_ratio: number;
}

export interface DashboardServiceRuleStatus {
  version: string;
  source: string;
  freshness_status: string;
  stale_evidence_count: number;
  open_findings_count: number;
  last_verified_at: string | null;
}

export interface DashboardProductUsage {
  tool_key: string;
  service_id: string | null;
  role: "core" | "overlay";
  integration_count: number;
  coverage_ratio: number;
}

export interface DashboardProductFootprint {
  captured_product_count: number;
  represented_product_count: number;
  rows_with_products: number;
  total_rows: number;
  products: DashboardProductUsage[];
}

export interface DashboardCharts {
  coverage: DashboardCoverage;
  completeness: DashboardCompleteness;
  pattern_mix: DashboardPatternMixEntry[];
  payload_distribution: DashboardPayloadDistributionBucket[];
  forecast_confidence: DashboardForecastConfidence;
  service_rules: DashboardServiceRuleStatus;
  product_footprint: DashboardProductFootprint;
}

export interface DashboardRisk {
  code: string;
  label: string;
  count: number;
  integration_ids: string[];
}

export interface DashboardMaturity {
  qa_ok_pct: number;
  pattern_assigned_pct: number;
  payload_informed_pct: number;
  governed_pct: number;
}

export interface DashboardSnapshotSummary {
  snapshot_id: string;
  volumetry_snapshot_id: string;
  mode: string;
  created_at: string;
}

export interface DashboardSnapshot {
  snapshot_id: string;
  project_id: string;
  volumetry_snapshot_id: string;
  mode: string;
  kpi_strip: DashboardKPIStrip;
  charts: DashboardCharts;
  risks: DashboardRisk[];
  maturity: DashboardMaturity;
  created_at: string;
}

export interface DashboardSnapshotList {
  snapshots: DashboardSnapshotSummary[];
  total: number;
}

export interface PriceSource {
  id: string;
  name: string;
  source_type: string;
  base_url: string | null;
  currency: string;
  status: string;
  last_synced_at: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface PriceSourceList {
  sources: PriceSource[];
  total: number;
}

export interface PriceSyncJob {
  id: string;
  source_id: string;
  requested_by: string;
  currency: string;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  item_count: number;
  changes_detected: number;
  snapshot_id: string | null;
  error_details: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface PriceSyncJobList {
  jobs: PriceSyncJob[];
  total: number;
}

export interface PriceCatalogSnapshot {
  id: string;
  source_id: string;
  sync_job_id: string | null;
  currency: string;
  source_last_updated: string | null;
  retrieved_at: string;
  content_hash: string;
  item_count: number;
  approval_status: string;
  approved_by: string | null;
  approved_at: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface PriceCatalogSnapshotList {
  snapshots: PriceCatalogSnapshot[];
  total: number;
}

export interface PriceItem {
  id: string;
  snapshot_id: string;
  part_number: string;
  display_name: string;
  metric_name: string;
  service_category: string;
  price_type: string;
  currency: string;
  model: string;
  value: number;
  range_min: number | null;
  range_max: number | null;
  range_unit: string | null;
}

export interface PriceItemList {
  items: PriceItem[];
  total: number;
  page: number;
  page_size: number;
}

export type SkuMappingStatus = "draft" | "approved" | "retired";

export interface SkuMapping {
  id: string;
  service_id: string;
  tool_key: string;
  part_number: string | null;
  billing_metric_key: string;
  formula_key: string;
  predicates: Record<string, unknown>;
  is_billable: boolean;
  status: SkuMappingStatus;
  version: string;
  source_url: string | null;
  confidence: number;
  updated_at: string;
}

export interface SkuMappingList {
  mappings: SkuMapping[];
  total: number;
  billable_count: number;
  non_billable_count: number;
}

export interface SkuMappingPatch {
  part_number?: string | null;
  billing_metric_key?: string;
  formula_key?: string;
  predicates?: Record<string, unknown>;
  is_billable?: boolean;
  status?: SkuMappingStatus;
  confidence?: number;
}

export interface DeploymentEnvironmentInput {
  name: string;
  active_hours_month: number;
  active_months_year: number;
  demand_share: number;
  ha_multiplier: number;
  dr_role: "primary" | "standby" | "none";
}

export interface DeploymentScenarioCreate {
  name: string;
  technical_snapshot_id?: string | null;
  currency: string;
  region: string;
  price_mode: "public_list" | "contract_rate" | "manual_rate_card";
  contract_months: number;
  environments: DeploymentEnvironmentInput[];
  service_config: Record<string, Record<string, unknown>>;
  assumptions: Record<string, unknown>;
}

export interface DeploymentScenario {
  id: string;
  project_id: string;
  name: string;
  status: string;
  currency: string;
  region: string;
  price_mode: string;
  technical_snapshot_id: string;
  contract_months: number;
  environments: Array<Record<string, unknown>>;
  service_config: Record<string, unknown>;
  assumptions: Record<string, unknown>;
  created_by: string;
  approved_by: string | null;
  approved_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface DeploymentScenarioList {
  scenarios: DeploymentScenario[];
  total: number;
}

export interface ScenarioAssistant {
  draft: DeploymentScenarioCreate;
  detected_services: string[];
  required_questions: string[];
  warnings: string[];
  confidence: string;
  ai_status: string;
  ai_summary: string | null;
}

export interface BomJob {
  id: string;
  project_id: string;
  scenario_id: string;
  requested_by: string;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  bom_snapshot_id: string | null;
  error_details: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface BomJobList {
  jobs: BomJob[];
  total: number;
}

export interface BomLineItem {
  id: string;
  environment: string;
  service_id: string;
  part_number: string | null;
  description: string;
  metric_name: string;
  quantity: number;
  unit: string;
  unit_price: number;
  monthly_amount: number;
  annual_amount: number;
  contract_amount: number;
  formula: string;
  inputs: Record<string, unknown>;
  status: string;
  warnings: unknown[];
  provenance: Record<string, unknown>;
}

export interface BomSnapshot {
  id: string;
  project_id: string;
  scenario_id: string;
  technical_snapshot_id: string;
  price_catalog_snapshot_id: string;
  mapping_version: string;
  engine_version: string;
  currency: string;
  coverage_pct: number;
  monthly_total: number;
  annual_total: number;
  contract_total: number;
  summary: Record<string, unknown>;
  warnings: unknown[];
  publication_status: string;
  approved_by: string | null;
  approved_at: string | null;
  line_items: BomLineItem[];
  created_at: string;
}

export interface BomSnapshotList {
  snapshots: BomSnapshot[];
  total: number;
}

export interface BomComparison {
  baseline_snapshot_id: string;
  comparison_snapshot_id: string;
  currency: string;
  monthly_delta: number;
  annual_delta: number;
  contract_delta: number;
  service_monthly_deltas: Record<string, number>;
  environment_monthly_deltas: Record<string, number>;
  drivers: string[];
}

export function isPriceSyncTerminal(status: string): boolean {
  return status === "completed" || status === "failed";
}

export function isBomJobTerminal(status: string): boolean {
  return status === "completed" || status === "failed";
}
