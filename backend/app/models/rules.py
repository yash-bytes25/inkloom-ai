from enum import Enum
from typing import List, Optional, Dict
from pydantic import BaseModel, Field


class Severity(str, Enum):
    critical = "critical"
    warning = "warning"
    info = "info"


class FindingCategory(str, Enum):
    prohibited_terminology = "prohibited_terminology"
    preferred_wording = "preferred_wording"
    fact_accuracy = "fact_accuracy"
    required_disclaimer = "required_disclaimer"


class EvidenceStatus(str, Enum):
    confirmed_violation = "confirmed_violation"
    potential_issue = "potential_issue"
    unverified_claim = "unverified_claim"


class ProhibitedTermRule(BaseModel):
    id: str = Field(..., description="Unique rule identifier")
    term_or_pattern: str = Field(..., description="Term or regex pattern to prohibit")
    is_regex: bool = Field(default=False, description="Whether pattern is a regex")
    case_sensitive: bool = Field(default=False, description="Case sensitivity flag")
    severity: Severity = Field(default=Severity.critical, description="Finding severity")
    explanation: str = Field(..., description="Why this term is prohibited")
    suggested_replacement: Optional[str] = Field(default=None, description="Suggested approved replacement")


class PreferredWordingRule(BaseModel):
    id: str = Field(..., description="Unique rule identifier")
    avoid_term: str = Field(..., description="Term to avoid or replace")
    preferred_term: str = Field(..., description="Approved/preferred terminology")
    case_sensitive: bool = Field(default=False, description="Case sensitivity flag")
    severity: Severity = Field(default=Severity.info, description="Finding severity")
    explanation: str = Field(..., description="Guidance on preferred brand voice")


class ApprovedFact(BaseModel):
    id: str = Field(..., description="Unique fact identifier")
    entity: str = Field(..., description="Target product or brand entity")
    attribute: str = Field(..., description="Fact attribute (e.g. price, battery_life, rating)")
    approved_value: str = Field(..., description="Exact approved factual value")
    context_keywords: List[str] = Field(
        default_factory=list,
        description="Keywords indicating this entity/attribute is being referenced"
    )
    conflicting_patterns: List[str] = Field(
        default_factory=list,
        description="Regex or explicit substrings that directly contradict this approved fact"
    )
    severity: Severity = Field(default=Severity.critical, description="Contradiction severity")
    explanation: str = Field(..., description="Fact accuracy explanation")


class RequiredDisclaimerRule(BaseModel):
    id: str = Field(..., description="Unique disclaimer rule identifier")
    trigger_pattern: str = Field(..., description="Regex or keyword trigger activating the requirement")
    trigger_description: str = Field(..., description="Human-readable condition that triggers the disclaimer")
    required_disclaimer_text: str = Field(..., description="Mandatory disclosure text")
    case_sensitive: bool = Field(default=False, description="Case sensitivity for trigger")
    severity: Severity = Field(default=Severity.warning, description="Missing disclaimer severity")
    explanation: str = Field(..., description="Regulatory or brand governance rationale")


class BrandRulesConfig(BaseModel):
    brand_name: str = Field(..., description="Brand or organization name")
    is_demo: bool = Field(default=False, description="Explicit flag indicating whether this is demo data")
    prohibited_terms: List[ProhibitedTermRule] = Field(default_factory=list)
    preferred_wording: List[PreferredWordingRule] = Field(default_factory=list)
    approved_facts: List[ApprovedFact] = Field(default_factory=list)
    required_disclaimers: List[RequiredDisclaimerRule] = Field(default_factory=list)


class Finding(BaseModel):
    id: str = Field(..., description="Unique finding ID")
    category: FindingCategory = Field(..., description="Finding category")
    severity: Severity = Field(..., description="Finding severity")
    matched_text: Optional[str] = Field(default=None, description="Exact matched text in submission")
    start_index: Optional[int] = Field(default=None, description="Start character offset")
    end_index: Optional[int] = Field(default=None, description="End character offset")
    explanation: str = Field(..., description="Detailed explanation of the issue")
    rule_id: Optional[str] = Field(default=None, description="Associated rule or fact ID")
    rule_name_or_fact: str = Field(..., description="Relevant configured rule or approved fact")
    suggested_correction: Optional[str] = Field(default=None, description="Actionable proposed replacement")
    evidence_status: EvidenceStatus = Field(..., description="Evidence status classification")


class ReviewRequest(BaseModel):
    text: str = Field(..., description="Content to review")
    rules: Optional[BrandRulesConfig] = Field(
        default=None,
        description="Brand rules to evaluate against. If omitted, uses demo brand rules."
    )


class ReviewResponse(BaseModel):
    text_length: int = Field(..., description="Character count of reviewed text")
    total_findings: int = Field(..., description="Total number of findings discovered")
    findings_by_severity: Dict[str, int] = Field(..., description="Findings tally grouped by severity")
    findings: List[Finding] = Field(default_factory=list, description="List of findings")
    is_compliant: bool = Field(..., description="True if zero critical or warning findings")
    brand_name: str = Field(..., description="Evaluated brand name")
    is_demo_data: bool = Field(default=False, description="Indicates if evaluation used demo brand rules")
