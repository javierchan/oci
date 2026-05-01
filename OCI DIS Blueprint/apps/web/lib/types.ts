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
  findings: AiReviewFinding[];
  groups: AiReviewGroup[];
  evidence: AiReviewEvidence[];
  evidence_pack: string[];
  reviewer_personas: AiReviewPersonaSummary[];
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

export interface ServiceCapabilityProfile {
  id: string;
  service_id: string;
  name: string;
  category:
    | "ORCHESTRATION"
    | "API_INGRESS"
    | "EVENT_BACKBONE"
    | "WORK_QUEUE"
    | "SERVERLESS_COMPUTE"
    | "OCI_DATA_MOVER"
    | "CDC_REPLICATION"
    | "DATABASE_REST"
    | "BATCH_ETL"
    | "OBSERVABILITY"
    | "IDENTITY_SECURITY"
    | string;
  sla_uptime_pct: number | null;
  pricing_model: string | null;
  limits: Record<string, unknown>;
  architectural_fit: string | null;
  anti_patterns: string | null;
  interoperability_notes: string | null;
  oracle_docs_urls: string | null;
  is_active: boolean;
  version: string;
  created_at: string;
  updated_at: string;
}

export interface ServiceCapabilityProfileList {
  services: ServiceCapabilityProfile[];
  total: number;
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
  oic_billing_threshold_kb: number;
  oic_pack_size_msgs_per_hour: number;
  oic_byol_pack_size_msgs_per_hour: number;
  month_days: number;
  oic_rest_max_payload_kb: number;
  oic_ftp_max_payload_kb: number;
  oic_kafka_max_payload_kb: number;
  oic_timeout_s: number;
  streaming_partition_throughput_mb_s: number;
  streaming_read_throughput_mb_s: number;
  streaming_max_message_size_mb: number;
  streaming_retention_days: number;
  streaming_default_partitions: number;
  functions_default_duration_ms: number;
  functions_default_memory_mb: number;
  functions_default_concurrency: number;
  functions_max_timeout_s: number;
  functions_batch_size_records: number;
  queue_billing_unit_kb: number;
  queue_max_message_kb: number;
  queue_retention_days: number;
  queue_throughput_soft_limit_msgs_per_second: number;
  data_integration_workspaces_per_region: number;
  data_integration_deleted_workspace_retention_days: number;
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
}

export interface GraphMeta {
  node_count: number;
  edge_count: number;
  integration_count: number;
  business_processes: string[];
  brands: string[];
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
  meta: GraphMeta;
}

export interface GraphParams {
  business_process?: string;
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

export interface DashboardCharts {
  coverage: DashboardCoverage;
  completeness: DashboardCompleteness;
  pattern_mix: DashboardPatternMixEntry[];
  payload_distribution: DashboardPayloadDistributionBucket[];
  forecast_confidence: DashboardForecastConfidence;
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
