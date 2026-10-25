from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from .rules import ReviewResponse


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


class DecisionRecord(BaseModel):
    id: str = Field(..., description="Unique decision record identifier")
    decision: DecisionType = Field(..., description="Review outcome")
    reviewer_name: str = Field(..., description="Reviewer name (clearly marked if demo)")
    is_demo_reviewer: bool = Field(default=True, description="Explicit flag indicating mock/demo identity")
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


class SubmissionCreate(BaseModel):
    title: str = Field(default="Campaign Copy Submission", description="Title of content submission")
    content: str = Field(..., description="Text content to govern")
    creator_name: str = Field(default="Jordan Lee (Demo Creator)", description="Content creator name")
    is_demo_creator: bool = Field(default=True, description="Flag indicating mock/demo creator identity")


class SubmissionUpdate(BaseModel):
    content: str = Field(..., description="Updated text content")
    title: Optional[str] = Field(default=None, description="Optional updated title")


class SubmitForReviewRequest(BaseModel):
    creator_name: Optional[str] = Field(default=None, description="Optional creator name override")


class DecisionRequest(BaseModel):
    decision: DecisionType = Field(..., description="Decision: approved, changes_requested, or rejected")
    reviewer_name: str = Field(
        default="Alex Morgan (Demo Brand Guardian)",
        description="Reviewer name or identifier"
    )
    is_demo_reviewer: bool = Field(default=True, description="Flag distinguishing demo reviewer from auth")
    comment: Optional[str] = Field(
        default=None,
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
