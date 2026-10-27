from datetime import datetime, timezone
from typing import Dict, List, Optional
import uuid
from fastapi import HTTPException
from supabase import Client

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
from ..models.rules import (
    ApprovedFact,
    BrandRulesConfig,
    EvidenceStatus,
    Finding,
    FindingCategory,
    PreferredWordingRule,
    ProhibitedTermRule,
    RequiredDisclaimerRule,
    ReviewResponse,
    Severity,
)
from .demo_data import DEMO_BRAND_RULES
from .evaluator import run_deterministic_review


class SupabaseWorkflowRepository:
    """Manages database persistence for content submissions and review lifecycle via Supabase PostgREST.

    Security & Tenancy Rules:
    - Enforces organisation-level isolation.
    - Verifies user membership in organisation before querying/modifying data.
    - Validates reviewer permissions for decision records.
    - Enforces approval invalidation upon content version change.
    """

    def __init__(self, client: Client):
        self.client = client

    def get_user_role_in_org(self, user_id: str, org_id: str) -> Optional[str]:
        """Fetch the exact role of user_id in org_id from organisation_members table."""
        if not user_id or not org_id:
            return None
        try:
            res = (
                self.client.table("organisation_members")
                .select("role")
                .eq("org_id", org_id)
                .eq("user_id", user_id)
                .execute()
            )
            if res.data and len(res.data) > 0:
                return res.data[0].get("role")
            return None
        except Exception:
            return None

    def get_user_org_ids(self, user_id: str) -> List[str]:
        """Fetch all organisation IDs the user belongs to."""
        if not user_id:
            return []
        try:
            res = (
                self.client.table("organisation_members")
                .select("org_id")
                .eq("user_id", user_id)
                .execute()
            )
            return [str(row["org_id"]) for row in res.data if "org_id" in row]
        except Exception:
            return []

    def verify_user_in_org(self, user_id: str, org_id: str) -> bool:
        """Verify that user_id is a registered member of org_id."""
        return self.get_user_role_in_org(user_id, org_id) is not None

    def verify_user_role(self, user_id: str, org_id: str, allowed_roles: List[str]) -> bool:
        """Verify that user holds one of the required roles in target organisation."""
        role = self.get_user_role_in_org(user_id, org_id)
        return role in allowed_roles if role else False

    def get_guidelines(
        self,
        org_id: str,
        user_id: Optional[str] = None,
    ) -> Optional[BrandRulesConfig]:
        """Fetch active brand guidelines and associated rules for the specified organisation."""
        if not org_id:
            return None

        if user_id and not self.verify_user_in_org(user_id, org_id):
            raise HTTPException(
                status_code=403,
                detail=f"Access denied: User is not an authorized member of organisation '{org_id}'."
            )

        res = (
            self.client.table("brand_guidelines")
            .select("*")
            .eq("org_id", org_id)
            .eq("is_active", True)
            .order("version", desc=True)
            .limit(1)
            .execute()
        )
        if not res.data or len(res.data) == 0:
            return None

        bg = res.data[0]
        guideline_id = str(bg["id"])

        # 1. Fetch Prohibited Terms
        pt_res = self.client.table("prohibited_terms").select("*").eq("guideline_id", guideline_id).execute()
        prohibited_terms = [
            ProhibitedTermRule(
                id=str(r["id"]),
                term_or_pattern=r["term_or_pattern"],
                is_regex=bool(r.get("is_regex", False)),
                case_sensitive=bool(r.get("case_sensitive", False)),
                severity=Severity(r.get("severity", "critical")),
                explanation=r["explanation"],
                suggested_replacement=r.get("suggested_replacement"),
            )
            for r in (pt_res.data or [])
        ]

        # 2. Fetch Preferred Wordings
        pw_res = self.client.table("preferred_wordings").select("*").eq("guideline_id", guideline_id).execute()
        preferred_wording = [
            PreferredWordingRule(
                id=str(r["id"]),
                avoid_term=r["avoid_term"],
                preferred_term=r["preferred_term"],
                case_sensitive=bool(r.get("case_sensitive", False)),
                severity=Severity(r.get("severity", "info")),
                explanation=r["explanation"],
            )
            for r in (pw_res.data or [])
        ]

        # 3. Fetch Approved Facts
        af_res = self.client.table("approved_facts").select("*").eq("guideline_id", guideline_id).execute()
        approved_facts = [
            ApprovedFact(
                id=str(r["id"]),
                entity=r["entity"],
                attribute=r["attribute"],
                approved_value=r["approved_value"],
                context_keywords=r.get("context_keywords") or [],
                conflicting_patterns=r.get("conflicting_patterns") or [],
                severity=Severity(r.get("severity", "critical")),
                explanation=r["explanation"],
            )
            for r in (af_res.data or [])
        ]

        # 4. Fetch Required Disclaimers
        rd_res = self.client.table("required_disclaimers").select("*").eq("guideline_id", guideline_id).execute()
        required_disclaimers = [
            RequiredDisclaimerRule(
                id=str(r["id"]),
                trigger_pattern=r["trigger_pattern"],
                trigger_description=r["trigger_description"],
                required_disclaimer_text=r["required_disclaimer_text"],
                case_sensitive=bool(r.get("case_sensitive", False)),
                severity=Severity(r.get("severity", "warning")),
                explanation=r["explanation"],
            )
            for r in (rd_res.data or [])
        ]

        return BrandRulesConfig(
            brand_name=bg.get("name", "Brand Guidelines"),
            description=bg.get("description"),
            voice_and_tone=bg.get("voice_and_tone"),
            is_demo=False,
            prohibited_terms=prohibited_terms,
            preferred_wording=preferred_wording,
            approved_facts=approved_facts,
            required_disclaimers=required_disclaimers,
        )

    def save_guidelines(
        self,
        org_id: str,
        rules: BrandRulesConfig,
        user_id: Optional[str] = None,
    ) -> BrandRulesConfig:
        """Persist updated brand guidelines and associated rules into Supabase PostgreSQL."""
        if not org_id:
            raise HTTPException(status_code=400, detail="Organisation ID is required.")

        if user_id:
            if not self.verify_user_in_org(user_id, org_id):
                raise HTTPException(
                    status_code=403,
                    detail=f"Access denied: User is not an authorized member of organisation '{org_id}'."
                )
            role = self.get_user_role_in_org(user_id, org_id)
            if role not in ["owner", "admin"]:
                raise HTTPException(
                    status_code=403,
                    detail=f"Access denied: Only organization admins or owners can modify brand guidelines. Current role is '{role or 'none'}'."
                )

        now = datetime.now(timezone.utc).isoformat()

        # Check for existing active guideline row for this org
        res = (
            self.client.table("brand_guidelines")
            .select("*")
            .eq("org_id", org_id)
            .eq("is_active", True)
            .order("version", desc=True)
            .limit(1)
            .execute()
        )

        if res.data and len(res.data) > 0:
            bg_id = str(res.data[0]["id"])
            new_version = int(res.data[0].get("version", 1)) + 1
            update_payload = {
                "name": rules.brand_name,
                "version": new_version,
                "updated_at": now,
            }
            if rules.description is not None:
                update_payload["description"] = rules.description
            if rules.voice_and_tone is not None:
                update_payload["voice_and_tone"] = rules.voice_and_tone

            self.client.table("brand_guidelines").update(update_payload).eq("id", bg_id).execute()

            # Clean out previous rule rows before re-inserting
            self.client.table("prohibited_terms").delete().eq("guideline_id", bg_id).execute()
            self.client.table("preferred_wordings").delete().eq("guideline_id", bg_id).execute()
            self.client.table("approved_facts").delete().eq("guideline_id", bg_id).execute()
            self.client.table("required_disclaimers").delete().eq("guideline_id", bg_id).execute()
        else:
            bg_id = str(uuid.uuid4())
            insert_payload = {
                "id": bg_id,
                "org_id": org_id,
                "name": rules.brand_name,
                "version": 1,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            }
            if rules.description is not None:
                insert_payload["description"] = rules.description
            if rules.voice_and_tone is not None:
                insert_payload["voice_and_tone"] = rules.voice_and_tone

            self.client.table("brand_guidelines").insert(insert_payload).execute()

        # Insert child rules with generated UUIDs if not standard UUID format
        if rules.prohibited_terms:
            pt_rows = []
            for r in rules.prohibited_terms:
                rule_id = r.id if (len(r.id) == 36 and "-" in r.id) else str(uuid.uuid4())
                pt_rows.append({
                    "id": rule_id,
                    "guideline_id": bg_id,
                    "term_or_pattern": r.term_or_pattern,
                    "is_regex": r.is_regex,
                    "case_sensitive": r.case_sensitive,
                    "severity": r.severity.value,
                    "explanation": r.explanation,
                    "suggested_replacement": r.suggested_replacement,
                    "created_at": now,
                })
            self.client.table("prohibited_terms").insert(pt_rows).execute()

        if rules.preferred_wording:
            pw_rows = []
            for r in rules.preferred_wording:
                rule_id = r.id if (len(r.id) == 36 and "-" in r.id) else str(uuid.uuid4())
                pw_rows.append({
                    "id": rule_id,
                    "guideline_id": bg_id,
                    "avoid_term": r.avoid_term,
                    "preferred_term": r.preferred_term,
                    "case_sensitive": r.case_sensitive,
                    "severity": r.severity.value,
                    "explanation": r.explanation,
                    "created_at": now,
                })
            self.client.table("preferred_wordings").insert(pw_rows).execute()

        if rules.approved_facts:
            af_rows = []
            for r in rules.approved_facts:
                rule_id = r.id if (len(r.id) == 36 and "-" in r.id) else str(uuid.uuid4())
                af_rows.append({
                    "id": rule_id,
                    "guideline_id": bg_id,
                    "entity": r.entity,
                    "attribute": r.attribute,
                    "approved_value": r.approved_value,
                    "context_keywords": r.context_keywords,
                    "conflicting_patterns": r.conflicting_patterns,
                    "severity": r.severity.value,
                    "explanation": r.explanation,
                    "created_at": now,
                })
            self.client.table("approved_facts").insert(af_rows).execute()

        if rules.required_disclaimers:
            rd_rows = []
            for r in rules.required_disclaimers:
                rule_id = r.id if (len(r.id) == 36 and "-" in r.id) else str(uuid.uuid4())
                rd_rows.append({
                    "id": rule_id,
                    "guideline_id": bg_id,
                    "trigger_pattern": r.trigger_pattern,
                    "trigger_description": r.trigger_description,
                    "required_disclaimer_text": r.required_disclaimer_text,
                    "case_sensitive": r.case_sensitive,
                    "severity": r.severity.value,
                    "explanation": r.explanation,
                    "created_at": now,
                })
            self.client.table("required_disclaimers").insert(rd_rows).execute()

        saved = self.get_guidelines(org_id, user_id)
        return saved if saved is not None else rules

    def reset_guidelines(
        self,
        org_id: str,
        user_id: Optional[str] = None,
    ) -> BrandRulesConfig:
        """Reset organisation brand guidelines to pristine demo baseline rules."""
        demo_copy = DEMO_BRAND_RULES.model_copy(deep=True)
        demo_copy.is_demo = False
        return self.save_guidelines(org_id, demo_copy, user_id)

    def list_submissions(
        self,
        org_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> List[Submission]:
        """Fetch all submissions for the target organisation, verifying tenancy scope."""
        if org_id:
            if user_id and not self.verify_user_in_org(user_id, org_id):
                raise HTTPException(
                    status_code=403,
                    detail=f"Access denied: User is not an authorized member of organisation '{org_id}'."
                )
            target_orgs = [org_id]
        elif user_id:
            target_orgs = self.get_user_org_ids(user_id)
            if not target_orgs:
                return []
        else:
            # Under service-role key or unauthenticated call, never dump all tenant records
            return []

        submissions: List[Submission] = []
        for o_id in target_orgs:
            res = (
                self.client.table("submissions")
                .select("*")
                .eq("org_id", o_id)
                .order("updated_at", desc=True)
                .execute()
            )
            for row in res.data:
                submissions.append(self._hydrate_submission(row))
        submissions.sort(key=lambda s: s.updated_at, reverse=True)
        return submissions

    def get_submission(
        self,
        sub_id: str,
        org_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Submission:
        """Retrieve submission by ID, verifying organisation scope."""
        query = self.client.table("submissions").select("*").eq("id", sub_id)
        if org_id:
            query = query.eq("org_id", org_id)

        res = query.execute()
        if not res.data:
            raise HTTPException(status_code=404, detail=f"Submission '{sub_id}' not found.")

        row = res.data[0]
        sub = self._hydrate_submission(row)

        # Cross-tenant read access control check
        if user_id and sub.org_id:
            if not self.verify_user_in_org(user_id, sub.org_id):
                raise HTTPException(
                    status_code=403,
                    detail=f"Access denied: User is not authorized to access submissions in organisation '{sub.org_id}'."
                )

        if org_id and sub.org_id and sub.org_id != org_id:
            raise HTTPException(
                status_code=403,
                detail=f"Access denied: Submission does not belong to organisation '{org_id}'."
            )

        return sub

    def create_submission(
        self,
        data: SubmissionCreate,
        org_id: str,
        user_id: Optional[str] = None,
    ) -> Submission:
        """Create new content submission and initial version snapshot (v1) in draft status."""
        if not org_id:
            raise HTTPException(status_code=400, detail="Organisation ID is required.")

        if user_id and not self.verify_user_in_org(user_id, org_id):
            raise HTTPException(
                status_code=403,
                detail=f"Access denied: User is not an authorized member of organisation '{org_id}'."
            )

        sub_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        # Run initial deterministic review
        review = run_deterministic_review(data.content)

        # 1. Insert into submissions
        sub_payload = {
            "id": sub_id,
            "org_id": org_id,
            "title": data.title,
            "current_version": 1,
            "status": ReviewStatus.draft.value,
            "creator_id": user_id,
            "creator_name": data.creator_name,
            "is_demo": data.is_demo_creator if not user_id else False,
            "submitted_at": None,
            "submitted_content_snapshot": None,
            "created_at": now,
            "updated_at": now,
        }
        self.client.table("submissions").insert(sub_payload).execute()

        # 2. Insert version 1 into submission_content_versions
        version_payload = {
            "submission_id": sub_id,
            "version": 1,
            "content": data.content,
            "created_by": user_id,
            "created_at": now,
        }
        self.client.table("submission_content_versions").insert(version_payload).execute()

        # 3. Persist review findings
        self._save_findings(sub_id, 1, review.findings)

        return self.get_submission(sub_id, org_id, user_id)

    def update_submission(
        self,
        sub_id: str,
        data: SubmissionUpdate,
        org_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Submission:
        """Update content of submission.
        CRITICAL RULE: Any content change increments version, resets status to 'draft',
        and invalidates any prior approval.
        """
        current_sub = self.get_submission(sub_id, org_id, user_id)
        target_org = current_sub.org_id or org_id

        if user_id and target_org and not self.verify_user_in_org(user_id, target_org):
            raise HTTPException(
                status_code=403,
                detail=f"Access denied: Cannot modify submission in organisation '{target_org}'."
            )

        # Verify creator or reviewer/admin permissions
        if user_id and current_sub.creator_id and user_id != current_sub.creator_id:
            user_role = self.get_user_role_in_org(user_id, target_org)
            if user_role not in ["reviewer", "admin", "owner"]:
                raise HTTPException(
                    status_code=403,
                    detail="Access denied: Only the submission creator or an organisation reviewer/admin can edit content."
                )

        now = datetime.now(timezone.utc).isoformat()
        content_changed = data.content != current_sub.content

        update_payload: Dict = {"updated_at": now}
        if data.title:
            update_payload["title"] = data.title

        if content_changed:
            new_version = current_sub.version + 1
            # Invalidate approval / reset to draft
            update_payload["current_version"] = new_version
            update_payload["status"] = ReviewStatus.draft.value
            update_payload["submitted_content_snapshot"] = None
            update_payload["submitted_at"] = None

            # 1. Update submissions table
            self.client.table("submissions").update(update_payload).eq("id", sub_id).execute()

            # 2. Insert new version row
            version_payload = {
                "submission_id": sub_id,
                "version": new_version,
                "content": data.content,
                "created_by": user_id,
                "created_at": now,
            }
            self.client.table("submission_content_versions").insert(version_payload).execute()

            # 3. Re-run policy review and save findings
            new_review = run_deterministic_review(data.content)
            self._save_findings(sub_id, new_version, new_review.findings)
        else:
            self.client.table("submissions").update(update_payload).eq("id", sub_id).execute()

        return self.get_submission(sub_id, target_org, user_id)

    def submit_for_review(
        self,
        sub_id: str,
        req: Optional[SubmitForReviewRequest] = None,
        org_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Submission:
        """Transition submission from draft/changes_requested to 'in_review'."""
        current_sub = self.get_submission(sub_id, org_id, user_id)
        target_org = current_sub.org_id or org_id

        if user_id and target_org and not self.verify_user_in_org(user_id, target_org):
            raise HTTPException(
                status_code=403,
                detail=f"Access denied: Cannot submit content in organisation '{target_org}'."
            )

        if current_sub.status == ReviewStatus.in_review:
            raise HTTPException(
                status_code=400,
                detail="Submission is already 'in_review'. Awaiting reviewer decision."
            )

        now = datetime.now(timezone.utc).isoformat()
        payload = {
            "status": ReviewStatus.in_review.value,
            "submitted_at": now,
            "submitted_content_snapshot": current_sub.content,
            "updated_at": now,
        }
        if req and req.creator_name:
            payload["creator_name"] = req.creator_name

        self.client.table("submissions").update(payload).eq("id", sub_id).execute()

        # Re-run review to ensure findings snapshot is fresh
        review = run_deterministic_review(current_sub.content)
        self._save_findings(sub_id, current_sub.version, review.findings)

        return self.get_submission(sub_id, target_org, user_id)

    def record_decision(
        self,
        sub_id: str,
        req: DecisionRequest,
        org_id: Optional[str] = None,
        reviewer_id: Optional[str] = None,
        user_role: Optional[str] = None,
    ) -> Submission:
        """Record reviewer approval, change request, or rejection.

        Enforces:
        - Submission must currently be in 'in_review' status.
        - Comments are strictly required for 'changes_requested' and 'rejected'.
        - Verifies reviewer role (reviewer, admin, owner) from verified organisation_members.
        - Attributed reviewer_id derives strictly from authenticated user.
        - Creates immutable review_decisions entry.
        """
        current_sub = self.get_submission(sub_id, org_id, user_id=reviewer_id)
        target_org = current_sub.org_id or org_id

        if reviewer_id and target_org:
            if not self.verify_user_in_org(reviewer_id, target_org):
                raise HTTPException(
                    status_code=403,
                    detail=f"Access denied: User is not a member of organisation '{target_org}'."
                )
            verified_role = self.get_user_role_in_org(reviewer_id, target_org)
            effective_role = verified_role or user_role
            if effective_role not in ["reviewer", "admin", "owner"]:
                raise HTTPException(
                    status_code=403,
                    detail=f"User role '{effective_role or 'none'}' lacks permission to record review decisions. Requires 'reviewer', 'admin', or 'owner'."
                )

            # Separation of Duties: Content creators cannot approve their own content
            if (
                req.decision == DecisionType.approved
                and current_sub.creator_id
                and current_sub.creator_id == reviewer_id
            ):
                raise HTTPException(
                    status_code=403,
                    detail="Separation of duties violation: Content creators cannot approve their own submissions. Review must be conducted by an independent reviewer."
                )
        elif user_role and user_role not in ["reviewer", "admin", "owner"]:
            raise HTTPException(
                status_code=403,
                detail=f"User role '{user_role}' lacks permission to record review decisions. Requires 'reviewer', 'admin', or 'owner'."
            )

        if current_sub.status != ReviewStatus.in_review:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Cannot record decision '{req.decision.value}' on submission with status '{current_sub.status.value}'. "
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

        # Build decision record payload
        findings_summary = (
            current_sub.latest_review_response.findings_by_severity
            if current_sub.latest_review_response
            else {}
        )

        decision_id = str(uuid.uuid4())
        decision_payload = {
            "id": decision_id,
            "submission_id": sub_id,
            "decision": req.decision.value,
            "reviewer_id": reviewer_id,  # Strictly verified authenticated ID
            "reviewer_name": req.reviewer_name,
            "is_demo_reviewer": req.is_demo_reviewer if not reviewer_id else False,
            "comment": req.comment.strip() if req.comment else None,
            "content_version": current_sub.version,
            "content_snapshot": current_sub.submitted_content_snapshot or current_sub.content,
            "findings_summary": findings_summary,
            "guideline_version": 1,
            "created_at": now,
        }
        self.client.table("review_decisions").insert(decision_payload).execute()

        # Update submission status
        self.client.table("submissions").update({
            "status": req.decision.value,
            "updated_at": now,
        }).eq("id", sub_id).execute()

        return self.get_submission(sub_id, target_org, reviewer_id)

    def update_decision(self, *args, **kwargs):
        """Review decisions are immutable audit records and cannot be updated."""
        raise HTTPException(
            status_code=403,
            detail="Review decisions are immutable audit records and cannot be modified."
        )

    def delete_decision(self, *args, **kwargs):
        """Review decisions are immutable audit records and cannot be deleted."""
        raise HTTPException(
            status_code=403,
            detail="Review decisions are immutable audit records and cannot be deleted."
        )

    def _save_findings(self, sub_id: str, version: int, findings: List[Finding]):
        """Persist policy findings for a submission content version."""
        if not findings:
            return
        payloads = []
        for f in findings:
            payloads.append({
                "submission_id": sub_id,
                "content_version": version,
                "category": f.category.value,
                "severity": f.severity.value,
                "matched_text": f.matched_text,
                "start_index": f.start_index,
                "end_index": f.end_index,
                "explanation": f.explanation,
                "rule_name_or_fact": f.rule_name_or_fact,
                "suggested_correction": f.suggested_correction,
                "evidence_status": f.evidence_status.value,
                "source": getattr(f, "source", "deterministic"),
                "confidence": getattr(f, "confidence", None),
            })
        try:
            self.client.table("review_findings").insert(payloads).execute()
        except Exception:
            pass

    def _hydrate_submission(self, row: Dict) -> Submission:
        """Hydrate full Submission object with latest content version, findings, and decision history."""
        sub_id = str(row["id"])
        current_version = int(row.get("current_version", 1))

        # 1. Fetch active content from submission_content_versions
        content_res = (
            self.client.table("submission_content_versions")
            .select("content")
            .eq("submission_id", sub_id)
            .eq("version", current_version)
            .execute()
        )
        content = content_res.data[0]["content"] if content_res.data else ""

        # 2. Fetch findings for current version
        findings_res = (
            self.client.table("review_findings")
            .select("*")
            .eq("submission_id", sub_id)
            .eq("content_version", current_version)
            .execute()
        )
        findings: List[Finding] = []
        if findings_res.data:
            for f_row in findings_res.data:
                findings.append(
                    Finding(
                        id=str(f_row.get("id")),
                        category=FindingCategory(f_row["category"]),
                        severity=Severity(f_row["severity"]),
                        matched_text=f_row.get("matched_text"),
                        start_index=f_row.get("start_index"),
                        end_index=f_row.get("end_index"),
                        explanation=f_row.get("explanation", ""),
                        rule_name_or_fact=f_row.get("rule_name_or_fact", ""),
                        suggested_correction=f_row.get("suggested_correction"),
                        evidence_status=EvidenceStatus(f_row.get("evidence_status", "potential_issue")),
                        source=f_row.get("source", "deterministic"),
                        confidence=float(f_row["confidence"]) if f_row.get("confidence") is not None else None,
                    )
                )

        findings_by_severity = {
            Severity.critical.value: sum(1 for f in findings if f.severity == Severity.critical),
            Severity.warning.value: sum(1 for f in findings if f.severity == Severity.warning),
            Severity.info.value: sum(1 for f in findings if f.severity == Severity.info),
        }
        is_compliant = findings_by_severity[Severity.critical.value] == 0 and findings_by_severity[Severity.warning.value] == 0

        latest_review = ReviewResponse(
            text_length=len(content),
            total_findings=len(findings),
            findings_by_severity=findings_by_severity,
            findings=findings,
            is_compliant=is_compliant,
            brand_name="NovaSound Audio",
            is_demo_data=bool(row.get("is_demo", False)),
        )

        # 3. Fetch decision history
        decisions_res = (
            self.client.table("review_decisions")
            .select("*")
            .eq("submission_id", sub_id)
            .order("created_at", desc=False)
            .execute()
        )
        decisions: List[DecisionRecord] = []
        if decisions_res.data:
            for d_row in decisions_res.data:
                decisions.append(
                    DecisionRecord(
                        id=str(d_row.get("id") or uuid.uuid4()),
                        decision=DecisionType(d_row["decision"]),
                        reviewer_name=d_row.get("reviewer_name", "Reviewer"),
                        is_demo_reviewer=bool(d_row.get("is_demo_reviewer", True)),
                        reviewer_id=str(d_row["reviewer_id"]) if d_row.get("reviewer_id") else None,
                        comment=d_row.get("comment"),
                        timestamp=d_row.get("created_at", datetime.now(timezone.utc).isoformat()),
                        content_version=int(d_row.get("content_version", 1)),
                        content_snapshot=d_row.get("content_snapshot", ""),
                        findings_summary=d_row.get("findings_summary") or {},
                        guideline_version=int(d_row.get("guideline_version", 1)),
                    )
                )

        # 4. Fetch version history
        v_res = (
            self.client.table("submission_content_versions")
            .select("*")
            .eq("submission_id", sub_id)
            .order("version", desc=False)
            .execute()
        )
        version_history: List[SubmissionVersionSnapshot] = []
        if v_res.data:
            for v_row in v_res.data:
                version_history.append(
                    SubmissionVersionSnapshot(
                        version=int(v_row["version"]),
                        content=v_row.get("content", ""),
                        title=row.get("title", "Untitled Submission"),
                        timestamp=v_row.get("created_at", row.get("created_at", datetime.now(timezone.utc).isoformat())),
                        creator_name=row.get("creator_name", "Jordan Lee"),
                        status_at_save=ReviewStatus.draft,
                    )
                )
        if not version_history:
            version_history.append(
                SubmissionVersionSnapshot(
                    version=current_version,
                    content=content,
                    title=row.get("title", "Untitled Submission"),
                    timestamp=row.get("updated_at", datetime.now(timezone.utc).isoformat()),
                    creator_name=row.get("creator_name", "Jordan Lee"),
                    status_at_save=ReviewStatus(row.get("status", "draft")),
                )
            )

        return Submission(
            id=sub_id,
            title=row.get("title", "Untitled Submission"),
            content=content,
            version=current_version,
            status=ReviewStatus(row.get("status", "draft")),
            creator_name=row.get("creator_name", "Jordan Lee"),
            is_demo_creator=bool(row.get("is_demo", False)),
            creator_id=str(row["creator_id"]) if row.get("creator_id") else None,
            org_id=str(row["org_id"]) if row.get("org_id") else None,
            storage_mode="supabase_persistent",
            created_at=row.get("created_at", datetime.now(timezone.utc).isoformat()),
            updated_at=row.get("updated_at", datetime.now(timezone.utc).isoformat()),
            submitted_at=row.get("submitted_at"),
            submitted_content_snapshot=row.get("submitted_content_snapshot"),
            latest_review_response=latest_review,
            decision_history=decisions,
            version_history=version_history,
        )
