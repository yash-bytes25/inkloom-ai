from datetime import datetime, timezone
from typing import Dict, List, Optional
import uuid
from fastapi import HTTPException
from ..models.workflow import (
    ReviewStatus,
    DecisionType,
    DecisionRecord,
    SubmissionCreate,
    SubmissionUpdate,
    SubmitForReviewRequest,
    DecisionRequest,
    Submission,
)
from .evaluator import run_deterministic_review


class WorkflowService:
    """Manages content submissions and human review lifecycle state machine in-memory."""

    def __init__(self):
        self._submissions: Dict[str, Submission] = {}
        self._seed_demo_submission()

    def _seed_demo_submission(self):
        """Pre-seed an initial demo submission for immediate local testing."""
        sample_text = (
            "These cheap headphones and earbuds feature a lifetime warranty. "
            "The NovaSound Apex Wireless costs $199 and our unbreakable build kills the competition."
        )
        sub_id = "sub-demo-01"
        review = run_deterministic_review(sample_text)
        self._submissions[sub_id] = Submission(
            id=sub_id,
            title="NovaSound Apex Wireless — Launch Campaign Copy",
            content=sample_text,
            version=1,
            status=ReviewStatus.draft,
            creator_name="Jordan Lee (Demo Creator)",
            is_demo_creator=True,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
            latest_review_response=review,
            decision_history=[],
        )

    def list_submissions(self) -> List[Submission]:
        """Return all submissions sorted by latest update."""
        return sorted(
            self._submissions.values(),
            key=lambda s: s.updated_at,
            reverse=True,
        )

    def get_submission(self, sub_id: str) -> Submission:
        """Fetch a submission by ID or raise 404."""
        if sub_id not in self._submissions:
            raise HTTPException(status_code=404, detail=f"Submission '{sub_id}' not found.")
        return self._submissions[sub_id]

    def create_submission(self, data: SubmissionCreate) -> Submission:
        """Create a new content submission starting in 'draft' status."""
        sub_id = f"sub-{uuid.uuid4().hex[:8]}"
        review = run_deterministic_review(data.content)
        now = datetime.now(timezone.utc).isoformat()

        submission = Submission(
            id=sub_id,
            title=data.title,
            content=data.content,
            version=1,
            status=ReviewStatus.draft,
            creator_name=data.creator_name,
            is_demo_creator=data.is_demo_creator,
            created_at=now,
            updated_at=now,
            latest_review_response=review,
            decision_history=[],
        )
        self._submissions[sub_id] = submission
        return submission

    def update_submission(self, sub_id: str, data: SubmissionUpdate) -> Submission:
        """Update content of a submission.

        CRITICAL GOVERNANCE PRINCIPLE (Requirement 8):
        An old approval does not silently carry over after content changes.
        Any modification to content resets the workflow status to 'draft'
        and increments the content version.
        """
        sub = self.get_submission(sub_id)
        now = datetime.now(timezone.utc).isoformat()

        content_changed = data.content != sub.content

        if content_changed:
            # Invalidate approval / active review state
            sub.status = ReviewStatus.draft
            sub.version += 1
            sub.content = data.content
            sub.submitted_content_snapshot = None
            sub.latest_review_response = run_deterministic_review(data.content)

        if data.title:
            sub.title = data.title

        sub.updated_at = now
        return sub

    def submit_for_review(self, sub_id: str, req: SubmitForReviewRequest = None) -> Submission:
        """Creator transitions submission from draft/changes_requested to 'in_review'."""
        sub = self.get_submission(sub_id)

        if sub.status == ReviewStatus.in_review:
            raise HTTPException(
                status_code=400,
                detail="Submission is already 'in_review'. Awaiting reviewer decision."
            )

        now = datetime.now(timezone.utc).isoformat()
        if req and req.creator_name:
            sub.creator_name = req.creator_name

        # Re-run policy audit on current content to ensure fresh findings snapshot
        sub.latest_review_response = run_deterministic_review(sub.content)
        sub.submitted_content_snapshot = sub.content
        sub.submitted_at = now
        sub.updated_at = now
        sub.status = ReviewStatus.in_review
        return sub

    def record_decision(self, sub_id: str, req: DecisionRequest) -> Submission:
        """Reviewer approves, requests changes, or rejects the submitted version.

        Enforces:
        - Submission must currently be in 'in_review' state.
        - Changes requested or Rejection REQUIRES non-empty comment.
        - Preserves exact content version snapshot.
        - Clearly tracks demo reviewer identity.
        """
        sub = self.get_submission(sub_id)

        # Validate valid transition
        if sub.status != ReviewStatus.in_review:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Cannot record decision '{req.decision.value}' on submission with status '{sub.status.value}'. "
                    f"Submission must be in 'in_review' state."
                ),
            )

        # Validate mandatory comments for changes_requested and rejected
        if req.decision in [DecisionType.changes_requested, DecisionType.rejected]:
            if not req.comment or not req.comment.strip():
                action_name = "requesting changes" if req.decision == DecisionType.changes_requested else "rejecting content"
                raise HTTPException(
                    status_code=422,
                    detail=f"A comment explaining the rationale is strictly required when {action_name}."
                )

        now = datetime.now(timezone.utc).isoformat()

        # Build immutable decision record
        decision_record = DecisionRecord(
            id=f"dec-{len(sub.decision_history) + 1}",
            decision=req.decision,
            reviewer_name=req.reviewer_name,
            is_demo_reviewer=req.is_demo_reviewer,
            comment=req.comment.strip() if req.comment else None,
            timestamp=now,
            content_version=sub.version,
            content_snapshot=sub.submitted_content_snapshot or sub.content,
            findings_summary=sub.latest_review_response.findings_by_severity if sub.latest_review_response else {},
        )

        sub.decision_history.append(decision_record)
        sub.status = ReviewStatus(req.decision.value)
        sub.updated_at = now
        return sub


# Global singleton workflow service instance
workflow_service = WorkflowService()
