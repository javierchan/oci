/* TypeScript contracts for the OCI DIS Blueprint frontend. */

export interface Project {
  id: string;
  name: string;
  owner_id: string;
  description: string | null;
  status: string;
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
  included: boolean;
  exclusion_reason: string | null;
  normalization_events: NormalizationEvent[];
  import_batch_id: string;
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
}

export interface CatalogPage {
  integrations: Integration[];
  total: number;
  page: number;
  page_size: number;
}

export interface CatalogParams {
  page?: number;
  page_size?: number;
  qa_status?: string;
  search?: string;
  pattern?: string;
  brand?: string;
}

export interface PatternDefinition {
  id: string;
  pattern_id: string;
  name: string;
  category: string;
  description: string | null;
  is_active: boolean;
  version: string;
}

export interface PatternList {
  patterns: PatternDefinition[];
  total: number;
}

export interface DictionaryOption {
  id: string;
  category: string;
  code: string | null;
  value: string;
  description: string | null;
  executions_per_day: number | null;
  sort_order: number;
  is_active: boolean;
}

export interface DictionaryOptionList {
  category: string;
  options: DictionaryOption[];
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

export interface VolumetrySnapshotList {
  snapshots: VolumetrySnapshot[];
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
