from typing import List
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .models.rules import ReviewRequest, ReviewResponse, BrandRulesConfig
from .models.workflow import (
    Submission,
    SubmissionCreate,
    SubmissionUpdate,
    SubmitForReviewRequest,
    DecisionRequest,
)
from .engine.evaluator import run_deterministic_review
from .engine.demo_data import DEMO_BRAND_RULES
from .engine.workflow_service import workflow_service

app = FastAPI(
    title="Inkloom AI Backend",
    description="Deterministic brand-governance evaluation and human review workflow API",
    version="0.2.0"
)

# Allow requests from frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {
        "name": "Inkloom AI API",
        "version": "0.2.0",
        "docs": "/docs",
        "endpoints": {
            "health": "/api/health",
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
        "version": "0.2.0"
    }


@app.get("/api/demo-rules", response_model=BrandRulesConfig)
def get_demo_rules():
    """Retrieve sample brand rules for the fictional demo brand (NovaSound Audio)."""
    return DEMO_BRAND_RULES


@app.post("/api/review", response_model=ReviewResponse)
def review_content(request: ReviewRequest):
    """Evaluate submitted content against configured brand rules or default demo rules."""
    return run_deterministic_review(text=request.text, rules=request.rules)


# ==========================================
# Workflow & Human Decision Lifecycle API
# ==========================================

@app.get("/api/submissions", response_model=List[Submission])
def list_submissions():
    """List all content submissions and their active review statuses."""
    return workflow_service.list_submissions()


@app.post("/api/submissions", response_model=Submission, status_code=201)
def create_submission(request: SubmissionCreate):
    """Create a new content submission starting in 'draft' status."""
    return workflow_service.create_submission(request)


@app.get("/api/submissions/{sub_id}", response_model=Submission)
def get_submission(sub_id: str):
    """Fetch details, current state, snapshots, and decision history for a submission."""
    return workflow_service.get_submission(sub_id)


@app.put("/api/submissions/{sub_id}", response_model=Submission)
def update_submission(sub_id: str, request: SubmissionUpdate):
    """Update content of a submission. Resets workflow to 'draft' if content changes."""
    return workflow_service.update_submission(sub_id, request)


@app.post("/api/submissions/{sub_id}/submit", response_model=Submission)
def submit_for_review(sub_id: str, request: SubmitForReviewRequest = None):
    """Creator submits draft content for reviewer approval (transitions to 'in_review')."""
    return workflow_service.submit_for_review(sub_id, request)


@app.post("/api/submissions/{sub_id}/decision", response_model=Submission)
def record_decision(sub_id: str, request: DecisionRequest):
    """Reviewer records approval, requested changes, or rejection on submitted content."""
    return workflow_service.record_decision(sub_id, request)
