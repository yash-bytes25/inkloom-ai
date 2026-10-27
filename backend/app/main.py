import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load backend/.env when running server or interactive scripts
if "pytest" not in sys.modules and not os.environ.get("PYTEST_CURRENT_TEST"):
    _env_path = Path(__file__).resolve().parent.parent / ".env"
    if _env_path.exists():
        load_dotenv(dotenv_path=_env_path)

from typing import List, Optional
from pydantic import BaseModel
from fastapi import FastAPI, Depends, Header, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .models.rules import ReviewRequest, ReviewResponse, BrandRulesConfig
from .models.workflow import (
    Submission,
    SubmissionCreate,
    SubmissionUpdate,
    SubmitForReviewRequest,
    DecisionRequest,
    RevisionDiffResponse,
)
from .engine.evaluator import run_deterministic_review
from .engine.gemini_evaluator import run_combined_review
from .engine.demo_data import DEMO_BRAND_RULES
from .engine.workflow_service import workflow_service
from .engine.diff_service import diff_service
from .engine.supabase_client import is_supabase_configured, get_supabase_client
from .engine.rate_limiter import ai_audit_limiter, decision_limiter

app = FastAPI(
    title="Inkloom AI Backend",
    description="Deterministic brand-governance evaluation, Gemini AI contextual audit, and human review workflow API",
    version="0.3.0"
)

# Allow requests from frontend dev servers and configured deployment origins
allowed_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
env_origins = os.environ.get("ALLOWED_ORIGINS", "").strip()
if env_origins:
    allowed_origins.extend([origin.strip() for origin in env_origins.split(",") if origin.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


from .engine.auth import get_auth_context, is_production


from .engine.rules_service import rules_service

@app.get("/")
def read_root():
    return {
        "name": "Inkloom AI API",
        "version": "0.3.0",
        "docs": "/docs",
        "storage": "supabase_persistent" if is_supabase_configured() else "local_demo",
        "endpoints": {
            "health": "/api/health",
            "guidelines": "/api/guidelines",
            "demo_rules": "/api/demo-rules",
            "review": "/api/review",
            "submissions": "/api/submissions"
        }
    }


@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "service": "inkloom-backend",
        "version": "0.3.0",
        "storage_mode": "supabase_persistent" if is_supabase_configured() else "local_demo",
    }


class LoginRequest(BaseModel):
    email: str
    password: str


@app.post("/api/auth/login")
def login(req: LoginRequest):
    """Authenticate user with Supabase Auth (persistent mode) or demo persona (local demo mode)."""
    if is_supabase_configured():
        client = get_supabase_client()
        if not client:
            raise HTTPException(status_code=503, detail="Supabase client initialization failed.")
        try:
            auth_res = client.auth.sign_in_with_password({"email": req.email, "password": req.password})
            if not auth_res or not getattr(auth_res, "session", None):
                raise HTTPException(status_code=401, detail="Invalid email or password.")
            return {
                "access_token": auth_res.session.access_token,
                "refresh_token": getattr(auth_res.session, "refresh_token", None),
                "expires_at": getattr(auth_res.session, "expires_at", None),
                "user": {
                    "id": str(auth_res.user.id),
                    "email": auth_res.user.email,
                },
                "is_demo": False,
            }
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=401, detail=f"Authentication failed: {exc}")

    # Local demo mode authentication
    return {
        "access_token": "demo-local-jwt-token",
        "refresh_token": None,
        "expires_at": None,
        "user": {
            "id": "demo-local-user",
            "email": req.email or "jordan.lee@novasound.example",
        },
        "is_demo": True,
    }


@app.get("/api/auth/me")
def get_current_user_profile(auth: dict = Depends(get_auth_context)):
    """Fetch profile and verified organisation role for current authenticated session."""
    user_id = auth.get("user_id")
    org_id = auth.get("org_id")
    role = None

    if not auth.get("is_demo") and user_id and org_id and is_supabase_configured():
        repo = workflow_service.get_repository(auth.get("token"))
        if repo:
            role = repo.get_user_role_in_org(user_id, org_id)

    return {
        "user_id": user_id,
        "email": auth.get("user_name"),
        "org_id": org_id,
        "role": role or ("reviewer" if auth.get("is_demo") else None),
        "is_demo": auth.get("is_demo", False),
    }


@app.get("/api/guidelines", response_model=BrandRulesConfig)
def get_brand_guidelines(
    org_id: Optional[str] = Query(default=None),
    auth: dict = Depends(get_auth_context),
):
    """Retrieve active brand guidelines (persisted in Supabase or local demo rules)."""
    target_org = org_id or auth.get("org_id")
    return workflow_service.get_guidelines(
        org_id=target_org,
        user_id=auth.get("user_id"),
        token=auth.get("token"),
    )


@app.put("/api/guidelines", response_model=BrandRulesConfig)
def update_brand_guidelines(
    rules: BrandRulesConfig,
    org_id: Optional[str] = Query(default=None),
    auth: dict = Depends(get_auth_context),
):
    """Update active brand guidelines with newly configured rules and voice & tone guidance."""
    target_org = org_id or auth.get("org_id")
    return workflow_service.save_guidelines(
        rules=rules,
        org_id=target_org,
        user_id=auth.get("user_id"),
        token=auth.get("token"),
    )


@app.post("/api/guidelines/reset", response_model=BrandRulesConfig)
def reset_brand_guidelines(
    org_id: Optional[str] = Query(default=None),
    auth: dict = Depends(get_auth_context),
):
    """Restore the original pristine NovaSound Audio demo configuration."""
    target_org = org_id or auth.get("org_id")
    return workflow_service.reset_guidelines(
        org_id=target_org,
        user_id=auth.get("user_id"),
        token=auth.get("token"),
    )


@app.get("/api/demo-rules", response_model=BrandRulesConfig)
def get_demo_rules():
    """Retrieve sample brand rules for the fictional demo brand (NovaSound Audio)."""
    return DEMO_BRAND_RULES


@app.post("/api/review", response_model=ReviewResponse)
def review_content(
    request: ReviewRequest,
    auth: dict = Depends(get_auth_context),
):
    """Evaluate submitted content against configured brand rules or active brand guidelines.
    If request.include_ai is True, executes combined deterministic and Gemini AI contextual analysis.
    """
    effective_rules = request.rules
    if not effective_rules:
        effective_rules = workflow_service.get_guidelines(
            org_id=auth.get("org_id"),
            user_id=auth.get("user_id"),
            token=auth.get("token"),
        )

    if request.include_ai:
        ai_audit_limiter.check("public-review")
        return run_combined_review(text=request.text, rules=effective_rules, include_ai=True)
    return run_deterministic_review(text=request.text, rules=effective_rules)


# ==========================================
# Workflow & Human Decision Lifecycle API
# ==========================================

@app.get("/api/submissions", response_model=List[Submission])
def list_submissions(
    org_id: Optional[str] = Query(default=None),
    auth: dict = Depends(get_auth_context),
):
    """List content submissions for active organisation or local demo data."""
    target_org = org_id or auth.get("org_id")
    return workflow_service.list_submissions(
        org_id=target_org,
        user_id=auth.get("user_id"),
        token=auth.get("token"),
    )


@app.post("/api/submissions", response_model=Submission, status_code=201)
def create_submission(
    request: SubmissionCreate,
    auth: dict = Depends(get_auth_context),
):
    """Create a new content submission starting in 'draft' status."""
    creator_id = "demo-creator-jordan" if auth.get("is_demo") else auth.get("user_id")
    return workflow_service.create_submission(
        data=request,
        org_id=request.org_id or auth.get("org_id"),
        user_id=creator_id,
        token=auth.get("token"),
    )


@app.get("/api/submissions/{sub_id}", response_model=Submission)
def get_submission(
    sub_id: str,
    auth: dict = Depends(get_auth_context),
):
    """Fetch details, current state, snapshots, and decision history for a submission."""
    return workflow_service.get_submission(
        sub_id=sub_id,
        org_id=auth.get("org_id"),
        user_id=auth.get("user_id"),
        token=auth.get("token"),
    )


@app.put("/api/submissions/{sub_id}", response_model=Submission)
def update_submission(
    sub_id: str,
    request: SubmissionUpdate,
    auth: dict = Depends(get_auth_context),
):
    """Update content of a submission. Resets workflow to 'draft' if content changes."""
    user_id = "demo-creator-jordan" if auth.get("is_demo") else auth.get("user_id")
    return workflow_service.update_submission(
        sub_id=sub_id,
        data=request,
        org_id=auth.get("org_id"),
        user_id=user_id,
        token=auth.get("token"),
    )


@app.post("/api/submissions/{sub_id}/submit", response_model=Submission)
def submit_for_review(
    sub_id: str,
    request: Optional[SubmitForReviewRequest] = None,
    auth: dict = Depends(get_auth_context),
):
    """Creator submits draft content for reviewer approval (transitions to 'in_review')."""
    user_id = "demo-creator-jordan" if auth.get("is_demo") else auth.get("user_id")
    return workflow_service.submit_for_review(
        sub_id=sub_id,
        req=request,
        org_id=auth.get("org_id"),
        user_id=user_id,
        token=auth.get("token"),
    )


@app.post("/api/submissions/{sub_id}/ai-audit", response_model=Submission)
def audit_submission_with_ai(
    sub_id: str,
    auth: dict = Depends(get_auth_context),
):
    """Run combined deterministic and Gemini AI contextual analysis on a submission."""
    limiter_key = auth.get("user_id") or "demo-user"
    ai_audit_limiter.check(limiter_key)
    sub = workflow_service.get_submission(
        sub_id=sub_id,
        org_id=auth.get("org_id"),
        user_id=auth.get("user_id"),
        token=auth.get("token"),
    )
    sub.latest_review_response = run_combined_review(text=sub.content, include_ai=True)
    return sub


@app.post("/api/submissions/{sub_id}/decision", response_model=Submission)
def record_decision(
    sub_id: str,
    request: DecisionRequest,
    auth: dict = Depends(get_auth_context),
):
    """Reviewer records approval, requested changes, or rejection on submitted content."""
    limiter_key = auth.get("user_id") or request.reviewer_name
    decision_limiter.check(limiter_key)
    reviewer_id = (
        ("demo-reviewer-alex" if request.is_demo_reviewer else "demo-reviewer-generic")
        if auth.get("is_demo")
        else auth.get("user_id")
    )
    return workflow_service.record_decision(
        sub_id=sub_id,
        req=request,
        org_id=auth.get("org_id"),
        reviewer_id=reviewer_id,
        user_role=auth.get("user_role") if auth.get("is_demo") else None,
        token=auth.get("token"),
    )


@app.get("/api/submissions/{sub_id}/diff", response_model=RevisionDiffResponse)
def get_submission_diff(
    sub_id: str,
    orig: Optional[int] = Query(None, description="Original/base version number"),
    newer: Optional[int] = Query(None, description="Newer/comparison version number"),
    auth: dict = Depends(get_auth_context),
):
    """Compare two content versions of a submission with detailed side-by-side text diff,
    statistical changes, and governance finding resolution comparison.
    """
    sub = workflow_service.get_submission(
        sub_id=sub_id,
        org_id=auth.get("org_id"),
        user_id=auth.get("user_id"),
        token=auth.get("token"),
    )
    target_newer = newer if newer is not None else sub.version
    target_orig = orig if orig is not None else (max(1, target_newer - 1) if target_newer > 1 else 1)

    return diff_service.build_revision_diff(sub, target_orig, target_newer)

