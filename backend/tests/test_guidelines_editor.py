import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.models.rules import (
    BrandRulesConfig,
    ProhibitedTermRule,
    PreferredWordingRule,
    ApprovedFact,
    RequiredDisclaimerRule,
    Severity,
    FindingCategory,
)
from backend.app.engine.rules_service import rules_service
from backend.app.engine.demo_data import DEMO_BRAND_RULES

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_rules():
    """Ensure each test starts and ends with pristine demo brand rules."""
    rules_service.reset_to_demo()
    yield
    rules_service.reset_to_demo()


def test_get_guidelines_defaults_to_demo():
    """GET /api/guidelines returns the default NovaSound Audio demo rules."""
    res = client.get("/api/guidelines")
    assert res.status_code == 200
    data = res.json()
    assert "NovaSound Audio" in data["brand_name"]
    assert data["is_demo"] is True
    assert len(data["prohibited_terms"]) >= 3
    assert len(data["approved_facts"]) >= 3
    assert data.get("voice_and_tone") is not None


def test_update_brand_identity_and_voice():
    """PUT /api/guidelines updates brand name, description, and voice/tone."""
    current = client.get("/api/guidelines").json()
    current["brand_name"] = "Aura Acoustics"
    current["description"] = "Sustainable acoustic monitors engineered for creators."
    current["voice_and_tone"] = "Warm, minimalist, artisanal, and authentic."

    update_res = client.put("/api/guidelines", json=current)
    assert update_res.status_code == 200
    updated = update_res.json()
    assert updated["brand_name"] == "Aura Acoustics"
    assert updated["description"] == "Sustainable acoustic monitors engineered for creators."
    assert updated["voice_and_tone"] == "Warm, minimalist, artisanal, and authentic."
    assert updated["is_demo"] is False


def test_add_prohibited_term_affects_subsequent_reviews():
    """Adding a new prohibited term immediately causes the engine to flag it in subsequent content reviews."""
    current = client.get("/api/guidelines").json()
    current["prohibited_terms"].append({
        "id": "rule-custom-01",
        "term_or_pattern": "cheap plastic",
        "is_regex": False,
        "case_sensitive": False,
        "severity": "critical",
        "explanation": "Never describe our composite casing as cheap plastic.",
        "suggested_replacement": "recycled aerospace polymer",
    })

    put_res = client.put("/api/guidelines", json=current)
    assert put_res.status_code == 200

    # Review copy containing the newly prohibited term without passing explicit rules
    review_res = client.post("/api/review", json={
        "text": "The chassis is made of cheap plastic.",
        "rules": None,
    })
    assert review_res.status_code == 200
    data = review_res.json()
    findings = [f for f in data["findings"] if f["category"] == FindingCategory.prohibited_terminology.value]
    assert len(findings) >= 1
    assert any("cheap plastic" in f["matched_text"].lower() for f in findings)
    assert any("recycled aerospace polymer" == f["suggested_correction"] for f in findings)


def test_add_preferred_wording_rule():
    """Adding a preferred wording rule suggests the approved nomenclature."""
    current = client.get("/api/guidelines").json()
    current["preferred_wording"].append({
        "id": "pref-custom-01",
        "avoid_term": "noise blocker",
        "preferred_term": "SoundShield Isolation",
        "case_sensitive": False,
        "severity": "info",
        "explanation": "Use our trademarked SoundShield Isolation term.",
    })

    client.put("/api/guidelines", json=current)

    review_res = client.post("/api/review", json={
        "text": "Features innovative noise blocker technology.",
        "rules": None,
    })
    data = review_res.json()
    pref_findings = [f for f in data["findings"] if f["category"] == FindingCategory.preferred_wording.value]
    assert len(pref_findings) >= 1
    assert any("noise blocker" in f["matched_text"].lower() for f in pref_findings)
    assert any("SoundShield Isolation" == f["suggested_correction"] for f in pref_findings)


def test_add_approved_fact_and_detect_contradiction():
    """Adding an approved fact identifies explicit contradictory statements."""
    current = client.get("/api/guidelines").json()
    current["approved_facts"].append({
        "id": "fact-custom-01",
        "entity": "Solaris Headset",
        "attribute": "Wireless Range",
        "approved_value": "100 meters",
        "context_keywords": ["range", "distance", "meters", "feet"],
        "conflicting_patterns": [r"\b(?:30|40|50)\s*meters?\b"],
        "severity": "critical",
        "explanation": "Certified range is 100 meters.",
    })

    client.put("/api/guidelines", json=current)

    # Contradicting copy
    review_res = client.post("/api/review", json={
        "text": "Solaris Headset offers a reliable range of 30 meters.",
        "rules": None,
    })
    data = review_res.json()
    fact_findings = [f for f in data["findings"] if f["category"] == FindingCategory.fact_accuracy.value]
    assert len(fact_findings) >= 1
    assert any(f["suggested_correction"] == "100 meters" for f in fact_findings)


def test_add_required_disclaimer():
    """Adding a required disclaimer flags content activating the trigger without disclosure."""
    current = client.get("/api/guidelines").json()
    current["required_disclaimers"].append({
        "id": "disc-custom-01",
        "trigger_pattern": r"\bmoney\s*back\s*guarantee\b",
        "trigger_description": "References money back guarantee",
        "required_disclaimer_text": "*Terms apply. 30-day refund window for unopened products.",
        "case_sensitive": False,
        "severity": "warning",
        "explanation": "Refund promises require standard qualification.",
    })

    client.put("/api/guidelines", json=current)

    review_res = client.post("/api/review", json={
        "text": "Every purchase includes our unconditional money back guarantee.",
        "rules": None,
    })
    data = review_res.json()
    disc_findings = [f for f in data["findings"] if f["category"] == FindingCategory.required_disclaimer.value]
    assert len(disc_findings) >= 1
    assert any("Terms apply" in f["suggested_correction"] for f in disc_findings)


def test_delete_rule_removes_detection():
    """Deleting a rule ensures that term is no longer flagged."""
    current = client.get("/api/guidelines").json()
    # Remove "cheap headphones" from prohibited terms
    current["prohibited_terms"] = [
        r for r in current["prohibited_terms"]
        if "cheap headphones" not in r["term_or_pattern"].lower()
    ]

    client.put("/api/guidelines", json=current)

    review_res = client.post("/api/review", json={
        "text": "These cheap headphones are great.",
        "rules": None,
    })
    data = review_res.json()
    cheap_findings = [
        f for f in data["findings"]
        if f.get("matched_text") and "cheap headphones" in f["matched_text"].lower()
    ]
    assert len(cheap_findings) == 0


def test_validation_rejects_empty_brand_name():
    """Validation rejects empty or whitespace-only brand name with HTTP 422."""
    current = client.get("/api/guidelines").json()
    current["brand_name"] = "    "
    res = client.put("/api/guidelines", json=current)
    assert res.status_code == 422


def test_validation_rejects_empty_prohibited_term():
    """Validation rejects empty prohibited term with HTTP 422."""
    current = client.get("/api/guidelines").json()
    current["prohibited_terms"].append({
        "id": "invalid-rule",
        "term_or_pattern": "   ",
        "explanation": "Cannot be blank",
    })
    res = client.put("/api/guidelines", json=current)
    assert res.status_code == 422


def test_reset_guidelines_restores_novasound_demo():
    """POST /api/guidelines/reset restores pristine NovaSound Audio demo configuration."""
    current = client.get("/api/guidelines").json()
    current["brand_name"] = "Temporary Brand"
    current["prohibited_terms"] = []
    client.put("/api/guidelines", json=current)

    # Verify changed
    modified = client.get("/api/guidelines").json()
    assert modified["brand_name"] == "Temporary Brand"
    assert len(modified["prohibited_terms"]) == 0

    # Reset
    reset_res = client.post("/api/guidelines/reset")
    assert reset_res.status_code == 200
    restored = reset_res.json()
    assert "NovaSound Audio" in restored["brand_name"]
    assert restored["is_demo"] is True
    assert len(restored["prohibited_terms"]) >= 3
