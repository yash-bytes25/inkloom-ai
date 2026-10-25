export type Severity = 'critical' | 'warning' | 'info'

export type FindingCategory =
  | 'prohibited_terminology'
  | 'preferred_wording'
  | 'fact_accuracy'
  | 'required_disclaimer'

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
}

export interface BrandRulesConfig {
  brand_name: string
  is_demo: boolean
  prohibited_terms: Array<{
    id: string
    term_or_pattern: string
    is_regex: boolean
    case_sensitive: boolean
    severity: Severity
    explanation: string
    suggested_replacement?: string | null
  }>
  preferred_wording: Array<{
    id: string
    avoid_term: string
    preferred_term: string
    case_sensitive: boolean
    severity: Severity
    explanation: string
  }>
  approved_facts: Array<{
    id: string
    entity: string
    attribute: string
    approved_value: string
    severity: Severity
    explanation: string
  }>
  required_disclaimers: Array<{
    id: string
    trigger_pattern: string
    trigger_description: string
    required_disclaimer_text: string
    severity: Severity
    explanation: string
  }>
}

export type ReviewStatus = 'draft' | 'in_review' | 'changes_requested' | 'approved' | 'rejected'

export type DecisionType = 'approved' | 'changes_requested' | 'rejected'

export interface DecisionRecord {
  id: string
  decision: DecisionType
  reviewer_name: string
  is_demo_reviewer: boolean
  comment: string | null
  timestamp: string
  content_version: number
  content_snapshot: string
  findings_summary: Record<string, number>
}

export interface Submission {
  id: string
  title: string
  content: string
  version: number
  status: ReviewStatus
  creator_name: string
  is_demo_creator: boolean
  created_at: string
  updated_at: string
  submitted_at?: string | null
  submitted_content_snapshot?: string | null
  latest_review_response?: ReviewResponse | null
  decision_history: DecisionRecord[]
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
