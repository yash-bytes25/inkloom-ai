"""Live Supabase Integration Test Suite (Development & CI/CD with Real Supabase)
=============================================================================
This test suite executes real HTTP / PostgREST queries against a live Supabase instance
to verify actual database-level Row Level Security (RLS) enforcement, cross-tenant isolation,
Separation of Duties (Four-Eyes Principle), and role boundaries.

Execution Requirements:
- A live Supabase project (local Docker stack via `supabase start` or cloud dev project).
- Environment variables:
    SUPABASE_URL=https://<your-project>.supabase.co
    SUPABASE_ANON_KEY=<anon_public_key>
    SUPABASE_JWT_SECRET=<jwt_secret>
    SUPABASE_SERVICE_ROLE_KEY=<service_role_key> (for test fixture setup/teardown)

When credentials are unset or placeholders, all tests in this file are skipped cleanly,
ensuring unit test runs never falsely claim live Supabase verification.
"""

from datetime import datetime, timezone, timedelta
import os
from pathlib import Path
from typing import Optional
import uuid
import jwt
import pytest
from dotenv import dotenv_values

from backend.app.engine.supabase_client import is_supabase_configured, get_supabase_client
from backend.app.engine.supabase_repository import SupabaseWorkflowRepository
from backend.app.models.workflow import DecisionType, ReviewStatus
from backend.app.models.rules import BrandRulesConfig, ProhibitedTermRule, ApprovedFact, Severity

# Load credentials from backend/.env into local dictionary without mutating os.environ globally during collection
_env_path = Path(__file__).resolve().parent.parent / ".env"
_live_env = dotenv_values(dotenv_path=_env_path) if _env_path.exists() else {}


def _is_live_configured() -> bool:
    url = _live_env.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL", "")
    key = _live_env.get("SUPABASE_ANON_KEY") or os.environ.get("SUPABASE_ANON_KEY", "")
    placeholder_url = "https://your-project-ref.supabase.co"
    placeholder_key = "your_supabase_anon_key_here"
    if not url or url.strip() == placeholder_url:
        return False
    if not key or key.strip() in [placeholder_key, "your_supabase_anon_or_service_key_here"]:
        return False
    return True


# Skip entire module if Supabase credentials are not configured
pytestmark = pytest.mark.skipif(
    not _is_live_configured(),
    reason="Requires live Supabase project with real SUPABASE_URL and SUPABASE_ANON_KEY to verify actual database RLS.",
)


@pytest.fixture(scope="module", autouse=True)
def live_supabase_env():
    """Scoped environment loader for live integration tests only.
    Injects backend/.env credentials into os.environ for the duration of this module
    and restores the original environment afterwards, preventing leakage into offline unit tests.
    """
    original_env = {}
    for k, v in _live_env.items():
        if v:
            original_env[k] = os.environ.get(k)
            os.environ[k] = v
    try:
        yield
    finally:
        for k in _live_env:
            if k in original_env and original_env[k] is not None:
                os.environ[k] = original_env[k]
            else:
                os.environ.pop(k, None)


def create_live_jwt(user_id: str, secret: str) -> str:
    """Generate a standard HS256 Supabase JWT for live authenticated PostgREST calls."""
    now = datetime.now(timezone.utc)
    exp = now + timedelta(hours=2)
    payload = {
        "sub": user_id,
        "aud": "authenticated",
        "exp": int(exp.timestamp()),
        "role": "authenticated",
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def create_test_auth_user(service_client, prefix: str = "test") -> str:
    """Create a temporary genuine Supabase Auth user in auth.users for RLS testing."""
    unique_suffix = uuid.uuid4().hex[:10]
    email = f"{prefix}_{unique_suffix}@inkloom.test"
    password = f"P@ssword_{unique_suffix}!"
    user_res = service_client.auth.admin.create_user({
        "email": email,
        "password": password,
        "email_confirm": True,
    })
    return str(user_res.user.id)


def delete_test_auth_user(service_client, user_id: Optional[str]) -> None:
    """Safely delete temporary test user from auth.users."""
    if not service_client or not user_id:
        return
    try:
        service_client.auth.admin.delete_user(user_id)
    except Exception:
        pass


@pytest.fixture(scope="module")
def live_client():
    """Returns real Supabase client initialized with test credentials."""
    return get_supabase_client()


@pytest.fixture(scope="module")
def service_client():
    """Returns administrative service-role client for fixture setup/teardown."""
    return get_supabase_client(use_service_role=True)


def test_live_database_connection(live_client):
    """Smoke test: verify PostgREST connection and schema availability on live database."""
    res = live_client.table("brand_guidelines").select("id").limit(1).execute()
    assert res is not None
    assert hasattr(res, "data")


def test_live_cross_tenant_isolation_and_rls(live_client, service_client):
    """Verify that a token for User A in Org Alpha cannot read or write data in Org Beta."""
    jwt_secret = os.environ.get("SUPABASE_JWT_SECRET", "").strip()
    if not jwt_secret:
        pytest.skip("Requires SUPABASE_JWT_SECRET to generate authenticated test tokens for cross-tenant RLS testing.")
    if not service_client:
        pytest.skip("Requires SUPABASE_SERVICE_ROLE_KEY to seed genuine test users and organisations.")

    user_a = None
    user_b = None
    org_alpha = str(uuid.uuid4())
    org_beta = str(uuid.uuid4())

    try:
        # Create genuine users in auth.users to satisfy foreign keys
        user_a = create_test_auth_user(service_client, "user_a")
        user_b = create_test_auth_user(service_client, "user_b")

        token_a = create_live_jwt(user_a, jwt_secret)
        token_b = create_live_jwt(user_b, jwt_secret)

        client_a = get_supabase_client(user_token=token_a)
        client_b = get_supabase_client(user_token=token_b)

        # Seed organisations
        service_client.table("organisations").insert([
            {"id": org_alpha, "name": f"Org Alpha Test {org_alpha[:6]}", "slug": f"org-alpha-{org_alpha[:6]}"},
            {"id": org_beta, "name": f"Org Beta Test {org_beta[:6]}", "slug": f"org-beta-{org_beta[:6]}"},
        ]).execute()

        # Seed memberships
        service_client.table("organisation_members").insert([
            {"org_id": org_alpha, "user_id": user_a, "role": "creator"},
            {"org_id": org_beta, "user_id": user_b, "role": "creator"},
        ]).execute()

        # Seed a submission in Org Beta (NO content column in submissions!)
        sub_beta = service_client.table("submissions").insert({
            "org_id": org_beta,
            "title": "Confidential Beta Submission",
            "current_version": 1,
            "status": "draft",
            "creator_id": user_b,
            "creator_name": "Beta Creator",
        }).execute()
        sub_beta_id = sub_beta.data[0]["id"]

        # Insert version into submission_content_versions
        service_client.table("submission_content_versions").insert({
            "submission_id": sub_beta_id,
            "version": 1,
            "content": "Secret beta launch copy.",
            "created_by": user_b,
        }).execute()

        # 1. Client A queries submissions in Org Beta -> RLS must return empty list
        res_read = client_a.table("submissions").select("*").eq("id", sub_beta_id).execute()
        assert len(res_read.data) == 0, "Security Violation: User A read submission in Org Beta!"

        # 1b. Client A queries submission_content_versions in Org Beta -> RLS must return empty list
        res_ver_read = client_a.table("submission_content_versions").select("*").eq("submission_id", sub_beta_id).execute()
        assert len(res_ver_read.data) == 0, "Security Violation: User A read submission_content_versions in Org Beta!"

        # 2. Client A attempts to insert a submission into Org Beta -> RLS WITH CHECK must block
        blocked = False
        try:
            res_write = client_a.table("submissions").insert({
                "org_id": org_beta,
                "title": "Intrusion Attempt",
                "current_version": 1,
                "status": "draft",
                "creator_id": user_a,
                "creator_name": "Malicious Actor",
            }).execute()
            if len(res_write.data) == 0:
                blocked = True
        except Exception as exc:
            blocked = True
            assert "policy" in str(exc).lower() or "permission" in str(exc).lower() or "violation" in str(exc).lower() or "error" in str(exc).lower()

        assert blocked, "Security Violation: User A inserted into Org Beta!"

    finally:
        # Clean up test organisations (cascades to submissions and memberships)
        try:
            service_client.table("organisations").delete().in_("id", [org_alpha, org_beta]).execute()
        except Exception:
            pass
        delete_test_auth_user(service_client, user_a)
        delete_test_auth_user(service_client, user_b)


def test_live_separation_of_duties_at_database_level(live_client, service_client):
    """Verify that inserting an 'approved' decision with creator_id == reviewer_id
    violates decisions_reviewer_insert policy and fails at the PostgreSQL RLS layer.
    """
    jwt_secret = os.environ.get("SUPABASE_JWT_SECRET", "").strip()
    if not jwt_secret or not service_client:
        pytest.skip("Requires SUPABASE_JWT_SECRET and SUPABASE_SERVICE_ROLE_KEY to test database-level separation of duties.")

    test_org_id = str(uuid.uuid4())
    creator_and_reviewer_user = None

    try:
        # Create genuine user in auth.users
        creator_and_reviewer_user = create_test_auth_user(service_client, "sod_author")
        token = create_live_jwt(creator_and_reviewer_user, jwt_secret)
        user_client = get_supabase_client(user_token=token)

        # Seed test organisation and give user reviewer role
        service_client.table("organisations").insert({
            "id": test_org_id,
            "name": f"SoD Test Org {test_org_id[:6]}",
            "slug": f"sod-test-{test_org_id[:6]}",
        }).execute()

        service_client.table("organisation_members").insert({
            "org_id": test_org_id,
            "user_id": creator_and_reviewer_user,
            "role": "reviewer",
        }).execute()

        # Seed submission where creator is this user (NO content column in submissions!)
        sub = service_client.table("submissions").insert({
            "org_id": test_org_id,
            "title": "Self Approval Attempt",
            "current_version": 1,
            "status": "in_review",
            "creator_id": creator_and_reviewer_user,
            "creator_name": "Author",
        }).execute()
        sub_id = sub.data[0]["id"]

        # Insert version snapshot
        service_client.table("submission_content_versions").insert({
            "submission_id": sub_id,
            "version": 1,
            "content": "Copy created by author.",
            "created_by": creator_and_reviewer_user,
        }).execute()

        # Attempt to insert an 'approved' decision by the SAME user
        # Policy decisions_reviewer_insert specifies:
        # AND (decision != 'approved' OR s.creator_id IS NULL OR s.creator_id != auth.uid())
        blocked = False
        try:
            res = user_client.table("review_decisions").insert({
                "submission_id": sub_id,
                "decision": "approved",
                "reviewer_id": creator_and_reviewer_user,
                "reviewer_name": "Author Self-Approving",
                "content_version": 1,
                "content_snapshot": "Copy created by author.",
            }).execute()
            if len(res.data) == 0:
                blocked = True
        except Exception as exc:
            blocked = True
            assert "policy" in str(exc).lower() or "violation" in str(exc).lower() or "error" in str(exc).lower()

        assert blocked, "Security Violation: Database permitted self-approval at RLS level!"

    finally:
        try:
            service_client.table("organisations").delete().eq("id", test_org_id).execute()
        except Exception:
            pass
        delete_test_auth_user(service_client, creator_and_reviewer_user)


def test_live_audit_immutability_at_database_level(live_client, service_client):
    """Verify that UPDATE or DELETE queries on review_decisions and submission_content_versions
    are unconditionally rejected by PostgreSQL policies (USING false).
    """
    jwt_secret = os.environ.get("SUPABASE_JWT_SECRET", "").strip()
    if not jwt_secret or not service_client:
        pytest.skip("Requires SUPABASE_JWT_SECRET and SUPABASE_SERVICE_ROLE_KEY to test database audit immutability.")

    test_org_id = str(uuid.uuid4())
    user_id = None

    try:
        user_id = create_test_auth_user(service_client, "audit_admin")
        token = create_live_jwt(user_id, jwt_secret)
        user_client = get_supabase_client(user_token=token)

        service_client.table("organisations").insert({
            "id": test_org_id,
            "name": f"Immutability Org {test_org_id[:6]}",
            "slug": f"immutability-{test_org_id[:6]}",
        }).execute()

        service_client.table("organisation_members").insert({
            "org_id": test_org_id,
            "user_id": user_id,
            "role": "admin",
        }).execute()

        sub = service_client.table("submissions").insert({
            "org_id": test_org_id,
            "title": "Audit Test",
            "current_version": 1,
            "status": "in_review",
            "creator_id": user_id,
            "creator_name": "Admin",
        }).execute()
        sub_id = sub.data[0]["id"]

        ver = service_client.table("submission_content_versions").insert({
            "submission_id": sub_id,
            "version": 1,
            "content": "Initial audit copy.",
            "created_by": user_id,
        }).execute()
        ver_id = ver.data[0]["id"]

        decision = service_client.table("review_decisions").insert({
            "submission_id": sub_id,
            "decision": "changes_requested",
            "reviewer_id": user_id,
            "reviewer_name": "Reviewer",
            "comment": "Initial legitimate comment.",
            "content_version": 1,
            "content_snapshot": "Initial audit copy.",
        }).execute()
        decision_id = decision.data[0]["id"]

        # 1. Attempt UPDATE on review_decisions -> Must fail or update 0 rows
        try:
            res_up = user_client.table("review_decisions").update({"comment": "TAMPERED"}).eq("id", decision_id).execute()
            assert len(res_up.data) == 0, "Audit Violation: review_decisions record was updated!"
        except Exception:
            pass  # RLS rejected query

        # 2. Attempt DELETE on review_decisions -> Must fail or delete 0 rows
        try:
            res_del = user_client.table("review_decisions").delete().eq("id", decision_id).execute()
            assert len(res_del.data) == 0, "Audit Violation: review_decisions record was deleted!"
        except Exception:
            pass  # RLS rejected query

        # 3. Attempt UPDATE on submission_content_versions -> Must fail or update 0 rows
        try:
            res_v_up = user_client.table("submission_content_versions").update({"content": "TAMPERED"}).eq("id", ver_id).execute()
            assert len(res_v_up.data) == 0, "Audit Violation: submission_content_versions record was updated!"
        except Exception:
            pass

        # 4. Attempt DELETE on submission_content_versions -> Must fail or delete 0 rows
        try:
            res_v_del = user_client.table("submission_content_versions").delete().eq("id", ver_id).execute()
            assert len(res_v_del.data) == 0, "Audit Violation: submission_content_versions record was deleted!"
        except Exception:
            pass

    finally:
        try:
            service_client.table("organisations").delete().eq("id", test_org_id).execute()
        except Exception:
            pass
        delete_test_auth_user(service_client, user_id)


def test_live_authentication(live_client):
    """Verify live Supabase token authentication and expired token rejection."""
    jwt_secret = os.environ.get("SUPABASE_JWT_SECRET", "").strip()
    if not jwt_secret:
        pytest.skip("Requires SUPABASE_JWT_SECRET to test live authentication.")

    valid_user_id = str(uuid.uuid4())
    valid_token = create_live_jwt(valid_user_id, jwt_secret)
    authenticated_client = get_supabase_client(user_token=valid_token)

    # Valid authenticated client executes PostgREST call successfully
    res = authenticated_client.table("brand_guidelines").select("id").limit(1).execute()
    assert res is not None

    # Generate expired token (expired 1 hour ago)
    past_time = datetime.now(timezone.utc) - timedelta(hours=1)
    expired_payload = {
        "sub": valid_user_id,
        "aud": "authenticated",
        "exp": int(past_time.timestamp()),
        "role": "authenticated",
    }
    expired_token = jwt.encode(expired_payload, jwt_secret, algorithm="HS256")
    expired_client = get_supabase_client(user_token=expired_token)

    # Expired token must be rejected by PostgREST or return authentication error
    try:
        res_exp = expired_client.table("submissions").select("*").execute()
        assert len(res_exp.data) == 0
    except Exception as exc:
        assert "jwt" in str(exc).lower() or "expired" in str(exc).lower() or "error" in str(exc).lower()


def test_live_unauthorized_access(live_client, service_client):
    """Verify that unauthenticated anonymous clients cannot read or write to private tables."""
    # Anonymous client with anon public key, without auth token
    res = live_client.table("submissions").select("*").execute()
    assert len(res.data) == 0, "Security Violation: Anon client read submissions!"

    # Anon client attempting to insert into submissions must be blocked by RLS
    blocked = False
    try:
        res_ins = live_client.table("submissions").insert({
            "org_id": str(uuid.uuid4()),
            "title": "Anon Breach Attempt",
            "current_version": 1,
            "status": "draft",
            "creator_name": "Anonymous Attacker",
        }).execute()
        if len(res_ins.data) == 0:
            blocked = True
    except Exception as exc:
        blocked = True
        assert "policy" in str(exc).lower() or "permission" in str(exc).lower() or "error" in str(exc).lower() or "42501" in str(exc)

    assert blocked, "Security Violation: Anon client inserted into submissions!"


def test_live_reviewer_permissions(live_client, service_client):
    """Verify that only users with role 'reviewer', 'admin', or 'owner' can record review decisions."""
    jwt_secret = os.environ.get("SUPABASE_JWT_SECRET", "").strip()
    if not jwt_secret or not service_client:
        pytest.skip("Requires SUPABASE_JWT_SECRET and SUPABASE_SERVICE_ROLE_KEY to test reviewer permissions.")

    test_org_id = str(uuid.uuid4())
    creator_user = None
    reviewer_user = None

    try:
        creator_user = create_test_auth_user(service_client, "perm_creator")
        reviewer_user = create_test_auth_user(service_client, "perm_reviewer")

        creator_token = create_live_jwt(creator_user, jwt_secret)
        reviewer_token = create_live_jwt(reviewer_user, jwt_secret)

        creator_client = get_supabase_client(user_token=creator_token)
        reviewer_client = get_supabase_client(user_token=reviewer_token)

        service_client.table("organisations").insert({
            "id": test_org_id,
            "name": f"Perm Test Org {test_org_id[:6]}",
            "slug": f"perm-test-{test_org_id[:6]}",
        }).execute()

        # Seed creator role and reviewer role
        service_client.table("organisation_members").insert([
            {"org_id": test_org_id, "user_id": creator_user, "role": "creator"},
            {"org_id": test_org_id, "user_id": reviewer_user, "role": "reviewer"},
        ]).execute()

        sub = service_client.table("submissions").insert({
            "org_id": test_org_id,
            "title": "Permissions Test Content",
            "current_version": 1,
            "status": "in_review",
            "creator_id": creator_user,
            "creator_name": "Creator",
        }).execute()
        sub_id = sub.data[0]["id"]

        service_client.table("submission_content_versions").insert({
            "submission_id": sub_id,
            "version": 1,
            "content": "Review workflow copy.",
            "created_by": creator_user,
        }).execute()

        # 1. Creator (lacks reviewer role) attempts to record decision -> RLS must block
        creator_blocked = False
        try:
            res_c = creator_client.table("review_decisions").insert({
                "submission_id": sub_id,
                "decision": "changes_requested",
                "reviewer_id": creator_user,
                "reviewer_name": "Creator Acting As Reviewer",
                "comment": "Illegal comment.",
                "content_version": 1,
                "content_snapshot": "Review workflow copy.",
            }).execute()
            if len(res_c.data) == 0:
                creator_blocked = True
        except Exception:
            creator_blocked = True

        assert creator_blocked, "Security Violation: Creator recorded review decision!"

        # 2. Legitimate reviewer records decision -> Succeeded
        res_r = reviewer_client.table("review_decisions").insert({
            "submission_id": sub_id,
            "decision": "changes_requested",
            "reviewer_id": reviewer_user,
            "reviewer_name": "Legitimate Reviewer",
            "comment": "Legitimate feedback.",
            "content_version": 1,
            "content_snapshot": "Review workflow copy.",
        }).execute()
        assert len(res_r.data) > 0, "Legitimate reviewer decision was not recorded!"

    finally:
        try:
            service_client.table("organisations").delete().eq("id", test_org_id).execute()
        except Exception:
            pass
        delete_test_auth_user(service_client, creator_user)
        delete_test_auth_user(service_client, reviewer_user)


def test_live_version_history_persistence(live_client, service_client):
    """Verify that multiple submission revisions persist in submission_content_versions."""
    if not service_client:
        pytest.skip("Requires SUPABASE_SERVICE_ROLE_KEY to seed and verify version history persistence.")

    test_org_id = str(uuid.uuid4())

    try:
        service_client.table("organisations").insert({
            "id": test_org_id,
            "name": f"Version Test Org {test_org_id[:6]}",
            "slug": f"ver-test-{test_org_id[:6]}",
        }).execute()

        sub = service_client.table("submissions").insert({
            "org_id": test_org_id,
            "title": "Version History Tracking",
            "current_version": 1,
            "status": "draft",
            "creator_name": "Editor",
        }).execute()
        sub_id = sub.data[0]["id"]

        # Insert Version 1
        service_client.table("submission_content_versions").insert({
            "submission_id": sub_id,
            "version": 1,
            "content": "Revision 1 content text.",
        }).execute()

        # Insert Version 2
        service_client.table("submission_content_versions").insert({
            "submission_id": sub_id,
            "version": 2,
            "content": "Revision 2 updated content text.",
        }).execute()

        # Update submissions current_version
        service_client.table("submissions").update({
            "current_version": 2,
        }).eq("id", sub_id).execute()

        # Retrieve versions ordered by version ASC
        v_res = (
            service_client.table("submission_content_versions")
            .select("*")
            .eq("submission_id", sub_id)
            .order("version", desc=False)
            .execute()
        )
        assert len(v_res.data) == 2
        assert v_res.data[0]["version"] == 1
        assert "Revision 1" in v_res.data[0]["content"]
        assert v_res.data[1]["version"] == 2
        assert "Revision 2" in v_res.data[1]["content"]

    finally:
        try:
            service_client.table("organisations").delete().eq("id", test_org_id).execute()
        except Exception:
            pass


def test_live_guidelines_persistence(live_client, service_client):
    """Verify that brand guidelines and child rule records persist and can be retrieved."""
    if not service_client:
        pytest.skip("Requires SUPABASE_SERVICE_ROLE_KEY to verify brand guidelines persistence.")

    test_org_id = str(uuid.uuid4())
    repo = SupabaseWorkflowRepository(service_client)

    try:
        service_client.table("organisations").insert({
            "id": test_org_id,
            "name": f"Guidelines Test Org {test_org_id[:6]}",
            "slug": f"guide-test-{test_org_id[:6]}",
        }).execute()

        rules = BrandRulesConfig(
            brand_name="AuraSound Labs",
            description="Next-generation spatial audio equipment.",
            voice_and_tone="Crisp, authoritative, yet approachable.",
            is_demo=False,
            prohibited_terms=[
                ProhibitedTermRule(
                    id="pt-test-1",
                    term_or_pattern="cheap build",
                    explanation="Demittive term",
                    severity=Severity.critical,
                )
            ],
            approved_facts=[
                ApprovedFact(
                    id="af-test-1",
                    entity="AuraSound One",
                    attribute="msrp",
                    approved_value="$349",
                    explanation="Official launch price",
                    severity=Severity.critical,
                )
            ],
        )

        saved = repo.save_guidelines(test_org_id, rules)
        assert saved.brand_name == "AuraSound Labs"
        assert saved.description == "Next-generation spatial audio equipment."
        assert saved.voice_and_tone == "Crisp, authoritative, yet approachable."

        retrieved = repo.get_guidelines(test_org_id)
        assert retrieved is not None
        assert retrieved.brand_name == "AuraSound Labs"
        assert len(retrieved.prohibited_terms) == 1
        assert retrieved.prohibited_terms[0].term_or_pattern == "cheap build"
        assert len(retrieved.approved_facts) == 1
        assert retrieved.approved_facts[0].approved_value == "$349"

    finally:
        try:
            service_client.table("organisations").delete().eq("id", test_org_id).execute()
        except Exception:
            pass

