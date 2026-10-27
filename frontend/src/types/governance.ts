export type Severity = 'critical' | 'warning' | 'info'

export type FindingCategory =
  | 'prohibited_terminology'
  | 'preferred_wording'
  | 'fact_accuracy'
  | 'required_disclaimer'
  | 'brand_tone'
  | 'contextual_messaging'
  | 'unsupported_claim'
  | 'nuanced_inconsistency'

export type EvidenceStatus =
  | 'confirmed_violation'
  | 'potential_issue'
  | 'unverified_claim'

export interface Finding {
  id: string
  category: FindingCategory
  severity: Severity
  matched_text: string | null
  start_index: number | null
  end_index: number | null
  explanation: string
  rule_id: string | null
  rule_name_or_fact: string
  suggested_correction: string | null
  evidence_status: EvidenceStatus
  source?: 'deterministic' | 'gemini_ai'
  confidence?: number | null
}

export interface ReviewResponse {
  text_length: number
  total_findings: number
  findings_by_severity: {
    critical: number
    warning: number
    info: number
  }
  findings: Finding[]
  is_compliant: boolean
  brand_name: string
  is_demo_data: boolean
  ai_status?: 'not_requested' | 'completed' | 'unavailable' | 'failed'
  ai_model?: string | null
  ai_error?: string | null
  ai_summary?: string | null
  deterministic_count?: number
  ai_count?: number
}

export interface ProhibitedTermRule {
  id: string
  term_or_pattern: string
  is_regex: boolean
  case_sensitive: boolean
  severity: Severity
  explanation: string
  suggested_replacement?: string | null
}

export interface PreferredWordingRule {
  id: string
  avoid_term: string
  preferred_term: string
  case_sensitive: boolean
  severity: Severity
  explanation: string
}

export interface ApprovedFact {
  id: string
  entity: string
  attribute: string
  approved_value: string
  context_keywords?: string[]
  conflicting_patterns?: string[]
  severity: Severity
  explanation: string
}

export interface RequiredDisclaimerRule {
  id: string
  trigger_pattern: string
  trigger_description: string
  required_disclaimer_text: string
  case_sensitive?: boolean
  severity: Severity
  explanation: string
}

export interface BrandRulesConfig {
  brand_name: string
  description?: string | null
  voice_and_tone?: string | null
  is_demo: boolean
  prohibited_terms: ProhibitedTermRule[]
  preferred_wording: PreferredWordingRule[]
  approved_facts: ApprovedFact[]
  required_disclaimers: RequiredDisclaimerRule[]
}

export type ReviewStatus = 'draft' | 'in_review' | 'changes_requested' | 'approved' | 'rejected'

export type DecisionType = 'approved' | 'changes_requested' | 'rejected'

export interface DecisionRecord {
  id: string
  decision: DecisionType
  reviewer_name: string
  is_demo_reviewer: boolean
  reviewer_id?: string | null
  guideline_version?: number
  comment: string | null
  timestamp: string
  content_version: number
  content_snapshot: string
  findings_summary: Record<string, number>
}

export interface SubmissionVersionSnapshot {
  version: number
  content: string
  timestamp: string
  title?: string | null
  status_at_save?: ReviewStatus | null
  creator_name?: string | null
}

export interface Submission {
  id: string
  title: string
  content: string
  version: number
  status: ReviewStatus
  creator_name: string
  is_demo_creator: boolean
  creator_id?: string | null
  org_id?: string | null
  storage_mode?: 'local_demo' | 'supabase_persistent'
  created_at: string
  updated_at: string
  submitted_at?: string | null
  submitted_content_snapshot?: string | null
  latest_review_response?: ReviewResponse | null
  decision_history: DecisionRecord[]
  version_history?: SubmissionVersionSnapshot[]
}

export type DiffChunkType = 'equal' | 'insert' | 'delete' | 'replace'

export type FindingResolutionStatus = 'resolved' | 'unresolved' | 'introduced'

export interface DiffSegment {
  type: DiffChunkType
  text: string
}

export interface DiffLine {
  line_number_orig?: number | null
  line_number_newer?: number | null
  type: DiffChunkType
  orig_text?: string | null
  newer_text?: string | null
  orig_segments?: DiffSegment[] | null
  newer_segments?: DiffSegment[] | null
}

export interface RevisionDiffResponse {
  submission_id: string
  orig_version: number
  newer_version: number
  orig_timestamp: string
  newer_timestamp: string
  orig_content: string
  newer_content: string
  orig_creator?: string | null
  newer_creator?: string | null
  stats: {
    additions: number
    deletions: number
    modifications: number
    total_lines_orig: number
    total_lines_newer: number
  }
  lines: DiffLine[]
  resolved_findings: Finding[]
  unresolved_findings: Finding[]
  introduced_findings: Finding[]
  findings_summary: {
    resolved_count: number
    unresolved_count: number
    introduced_count: number
    orig_total: number
    newer_total: number
    net_change: number
  }
  available_versions: number[]
}

export interface SubmissionCreate {
  title: string
  content: string
  creator_name?: string
  is_demo_creator?: boolean
}

export interface SubmissionUpdate {
  content: string
  title?: string
}

export interface DecisionRequest {
  decision: DecisionType
  reviewer_name?: string
  is_demo_reviewer?: boolean
  comment?: string | null
}
