import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.models.workflow import ReviewStatus, DecisionType

client = TestClient(app)


def test_create_and_fetch_submission():
    """New submissions must initialize in 'draft' state at version 1."""
    payload = {
        "title": "Spring Promo Ad",
        "content": "Experience the NovaSound Apex Wireless at $299 with 40 hours battery life.",
        "creator_name": "Jordan Lee (Demo Creator)",
        "is_demo_creator": True
    }
    create_res = client.post("/api/submissions", json=payload)
    assert create_res.status_code == 201
    sub = create_res.json()
    assert sub["status"] == ReviewStatus.draft.value
    assert sub["version"] == 1
    assert sub["title"] == "Spring Promo Ad"
    assert sub["latest_review_response"]["is_compliant"] is True
    assert sub["decision_history"] == []

    # Fetch by ID
    get_res = client.get(f"/api/submissions/{sub['id']}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == sub["id"]


def test_submit_for_review_transition():
    """Submitting draft content transitions status to 'in_review' and locks a snapshot."""
    create_res = client.post("/api/submissions", json={
        "title": "Launch Copy",
        "content": "These cheap headphones cost $199."
    })
    sub_id = create_res.json()["id"]

    submit_res = client.post(f"/api/submissions/{sub_id}/submit")
    assert submit_res.status_code == 200
    sub = submit_res.json()
    assert sub["status"] == ReviewStatus.in_review.value
    assert sub["submitted_at"] is not None
    assert sub["submitted_content_snapshot"] == "These cheap headphones cost $199."


def test_reviewer_approval_workflow():
    """Reviewer approves content in review, recording decision, timestamp, and version snapshot."""
    create_res = client.post("/api/submissions", json={
        "title": "Compliant Earphones Copy",
        "content": "NovaSound Apex Wireless delivers 40 hours of playback at $299."
    })
    sub_id = create_res.json()["id"]

    # Submit for review
    client.post(f"/api/submissions/{sub_id}/submit")

    # Record approval
    decision_payload = {
        "decision": DecisionType.approved.value,
        "reviewer_name": "Alex Morgan (Demo Brand Guardian)",
        "is_demo_reviewer": True,
        "comment": "All certified specs and brand guidelines verified."
    }
    dec_res = client.post(f"/api/submissions/{sub_id}/decision", json=decision_payload)
    assert dec_res.status_code == 200
    sub = dec_res.json()
    assert sub["status"] == ReviewStatus.approved.value
    assert len(sub["decision_history"]) == 1

    rec = sub["decision_history"][0]
    assert rec["decision"] == DecisionType.approved.value
    assert rec["reviewer_name"] == "Alex Morgan (Demo Brand Guardian)"
    assert rec["is_demo_reviewer"] is True
    assert rec["content_version"] == 1
    assert "NovaSound Apex Wireless" in rec["content_snapshot"]


def test_reviewer_request_changes_workflow():
    """Reviewer requests revisions with mandatory comment, transitioning state to 'changes_requested'."""
    create_res = client.post("/api/submissions", json={
        "title": "Ad Copy v1",
        "content": "These cheap headphones are great."
    })
    sub_id = create_res.json()["id"]
    client.post(f"/api/submissions/{sub_id}/submit")

    # Request changes
    decision_payload = {
        "decision": DecisionType.changes_requested.value,
        "reviewer_name": "Alex Morgan (Demo Brand Guardian)",
        "comment": "Replace 'cheap headphones' with 'accessible high-fidelity audio' as per brand guidelines."
    }
    dec_res = client.post(f"/api/submissions/{sub_id}/decision", json=decision_payload)
    assert dec_res.status_code == 200
    sub = dec_res.json()
    assert sub["status"] == ReviewStatus.changes_requested.value
    assert len(sub["decision_history"]) == 1
    assert "cheap headphones" in sub["decision_history"][0]["comment"]


def test_reviewer_rejection_workflow():
    """Reviewer rejects content with mandatory comment, transitioning state to 'rejected'."""
    create_res = client.post("/api/submissions", json={
        "title": "Defamatory Ad Copy",
        "content": "Our headphones kill the competition."
    })
    sub_id = create_res.json()["id"]
    client.post(f"/api/submissions/{sub_id}/submit")

    decision_payload = {
        "decision": DecisionType.rejected.value,
        "reviewer_name": "Alex Morgan (Demo Brand Guardian)",
        "comment": "Aggressive competitive attack violates corporate advertising policy."
    }
    dec_res = client.post(f"/api/submissions/{sub_id}/decision", json=decision_payload)
    assert dec_res.status_code == 200
    sub = dec_res.json()
    assert sub["status"] == ReviewStatus.rejected.value
    assert sub["decision_history"][0]["decision"] == DecisionType.rejected.value


def test_mandatory_comment_validation():
    """Comments are strictly required when requesting changes or rejecting content."""
    create_res = client.post("/api/submissions", json={
        "title": "Test Copy",
        "content": "Unverified claims here."
    })
    sub_id = create_res.json()["id"]
    client.post(f"/api/submissions/{sub_id}/submit")

    # 1. Changes requested without comment -> 422
    res_empty_comment = client.post(f"/api/submissions/{sub_id}/decision", json={
        "decision": DecisionType.changes_requested.value,
        "comment": ""
    })
    assert res_empty_comment.status_code == 422

    # 2. Reject with whitespace only comment -> 422
    res_ws_comment = client.post(f"/api/submissions/{sub_id}/decision", json={
        "decision": DecisionType.rejected.value,
        "comment": "   \n\t   "
    })
    assert res_ws_comment.status_code == 422


def test_content_change_after_approval_invalidates_approval():
    """CRITICAL RULE: Old approval must NOT carry over after content changes. Resets to draft and increments version."""
    create_res = client.post("/api/submissions", json={
        "title": "Approved Copy",
        "content": "NovaSound Apex Wireless is $299."
    })
    sub_id = create_res.json()["id"]

    # Submit and Approve
    client.post(f"/api/submissions/{sub_id}/submit")
    client.post(f"/api/submissions/{sub_id}/decision", json={
        "decision": DecisionType.approved.value,
        "comment": "Approved initial version."
    })

    approved_sub = client.get(f"/api/submissions/{sub_id}").json()
    assert approved_sub["status"] == ReviewStatus.approved.value
    assert approved_sub["version"] == 1

    # Creator modifies content post-approval
    update_res = client.put(f"/api/submissions/{sub_id}", json={
        "content": "NovaSound Apex Wireless is $299 and comes with cheap headphones."
    })
    assert update_res.status_code == 200
    updated_sub = update_res.json()

    # Status MUST reset to draft and version must increment
    assert updated_sub["status"] == ReviewStatus.draft.value
    assert updated_sub["version"] == 2
    assert updated_sub["submitted_content_snapshot"] is None
    # Findings must re-run immediately
    assert updated_sub["latest_review_response"]["is_compliant"] is False


def test_invalid_state_transitions():
    """State machine prevents illegal transitions."""
    create_res = client.post("/api/submissions", json={
        "title": "State Test",
        "content": "Draft content."
    })
    sub_id = create_res.json()["id"]

    # 1. Cannot decide on a draft submission (must be in_review)
    dec_on_draft = client.post(f"/api/submissions/{sub_id}/decision", json={
        "decision": DecisionType.approved.value
    })
    assert dec_on_draft.status_code == 400

    # 2. Submit to in_review
    client.post(f"/api/submissions/{sub_id}/submit")

    # 3. Cannot submit again when already in_review
    re_submit = client.post(f"/api/submissions/{sub_id}/submit")
    assert re_submit.status_code == 400

    # 4. Approve
    client.post(f"/api/submissions/{sub_id}/decision", json={
        "decision": DecisionType.approved.value
    })

    # 5. Cannot decide on already approved submission without re-submission
    dec_on_approved = client.post(f"/api/submissions/{sub_id}/decision", json={
        "decision": DecisionType.rejected.value,
        "comment": "Should not work without in_review"
    })
    assert dec_on_approved.status_code == 400


def test_high_severity_findings_remain_visible():
    """CRITICAL RULE: High-severity findings remain clearly visible during review."""
    create_res = client.post("/api/submissions", json={
        "title": "Dirty Copy",
        "content": "These cheap headphones cost $199 with unbreakable build."
    })
    sub_id = create_res.json()["id"]
    submit_res = client.post(f"/api/submissions/{sub_id}/submit")
    sub = submit_res.json()

    assert sub["status"] == ReviewStatus.in_review.value
    assert sub["latest_review_response"]["is_compliant"] is False
    assert sub["latest_review_response"]["findings_by_severity"]["critical"] >= 2
    assert len(sub["latest_review_response"]["findings"]) >= 2
