from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from .rules import Finding, ReviewResponse


class ReviewStatus(str, Enum):
    draft = "draft"
    in_review = "in_review"
    changes_requested = "changes_requested"
    approved = "approved"
    rejected = "rejected"


class DecisionType(str, Enum):
    approved = "approved"
    changes_requested = "changes_requested"
    rejected = "rejected"


class SubmissionVersionSnapshot(BaseModel):
    version: int = Field(..., description="Sequential version number")
    content: str = Field(..., description="Content text snapshot for this revision")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO timestamp when this version was created"
    )
    title: Optional[str] = Field(default=None, description="Title at this version")
    status_at_save: Optional[ReviewStatus] = Field(default=None, description="Workflow status at save time")
    creator_name: Optional[str] = Field(default=None, description="Creator or modifier name")


class DecisionRecord(BaseModel):
    id: str = Field(..., description="Unique decision record identifier")
    decision: DecisionType = Field(..., description="Review outcome")
    reviewer_name: str = Field(..., description="Reviewer name (clearly marked if demo)")
    is_demo_reviewer: bool = Field(default=True, description="Explicit flag indicating mock/demo identity")
    reviewer_id: Optional[str] = Field(default=None, description="Authenticated reviewer user ID if Supabase Auth is enabled")
    comment: Optional[str] = Field(default=None, description="Reviewer feedback or rationale")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of decision"
    )
    content_version: int = Field(..., description="Version of the content evaluated")
    content_snapshot: str = Field(..., description="Exact content text evaluated in this decision")
    findings_summary: Dict[str, int] = Field(
        default_factory=dict,
        description="Summary of critical, warning, and info findings at decision time"
    )
    guideline_version: int = Field(default=1, description="Version of the brand guidelines at decision time")


class SubmissionCreate(BaseModel):
    title: str = Field(default="Campaign Copy Submission", max_length=255, description="Title of content submission")
    content: str = Field(..., max_length=50000, description="Text content to govern")
    creator_name: str = Field(default="Jordan Lee (Demo Creator)", max_length=100, description="Content creator name")
    is_demo_creator: bool = Field(default=True, description="Flag indicating mock/demo creator identity")
    org_id: Optional[str] = Field(default=None, max_length=100, description="Target organisation identifier")


class SubmissionUpdate(BaseModel):
    content: str = Field(..., max_length=50000, description="Updated text content")
    title: Optional[str] = Field(default=None, max_length=255, description="Optional updated title")


class SubmitForReviewRequest(BaseModel):
    creator_name: Optional[str] = Field(default=None, max_length=100, description="Optional creator name override")


class DecisionRequest(BaseModel):
    decision: DecisionType = Field(..., description="Decision: approved, changes_requested, or rejected")
    reviewer_name: str = Field(
        default="Alex Morgan (Demo Brand Guardian)",
        max_length=100,
        description="Reviewer name or identifier"
    )
    is_demo_reviewer: bool = Field(default=True, description="Flag distinguishing demo reviewer from auth")
    reviewer_id: Optional[str] = Field(default=None, max_length=100, description="Authenticated reviewer user ID if auth enabled")
    comment: Optional[str] = Field(
        default=None,
        max_length=5000,
        description="Reviewer notes. Mandatory when requesting changes or rejecting."
    )


class Submission(BaseModel):
    id: str = Field(..., description="Submission ID")
    title: str = Field(..., description="Submission title")
    content: str = Field(..., description="Active text content")
    version: int = Field(default=1, description="Sequential version counter")
    status: ReviewStatus = Field(default=ReviewStatus.draft, description="Current workflow state")
    creator_name: str = Field(..., description="Creator name")
    is_demo_creator: bool = Field(default=True, description="Demo identity flag")
    creator_id: Optional[str] = Field(default=None, description="Authenticated creator user ID")
    org_id: Optional[str] = Field(default=None, description="Associated organisation ID")
    storage_mode: str = Field(
        default="local_demo",
        description="Persistence mode: local_demo or supabase_persistent"
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Creation timestamp"
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Last modified timestamp"
    )
    submitted_at: Optional[str] = Field(default=None, description="Timestamp when submitted for review")
    submitted_content_snapshot: Optional[str] = Field(
        default=None,
        description="Exact snapshot of content when submitted for review"
    )
    latest_review_response: Optional[ReviewResponse] = Field(
        default=None,
        description="Latest deterministic policy audit findings"
    )
    decision_history: List[DecisionRecord] = Field(
        default_factory=list,
        description="Audit log of all reviewer decisions"
    )
    version_history: List[SubmissionVersionSnapshot] = Field(
        default_factory=list,
        description="Chronological record of all content versions for revision comparison"
    )


class DiffChunkType(str, Enum):
    equal = "equal"
    insert = "insert"
    delete = "delete"
    replace = "replace"


class DiffSegment(BaseModel):
    type: DiffChunkType
    text: str


class DiffLine(BaseModel):
    line_number_orig: Optional[int] = None
    line_number_newer: Optional[int] = None
    type: DiffChunkType
    orig_text: Optional[str] = None
    newer_text: Optional[str] = None
    orig_segments: Optional[List[DiffSegment]] = None
    newer_segments: Optional[List[DiffSegment]] = None


class FindingResolutionStatus(str, Enum):
    resolved = "resolved"
    unresolved = "unresolved"
    introduced = "introduced"


class RevisionDiffResponse(BaseModel):
    submission_id: str
    orig_version: int
    newer_version: int
    orig_timestamp: str
    newer_timestamp: str
    orig_content: str
    newer_content: str
    orig_creator: Optional[str] = None
    newer_creator: Optional[str] = None
    stats: Dict[str, int]
    lines: List[DiffLine]
    resolved_findings: List[Finding]
    unresolved_findings: List[Finding]
    introduced_findings: List[Finding]
    findings_summary: Dict[str, int]
    available_versions: List[int]
