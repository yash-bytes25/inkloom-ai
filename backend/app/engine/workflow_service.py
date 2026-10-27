from datetime import datetime, timezone
import logging
from typing import Dict, List, Optional
import uuid
from fastapi import HTTPException

from ..models.workflow import (
    DecisionRecord,
    DecisionRequest,
    DecisionType,
    ReviewStatus,
    Submission,
    SubmissionCreate,
    SubmissionUpdate,
    SubmissionVersionSnapshot,
    SubmitForReviewRequest,
)
from .evaluator import run_deterministic_review
from .supabase_client import get_supabase_client, is_supabase_configured
from .supabase_repository import SupabaseWorkflowRepository

logger = logging.getLogger(__name__)


from .auth import is_production
from ..models.rules import BrandRulesConfig
from .rules_service import rules_service

class WorkflowService:
    """Manages content submissions and human review lifecycle.
    Backed by Supabase PostgreSQL when credentials are configured,
    or local in-memory storage when credentials are absent (local demo mode).
    """

    def __init__(self, repository: Optional[SupabaseWorkflowRepository] = None):
        self._repo = repository
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
        now = datetime.now(timezone.utc).isoformat()
        self._submissions[sub_id] = Submission(
            id=sub_id,
            title="NovaSound Apex Wireless — Launch Campaign Copy",
            content=sample_text,
            version=1,
            status=ReviewStatus.draft,
            creator_name="Jordan Lee (Demo Creator)",
            is_demo_creator=True,
            storage_mode="local_demo",
            created_at=now,
            updated_at=now,
            latest_review_response=review,
            decision_history=[],
            version_history=[
                SubmissionVersionSnapshot(
                    version=1,
                    content=sample_text,
                    timestamp=now,
                    title="NovaSound Apex Wireless — Launch Campaign Copy",
                    status_at_save=ReviewStatus.draft,
                    creator_name="Jordan Lee (Demo Creator)",
                )
            ],
        )

    def get_repository(self, token: Optional[str] = None) -> Optional[SupabaseWorkflowRepository]:
        """Resolve active Supabase repository instance or None if not configured.
        Never silently falls back to in-memory mode if Supabase credentials are provided or in production.
        """
        if self._repo:
            return self._repo
        if is_supabase_configured():
            client = get_supabase_client(user_token=token)
            if client:
                return SupabaseWorkflowRepository(client)
            raise HTTPException(
                status_code=503,
                detail="Supabase service error: Client initialization failed for configured database."
            )
        if is_production():
            raise HTTPException(
                status_code=503,
                detail="Production service misconfigured: Supabase credentials are required."
            )
        return None

    def get_guidelines(
        self,
        org_id: Optional[str] = None,
        user_id: Optional[str] = None,
        token: Optional[str] = None,
    ) -> BrandRulesConfig:
        """Retrieve active brand guidelines from Supabase when configured or local demo memory."""
        repo = self.get_repository(token)
        if repo:
            if not org_id:
                # If no org_id supplied, attempt to resolve from user's primary organisation
                user_orgs = repo.get_user_org_ids(user_id) if user_id else []
                target_org = user_orgs[0] if user_orgs else None
            else:
                target_org = org_id

            if target_org:
                db_rules = repo.get_guidelines(target_org, user_id)
                if db_rules:
                    return db_rules
                # Seed pristine baseline rules into database for newly initialized organisation
                return repo.reset_guidelines(target_org, user_id)
            return rules_service.get_active_rules()

        if is_production() or is_supabase_configured():
            raise HTTPException(
                status_code=503,
                detail="Production service misconfigured: Supabase credentials are required."
            )

        return rules_service.get_active_rules()

    def save_guidelines(
        self,
        rules: BrandRulesConfig,
        org_id: Optional[str] = None,
        user_id: Optional[str] = None,
        token: Optional[str] = None,
    ) -> BrandRulesConfig:
        """Persist updated brand guidelines into Supabase PostgreSQL or local demo memory."""
        repo = self.get_repository(token)
        if repo:
            target_org = org_id
            if not target_org and user_id:
                user_orgs = repo.get_user_org_ids(user_id)
                target_org = user_orgs[0] if user_orgs else None

            if not target_org:
                raise HTTPException(status_code=400, detail="Organisation ID is required to save brand guidelines.")

            return repo.save_guidelines(target_org, rules, user_id)

        if is_production() or is_supabase_configured():
            raise HTTPException(
                status_code=503,
                detail="Production service misconfigured: Supabase credentials are required."
            )

        return rules_service.update_rules(rules)

    def reset_guidelines(
        self,
        org_id: Optional[str] = None,
        user_id: Optional[str] = None,
        token: Optional[str] = None,
    ) -> BrandRulesConfig:
        """Restore pristine brand guidelines in Supabase PostgreSQL or local demo memory."""
        repo = self.get_repository(token)
        if repo:
            target_org = org_id
            if not target_org and user_id:
                user_orgs = repo.get_user_org_ids(user_id)
                target_org = user_orgs[0] if user_orgs else None

            if not target_org:
                raise HTTPException(status_code=400, detail="Organisation ID is required to reset brand guidelines.")

            return repo.reset_guidelines(target_org, user_id)

        if is_production() or is_supabase_configured():
            raise HTTPException(
                status_code=503,
                detail="Production service misconfigured: Supabase credentials are required."
            )

        return rules_service.reset_to_demo()

    def list_submissions(
        self,
        org_id: Optional[str] = None,
        user_id: Optional[str] = None,
        token: Optional[str] = None,
    ) -> List[Submission]:
        """Return submissions for organisation or all demo submissions."""
        repo = self.get_repository(token)
        if repo:
            return repo.list_submissions(org_id, user_id)

        if is_production() or is_supabase_configured():
            raise HTTPException(
                status_code=503,
                detail="Production service misconfigured: Supabase credentials are required."
            )

        return sorted(
            self._submissions.values(),
            key=lambda s: s.updated_at,
            reverse=True,
        )

    def get_submission(
        self,
        sub_id: str,
        org_id: Optional[str] = None,
        user_id: Optional[str] = None,
        token: Optional[str] = None,
    ) -> Submission:
        """Fetch submission by ID, checking Supabase if enabled, then in-memory."""
        repo = self.get_repository(token)
        if repo:
            return repo.get_submission(sub_id, org_id, user_id)

        if is_production() or is_supabase_configured():
            raise HTTPException(
                status_code=503,
                detail="Production service misconfigured: Supabase credentials are required."
            )

        if sub_id not in self._submissions:
            raise HTTPException(status_code=404, detail=f"Submission '{sub_id}' not found.")
        return self._submissions[sub_id]

    def create_submission(
        self,
        data: SubmissionCreate,
        org_id: Optional[str] = None,
        user_id: Optional[str] = None,
        token: Optional[str] = None,
    ) -> Submission:
        """Create new content submission starting in 'draft' status."""
        target_org = org_id or data.org_id
        repo = self.get_repository(token)
        if repo:
            if not target_org:
                raise HTTPException(status_code=400, detail="Organisation ID is required.")
            return repo.create_submission(data, target_org, user_id)

        if is_production() or is_supabase_configured():
            raise HTTPException(
                status_code=503,
                detail="Production service misconfigured: Supabase credentials are required."
            )

        # Local in-memory creation (development demo mode)
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
            creator_id=user_id,
            org_id=target_org,
            storage_mode="local_demo",
            created_at=now,
            updated_at=now,
            latest_review_response=review,
            decision_history=[],
            version_history=[
                SubmissionVersionSnapshot(
                    version=1,
                    content=data.content,
                    timestamp=now,
                    title=data.title,
                    status_at_save=ReviewStatus.draft,
                    creator_name=data.creator_name,
                )
            ],
        )
        self._submissions[sub_id] = submission
        return submission

    def update_submission(
        self,
        sub_id: str,
        data: SubmissionUpdate,
        org_id: Optional[str] = None,
        user_id: Optional[str] = None,
        token: Optional[str] = None,
    ) -> Submission:
        """Update content of submission.
        CRITICAL GOVERNANCE RULE: Content change resets status to 'draft',
        increments version, and invalidates any previous approval.
        """
        repo = self.get_repository(token)
        if repo:
            return repo.update_submission(sub_id, data, org_id, user_id)

        if is_production() or is_supabase_configured():
            raise HTTPException(
                status_code=503,
                detail="Production service misconfigured: Supabase credentials are required."
            )

        sub = self.get_submission(sub_id)
        now = datetime.now(timezone.utc).isoformat()

        content_changed = data.content != sub.content

        if content_changed:
            # Ensure earlier version snapshot exists in history
            if not sub.version_history:
                sub.version_history.append(
                    SubmissionVersionSnapshot(
                        version=sub.version,
                        content=sub.content,
                        timestamp=sub.created_at,
                        title=sub.title,
                        status_at_save=sub.status,
                        creator_name=sub.creator_name,
                    )
                )

            # Invalidate approval / active review state
            sub.status = ReviewStatus.draft
            sub.version += 1
            sub.content = data.content
            sub.submitted_content_snapshot = None
            sub.latest_review_response = run_deterministic_review(data.content)

            sub.version_history.append(
                SubmissionVersionSnapshot(
                    version=sub.version,
                    content=data.content,
                    timestamp=now,
                    title=data.title or sub.title,
                    status_at_save=ReviewStatus.draft,
                    creator_name=sub.creator_name,
                )
            )

        if data.title:
            sub.title = data.title

        sub.updated_at = now
        return sub

    def submit_for_review(
        self,
        sub_id: str,
        req: Optional[SubmitForReviewRequest] = None,
        org_id: Optional[str] = None,
        user_id: Optional[str] = None,
        token: Optional[str] = None,
    ) -> Submission:
        """Transition submission from draft/changes_requested to 'in_review'."""
        repo = self.get_repository(token)
        if repo:
            return repo.submit_for_review(sub_id, req, org_id, user_id)

        if is_production() or is_supabase_configured():
            raise HTTPException(
                status_code=503,
                detail="Production service misconfigured: Supabase credentials are required."
            )

        sub = self.get_submission(sub_id)

        if sub.status == ReviewStatus.in_review:
            raise HTTPException(
                status_code=400,
                detail="Submission is already 'in_review'. Awaiting reviewer decision."
            )

        now = datetime.now(timezone.utc).isoformat()
        if req and req.creator_name:
            sub.creator_name = req.creator_name

        sub.latest_review_response = run_deterministic_review(sub.content)
        sub.submitted_content_snapshot = sub.content
        sub.submitted_at = now
        sub.updated_at = now
        sub.status = ReviewStatus.in_review
        return sub

    def record_decision(
        self,
        sub_id: str,
        req: DecisionRequest,
        org_id: Optional[str] = None,
        reviewer_id: Optional[str] = None,
        user_role: Optional[str] = None,
        token: Optional[str] = None,
    ) -> Submission:
        """Reviewer records approval, requested changes, or rejection.

        Enforces:
        - Submission must be in 'in_review' state.
        - Comments are mandatory for changes_requested and rejected.
        - Enforces reviewer permissions from verified membership.
        - Stores immutable DecisionRecord with content snapshot.
        """
        repo = self.get_repository(token)
        if repo:
            return repo.record_decision(sub_id, req, org_id, reviewer_id, user_role)

        if is_production() or is_supabase_configured():
            raise HTTPException(
                status_code=503,
                detail="Production service misconfigured: Supabase credentials are required."
            )

        # Enforce reviewer role permission in local demo mode
        if user_role and user_role not in ["reviewer", "admin", "owner"]:
            raise HTTPException(
                status_code=403,
                detail=f"User role '{user_role}' lacks permission to record review decisions. Requires 'reviewer', 'admin', or 'owner'."
            )

        sub = self.get_submission(sub_id)

        if sub.status != ReviewStatus.in_review:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Cannot record decision '{req.decision.value}' on submission with status '{sub.status.value}'. "
                    f"Submission must be in 'in_review' state."
                ),
            )

        # Separation of Duties: Creators cannot approve their own content
        if (
            req.decision == DecisionType.approved
            and sub.creator_id
            and reviewer_id
            and sub.creator_id == reviewer_id
        ):
            raise HTTPException(
                status_code=403,
                detail="Separation of duties violation: Content creators cannot approve their own submissions. Review must be conducted by an independent reviewer."
            )

        if req.decision in [DecisionType.changes_requested, DecisionType.rejected]:
            if not req.comment or not req.comment.strip():
                action_name = "requesting changes" if req.decision == DecisionType.changes_requested else "rejecting content"
                raise HTTPException(
                    status_code=422,
                    detail=f"A comment explaining the rationale is strictly required when {action_name}."
                )

        now = datetime.now(timezone.utc).isoformat()

        decision_record = DecisionRecord(
            id=f"dec-{len(sub.decision_history) + 1}",
            decision=req.decision,
            reviewer_name=req.reviewer_name,
            is_demo_reviewer=req.is_demo_reviewer,
            reviewer_id=reviewer_id or req.reviewer_id,
            comment=req.comment.strip() if req.comment else None,
            timestamp=now,
            content_version=sub.version,
            content_snapshot=sub.submitted_content_snapshot or sub.content,
            findings_summary=sub.latest_review_response.findings_by_severity if sub.latest_review_response else {},
            guideline_version=1,
        )

        sub.decision_history.append(decision_record)
        sub.status = ReviewStatus(req.decision.value)
        sub.updated_at = now
        return sub


# Global singleton workflow service instance
workflow_service = WorkflowService()
