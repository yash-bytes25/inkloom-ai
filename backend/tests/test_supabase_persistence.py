from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock
import uuid
import jwt
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.models.workflow import (
    DecisionRequest,
    DecisionType,
    ReviewStatus,
    SubmissionCreate,
    SubmissionUpdate,
)
from backend.app.models.rules import (
    BrandRulesConfig,
    ProhibitedTermRule,
    ApprovedFact,
    Severity,
)
from backend.app.engine.supabase_client import (
    is_supabase_configured,
    get_supabase_client,
)
from backend.app.engine.supabase_repository import SupabaseWorkflowRepository
from backend.app.engine.workflow_service import WorkflowService, workflow_service
from backend.app.engine.auth import verify_jwt_token, is_production

client = TestClient(app)

TEST_JWT_SECRET = "super-secret-supabase-jwt-key-for-tests-32char!"


def create_test_token(
    user_id: str,
    secret: str = TEST_JWT_SECRET,
    expired: bool = False,
    email: str = "test@inkloom.ai",
    aud: str = "authenticated",
) -> str:
    """Helper to generate standard Supabase JWTs for tests."""
    now = datetime.now(timezone.utc)
    exp = (now - timedelta(hours=1)) if expired else (now + timedelta(hours=2))
    payload = {
        "sub": user_id,
        "email": email,
        "aud": aud,
        "exp": int(exp.timestamp()),
        "role": "authenticated",
    }
    return jwt.encode(payload, secret, algorithm="HS256")


class MockPostgrestQuery:
    """Simulates PostgREST query chain builder for unit testing without live Supabase."""

    def __init__(self, table_rows=None):
        self._table_rows = table_rows if table_rows is not None else []
        self._filters = []
        self._pending_update = None
        self._pending_insert = None
        self._pending_delete = False
        self._limit = None

    def select(self, *args, **kwargs):
        return self

    def insert(self, payload, *args, **kwargs):
        self._pending_insert = payload
        return self

    def update(self, payload, *args, **kwargs):
        self._pending_update = payload
        return self

    def delete(self, *args, **kwargs):
        self._pending_delete = True
        return self

    def eq(self, column, value):
        self._filters.append((column, value))
        return self

    def order(self, column, desc=False):
        return self

    def limit(self, count):
        self._limit = count
        return self

    def execute(self):
        res = MagicMock()

        # Handle insert
        if self._pending_insert is not None:
            inserted = []
            if isinstance(self._pending_insert, list):
                for item in self._pending_insert:
                    row = dict(item)
                    if "id" not in row:
                        row["id"] = str(uuid.uuid4())
                    self._table_rows.append(row)
                    inserted.append(row)
            else:
                row = dict(self._pending_insert)
                if "id" not in row:
                    row["id"] = str(uuid.uuid4())
                self._table_rows.append(row)
                inserted.append(row)
            res.data = inserted
            return res

        # Filter rows
        matched = []
        for row in self._table_rows:
            match = True
            for col, val in self._filters:
                if row.get(col) != val:
                    match = False
                    break
            if match:
                matched.append(row)

        # Handle delete
        if self._pending_delete:
            for row in matched:
                if row in self._table_rows:
                    self._table_rows.remove(row)
            res.data = matched
            return res

        # Handle update
        if self._pending_update is not None:
            for row in matched:
                row.update(self._pending_update)
            res.data = matched
            return res

        if self._limit is not None:
            res.data = matched[:self._limit]
        else:
            res.data = matched
        return res


class MockSupabaseAuth:
    """Simulates Supabase Auth API GoTrue service."""

    def __init__(self, users=None):
        self._users = users or {}

    def get_user(self, token: str):
        if token in self._users:
            u_info = self._users[token]
            res = MagicMock()
            user = MagicMock()
            user.id = u_info.get("id", "user-uuid-1")
            user.email = u_info.get("email", "user@inkloom.ai")
            res.user = user
            return res
        raise Exception("Invalid token or user session expired")


class MockSupabaseClient:
    """Mock Supabase Client with in-memory tables and Auth mock."""

    def __init__(self, auth_users=None):
        self.tables = {
            "submissions": [],
            "submission_content_versions": [],
            "review_findings": [],
            "review_decisions": [],
            "organisation_members": [],
            "brand_guidelines": [],
            "prohibited_terms": [],
            "preferred_wordings": [],
            "approved_facts": [],
            "required_disclaimers": [],
        }
        self.auth = MockSupabaseAuth(auth_users)
        self.postgrest = MagicMock()

    def table(self, name):
        if name not in self.tables:
            self.tables[name] = []
        rows = self.tables[name]
        return MockPostgrestQuery(rows)


# ==============================================================================
# 1. Supabase Configuration & Fallback Detection
# ==============================================================================

def test_is_supabase_configured_detection(monkeypatch):
    """is_supabase_configured detects placeholders and missing variables accurately."""
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
    assert is_supabase_configured() is False

    monkeypatch.setenv("SUPABASE_URL", "https://your-project-ref.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "your_supabase_anon_key_here")
    assert is_supabase_configured() is False

    monkeypatch.setenv("SUPABASE_URL", "https://xyzcompany.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.validkey")
    assert is_supabase_configured() is True


def test_workflow_service_local_demo_storage_mode(monkeypatch):
    """When Supabase is not configured in dev, WorkflowService operates in local demo mode."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)

    service = WorkflowService()
    submissions = service.list_submissions()
    assert len(submissions) >= 1
    assert submissions[0].storage_mode == "local_demo"


def test_api_health_endpoint_reports_storage_mode():
    """GET /api/health reports storage_mode ('local_demo' or 'supabase_persistent')."""
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert "storage_mode" in data
    assert data["storage_mode"] in ["local_demo", "supabase_persistent"]


# ==============================================================================
# 2. Authentication Verification: Missing, Expired, Malformed, Invalid Signature
# ==============================================================================

def test_auth_missing_token_in_production_mode(monkeypatch):
    """Missing Authorization token in production mode returns HTTP 401."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    res = client.get("/api/submissions")
    assert res.status_code == 401
    assert "Missing Authorization" in res.json()["detail"] or "not provided" in res.json()["detail"]


def test_auth_missing_token_in_persistent_mode(monkeypatch):
    """Missing Authorization token when Supabase is configured returns HTTP 401."""
    monkeypatch.setenv("SUPABASE_URL", "https://live.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "valid-key-xyz")
    res = client.get("/api/submissions")
    assert res.status_code == 401
    assert "Authentication credentials were not provided" in res.json()["detail"]


def test_auth_expired_token_rejected(monkeypatch):
    """Expired JWT access token is rejected with HTTP 401."""
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    expired_token = create_test_token("user-1", TEST_JWT_SECRET, expired=True)

    with pytest.raises(HTTPException) as exc_info:
        verify_jwt_token(expired_token)
    assert exc_info.value.status_code == 401
    assert "Token has expired" in exc_info.value.detail


def test_auth_malformed_token_rejected():
    """Malformed non-JWT tokens are rejected with HTTP 401."""
    with pytest.raises(HTTPException) as exc1:
        verify_jwt_token("not_a_valid_jwt_string")
    assert exc1.value.status_code == 401
    assert "Malformed authentication token" in exc1.value.detail

    with pytest.raises(HTTPException) as exc2:
        verify_jwt_token("a.b.c.d.extra")
    assert exc2.value.status_code == 401
    assert "Malformed authentication token" in exc2.value.detail


def test_auth_invalid_signature_token_rejected(monkeypatch):
    """Token signed with wrong key is rejected with HTTP 401."""
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    fake_token = create_test_token("user-hacker", secret="attacker-untrusted-key-1234567890!")

    with pytest.raises(HTTPException) as exc_info:
        verify_jwt_token(fake_token)
def make_raw_jwt(header_dict: dict, payload_dict: dict, sig: str = "") -> str:
    """Helper to assemble raw unverified JWT strings for adversarial edge-case testing."""
    import base64
    import json
    h = base64.urlsafe_b64encode(json.dumps(header_dict).encode()).decode().rstrip("=")
    p = base64.urlsafe_b64encode(json.dumps(payload_dict).encode()).decode().rstrip("=")
    return f"{h}.{p}.{sig}"


def test_auth_alg_none_token_rejected(monkeypatch):
    """Tokens with alg='none' are strictly rejected with HTTP 401."""
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    header = {"alg": "none", "typ": "JWT"}
    payload = {
        "sub": "user-attacker",
        "aud": "authenticated",
        "exp": int(datetime.now(timezone.utc).timestamp() + 3600),
    }
    none_token = make_raw_jwt(header, payload, sig="")

    with pytest.raises(HTTPException) as exc_info:
        verify_jwt_token(none_token)
    assert exc_info.value.status_code == 401
    assert "none" in exc_info.value.detail.lower() or "strictly forbidden" in exc_info.value.detail.lower()


def test_auth_unexpected_algorithm_rejected(monkeypatch):
    """Tokens specifying unexpected or unsupported algorithms (e.g. RS256) are rejected with HTTP 401."""
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    header = {"alg": "RS256", "typ": "JWT"}
    payload = {
        "sub": "user-attacker",
        "aud": "authenticated",
        "exp": int(datetime.now(timezone.utc).timestamp() + 3600),
    }
    rs_token = make_raw_jwt(header, payload, sig="fakesig")

    with pytest.raises(HTTPException) as exc_info:
        verify_jwt_token(rs_token)
    assert exc_info.value.status_code == 401
    assert "RS256" in exc_info.value.detail or "not permitted" in exc_info.value.detail


def test_auth_invalid_audience_rejected(monkeypatch):
    """Tokens with wrong audience (e.g. not 'authenticated') are rejected with HTTP 401."""
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    token_wrong_aud = create_test_token("user-1", TEST_JWT_SECRET, aud="anon_public_client")

    with pytest.raises(HTTPException) as exc_info:
        verify_jwt_token(token_wrong_aud)
    assert exc_info.value.status_code == 401
    assert "audience" in exc_info.value.detail.lower()


def test_auth_unconfigured_authority_rejects_tokens(monkeypatch):
    """When no verification authority (secret or Supabase client) is configured, tokens are rejected."""
    monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)

    token = create_test_token("user-1", secret="any-secret")
    with pytest.raises(HTTPException) as exc_info:
        verify_jwt_token(token)
    assert exc_info.value.status_code == 401
    assert "Unable to verify token" in exc_info.value.detail


def test_production_mode_strictly_disallows_demo_fallback(monkeypatch):
    """In production, service rejects requests with HTTP 503 if Supabase is unconfigured."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)

    service = WorkflowService()
    with pytest.raises(HTTPException) as exc:
        service.list_submissions()
    assert exc.value.status_code == 503
    assert "Production service misconfigured" in exc.value.detail


# ==============================================================================
# 3. Multi-Tenant Isolation & Role Authorization
# ==============================================================================

def test_supabase_repository_create_and_version_tracking():
    """Repository creates submission, initial version v1, and verifies membership."""
    mock_client = MockSupabaseClient()
    org_id = "org-acme-123"
    user_id = "user-creator-456"

    # Add member to organisation
    mock_client.tables["organisation_members"].append({
        "org_id": org_id,
        "user_id": user_id,
        "role": "creator",
    })

    repo = SupabaseWorkflowRepository(mock_client)
    create_data = SubmissionCreate(
        title="Apex Wireless Launch Copy",
        content="Experience NovaSound Apex Wireless at $299 with 40 hours battery life.",
        creator_name="Jordan Lee",
        is_demo_creator=False,
    )

    sub = repo.create_submission(create_data, org_id=org_id, user_id=user_id)

    assert sub.title == "Apex Wireless Launch Copy"
    assert sub.version == 1
    assert sub.status == ReviewStatus.draft
    assert sub.storage_mode == "supabase_persistent"
    assert len(mock_client.tables["submissions"]) == 1
    assert len(mock_client.tables["submission_content_versions"]) == 1
    assert mock_client.tables["submission_content_versions"][0]["version"] == 1


def test_supabase_repository_content_change_invalidates_approval():
    """Updating content in Supabase repository increments version and invalidates prior approval."""
    mock_client = MockSupabaseClient()
    org_id = "org-acme-123"
    user_id = "user-1"

    mock_client.tables["organisation_members"].append({
        "org_id": org_id,
        "user_id": user_id,
        "role": "creator",
    })

    # Seed approved submission
    sub_id = "sub-test-01"
    mock_client.tables["submissions"].append({
        "id": sub_id,
        "org_id": org_id,
        "title": "Ad Copy",
        "current_version": 1,
        "status": ReviewStatus.approved.value,
        "creator_id": user_id,
        "creator_name": "Jordan",
        "is_demo": False,
        "submitted_at": "2026-10-25T10:00:00Z",
        "submitted_content_snapshot": "Approved text.",
    })
    mock_client.tables["submission_content_versions"].append({
        "submission_id": sub_id,
        "version": 1,
        "content": "Approved text.",
    })

    repo = SupabaseWorkflowRepository(mock_client)
    update_data = SubmissionUpdate(content="Modified text with cheap headphones.")
    updated_sub = repo.update_submission(sub_id, update_data, org_id=org_id, user_id=user_id)

    # Version increments to 2, status resets to draft, prior approval is invalidated
    assert updated_sub.version == 2
    assert updated_sub.status == ReviewStatus.draft
    assert len(mock_client.tables["submission_content_versions"]) == 2
    assert mock_client.tables["submission_content_versions"][1]["version"] == 2


def test_creator_cannot_approve_content_returns_403():
    """Users with 'creator' role attempting to approve/reject content are strictly forbidden (HTTP 403)."""
    mock_client = MockSupabaseClient()
    sub_id = "sub-rev-01"
    org_id = "org-1"

    # Register Bob as creator and Alex as reviewer
    mock_client.tables["organisation_members"].append({
        "org_id": org_id,
        "user_id": "user-bob",
        "role": "creator",
    })
    mock_client.tables["organisation_members"].append({
        "org_id": org_id,
        "user_id": "user-alex",
        "role": "reviewer",
    })

    mock_client.tables["submissions"].append({
        "id": sub_id,
        "org_id": org_id,
        "title": "Copy",
        "current_version": 1,
        "status": ReviewStatus.in_review.value,
        "creator_id": "user-bob",
        "creator_name": "Jordan",
    })
    mock_client.tables["submission_content_versions"].append({
        "submission_id": sub_id,
        "version": 1,
        "content": "Submitted text.",
    })

    repo = SupabaseWorkflowRepository(mock_client)
    req = DecisionRequest(
        decision=DecisionType.approved,
        reviewer_name="Bob (Creator Only)",
        comment="Trying to self-approve.",
    )

    # 1. Creator attempting to approve -> 403 Forbidden
    with pytest.raises(HTTPException) as exc_info:
        repo.record_decision(sub_id, req, org_id=org_id, reviewer_id="user-bob")
    assert exc_info.value.status_code == 403
    assert "lacks permission" in exc_info.value.detail or "Requires 'reviewer'" in exc_info.value.detail

    # 2. Reviewer succeeds
    approved_sub = repo.record_decision(sub_id, req, org_id=org_id, reviewer_id="user-alex")
    assert approved_sub.status == ReviewStatus.approved
    assert len(mock_client.tables["review_decisions"]) == 1


def test_non_member_organisation_access_returns_403():
    """Attempting to access or list submissions for a non-member organisation returns HTTP 403."""
    mock_client = MockSupabaseClient()
    mock_client.tables["organisation_members"].append({
        "org_id": "org-allowed",
        "user_id": "user-alice",
        "role": "reviewer",
    })

    repo = SupabaseWorkflowRepository(mock_client)

    # Allowed access
    assert repo.verify_user_in_org("user-alice", "org-allowed") is True

    # Denied access to unauthorized organisation
    with pytest.raises(HTTPException) as exc:
        repo.list_submissions(org_id="org-foreign", user_id="user-alice")
    assert exc.value.status_code == 403
    assert "not an authorized member" in exc.value.detail


def test_cross_tenant_reads_and_writes_prevented():
    """Users cannot read or write submissions belonging to another organisation."""
    mock_client = MockSupabaseClient()
    sub_id = "sub-secret-tenant-a"
    org_a = "org-alpha"
    org_b = "org-beta"

    # User Eve is only a member of org-beta
    mock_client.tables["organisation_members"].append({
        "org_id": org_b,
        "user_id": "user-eve",
        "role": "reviewer",
    })

    # Submission belongs to org-alpha
    mock_client.tables["submissions"].append({
        "id": sub_id,
        "org_id": org_a,
        "title": "Secret Strategy Copy",
        "current_version": 1,
        "status": ReviewStatus.draft.value,
        "creator_id": "user-alpha-creator",
    })
    mock_client.tables["submission_content_versions"].append({
        "submission_id": sub_id,
        "version": 1,
        "content": "Confidential text.",
    })

    repo = SupabaseWorkflowRepository(mock_client)

    # 1. Cross-tenant read is blocked with 403
    with pytest.raises(HTTPException) as exc_read:
        repo.get_submission(sub_id, user_id="user-eve")
    assert exc_read.value.status_code == 403
    assert "not authorized to access submissions" in exc_read.value.detail

    # 2. Cross-tenant write (content update) is blocked with 403
    with pytest.raises(HTTPException) as exc_write:
        repo.update_submission(
            sub_id,
            SubmissionUpdate(content="Tampered content"),
            user_id="user-eve",
        )
    assert exc_write.value.status_code == 403

    # 3. Cross-tenant submit is blocked with 403
    with pytest.raises(HTTPException) as exc_submit:
        repo.submit_for_review(sub_id, user_id="user-eve")
    assert exc_submit.value.status_code == 403

    # 4. Cross-tenant creation into org-alpha by Eve is blocked with 403
    with pytest.raises(HTTPException) as exc_create:
        repo.create_submission(
            SubmissionCreate(title="Fake", content="Test"),
            org_id=org_a,
            user_id="user-eve",
        )
    assert exc_create.value.status_code == 403

    # 5. Cross-tenant decision recording by Eve is blocked with 403
    with pytest.raises(HTTPException) as exc_dec:
        repo.record_decision(
            sub_id,
            DecisionRequest(decision=DecisionType.approved, comment="Unauthorized cross-tenant approve"),
            org_id=org_a,
            reviewer_id="user-eve",
        )
    assert exc_dec.value.status_code == 403


def test_review_decision_history_is_immutable():
    """Review decisions cannot be updated or deleted, enforcing audit integrity."""
    mock_client = MockSupabaseClient()
    repo = SupabaseWorkflowRepository(mock_client)

    with pytest.raises(HTTPException) as exc_up:
        repo.update_decision()
    assert exc_up.value.status_code == 403
    assert "immutable audit records" in exc_up.value.detail

    with pytest.raises(HTTPException) as exc_del:
        repo.delete_decision()
    assert exc_del.value.status_code == 403
    assert "immutable audit records" in exc_del.value.detail


def test_supabase_repository_mandatory_comment_validation():
    """Requesting changes or rejecting in Supabase repository strictly requires non-empty comment (HTTP 422)."""
    mock_client = MockSupabaseClient()
    sub_id = "sub-dec-01"
    org_id = "org-1"
    reviewer_id = "user-rev-01"

    mock_client.tables["organisation_members"].append({
        "org_id": org_id,
        "user_id": reviewer_id,
        "role": "reviewer",
    })

    mock_client.tables["submissions"].append({
        "id": sub_id,
        "org_id": org_id,
        "title": "Copy",
        "current_version": 1,
        "status": ReviewStatus.in_review.value,
        "creator_name": "Jordan",
    })
    mock_client.tables["submission_content_versions"].append({
        "submission_id": sub_id,
        "version": 1,
        "content": "Submitted text.",
    })

    repo = SupabaseWorkflowRepository(mock_client)

    # Empty comment on change request -> 422
    with pytest.raises(HTTPException) as exc:
        repo.record_decision(
            sub_id,
            DecisionRequest(decision=DecisionType.changes_requested, comment="   "),
            org_id=org_id,
            reviewer_id=reviewer_id,
        )
    assert exc.value.status_code == 422


def test_separation_of_duties_creator_cannot_approve_own_content():
    """Separation of duties (four-eyes principle): Even if a user has 'reviewer' role,
    they cannot approve content that they created (HTTP 403). An independent reviewer must approve."""
    mock_client = MockSupabaseClient()
    sub_id = "sub-four-eyes-01"
    org_id = "org-corp"
    dual_role_user = "user-dual-role"
    independent_reviewer = "user-independent-reviewer"

    # Both users are registered as reviewers in org-corp
    mock_client.tables["organisation_members"].append({
        "org_id": org_id,
        "user_id": dual_role_user,
        "role": "reviewer",
    })
    mock_client.tables["organisation_members"].append({
        "org_id": org_id,
        "user_id": independent_reviewer,
        "role": "reviewer",
    })

    # dual_role_user authored the submission
    mock_client.tables["submissions"].append({
        "id": sub_id,
        "org_id": org_id,
        "title": "Dual Role Submission",
        "current_version": 1,
        "status": ReviewStatus.in_review.value,
        "creator_id": dual_role_user,
        "creator_name": "Author / Reviewer",
    })
    mock_client.tables["submission_content_versions"].append({
        "submission_id": sub_id,
        "version": 1,
        "content": "Self created marketing copy.",
    })

    repo = SupabaseWorkflowRepository(mock_client)

    # 1. Author attempting self-approval fails with 403 Separation of Duties violation
    with pytest.raises(HTTPException) as exc_self:
        repo.record_decision(
            sub_id,
            DecisionRequest(
                decision=DecisionType.approved,
                comment="Self-approving my own submission.",
            ),
            org_id=org_id,
            reviewer_id=dual_role_user,
        )
    assert exc_self.value.status_code == 403
    assert "Separation of duties violation" in exc_self.value.detail

    # 2. Independent reviewer can approve the submission successfully
    approved_sub = repo.record_decision(
        sub_id,
        DecisionRequest(
            decision=DecisionType.approved,
            comment="Independent review completed and verified.",
        ),
        org_id=org_id,
        reviewer_id=independent_reviewer,
    )
    assert approved_sub.status == ReviewStatus.approved


def test_reviewer_cannot_perform_unauthorized_administration():
    """Users with 'reviewer' role are restricted from administrative actions (e.g. member/org management)."""
    mock_client = MockSupabaseClient()
    org_id = "org-enterprise"
    reviewer_user = "user-pure-reviewer"
    admin_user = "user-admin-lead"

    mock_client.tables["organisation_members"].append({
        "org_id": org_id,
        "user_id": reviewer_user,
        "role": "reviewer",
    })
    mock_client.tables["organisation_members"].append({
        "org_id": org_id,
        "user_id": admin_user,
        "role": "admin",
    })

    repo = SupabaseWorkflowRepository(mock_client)

    # Verify reviewer cannot claim admin/owner rights
    assert repo.verify_user_role(reviewer_user, org_id, ["owner", "admin"]) is False
    assert repo.get_user_role_in_org(reviewer_user, org_id) == "reviewer"

    # Verify admin does satisfy admin/owner rights
    assert repo.verify_user_role(admin_user, org_id, ["owner", "admin"]) is True
    assert repo.get_user_role_in_org(admin_user, org_id) == "admin"


def test_workflow_service_demo_mode_separation_of_duties(monkeypatch):
    """Even in local demo mode, WorkflowService blocks creators from self-approving submissions."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)

    service = WorkflowService()
    # Create submission with creator_id
    sub = service.create_submission(
        SubmissionCreate(title="Demo Post", content="Demo copy"),
        user_id="user-author-99",
    )
    service.submit_for_review(sub.id)

    # Self-approval fails
    with pytest.raises(HTTPException) as exc:
        service.record_decision(
            sub.id,
            DecisionRequest(decision=DecisionType.approved, comment="Self approve"),
            reviewer_id="user-author-99",
            user_role="reviewer",
        )
    assert exc.value.status_code == 403
    assert "Separation of duties violation" in exc.value.detail

    # Independent reviewer succeeds
    approved = service.record_decision(
        sub.id,
        DecisionRequest(decision=DecisionType.approved, comment="Independent approve"),
        reviewer_id="user-peer-reviewer",
        user_role="reviewer",
    )
    assert approved.status == ReviewStatus.approved


def test_payload_size_limits_enforced():
    """Adversarial request bodies with oversized content, title, or comment are rejected with HTTP 422."""
    # 1. Submission content exceeding 50,000 characters
    oversized_content = "A" * 50001
    res1 = client.post("/api/submissions", json={
        "title": "Valid Title",
        "content": oversized_content,
    })
    assert res1.status_code == 422

    # 2. Submission title exceeding 255 characters
    oversized_title = "T" * 256
    res2 = client.post("/api/submissions", json={
        "title": oversized_title,
        "content": "Valid short content.",
    })
    assert res2.status_code == 422

    # 3. Decision comment exceeding 5,000 characters
    oversized_comment = "C" * 5001
    res3 = client.post("/api/submissions/sub-123/decision", json={
        "decision": DecisionType.changes_requested.value,
        "comment": oversized_comment,
    })
    assert res3.status_code == 422

    # 4. Review request text exceeding 50,000 characters
    res4 = client.post("/api/review", json={
        "text": oversized_content,
    })
    assert res4.status_code == 422


def test_rate_limiter_blocks_excessive_ai_audit_and_decision_calls():
    """SlidingWindowRateLimiter blocks requests exceeding quota with HTTP 429 and Retry-After header."""
    from backend.app.engine.rate_limiter import SlidingWindowRateLimiter

    limiter = SlidingWindowRateLimiter(max_requests=3, window_seconds=60, name="TestLimiter")

    # First 3 calls succeed
    limiter.check("client-ip-1")
    limiter.check("client-ip-1")
    limiter.check("client-ip-1")

    # 4th call within same window raises HTTP 429
    with pytest.raises(HTTPException) as exc:
        limiter.check("client-ip-1")
    assert exc.value.status_code == 429
    assert "Rate limit exceeded" in exc.value.detail
    assert "Retry-After" in exc.value.headers

    # Other clients remain unaffected
    limiter.check("client-ip-2")


def test_unconstrained_list_submissions_returns_empty_under_service_role():
    """When called without tenant context (org_id=None, user_id=None), list_submissions returns empty to prevent data dumping."""
    mock_client = MockSupabaseClient()
    mock_client.tables["submissions"].append({
        "id": "sub-1",
        "org_id": "org-secret-1",
        "title": "Secret 1",
        "current_version": 1,
        "status": ReviewStatus.draft.value,
        "creator_name": "Author",
    })
    mock_client.tables["submissions"].append({
        "id": "sub-2",
        "org_id": "org-secret-2",
        "title": "Secret 2",
        "current_version": 1,
        "status": ReviewStatus.draft.value,
        "creator_name": "Author",
    })

    repo = SupabaseWorkflowRepository(mock_client)
    res = repo.list_submissions(org_id=None, user_id=None)
    assert res == []


def test_supabase_repository_guidelines_persistence():
    """Verify SupabaseWorkflowRepository save_guidelines, get_guidelines, and reset_guidelines."""
    mock_client = MockSupabaseClient()
    mock_client.tables["organisation_members"].append({
        "org_id": "org-omega",
        "user_id": "admin-1",
        "role": "admin",
    })
    mock_client.tables["organisation_members"].append({
        "org_id": "org-omega",
        "user_id": "creator-1",
        "role": "creator",
    })

    repo = SupabaseWorkflowRepository(mock_client)

    rules = BrandRulesConfig(
        brand_name="NovaSound Test Corp",
        description="Pioneering next-gen audio",
        voice_and_tone="Bold and authentic",
        is_demo=False,
        prohibited_terms=[
            ProhibitedTermRule(
                id="pt-1",
                term_or_pattern="cheap earbuds",
                explanation="Unapproved phrasing",
                severity=Severity.critical,
            )
        ],
        approved_facts=[
            ApprovedFact(
                id="af-1",
                entity="Apex Wireless",
                attribute="price",
                approved_value="$299",
                explanation="Official retail price",
                severity=Severity.critical,
            )
        ],
    )

    # 1. Creator (not admin) cannot save guidelines
    with pytest.raises(HTTPException) as exc:
        repo.save_guidelines("org-omega", rules, user_id="creator-1")
    assert exc.value.status_code == 403

    # 2. Admin can save guidelines
    saved = repo.save_guidelines("org-omega", rules, user_id="admin-1")
    assert saved.brand_name == "NovaSound Test Corp"
    assert saved.description == "Pioneering next-gen audio"
    assert saved.voice_and_tone == "Bold and authentic"
    assert len(saved.prohibited_terms) == 1
    assert len(saved.approved_facts) == 1

    # 3. Read back guidelines
    retrieved = repo.get_guidelines("org-omega", user_id="creator-1")
    assert retrieved is not None
    assert retrieved.brand_name == "NovaSound Test Corp"
    assert retrieved.prohibited_terms[0].term_or_pattern == "cheap earbuds"

    # 4. Reset guidelines
    reset_rules = repo.reset_guidelines("org-omega", user_id="admin-1")
    assert "NovaSound Audio" in reset_rules.brand_name


def test_auth_login_and_me_endpoints():
    """Verify /api/auth/login and /api/auth/me endpoints in demo mode."""
    # Login in demo mode
    login_res = client.post("/api/auth/login", json={"email": "jordan@example.com", "password": "any"})
    assert login_res.status_code == 200
    login_data = login_res.json()
    assert login_data["access_token"] == "demo-local-jwt-token"
    assert login_data["is_demo"] is True

    # Call /api/auth/me unauthenticated (demo mode)
    me_res = client.get("/api/auth/me")
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["is_demo"] is True
    assert me_data["user_id"] == "demo-local-user"
    assert me_data["role"] == "reviewer"



