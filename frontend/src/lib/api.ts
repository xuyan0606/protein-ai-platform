const BASE = '/api'
const ACCESS_TOKEN_KEY = 'token'
const REFRESH_TOKEN_KEY = 'refreshToken'
const AUTH_CLEARED_EVENT = 'protein-ai:auth-cleared'
const AUTH_UPDATED_EVENT = 'protein-ai:auth-updated'

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export function isUnauthorizedError(error: unknown): error is ApiError {
  return error instanceof ApiError && error.status === 401
}

type RequestConfig = {
  authenticated?: boolean
}

type UploadConfig = {
  onProgress?: (progress: number) => void
  retryOn401?: boolean
}

export type ApiRecord = Record<string, unknown>

export type ResearchEvidenceScope = 'all' | 'training' | 'model_claim' | 'customer_delivery' | 'release' | 'human_target'

export type ResearchEvidence = {
  scope: ResearchEvidenceScope
  local_only: boolean
  read_only: boolean
  matrix?: {
    path: string
    exists: boolean
  }
  training?: {
    training_import_eligible_rows: number
    training_execution_allowed: boolean
    status: string
    cleanroom_kinetics_candidate?: {
      training_import_written_rows: number
      training_eligible: boolean
      validation_success: boolean
    }
  }
  model_claim?: {
    safe_for_model_claim: boolean
    claims_allowed: number
    status: string
  }
  customer_delivery?: {
    ready: boolean
    status: string
  }
  release?: {
    release_ready: boolean
    local_only: boolean
    status: string
  }
  human_target?: {
    status: string
    schema_contract_status: string
    source_runtime_validation_success: boolean
    split_manifest_validation_success: boolean
    total_sources: number
    ready_sources: number
    blocked_sources: number
    safe_for_model_claim: boolean
    customer_ready: boolean
    release_ready: boolean
    unlock_checklist?: {
      checklist_rows: number
      ready_to_unlock_rows: number
      blocked_rows: number
      validation_success: boolean
      path: string
      validation_path: string
      report_path: string
      rows?: Array<{
        checklist_id?: string
        source_id?: string
        source_manifest_path?: string
        current_status: string
        completed_steps?: string[]
        missing_steps?: string[]
        required_steps?: string[]
        ready_to_unlock: boolean
        claim_eligible: boolean
        customer_ready: boolean
        release_ready: boolean
      }>
    }
    sources?: Array<{
      source_id: string
      lane: string
      display_name: string
      split_manifest_path?: string | null
      status: string
      blocked_reason?: string | null
      required_artifacts?: string[]
      runtime_signal?: {
        required: boolean
        present: boolean
        present_names?: string[]
      }
      source_ready: boolean
      claim_eligible: boolean
      customer_ready: boolean
      release_ready: boolean
    }>
  }
  normalized_result?: Record<string, unknown>
  evidence_paths?: string[]
  forbidden_side_effects?: string[]
}

export type ApiConversationMessage = {
  id?: string
  role: 'user' | 'assistant' | 'system'
  content?: string | null
  tool_calls?: unknown
  toolCalls?: unknown
  files?: unknown
  thinking?: string[]
  created_at?: string | null
}

export type ApiConversationSummary = {
  id: string
  title?: string | null
  created_at?: string | null
  updated_at?: string | null
  message_count?: number | null
}

export type ApiConversationDetail = ApiConversationSummary & {
  messages?: ApiConversationMessage[]
}

export type ApiAgentPlanStep = {
  id: number
  tool_name: string
  description: string
  params?: Record<string, unknown>
  status: 'pending' | 'running' | 'submitted' | 'completed' | 'failed'
}

export type ApiAgentState = {
  stage: 'router' | 'research' | 'plan' | 'execute' | 'synthesize' | 'done'
  plan: ApiAgentPlanStep[]
  current_step: number
  step_results: Array<Record<string, unknown>>
  research_notes: string
  waiting_for: string | null
  strategy_signature?: string | null
  task_fingerprint?: string | null
  next_action?: string | null
  artifacts?: Record<string, unknown>
}

export type ApiActiveStrategyCheckpoint = {
  checkpoint: ApiRecord | null
  agent_state: ApiAgentState | null
}

export type ApiStrategyCheckpointHistory = {
  records: ApiRecord[]
}

export type ApiRecentStrategyMemory = {
  scope: {
    type: string
    conversation_id?: string | number | null
    project_id?: string | null
  }
  records: ApiRecord[]
}

export type ApiAgentStrategyPolicy = {
  status: string
  parse_error?: string | null
  policy: ApiRecord
}

export type ToolSchemaResponse = {
  name: string
  description: string
  category: string
  is_async: boolean
  parameters: {
    type: string
    properties: Record<string, { type: string; description?: string; default?: unknown; items?: { type: string } }>
    required?: string[]
  }
}

export type DataStats = {
  counts?: Record<string, number>
}

export type DataSearchResponse = {
  results?: {
    proteins?: Array<{ uniprot_id: string; name?: string | null; gene?: string | null }>
    substrates?: Array<{ cid: string | number; name?: string | null; formula?: string | null }>
    ec_numbers?: Array<{ ec: string; name?: string | null }>
    reactions?: Array<{ rhea_id: string | number; equation?: string | null }>
  }
}

export type EnzymeDbFamily =
  | 'amylase'
  | 'mannanase'
  | 'xylanase'
  | 'acid_protease'
  | 'phytase'
  | 'glucose_oxidase'

export type EnzymeDbPathInfo = {
  exists: boolean
  size_bytes: number
  updated_at?: string | null
}

export type EnzymeDbFamilyStatus = {
  status: 'ready' | 'partial' | 'missing' | 'error' | 'unknown_family' | string
  family: EnzymeDbFamily | string
  label?: string
  schema?: 'simplified_three_table' | string
  read_only: boolean
  path?: EnzymeDbPathInfo
  expected_tables?: string[]
  tables?: Record<string, number>
  missing_tables?: string[]
  metadata_policy_decisions?: {
    status?: string
    manifest_count?: number
    decision_count?: number
    record_types?: string[]
    review_statuses?: string[]
    manifests?: Array<Record<string, unknown>>
    errors?: Array<Record<string, unknown>>
  }
  quality?: {
    integrity_check: string
    ready_for_query: boolean
  }
  metadata_quality?: {
    missing_doi: number
    missing_pmid: number
    patent_like_sources: number
    preprint_papers?: number
    boundary_papers?: number
    boundary_measurements?: number
    policy_excluded_papers?: number
    policy_excluded_measurements?: number
    non_exportable_markers?: string[]
    export_policy?: {
      browser_scope?: string
      export_scope?: string
      patent_metadata?: string
      preprint_version_of_record?: string
      blocked_markers?: string[]
    }
    hold_papers: number
    hold_measurements: number
    export_safe_measurements: number
    metadata_gap_count: number
    browser_scope: string
  }
  error?: string
}

export type EnzymeDbFamiliesStatus = {
  status: 'ready' | 'partial' | string
  read_only: boolean
  root: {
    path: string
    exists: boolean
  }
  families: EnzymeDbFamilyStatus[]
}

export type EnzymeDbPaperList = {
  status: string
  family: EnzymeDbFamily | string
  export_scope: string
  export_safe: boolean
  policy: string
  count: number
  papers: ApiRecord[]
  path: EnzymeDbPathInfo
}

export type EnzymeDbVariantList = {
  status: string
  family: EnzymeDbFamily | string
  export_scope: string
  export_safe: boolean
  policy: string
  count: number
  variants: ApiRecord[]
  path: EnzymeDbPathInfo
}

export type EnzymeDbMeasurementList = {
  status: string
  family: EnzymeDbFamily | string
  export_scope: string
  export_safe: boolean
  policy: string
  count: number
  measurements: ApiRecord[]
  path: EnzymeDbPathInfo
}

export type EnzymeDbSearchResult = {
  status: string
  family: EnzymeDbFamily | string
  query?: string
  export_scope?: string
  export_safe?: boolean
  policy?: string
  results: {
    papers: ApiRecord[]
    variants: ApiRecord[]
    measurements: ApiRecord[]
  }
}

export type EnzymeDbPolicyDecisionPreview = {
  status: string
  dry_run: boolean
  family: EnzymeDbFamily | string
  read_only_source_db: boolean
  confirmation_required: boolean
  confirmation_token: string
  reviewer_user_id?: number | string
  manifest: {
    record_count: number
    record_types: string[]
    review_statuses?: string[]
    status_policy?: string
  }
  export_payload: {
    source?: string
    target?: string
    family?: EnzymeDbFamily | string
    record_count: number
    records: ApiRecord[]
    required_manual_steps?: string[]
  }
}

export type EnzymeMetadataCurationRecord = {
  id: number
  family: EnzymeDbFamily | string
  paper_id: string
  record_type: string
  status: string
  created_by_user_id?: number | string
  reviewed_by_user_id?: number | string | null
  decision?: string | null
  source_identifier?: string | null
  source_manifest_path?: string | null
  decision_payload?: ApiRecord
  reviewer_notes?: string | null
  created_at?: string | null
  updated_at?: string | null
  reviewed_at?: string | null
}

export type EnzymeMetadataCurationList = {
  count: number
  records: EnzymeMetadataCurationRecord[]
  reviewer_user_id?: number | string
}

export type EnzymeMetadataCurationMaterializeResult = {
  status: string
  dry_run: boolean
  family: EnzymeDbFamily | string
  read_only_source_db: boolean
  sqlite_mutated: boolean
  export_safe_released: boolean
  planned_count: number
  skipped_count: number
  planned_records: ApiRecord[]
  skipped_records: ApiRecord[]
  reviewer_user_id?: number | string
  manifest?: {
    record_count?: number
    record_types?: string[]
    status_policy?: string
  }
}

export type EnzymeMetadataCurationBatch = {
  id: number
  batch_key: string
  status: string
  created_by_user_id?: number | string
  archived_by_user_id?: number | string | null
  family?: EnzymeDbFamily | string | null
  record_type?: string | null
  record_ids: number[]
  manifest: ApiRecord
  export_payload: ApiRecord
  confirmation_token: string
  reviewer_notes?: string | null
  created_at?: string | null
  updated_at?: string | null
  archived_at?: string | null
}

export type EnzymeMetadataCurationBatchResult = {
  status: string
  dry_run?: boolean
  manifest?: ApiRecord
  export_payload?: ApiRecord
  confirmation_token?: string
  batch?: EnzymeMetadataCurationBatch
}

export type EnzymeMetadataCurationBatchList = {
  count: number
  batches: EnzymeMetadataCurationBatch[]
  reviewer_user_id?: number | string
}

export type BenchmarkPathInfo = {
  relative_path: string
  absolute_path: string
  exists: boolean
}

export type BenchmarkDiscoveryItem = {
  path: string
  project_relative_path: string
  size_bytes: number
  score: number
}

export type BenchmarkSelectedDoc = {
  source_path: string
  staged_path: string
  score: number
  size_bytes: number
}

export type BenchmarkSummary = {
  id: string
  slug: string
  title: string
  program?: string | null
  protein_name?: string | null
  objective: string
  target_ph_range: {
    min: number
    max: number
    focus?: number | null
  }
  sequence_length: number
  candidate_mutation_count: number
  maturity: 'delivery-ready' | 'bundle-ready' | 'structure-ready' | 'staged' | 'seed-only'
  bundle_download_url: string
  asset_status: {
    source_bundle_ready: boolean
    deploy_structure_ready: boolean
    foldseek_indexed: boolean
    alphafold_ready: boolean
    sifts_ready: boolean
    annotations_ready: boolean
    bundle_ready: boolean
    bundle_archive_ready: boolean
    reference_docs_ready: boolean
    reference_doc_manifest_ready: boolean
    discovery_report_ready: boolean
  }
  asset_counts: {
    alphafold_structures: number
    sifts_mappings: number
    annotation_files: number
    reference_doc_files: number
    foldseek_pdb_entries: number
    foldseek_alphafold_entries: number
    bundle_files: number
    bundle_archive_size_bytes: number
    discovered_structures: number
    discovered_alphafold: number
    discovered_sifts: number
    discovered_annotations: number
    discovered_reference_docs: number
  }
}

export type BenchmarkMutation = {
  mutation: string
  position: number
  wild_type: string
  mutant: string
  hypothesis: string
  evidence_goal?: string | null
}

export type BenchmarkAction = {
  title: string
  description: string
  href?: string | null
}

export type DeployDataComponentStatus = 'ready' | 'demo' | 'empty' | 'missing'

export type DeployDataFilePreview = {
  path: string
  project_relative_path: string
  exists: boolean
  size_bytes?: number
}

export type DeployDataReadiness = {
  summary: 'live-ready' | 'demo-ready' | 'partial' | 'empty'
  live_ready: boolean
  root: {
    path: string
    project_relative_path: string
    exists: boolean
  }
  components: Record<string, {
    status: DeployDataComponentStatus
    path: {
      path: string
      project_relative_path: string
      exists: boolean
    }
    count?: number
    counts?: Record<string, number>
    size_bytes: number
    version?: string | null
    updated_at?: string | null
    missing_items?: string[]
    preview: DeployDataFilePreview[] | Record<string, DeployDataFilePreview[]>
    failure_reason?: string | null
  }>
  updates: {
    manifest_count: number
    failure_count?: number
    manifests: Array<{
      label: string
      path: string
      project_relative_path: string
      exists: boolean
      updated_at?: string | null
      keys?: string[]
      counts?: Record<string, number>
      size_bytes?: number
      parse_error?: boolean
      status?: string
      failure_reason?: string | null
      component?: string
      version?: string | null
    }>
    filters?: {
      components: string[]
      statuses: string[]
    }
  }
  version_comparison?: {
    latest_manifest?: DeployDataReadiness['updates']['manifests'][number] | null
    ready_components: string[]
    not_ready_components: string[]
    all_components_ready: boolean
    manifest_versions: Array<{
      label?: string
      component?: string
      version?: string | null
      updated_at?: string | null
      status?: string
    }>
  }
  missing_or_demo_components: string[]
  next_actions: string[]
}

export type ToolCapabilityRow = {
  tool: string
  capability_status: string
  boundary: string
  minimum_artifacts: string[]
  report_action: string
}

export type ToolCapabilityAudit = {
  status: 'ready' | 'partial'
  capabilities: ToolCapabilityRow[]
  unknown_tools: string[]
  summary: {
    tool_count: number
    unknown_count: number
    status_counts: Record<string, number>
  }
  rules: {
    real_runtime: string
    proxy: string
    blocked: string
  }
}

export type DeployDataImportRequest = {
  annotations?: string
  sifts?: string
  pdb?: string
  alphafold?: string
  foldseek_root?: string
  foldseek_pdb?: string
  foldseek_alphafold?: string
  foldseek_custom?: string
  smoke_pdb?: string
  symlink?: boolean
  dry_run?: boolean
  confirmation?: string
}

export type LipaseDbStatus = {
  status: 'ready' | 'partial' | 'missing' | 'error' | string
  read_only: boolean
  path: {
    exists: boolean
    size_bytes: number
    updated_at?: string | null
  }
  expected_tables: string[]
  tables: Record<string, number>
  missing_tables: string[]
  extra_tables?: string[]
  summary?: {
    paper_count: number
    variant_count: number
    mutation_count: number
    claim_count: number
    metric_count: number
    substrate_count: number
    gap_count: number
  }
  quality: {
    integrity_check: string
    foreign_key_issues: Array<Record<string, unknown>>
    ready_for_ingestion: boolean
    error?: string
  }
  evidence_levels?: Array<{ evidence_level?: string | null; count: number }>
  claim_groups?: Array<{ claim_group?: string | null; count: number }>
  gap_summary?: Array<{ gap_type?: string | null; priority?: string | null; status?: string | null; count: number }>
  next_actions: string[]
}

export type LipaseVariantList = {
  status: string
  count: number
  variants: Array<Record<string, unknown>>
  path: LipaseDbStatus['path']
}

export type LipasePaperList = {
  status: string
  count: number
  papers: Array<Record<string, unknown>>
  path: LipaseDbStatus['path']
}

export type LipasePaperDetail = {
  status: string
  paper: Record<string, unknown>
  aliases: Array<Record<string, unknown>>
  variants: Array<Record<string, unknown>>
  claims: Array<Record<string, unknown>>
  gaps: Array<Record<string, unknown>>
  counts: Record<string, number>
  path: LipaseDbStatus['path']
}

export type LipaseGapList = {
  status: string
  count: number
  gaps: Array<Record<string, unknown>>
  path: LipaseDbStatus['path']
}

export type LipaseSearchResult = {
  status: string
  query: string
  results: {
    papers: Array<Record<string, unknown>>
    variants: Array<Record<string, unknown>>
    claims: Array<Record<string, unknown>>
    substrates: Array<Record<string, unknown>>
    gaps: Array<Record<string, unknown>>
  }
  counts?: Record<string, number>
  path?: LipaseDbStatus['path']
}

export type LipaseEvidenceContext = {
  status: string
  read_only: boolean
  query?: string | null
  requested_mutations: string[]
  requested_positions: number[]
  exact_mutation_matches: Array<Record<string, unknown>>
  position_matches: Array<Record<string, unknown>>
  search?: LipaseSearchResult | null
  counts: {
    exact_mutation_matches: number
    position_matches: number
    search_matches: number
  }
  strongest_evidence_level?: string
  recommended_use?: string
  path?: LipaseDbStatus['path']
}

export type LipaseCurationRecord = {
  id: number
  source_type: 'literature' | 'experiment' | 'tool_feedback' | 'manual_note' | string
  status: 'submitted' | 'triaged' | 'accepted' | 'rejected' | 'needs_more_evidence' | string
  created_by_user_id: number
  reviewed_by_user_id?: number | null
  paper_key?: string | null
  title?: string | null
  doi?: string | null
  pmid?: string | null
  enzyme_name?: string | null
  mutation_code?: string | null
  position?: number | null
  linked_task_id?: string | null
  evidence_payload?: Record<string, unknown> | null
  feedback_payload?: Record<string, unknown> | null
  notes?: string | null
  reviewer_notes?: string | null
  created_at?: string | null
  updated_at?: string | null
  reviewed_at?: string | null
}

export type LipaseCurationCreate = {
  source_type: LipaseCurationRecord['source_type']
  paper_key?: string | null
  title?: string | null
  doi?: string | null
  pmid?: string | null
  enzyme_name?: string | null
  mutation_code?: string | null
  position?: number | null
  linked_task_id?: string | null
  evidence_payload?: Record<string, unknown> | null
  feedback_payload?: Record<string, unknown> | null
  notes?: string | null
}

export type LipaseCurationBatch = {
  id: number
  batch_key: string
  status: 'prepared' | 'published' | 'voided' | string
  created_by_user_id: number
  published_by_user_id?: number | null
  source_type?: string | null
  record_ids: number[]
  manifest: Record<string, unknown>
  export_payload: Record<string, unknown>
  confirmation_token: string
  reviewer_notes?: string | null
  created_at?: string | null
  updated_at?: string | null
  published_at?: string | null
}

export type ExperimentFeedbackDecision = 'go' | 'watch' | 'no_go'

export type ExperimentFeedbackRecord = {
  id: number
  created_by_user_id: number
  project_id?: string | null
  linked_task_id?: string | null
  enzyme_name?: string | null
  variant_name: string
  parent_variant?: string | null
  mutations: string[]
  assay_payload?: Record<string, unknown> | null
  metrics_payload?: Record<string, unknown> | null
  quality_payload?: Record<string, unknown> | null
  interpretation_payload?: {
    decision?: ExperimentFeedbackDecision | string
    positive_flags?: string[]
    warning_flags?: string[]
    blocker_flags?: string[]
    strategy?: string
    evidence_level?: string
    required_next_measurements?: string[]
    [key: string]: unknown
  } | null
  notes?: string | null
  created_at?: string | null
  updated_at?: string | null
}

export type ExperimentFeedbackCreate = {
  project_id?: string | null
  linked_task_id?: string | null
  enzyme_name?: string | null
  variant_name: string
  parent_variant?: string | null
  mutations?: string[]
  assay_payload?: Record<string, unknown> | null
  metrics_payload?: Record<string, unknown> | null
  quality_payload?: Record<string, unknown> | null
  interpretation_payload?: Record<string, unknown> | null
  notes?: string | null
}

export type ExperimentFeedbackSummary = {
  count: number
  decision_counts: Record<ExperimentFeedbackDecision | string, number>
  validated_single_mutants: Array<{
    variant_name?: string | null
    mutation: string
    metrics: Record<string, unknown>
    quality: Record<string, unknown>
  }>
  blocker_counts: Record<string, number>
  warning_counts: Record<string, number>
  next_strategy: string
}

export type MutationEpistasisCheckResult = {
  status: string
  blocked_reason?: string
  recommendation?: ExperimentFeedbackDecision | string
  mutations?: string[]
  pairwise_risks?: Array<{
    pair: string[]
    risk: 'low' | 'medium' | 'high' | string
    score: number
    distance_angstrom?: number | null
    distance_source?: string
    reasons: string[]
  }>
  summary?: {
    high_risk_pairs: number
    medium_risk_pairs: number
    risk_score_total: number
    blocked_pairs: string[]
    watch_pairs: string[]
  }
  gradient_experiment_plan?: Array<{
    step: number
    variant: string
    purpose: string
  }>
  required_missing_evidence?: string[]
  report_contract?: {
    schema_version?: string
    evidence_inputs?: Record<string, string>
    distance_source_priority?: string[]
    required_missing_evidence?: string[]
    must_not_claim?: string[]
    boundary?: string
  }
}

export type ExperimentFeedbackIterationPlan = {
  status: string
  planner_mode?: string
  objective?: string
  structural_distance_source?: string
  data_quality?: Record<string, unknown>
  validated_singletons?: Array<Record<string, unknown>>
  pair_candidates?: Array<Record<string, unknown>>
  remote_exploration?: Array<Record<string, unknown>>
  next_round_library_design?: Record<string, unknown>
  combination_rule?: string
  required_next_measurements?: string[]
  scientific_boundary?: string
  blocked_reason?: string
}

export type OpsSummary = {
  status: 'ok' | string
  uptime_seconds: number
  process: {
    pid: number
    cwd: string
  }
  storage: {
    project_root: string
    deploy_data: DeployDataReadiness['root']
    disk: {
      path: string
      total_bytes: number
      used_bytes: number
      free_bytes: number
      used_percent: number | null
    }
  }
  data: {
    summary: DeployDataReadiness['summary']
    live_ready: boolean
    missing_or_demo_components: string[]
  }
  workers: Record<string, {
    queue: string
    soft_time_limit: number
    time_limit: number
  }>
  runtime?: {
    redis?: {
      status: string
      broker_url?: string
      queues?: Record<string, { length: number | null }>
      error?: string | null
    }
    celery?: {
      status: string
      online_workers: number
      active_tasks: number
      active_by_worker?: Record<string, number>
      registered_worker_count?: number
      error?: string | null
    }
  }
  external_endpoints: Record<string, string | null>
  notifications?: {
    enabled: boolean
    configured: boolean
    kind: string
    delivery: string
    target: string
    valid_url_shape: boolean
    mode: string
    policy?: Record<string, unknown>
  }
  monitoring: {
    alert_count: number
    checks: Array<{
      name: string
      status: string
      severity: string
      message: string
      details?: Record<string, unknown>
    }>
    alerts: Array<{
      name: string
      status: string
      severity: string
      message: string
      details?: Record<string, unknown>
    }>
  }
}

export type MdProtocol = {
  id: string
  label: string
  purpose: string
  recommended_for: string[]
  risk_level: string
  parameters: Record<string, string | number | boolean>
  scientific_controls?: {
    force_field_rationale?: string
    water_model_rationale?: string
    system_preparation_checks?: string[]
    cutoff_policy?: Record<string, string | number | boolean>
    constraint_policy?: Record<string, string | number | boolean>
    replicate_policy?: {
      recommended_replicates?: number
      minimum_for_ranking?: number
      note?: string
    }
  }
  interpretation_policy: {
    minimum_publishable_ns: number
    expected_confidence: string
    review_note: string
  }
}

export type MdProtocolList = {
  version: number
  default_protocol_id: string
  protocols: MdProtocol[]
}

export type ProjectAccessRole = 'owner' | 'editor' | 'viewer'
export type ProjectPermissions = Record<string, boolean>

export type ProjectMember = {
  id: string
  project_id: string
  user_id: number
  email?: string | null
  name?: string | null
  role: Exclude<ProjectAccessRole, 'owner'>
  created_at: string
}

export type OrganizationMember = {
  id: string
  organization_id: string
  user_id: number
  email?: string | null
  name?: string | null
  role: 'member' | 'admin' | string
  created_at: string
}

export type ProjectOrganizationGrant = {
  id: string
  project_id: string
  project_name?: string | null
  organization_id: string
  organization_name?: string | null
  role: Exclude<ProjectAccessRole, 'owner'>
  created_by_user_id?: number | null
  created_at: string
}

export type Organization = {
  id: string
  name: string
  owner_user_id: number
  members: OrganizationMember[]
  project_grants: ProjectOrganizationGrant[]
  created_at: string
}

export type PermissionAudit = {
  id: string
  action: string
  actor_user_id?: number | null
  target_user_id?: number | null
  project_id?: string | null
  organization_id?: string | null
  role_before?: string | null
  role_after?: string | null
  created_at: string
}

export type ProjectListItem = {
  id: string
  name: string
  description?: string | null
  sequence_count: number
  file_count: number
  wiki_ready: boolean
  access_role: ProjectAccessRole
  permissions?: ProjectPermissions
  created_at: string
  updated_at: string
}

export type ProjectDetail = {
  id: string
  name: string
  description?: string | null
  user_id: number
  sequences: Array<{ id: string; name: string; sequence: string; notes?: string | null; created_at: string }>
  batch_jobs: Array<{ id: string; status: string; total: number; completed: number; results?: ApiRecord; created_at: string }>
  access_role: ProjectAccessRole
  permissions?: ProjectPermissions
  members: ProjectMember[]
  created_at: string
  updated_at: string
}

export type ProjectDbtlTraceSummary = {
  schema_version: string
  status: string
  project_memory_status: string
  learning_status: string
  next_round_status: string
  next_round_structural_distance_source?: string
  next_round_combination_evidence_status?: string
  formal_decision_status: string
  counts: {
    rounds: number
    variants: number
    feedback_records: number
    training_eligible_feedback_records: number
  }
  missing_entities: string[]
  top_missing_for_training: Array<{ reason: string; count: number }>
  required_actions: Array<{
    action: string
    category?: string
    priority?: string
    reason: string
    blocks?: string[]
    top_missing_reasons?: Array<{ reason: string; count: number }>
  }>
  required_action_contract?: {
    schema_version: string
    status: string
    action_count: number
    by_category: Record<string, number>
    by_priority: Record<string, number>
    allowed_categories: string[]
    allowed_priorities: string[]
    read_only: boolean
    boundary: string
  }
  project_memory_readiness?: {
    schema_version: 'dbtl_project_memory_readiness_v1' | string
    status: string
    read_only: boolean
    entity_status: Record<string, {
      status: string
      count?: number
    }>
    ready_entity_count: number
    missing_entity_count: number
    missing_entities: string[]
    readiness_fraction: number
    source_contract: string
    required_entities: string[]
    must_not_claim: string[]
    boundary: string
  }
  feedback_readiness?: {
    schema_version: 'dbtl_feedback_readiness_summary_v1' | string
    status: string
    read_only: boolean
    source_contract: string
    record_count: number
    training_eligible_count: number
    training_batch_minimum: number
    top_missing_for_training: Array<{ reason: string; count: number }>
    missing_for_training_counts: Record<string, number>
    claim_eligible_counts: Record<string, number>
    assay_qc_summary: {
      qc_status_counts: Record<string, number>
      formal_decision_counts: Record<string, number>
      assay_condition_counts: Record<string, number>
      replicate_counts: Record<string, number>
      measured_metric_counts: Record<string, number>
    }
    next_round_constraint_status: string
    must_not_claim: string[]
    boundary: string
  }
  readiness_bridge?: {
    schema_version: string
    status: string
    read_only: boolean
    project_memory_readiness_status: string
    feedback_readiness_status: string
    next_round_constraint_status: string
    combination_evidence_status: string
    downstream_status_views: string[]
    required_actions: string[]
    must_not_claim: string[]
    boundary: string
  }
  p4_closed_loop_readiness?: {
    schema_version: string
    status: string
    read_only: boolean
    active_learning_batch_contract?: {
      schema_version: 'p4_active_learning_batch_contract_v1' | string
      status: string
      read_only: boolean
      batch_policy?: Record<string, unknown>
      observed?: Record<string, unknown>
      blocked_reasons?: string[]
      must_not_claim?: string[]
      boundary?: string
    }
    model_calibration_registry_contract?: {
      schema_version: 'p4_model_calibration_registry_contract_v1' | string
      status: string
      read_only: boolean
      required_registry_fields?: string[]
      observed?: Record<string, unknown>
      blocked_reasons?: string[]
      must_not_claim?: string[]
      boundary?: string
    }
    manufacturing_constraint_contract?: {
      schema_version: 'p4_manufacturing_constraint_schema_v1' | string
      status: string
      read_only: boolean
      required_constraint_fields?: string[]
      observed?: Record<string, unknown>
      blocked_reasons?: string[]
      must_not_claim?: string[]
      boundary?: string
    }
    operator_review_contract?: {
      schema_version: 'p4_operator_review_contract_v1' | string
      status: string
      read_only: boolean
      observed?: Record<string, unknown>
      required_review_fields?: string[]
      blocked_reasons?: string[]
      must_not_claim?: string[]
      boundary?: string
    }
    gates: Record<string, {
      status: string
      requires?: string[]
      observed?: Record<string, unknown>
    }>
    blocked_gates: string[]
    required_action_count: number
    must_not_claim: string[]
    boundary: string
  }
  report_contract: {
    show_project_model: boolean
    show_learning_readiness: boolean
    show_next_round_library_design: boolean
    must_label_computational_outputs_as_hypothesis: boolean
    must_not_claim_training_or_wet_lab_validation: boolean
  }
  boundary: string
}

export type ProjectDbtlTrace = {
  schema_version: string
  project_id: string
  round_key: string
  project_model: ApiRecord
  learning_readiness: ApiRecord
  next_round_library_design: ApiRecord
  trace_summary: ProjectDbtlTraceSummary
  wt_baseline: ApiRecord
  variants: ApiRecord[]
  formal_decision: ApiRecord
}

export type MdProtocolResolved = {
  protocol_id: string
  parameters: Record<string, string | number | boolean>
  template: MdProtocol
  protocol_review?: Record<string, unknown>
}

export type LigandStageResult = {
  stage: string
  status: string
  blocked_reason?: string | null
  required_tools?: string[]
  required_parameters?: string[]
  missing_parameters?: string[]
  provided_inputs?: Record<string, boolean>
  command_preview?: string | null
  next_action?: string | null
  missing_requirements?: string[]
}

export type LigandPreprocessResult = {
  status: string
  job_id?: string
  input?: Record<string, unknown>
  sdf?: {
    is_2d_sdf?: boolean
    atom_count?: number
    bond_count?: number
    inferred_dimension?: string
    header_dimension?: string
    all_z_zero?: boolean
    element_counts?: Record<string, number>
  }
  toolchain?: Record<string, { available?: boolean; commands?: Record<string, string | null> }>
  stage_results?: LigandStageResult[]
  stage_contract?: {
    requested_stages?: string[]
    parameters?: Record<string, unknown>
    required_parameters?: Record<string, string[]>
  }
  artifact_manifest?: Record<string, unknown>
  scientific_boundary?: {
    input_2d_sdf_can_enter_md_directly?: boolean
    requires_3d_conformer_before_docking?: boolean
    requires_ligand_topology_before_gromacs?: boolean
  }
  next_steps?: string[]
}

export type MdReplicateBatchRequest = {
  protocol_id?: string | null
  overrides?: Record<string, unknown>
  pdb_object_name?: string | null
  pdb_data?: string | null
  pdb_path?: string | null
  replicate_count?: number
  replicate_variants?: Array<string | Record<string, unknown>>
  replicate_seed_base?: number
  mutant_inputs?: Record<string, {
    pdb_object_name?: string | null
    pdb_data?: string | null
    pdb_path?: string | null
  }>
  dry_run?: boolean
  confirmation?: string | null
}

export type MdReplicateBatchResponse = {
  status: 'planned' | 'submitted' | 'partially_submitted' | string
  dry_run: boolean
  batch_id: string
  protocol_id: string
  replicate_execution_plan: Record<string, unknown>
  submittable_count?: number
  submitted_count?: number
  blocked_count: number
  submittable_tasks?: Array<Record<string, unknown>>
  submitted_tasks?: Array<{
    planned_task_id: string
    task_id: string
    tool: string
    queue?: string | null
    variant: string
    replicate_index: number
    seed: number
    status_url: string
  }>
  blocked_tasks: Array<Record<string, unknown>>
  confirmation_required?: string
  note?: string
  next_steps?: string[]
}

export type AdminUser = {
  id: number
  email: string
  name: string
  role: 'admin' | 'researcher' | string
  is_active?: boolean
  locked_at?: string | null
  disabled_reason?: string | null
  created_at?: string | null
}

export type ToolTaskAudit = {
  id: number
  task_id: string
  user_id: number
  tool: string
  status: string
  queue?: string | null
  runtime_policy?: {
    soft_time_limit?: number | null
    time_limit?: number | null
  }
  progress?: number | null
  stage?: string | null
  input_summary?: Record<string, unknown> | null
  result_summary?: Record<string, unknown> | null
  artifact_manifest?: Record<string, unknown> | null
  error?: string | null
  duration_seconds?: number | null
  failure_class?: string | null
  is_slow?: boolean
  runtime_environment?: {
    python_version?: string
    python_executable?: string
    platform?: string
    machine?: string
  }
  submitted_at?: string | null
  terminal_recorded_at?: string | null
  updated_at?: string | null
}

export type ToolTaskAuditSummary = {
  total: number
  status_counts: Record<string, number>
  tool_counts: Record<string, number>
  queue_counts: Record<string, number>
  failure_counts: Record<string, number>
  slow_count: number
  duration: {
    mean_seconds?: number | null
    max_seconds?: number | null
    sample_count: number
  }
  recent_failures: Array<{
    task_id?: string
    tool?: string
    failure_class?: string
    status?: string
    updated_at?: string | null
  }>
  failure_trend?: Array<{
    date: string
    failure_counts: Record<string, number>
    total_failures: number
  }>
  alerting?: {
    status: 'ok' | 'triggered' | string
    mode: string
    external_delivery: string
    rules: Array<{
      name: string
      status: string
      severity: string
      threshold: number
      observed: number
    }>
    recommended_actions: string[]
  }
  runtime_environment?: ToolTaskAudit['runtime_environment']
}

export type AdminTaskAuditFilters = {
  tool?: string
  status?: string
  queue?: string
  failure_class?: string
  submitted_after?: string
  submitted_before?: string
  failed_only?: boolean
  slow_only?: boolean
}

export type BenchmarkCase = {
  id: string
  slug: string
  title: string
  program?: string | null
  protein_name?: string | null
  objective: string
  target_ph_range: {
    min: number
    max: number
    focus?: number | null
  }
  sequence_length: number
  structure_model: {
    name: string
    type: string
    calcium_free?: boolean
  }
  source_summary: string
  analysis_highlights: string[]
  candidate_mutations: BenchmarkMutation[]
  evidence_goals: string[]
  recommended_actions: BenchmarkAction[]
  paths: {
    source_bundle_dir: BenchmarkPathInfo
    incoming_alphafold_dir: BenchmarkPathInfo
    incoming_sifts_dir: BenchmarkPathInfo
    incoming_annotations_dir: BenchmarkPathInfo
    incoming_reference_docs_dir: BenchmarkPathInfo
    incoming_reference_doc_manifest_file: BenchmarkPathInfo
    discovery_report_file: BenchmarkPathInfo
    background_file: BenchmarkPathInfo
    sequence_file: BenchmarkPathInfo
    original_structure_file: BenchmarkPathInfo
    deploy_structure_file: BenchmarkPathInfo
    deploy_alphafold_dir: BenchmarkPathInfo
    deploy_sifts_dir: BenchmarkPathInfo
    deploy_annotations_dir: BenchmarkPathInfo
    deploy_bundle_dir: BenchmarkPathInfo
    deploy_bundle_manifest_file: BenchmarkPathInfo
    deploy_bundle_archive_file: BenchmarkPathInfo
  }
  status: {
    pdb_staged: boolean
    alphafold_ready: boolean
    sifts_ready: boolean
    annotations_ready: boolean
    foldseek_indexed: boolean
    bundle_ready: boolean
    bundle_archive_ready: boolean
    reference_docs_ready: boolean
    reference_doc_manifest_ready: boolean
    discovery_report_ready: boolean
    asset_counts: {
      alphafold_structures: number
      sifts_mappings: number
      annotation_files: number
      reference_doc_files: number
      foldseek_pdb_entries: number
      foldseek_alphafold_entries: number
      bundle_files: number
      bundle_archive_size_bytes: number
      discovered_structures: number
      discovered_alphafold: number
      discovered_sifts: number
      discovered_annotations: number
      discovered_reference_docs: number
    }
  }
  discovery?: {
    report_path: BenchmarkPathInfo
    counts: Record<string, number>
    preview: Record<string, BenchmarkDiscoveryItem[]>
  } | null
  selected_reference_docs?: {
    manifest_path: BenchmarkPathInfo
    selected_count: number
    preview: BenchmarkSelectedDoc[]
  } | null
  bundle?: {
    manifest_path: BenchmarkPathInfo
    archive_path: BenchmarkPathInfo
    download_url?: string | null
    archive_size_bytes: number
    bundle_contents: Record<string, number>
  } | null
  summary: BenchmarkSummary
}

function emitAuthEvent(name: string) {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event(name))
  }
}

export function getAccessToken() {
  return localStorage.getItem(ACCESS_TOKEN_KEY)
}

export function getRefreshToken() {
  return localStorage.getItem(REFRESH_TOKEN_KEY)
}

function getTokenExpiryMs(token: string): number | null {
  try {
    const [, payload] = token.split('.')
    if (!payload) return null
    const normalized = payload.replace(/-/g, '+').replace(/_/g, '/')
    const decoded = JSON.parse(atob(normalized))
    if (typeof decoded.exp !== 'number') return null
    return decoded.exp * 1000
  } catch {
    return null
  }
}

export function storeAuthTokens(accessToken: string, refreshToken?: string | null) {
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken)
  if (refreshToken) {
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken)
  }
  emitAuthEvent(AUTH_UPDATED_EVENT)
}

export function clearAuthTokens() {
  localStorage.removeItem(ACCESS_TOKEN_KEY)
  localStorage.removeItem(REFRESH_TOKEN_KEY)
  localStorage.removeItem('currentConversationId')
  emitAuthEvent(AUTH_CLEARED_EVENT)
}

let refreshPromise: Promise<string | null> | null = null

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = getRefreshToken()
  if (!refreshToken) {
    clearAuthTokens()
    return null
  }
  if (refreshPromise) {
    return refreshPromise
  }

  refreshPromise = (async () => {
    try {
      const res = await fetch(`${BASE}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ refresh_token: refreshToken }),
      })

      if (!res.ok) {
        clearAuthTokens()
        return null
      }

      const data = await res.json() as {
        access_token: string
        refresh_token: string
      }
      storeAuthTokens(data.access_token, data.refresh_token)
      return data.access_token
    } catch {
      clearAuthTokens()
      return null
    } finally {
      refreshPromise = null
    }
  })()

  return refreshPromise
}

export async function ensureValidAccessToken(): Promise<string | null> {
  const token = getAccessToken()
  if (!token) return null

  const expiryMs = getTokenExpiryMs(token)
  if (!expiryMs) {
    return refreshAccessToken()
  }

  const refreshWindowMs = 60_000
  if (expiryMs && Date.now() >= expiryMs - refreshWindowMs) {
    return refreshAccessToken()
  }

  return token
}

export async function authFetch(
  input: string,
  options: RequestInit = {},
  retryOn401 = true
): Promise<Response> {
  const token = await ensureValidAccessToken()
  const headers = new Headers(options.headers || {})
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const response = await fetch(input, { ...options, headers, credentials: 'same-origin' })
  if (response.status !== 401) {
    return response
  }

  if (!retryOn401) {
    return response
  }

  const nextToken = await refreshAccessToken()
  if (!nextToken) {
    return response
  }

  const retryHeaders = new Headers(options.headers || {})
  retryHeaders.set('Authorization', `Bearer ${nextToken}`)
  return fetch(input, { ...options, headers: retryHeaders, credentials: 'same-origin' })
}

export function normalizeFileDownloadUrl(downloadUrl?: string | null, objectName?: string | null): string {
  if (objectName) {
    return `${BASE}/files/${objectName}/download`
  }

  if (!downloadUrl) {
    return ''
  }

  if (downloadUrl.startsWith('/api/')) {
    return downloadUrl
  }

  try {
    const parsed = new URL(downloadUrl, window.location.origin)
    if (parsed.pathname.startsWith('/api/')) {
      return `${parsed.pathname}${parsed.search}`
    }

    const bucketPrefix = '/protein-files/'
    if (parsed.pathname.startsWith(bucketPrefix)) {
      const normalizedObjectName = decodeURIComponent(parsed.pathname.slice(bucketPrefix.length))
      if (normalizedObjectName) {
        return `${BASE}/files/${normalizedObjectName}/download`
      }
    }
  } catch {
    // Fall through and return the original URL unchanged.
  }

  return downloadUrl
}

export function buildToolTaskArtifactBundleUrl(taskId: string): string {
  return `${BASE}/tools/tasks/${taskId}/artifacts/download`
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  config: RequestConfig = {}
): Promise<T> {
  const res = await requestRaw(path, options, config)
  // 204 No Content — nothing to parse
  if (res.status === 204) return undefined as T
  return res.json()
}

async function requestRaw(
  path: string,
  options: RequestInit = {},
  config: RequestConfig = {}
): Promise<Response> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((options.headers as Record<string, string>) || {}),
  }

  const authenticated = config.authenticated ?? true
  const res = authenticated
    ? await authFetch(`${BASE}${path}`, { ...options, headers })
    : await fetch(`${BASE}${path}`, { ...options, headers, credentials: 'same-origin' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new ApiError(err.detail || 'Request failed', res.status)
  }
  return res
}

async function requestText(
  path: string,
  options: RequestInit = {},
  config: RequestConfig = {}
): Promise<string> {
  const res = await requestRaw(path, options, config)
  return res.text()
}

function buildAdminTaskAuditQuery(limit: number, filters: AdminTaskAuditFilters = {}) {
  const params = new URLSearchParams({ limit: String(limit) })
  Object.entries(filters).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '' || value === false) return
    params.set(key, String(value))
  })
  return params.toString()
}

async function sendUploadAttempt(
  path: string,
  formData: FormData,
  token: string | null,
  onProgress?: (progress: number) => void
): Promise<{ status: number; responseText: string }> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${BASE}${path}`)
    if (token) {
      xhr.setRequestHeader('Authorization', `Bearer ${token}`)
    }

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(Math.round((event.loaded / event.total) * 100))
      }
    }

    xhr.onload = () => {
      resolve({
        status: xhr.status,
        responseText: xhr.responseText,
      })
    }

    xhr.onerror = () => reject(new Error('Network error'))
    xhr.send(formData)
  })
}

export async function uploadFormWithProgress<T>(
  path: string,
  formData: FormData,
  config: UploadConfig = {}
): Promise<T> {
  const retryOn401 = config.retryOn401 ?? true
  let token = await ensureValidAccessToken()
  let response = await sendUploadAttempt(path, formData, token, config.onProgress)

  if (response.status === 401 && retryOn401) {
    token = await refreshAccessToken()
    if (token) {
      response = await sendUploadAttempt(path, formData, token, config.onProgress)
    }
  }

  let payload: unknown = null
  if (response.responseText) {
    try {
      payload = JSON.parse(response.responseText)
    } catch {
      payload = response.responseText
    }
  }

  if (response.status < 200 || response.status >= 300) {
    const detail =
      typeof payload === 'object' && payload !== null && 'detail' in payload
        ? String((payload as { detail?: string }).detail || 'Upload failed')
        : typeof payload === 'string' && payload.trim()
          ? payload
          : 'Upload failed'
    throw new ApiError(detail, response.status)
  }

  return payload as T
}

async function getEnzymeDbStatus(): Promise<EnzymeDbFamiliesStatus>
async function getEnzymeDbStatus(family: EnzymeDbFamily): Promise<EnzymeDbFamilyStatus>
async function getEnzymeDbStatus(family?: EnzymeDbFamily) {
  if (family) {
    return request<EnzymeDbFamilyStatus>(`/data/enzyme-dbs/${encodeURIComponent(family)}/status`)
  }
  return request<EnzymeDbFamiliesStatus>('/data/enzyme-dbs/status')
}

export const api = {
  // Auth
  login: (email: string, password: string) =>
    request<{ access_token: string; refresh_token: string; token_type: string; user: { id: number; email: string; name: string; role?: string } }>(
      '/auth/login',
      { method: 'POST', body: JSON.stringify({ email, password }) },
      { authenticated: false }
    ),

  register: (email: string, password: string, name: string) =>
    request<{ access_token: string; refresh_token: string; token_type: string; user: { id: number; email: string; name: string; role?: string } }>(
      '/auth/register',
      { method: 'POST', body: JSON.stringify({ email, password, name }) },
      { authenticated: false }
    ),

  // Conversations
  getConversations: () => request<ApiConversationSummary[]>('/conversations'),

  createConversation: () =>
    request<ApiConversationSummary>('/conversations', { method: 'POST', body: JSON.stringify({ title: 'New Conversation' }) }),

  getConversation: (id: string) => request<ApiConversationDetail>(`/conversations/${id}`),

  getActiveStrategyCheckpoint: (conversationId: string) =>
    request<ApiActiveStrategyCheckpoint>(`/chat/strategy-checkpoints/active?conversation_id=${encodeURIComponent(conversationId)}`),

  getStrategyCheckpointHistory: (conversationId: string, limit = 20) =>
    request<ApiStrategyCheckpointHistory>(
      `/chat/strategy-checkpoints/history?conversation_id=${encodeURIComponent(conversationId)}&limit=${encodeURIComponent(String(limit))}`
    ),

  getRecentStrategyMemory: (params: { conversationId?: string; projectId?: string; limit?: number }) => {
    const query = new URLSearchParams()
    if (params.conversationId) query.set('conversation_id', params.conversationId)
    if (params.projectId) query.set('project_id', params.projectId)
    if (params.limit) query.set('limit', String(params.limit))
    return request<ApiRecentStrategyMemory>(`/chat/strategy-checkpoints/recent?${query}`)
  },

  getAgentStrategyPolicy: () => request<ApiAgentStrategyPolicy>('/chat/strategy-policy'),

  updateConversation: (id: string, title: string) =>
    request<ApiConversationDetail>(`/conversations/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ title }),
    }),

  deleteConversation: (id: string) =>
    request<void>(`/conversations/${id}`, { method: 'DELETE' }),

  // Models
  getModels: () => request<Array<{ id: string; name: string; provider: string; model: string; description: string; available: boolean }>>('/chat/models'),

  // Tools
  getTools: () => request<{ tools: ToolSchemaResponse[]; categories: Record<string, string[]> }>('/tools'),

  preflightTool: (name: string, evidence: Record<string, boolean>, options?: { task_ids?: string[]; snapshot_id?: string }) =>
    request<{ allowed: boolean; violations: Array<{ code: string; dependency?: string; tool?: string }>; warnings: Array<Record<string, unknown>> }>(`/tools/${name}/preflight`, {
      method: 'POST',
      body: JSON.stringify({ evidence, ...(options || {}) }),
    }),

  callTool: (name: string, params: Record<string, unknown>) =>
    request<{ status: string; result: Record<string, unknown> }>(`/tools/${name}/call`, {
      method: 'POST',
      body: JSON.stringify({ params }),
    }),

  runMutationEpistasisCheck: (params: Record<string, unknown>) =>
    request<{ status: string; result: MutationEpistasisCheckResult }>('/tools/mutation_epistasis_check/call', {
      method: 'POST',
      body: JSON.stringify({ params }),
    }),

  submitTool: (name: string, params: Record<string, unknown>) =>
    request<{ status: string; task_id: string; tool: string; queue?: string }>(`/tools/${name}/submit`, {
      method: 'POST',
      body: JSON.stringify({ params }),
    }),

  runLigandPreprocess: (params: Record<string, unknown>) =>
    request<{ status: string; task_id: string; tool: string; queue?: string }>('/tools/ligand_preprocess/submit', {
      method: 'POST',
      body: JSON.stringify({ params }),
    }),

  getToolTask: (taskId: string, options: RequestInit = {}) =>
    request<{
      task_id: string
      status: string
      tool?: string | null
      result?: { status?: string; tool?: string; result?: unknown; error?: string } | null
      error?: string | null
      progress?: number
      message?: string | null
      stage?: string | null
      current_step?: number | null
      total_steps?: number | null
      cancel_requested?: boolean
      cancel_requested_at?: string | null
      rid?: string | null
      can_resume?: boolean
    }>(`/tools/tasks/${taskId}`, options),

  resumeBlastTask: (taskId: string) =>
    request<{ status: string }>(`/tools/tasks/${taskId}/resume`, { method: 'POST' }),

  createBlastReportRevision: (taskId: string, conversationId: number) =>
    request<{ message_id: number; snapshot_id: string }>(`/tools/tasks/${taskId}/report-revision`, {
      method: 'POST', body: JSON.stringify({ conversation_id: conversationId }),
    }),

  listToolTaskAudits: (limit = 50) =>
    request<{ count: number; audits: ToolTaskAudit[] }>(`/tools/tasks/audits?limit=${encodeURIComponent(String(limit))}`),

  cancelToolTask: (taskId: string) =>
    request<{ task_id: string; status: string; tool?: string | null; cancel_requested_at?: string | null }>(`/tools/tasks/${taskId}/cancel`, {
      method: 'POST',
    }),

  getMdProtocols: () => request<MdProtocolList>('/tools/md/protocols'),

  resolveMdProtocol: (protocolId: string, overrides: Record<string, unknown> = {}) =>
    request<MdProtocolResolved>(`/tools/md/protocols/${protocolId}/resolve`, {
      method: 'POST',
      body: JSON.stringify({ overrides }),
    }),

  submitMdReplicateBatch: (payload: MdReplicateBatchRequest) =>
    request<MdReplicateBatchResponse>('/tools/md/replicates/submit', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  listAdminUsers: () =>
    request<{ count: number; users: AdminUser[] }>('/auth/admin/users'),

  updateAdminUserRole: (userId: number, role: 'admin' | 'researcher') =>
    request<AdminUser>(`/auth/admin/users/${userId}/role`, {
      method: 'PATCH',
      body: JSON.stringify({ role }),
    }),

  updateAdminUserStatus: (userId: number, payload: { is_active?: boolean; locked?: boolean; disabled_reason?: string | null }) =>
    request<AdminUser>(`/auth/admin/users/${userId}/status`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  listAdminOrganizations: (limit = 100) =>
    request<{ count: number; organizations: Organization[] }>(`/projects/admin/organizations?limit=${limit}`),

  createAdminOrganization: (name: string) =>
    request<Organization>('/projects/admin/organizations', {
      method: 'POST',
      body: JSON.stringify({ name }),
    }),

  addAdminOrganizationMember: (organizationId: string, email: string, role: 'member' | 'admin') =>
    request<OrganizationMember>(`/projects/admin/organizations/${organizationId}/members`, {
      method: 'POST',
      body: JSON.stringify({ email, role }),
    }),

  updateAdminOrganizationMember: (organizationId: string, memberId: string, role: 'member' | 'admin') =>
    request<OrganizationMember>(`/projects/admin/organizations/${organizationId}/members/${memberId}`, {
      method: 'PATCH',
      body: JSON.stringify({ role }),
    }),

  removeAdminOrganizationMember: (organizationId: string, memberId: string) =>
    request<void>(`/projects/admin/organizations/${organizationId}/members/${memberId}`, { method: 'DELETE' }),

  listAdminPermissionAudits: (limit = 100, filters: { action?: string; project_id?: string; organization_id?: string } = {}) => {
    const params = new URLSearchParams({ limit: String(limit) })
    if (filters.action) params.set('action', filters.action)
    if (filters.project_id) params.set('project_id', filters.project_id)
    if (filters.organization_id) params.set('organization_id', filters.organization_id)
    return request<{ count: number; audits: PermissionAudit[] }>(`/projects/admin/permission-audits?${params}`)
  },

  listAdminTaskAudits: (limit = 50, filters: AdminTaskAuditFilters = {}) =>
    request<{ count: number; audits: ToolTaskAudit[]; summary?: ToolTaskAuditSummary }>(
      `/tools/admin/tasks/audits?${buildAdminTaskAuditQuery(limit, filters)}`
    ),

  getAdminTaskAuditSummary: (limit = 500, filters: AdminTaskAuditFilters = {}) =>
    request<ToolTaskAuditSummary>(`/tools/admin/tasks/audits/summary?${buildAdminTaskAuditQuery(limit, filters)}`),

  exportAdminTaskAudits: (limit = 500, filters: AdminTaskAuditFilters = {}) =>
    requestRaw(`/tools/admin/tasks/audits/export?${buildAdminTaskAuditQuery(limit, filters)}`),

  getAdminDataReadiness: () =>
    request<DeployDataReadiness & { admin?: { user_id: number; view: string; read_only: boolean } }>('/data/admin/readiness'),

  listAdminDeployDataUpdates: (filters: { component?: string; status?: string; limit?: number } = {}) => {
    const params = new URLSearchParams({ limit: String(filters.limit || 50) })
    if (filters.component) params.set('component', filters.component)
    if (filters.status) params.set('status', filters.status)
    return request<{ count: number; updates: DeployDataReadiness['updates']['manifests']; filters?: DeployDataReadiness['updates']['filters'] }>(
      `/data/admin/updates?${params.toString()}`
    )
  },

  triggerDeployDataImport: (payload: DeployDataImportRequest) =>
    request<{
      status: string
      plan?: Record<string, unknown>
      returncode?: number
      stdout?: string
      stderr?: string
      readiness?: DeployDataReadiness
    }>('/data/admin/import', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  // Auth (extended)
  getSession: () =>
    request<{ authenticated: boolean; user: { id: number | string; email: string; name: string; role?: string } | null }>(
      '/auth/session'
    ),

  getMe: () =>
    request<{ id: string; email: string; name: string }>('/auth/me'),

  refreshToken: (refresh_token: string) =>
    request<{ access_token: string; refresh_token: string }>('/auth/refresh', {
      method: 'POST',
      body: JSON.stringify({ refresh_token }),
    }, { authenticated: false }),

  refreshSession: () =>
    request<{ access_token: string; refresh_token: string; token_type: string; user: { id: number; email: string; name: string; role?: string } }>(
      '/auth/refresh',
      { method: 'POST', body: JSON.stringify({ refresh_token: null }) },
      { authenticated: false }
    ),

  logout: () =>
    request<void>('/auth/logout', {
      method: 'POST',
    }, { authenticated: false }),

  // Projects
  getProjects: () => request<ProjectListItem[]>('/projects'),

  createProject: (name: string, description?: string) =>
    request<ProjectDetail>('/projects', { method: 'POST', body: JSON.stringify({ name, description }) }),

  getProject: (id: string) => request<ProjectDetail>(`/projects/${id}`),

  getProjectDbtlTrace: (projectId: string, roundKey?: string) => {
    const params = roundKey ? `?round_key=${encodeURIComponent(roundKey)}` : ''
    return request<ProjectDbtlTrace>(`/projects/${projectId}/dbtl/trace${params}`)
  },

  updateProject: (id: string, data: { name?: string; description?: string }) =>
    request<ProjectDetail>(`/projects/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),

  deleteProject: (id: string) =>
    request<void>(`/projects/${id}`, { method: 'DELETE' }),

  addSequence: (projectId: string, name: string, sequence: string, notes?: string) =>
    request<{ id: string; name: string; sequence: string; notes?: string | null; created_at: string }>(`/projects/${projectId}/sequences`, {
      method: 'POST',
      body: JSON.stringify({ name, sequence, notes }),
    }),

  removeSequence: (projectId: string, seqId: string) =>
    request<void>(`/projects/${projectId}/sequences/${seqId}`, { method: 'DELETE' }),

  batchRun: (projectId: string, tool: string, params?: Record<string, unknown>) =>
    request<ApiRecord>(`/projects/${projectId}/batch-run`, {
      method: 'POST',
      body: JSON.stringify({ tool, params: params || {} }),
    }),

  getBatchJobs: (projectId: string) => request<ProjectDetail['batch_jobs']>(`/projects/${projectId}/batch-jobs`),

  getProjectMembers: (projectId: string) =>
    request<ProjectMember[]>(`/projects/${projectId}/members`),

  addProjectMember: (projectId: string, email: string, role: 'viewer' | 'editor') =>
    request<ProjectMember>(`/projects/${projectId}/members`, {
      method: 'POST',
      body: JSON.stringify({ email, role }),
    }),

  updateProjectMember: (projectId: string, memberId: string, role: 'viewer' | 'editor') =>
    request<ProjectMember>(`/projects/${projectId}/members/${memberId}`, {
      method: 'PATCH',
      body: JSON.stringify({ role }),
    }),

  removeProjectMember: (projectId: string, memberId: string) =>
    request<void>(`/projects/${projectId}/members/${memberId}`, { method: 'DELETE' }),

  getProjectOrganizationGrants: (projectId: string) =>
    request<ProjectOrganizationGrant[]>(`/projects/${projectId}/organization-grants`),

  addProjectOrganizationGrant: (projectId: string, organizationId: string, role: 'viewer' | 'editor') =>
    request<ProjectOrganizationGrant>(`/projects/${projectId}/organization-grants`, {
      method: 'POST',
      body: JSON.stringify({ organization_id: organizationId, role }),
    }),

  updateProjectOrganizationGrant: (projectId: string, grantId: string, role: 'viewer' | 'editor') =>
    request<ProjectOrganizationGrant>(`/projects/${projectId}/organization-grants/${grantId}`, {
      method: 'PATCH',
      body: JSON.stringify({ role }),
    }),

  removeProjectOrganizationGrant: (projectId: string, grantId: string) =>
    request<void>(`/projects/${projectId}/organization-grants/${grantId}`, { method: 'DELETE' }),

  // Files
  getFiles: () => request<ApiRecord[]>('/files'),

  uploadFile: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return uploadFormWithProgress<{
      id: string
      object_name?: string
      download_url?: string
    }>('/files/upload', formData)
  },

  getPdbResidueMappingByName: (objectName: string, chainId?: string, uniprotId?: string, uniprotStart = 1) =>
    request<unknown>('/pdb/mapping-by-name', {
      method: 'POST',
      body: JSON.stringify({
        object_name: objectName,
        chain_id: chainId || null,
        uniprot_id: uniprotId || null,
        uniprot_start: uniprotStart,
      }),
    }),

  getPdbStructureSearchByName: (objectName: string, database = 'pdb', maxResults = 5) =>
    request<unknown>('/pdb/structure-search-by-name', {
      method: 'POST',
      body: JSON.stringify({
        object_name: objectName,
        database,
        max_results: maxResults,
      }),
    }),

  // ========== Data Browser ==========
  getDataStats: () => request<DataStats>('/data/stats'),

  getDataReadiness: () => request<DeployDataReadiness>('/data/readiness'),

  getToolCapabilities: () => request<ToolCapabilityAudit>('/data/tool-capabilities'),

  getLipaseDbStatus: () => request<LipaseDbStatus>('/data/lipase/status'),

  getEnzymeDbFamilies: () => getEnzymeDbStatus(),

  getEnzymeDbStatus,

  searchEnzymeDb: (family: EnzymeDbFamily, q: string, limit = 50) => {
    const params = new URLSearchParams({ q, limit: String(limit) })
    return request<EnzymeDbSearchResult>(
      `/data/enzyme-dbs/${encodeURIComponent(family)}/search?${params}`
    )
  },

  getEnzymeDbPapers: (family: EnzymeDbFamily, q?: string, limit = 50) => {
    const params = new URLSearchParams({ limit: String(limit) })
    if (q) params.set('q', q)
    return request<EnzymeDbPaperList>(
      `/data/enzyme-dbs/${encodeURIComponent(family)}/papers?${params}`
    )
  },

  getEnzymeDbVariants: (family: EnzymeDbFamily, q?: string, limit = 50) => {
    const params = new URLSearchParams({ limit: String(limit) })
    if (q) params.set('q', q)
    return request<EnzymeDbVariantList>(
      `/data/enzyme-dbs/${encodeURIComponent(family)}/variants?${params}`
    )
  },

  getEnzymeDbMeasurements: (family: EnzymeDbFamily, q?: string, limit = 50) => {
    const params = new URLSearchParams({ limit: String(limit) })
    if (q) params.set('q', q)
    return request<EnzymeDbMeasurementList>(
      `/data/enzyme-dbs/${encodeURIComponent(family)}/measurements?${params}`
    )
  },

  previewEnzymeDbPolicyDecisions: (family: EnzymeDbFamily, limit = 100) => {
    const params = new URLSearchParams({ limit: String(limit) })
    return request<EnzymeDbPolicyDecisionPreview>(
      `/data/enzyme-dbs/${encodeURIComponent(family)}/policy-decisions/preview?${params}`,
      { method: 'POST' }
    )
  },

  materializeEnzymeMetadataCuration: (family: EnzymeDbFamily, dryRun = true, limit = 100) =>
    request<EnzymeMetadataCurationMaterializeResult>(
      `/data/enzyme-dbs/${encodeURIComponent(family)}/metadata-curation/materialize`,
      {
        method: 'POST',
        body: JSON.stringify({ dry_run: dryRun, limit }),
      }
    ),

  listEnzymeMetadataCurationRecords: (filters: { family?: EnzymeDbFamily; status?: string; record_type?: string; limit?: number } = {}) => {
    const params = new URLSearchParams({ limit: String(filters.limit || 100) })
    if (filters.family) params.set('family', filters.family)
    if (filters.status) params.set('status', filters.status)
    if (filters.record_type) params.set('record_type', filters.record_type)
    return request<EnzymeMetadataCurationList>(`/data/enzyme-metadata/curation-records?${params}`)
  },

  reviewEnzymeMetadataCurationRecord: (recordId: number, status: string, reviewerNotes?: string) =>
    request<{ status: string; record: EnzymeMetadataCurationRecord }>(
      `/data/enzyme-metadata/curation-records/${recordId}/review`,
      {
        method: 'PATCH',
        body: JSON.stringify({ status, reviewer_notes: reviewerNotes }),
      }
    ),

  createEnzymeMetadataCurationBatch: (payload: { record_ids?: number[]; family?: EnzymeDbFamily; record_type?: string; limit?: number; dry_run?: boolean }) =>
    request<EnzymeMetadataCurationBatchResult>('/data/enzyme-metadata/curation-batches', {
      method: 'POST',
      body: JSON.stringify({
        record_ids: payload.record_ids,
        family: payload.family,
        record_type: payload.record_type,
        limit: payload.limit ?? 100,
        dry_run: payload.dry_run ?? true,
      }),
    }),

  listEnzymeMetadataCurationBatches: (filters: { status?: string; family?: EnzymeDbFamily; limit?: number } = {}) => {
    const params = new URLSearchParams({ limit: String(filters.limit || 100) })
    if (filters.status) params.set('status', filters.status)
    if (filters.family) params.set('family', filters.family)
    return request<EnzymeMetadataCurationBatchList>(`/data/enzyme-metadata/curation-batches?${params}`)
  },

  archiveEnzymeMetadataCurationBatch: (batchId: number, confirmation: string, reviewerNotes?: string) =>
    request<{ status: string; batch: EnzymeMetadataCurationBatch }>(
      `/data/enzyme-metadata/curation-batches/${batchId}/archive`,
      {
        method: 'PATCH',
        body: JSON.stringify({ confirmation, reviewer_notes: reviewerNotes }),
      }
    ),

  getLipasePapers: (q?: string, limit = 50) => {
    const params = new URLSearchParams({ limit: String(limit) })
    if (q) params.set('q', q)
    return request<LipasePaperList>(`/data/lipase/papers?${params}`)
  },

  getLipasePaperDetail: (paperKey: string) =>
    request<LipasePaperDetail>(`/data/lipase/papers/${encodeURIComponent(paperKey)}`),

  getLipaseVariants: (q?: string, limit = 50) => {
    const params = new URLSearchParams({ limit: String(limit) })
    if (q) params.set('q', q)
    return request<LipaseVariantList>(`/data/lipase/variants?${params}`)
  },

  getLipaseGaps: (filters: { priority?: string; status?: string; limit?: number } = {}) => {
    const params = new URLSearchParams({ limit: String(filters.limit || 100) })
    if (filters.priority) params.set('priority', filters.priority)
    if (filters.status) params.set('status', filters.status)
    return request<LipaseGapList>(`/data/lipase/gaps?${params}`)
  },

  searchLipaseEvidence: (q: string, limit = 50) => {
    const params = new URLSearchParams({ q, limit: String(limit) })
    return request<LipaseSearchResult>(`/data/lipase/search?${params}`)
  },

  getLipaseEvidenceContext: (filters: { mutations?: string[]; positions?: number[]; q?: string; limit?: number } = {}) => {
    const params = new URLSearchParams({ limit: String(filters.limit || 20) })
    for (const mutation of filters.mutations || []) params.append('mutations', mutation)
    for (const position of filters.positions || []) params.append('positions', String(position))
    if (filters.q) params.set('q', filters.q)
    return request<LipaseEvidenceContext>(`/data/lipase/evidence-context?${params}`)
  },

  submitLipaseCurationRecord: (payload: LipaseCurationCreate) =>
    request<{ status: string; record: LipaseCurationRecord }>('/data/lipase/curation-records', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  listLipaseCurationRecords: (filters: { status?: string; source_type?: string; limit?: number } = {}) => {
    const params = new URLSearchParams({ limit: String(filters.limit || 100) })
    if (filters.status) params.set('status', filters.status)
    if (filters.source_type) params.set('source_type', filters.source_type)
    return request<{ count: number; records: LipaseCurationRecord[]; reviewer_user_id: number }>(`/data/lipase/curation-records?${params}`)
  },

  reviewLipaseCurationRecord: (recordId: number, payload: { status: string; reviewer_notes?: string | null }) =>
    request<{ status: string; record: LipaseCurationRecord }>(`/data/lipase/curation-records/${recordId}/review`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  createLipaseCurationBatch: (payload: { record_ids?: number[]; source_type?: string | null; limit?: number; dry_run?: boolean }) =>
    request<
      | { status: 'planned'; dry_run: true; manifest: Record<string, unknown>; export_payload: Record<string, unknown>; confirmation_token: string }
      | { status: 'prepared'; batch: LipaseCurationBatch }
    >('/data/lipase/curation-batches', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  listLipaseCurationBatches: (filters: { status?: string; limit?: number } = {}) => {
    const params = new URLSearchParams({ limit: String(filters.limit || 100) })
    if (filters.status) params.set('status', filters.status)
    return request<{ count: number; batches: LipaseCurationBatch[]; reviewer_user_id: number }>(`/data/lipase/curation-batches?${params}`)
  },

  publishLipaseCurationBatch: (batchId: number, payload: { confirmation: string; reviewer_notes?: string | null }) =>
    request<{ status: string; batch: LipaseCurationBatch }>(`/data/lipase/curation-batches/${batchId}/publish`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  submitExperimentFeedback: (payload: ExperimentFeedbackCreate) =>
    request<{ status: string; record: ExperimentFeedbackRecord }>('/data/experiment-feedback', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  listExperimentFeedback: (filters: { project_id?: string; enzyme_name?: string; decision?: string; include_all_users?: boolean; limit?: number } = {}) => {
    const params = new URLSearchParams({ limit: String(filters.limit || 100) })
    if (filters.project_id) params.set('project_id', filters.project_id)
    if (filters.enzyme_name) params.set('enzyme_name', filters.enzyme_name)
    if (filters.decision) params.set('decision', filters.decision)
    if (filters.include_all_users) params.set('include_all_users', 'true')
    return request<{ count: number; records: ExperimentFeedbackRecord[] }>(`/data/experiment-feedback?${params}`)
  },

  summarizeExperimentFeedback: (filters: { project_id?: string; enzyme_name?: string; decision?: string; include_all_users?: boolean; limit?: number } = {}) => {
    const params = new URLSearchParams({ limit: String(filters.limit || 500) })
    if (filters.project_id) params.set('project_id', filters.project_id)
    if (filters.enzyme_name) params.set('enzyme_name', filters.enzyme_name)
    if (filters.decision) params.set('decision', filters.decision)
    if (filters.include_all_users) params.set('include_all_users', 'true')
    return request<ExperimentFeedbackSummary>(`/data/experiment-feedback/summary?${params}`)
  },

  planExperimentFeedbackIteration: (payload: {
    project_id?: string | null
    enzyme_name?: string | null
    objective?: string
    mechanism_tags?: Record<string, string[]>
    structural_distances?: Record<string, number>
    residue_distance_graph?: Record<string, unknown>
    same_region_groups?: string[][]
    remote_candidates?: Array<Record<string, unknown>>
    allow_exploratory_combinations?: boolean
  }) =>
    request<ExperimentFeedbackIterationPlan>('/data/experiment-feedback/iteration-plan', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  getOpsSummary: () => request<OpsSummary>('/ops/summary'),

  getResearchEvidence: (scope: ResearchEvidenceScope = 'all') =>
    request<ResearchEvidence>(`/research/evidence?scope=${encodeURIComponent(scope)}`),

  searchData: (q: string, category?: string, limit = 20) => {
    const params = new URLSearchParams({ q, limit: String(limit) })
    if (category) params.set('category', category)
    return request<DataSearchResponse>(`/data/search?${params}`)
  },

  getProtein: (uniprotId: string) => request<ApiRecord>(`/data/protein/${uniprotId}`),

  getProteinKinetics: (uniprotId: string, paramType?: string) => {
    const params = paramType ? `?param_type=${paramType}` : ''
    return request<ApiRecord>(`/data/protein/${uniprotId}/kinetics${params}`)
  },

  getProteinStability: (uniprotId: string) =>
    request<ApiRecord>(`/data/protein/${uniprotId}/stability`),

  getProteinStructures: (uniprotId: string) =>
    request<ApiRecord>(`/data/protein/${uniprotId}/structures`),

  getProteinEvolution: (uniprotId: string) =>
    request<ApiRecord>(`/data/protein/${uniprotId}/evolution`),

  getECNumber: (ec: string) => request<ApiRecord>(`/data/ec/${ec}`),

  searchSubstrate: (query: string) => request<ApiRecord>(`/data/substrate/${query}`),

  getReaction: (rheaId: number) => request<ApiRecord>(`/data/reaction/${rheaId}`),

  triggerIngestion: (source: string, force = false) =>
    request<ApiRecord>(`/data/ingest/${source}?force=${force}`, { method: 'POST' }),

  getBenchmarks: () =>
    request<{ benchmarks: BenchmarkSummary[]; count: number }>(
      '/data/benchmarks',
      {},
      { authenticated: false }
    ),

  getBenchmark: (caseId: string) =>
    request<BenchmarkCase>(
      `/data/benchmarks/${caseId}`,
      {},
      { authenticated: false }
    ),

  // Publish — Wiki + knowledge base
  publishReport: (projectId: string, data: {
    title: string; content: string; conversation_id?: number; tags?: string[]; collection_id?: string; parent_document_id?: string
  }) => request<{
    file_id: string; filename: string; outline_doc_id: string | null; wiki_url: string | null
  }>(`/projects/${projectId}/publish`, { method: 'POST', body: JSON.stringify(data) }),

  publishToWikiCollection: (data: {
    title: string; content: string; conversation_id?: number; tags?: string[]; collection_id: string; parent_document_id?: string
  }) => request<{
    file_id: string; filename: string; outline_doc_id: string | null; wiki_url: string | null
  }>(`/wiki/publish`, { method: 'POST', body: JSON.stringify(data) }),

  generateReport: (projectId: string, conversationId: number) =>
    request<{ title: string; content: string; conversation_id: number }>(
      `/projects/${projectId}/generate-report`,
      { method: 'POST', body: JSON.stringify({ conversation_id: conversationId }) }
    ),

  getProjectFiles: (projectId: string, fileType?: string) => {
    const params = fileType ? `?file_type=${fileType}` : ''
    return request<ApiRecord[]>(`/projects/${projectId}/files${params}`)
  },

  deleteProjectFile: (projectId: string, fileId: string) =>
    request<{ ok: boolean }>(`/projects/${projectId}/files/${fileId}`, { method: 'DELETE' }),

  bindConversationToProject: (conversationId: number, projectId: string | null) =>
    request<{ ok: boolean }>(`/conversations/${conversationId}/project`, {
      method: 'PATCH', body: JSON.stringify({ project_id: projectId })
    }),

  getProjectConversations: (projectId: string) =>
    request<ApiConversationSummary[]>(`/projects/${projectId}/conversations`),

  getWikiCollections: () =>
    request<Array<{
      id: string
      name: string
      description?: string | null
      url?: string | null
      document_count?: number | null
    }>>('/wiki/collections'),

  getCollectionTree: (collectionId: string) =>
    request<{ collection_id: string | null; root_doc_id: string | null; documents: Array<{
      id: string; title: string; parent_id: string | null; url_id: string | null;
      updated_at: string | null; emoji: string | null
    }>; error?: string }>(`/wiki/collections/${collectionId}/tree`),

  // Wiki tree + pages
  getWikiTree: (projectId: string) =>
    request<{ collection_id: string | null; root_doc_id: string | null; documents: Array<{
      id: string; title: string; parent_id: string | null; url_id: string | null;
      updated_at: string | null; emoji: string | null
    }>; error?: string }>(`/projects/${projectId}/wiki/tree`),

  getWikiPage: (projectId: string, docId: string) =>
    request<{ id: string; title: string; text: string; updated_at: string | null; url_id: string | null }>(
      `/projects/${projectId}/wiki/pages/${docId}`
    ),

  downloadProjectFile: (projectId: string, fileId: string) => {
    return requestRaw(`/projects/${projectId}/files/${fileId}/download`)
  },

  getFileContent: (projectId: string, fileId: string) => {
    return requestText(`/projects/${projectId}/files/${fileId}/content`)
  },
}
