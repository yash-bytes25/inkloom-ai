import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.engine.evaluator import run_deterministic_review
from backend.app.engine.demo_data import DEMO_BRAND_RULES
from backend.app.models.rules import (
    FindingCategory,
    Severity,
    EvidenceStatus,
    BrandRulesConfig,
    ProhibitedTermRule,
)

client = TestClient(app)


def test_empty_input():
    """Empty or whitespace input must return zero findings and compliant status."""
    res_empty = run_deterministic_review("")
    assert res_empty.total_findings == 0
    assert res_empty.is_compliant is True
    assert res_empty.text_length == 0

    res_whitespace = run_deterministic_review("   \n\t   ")
    assert res_whitespace.total_findings == 0
    assert res_whitespace.is_compliant is True


def test_compliant_text():
    """Text adhering strictly to brand guidelines produces no warnings or critical violations."""
    compliant_copy = (
        "Experience the NovaSound Apex Wireless with our patented Active Acoustic Isolation™. "
        "At $299, it delivers 40 hours of continuous high-fidelity sound."
    )
    result = run_deterministic_review(compliant_copy, DEMO_BRAND_RULES)
    assert result.is_compliant is True
    assert result.findings_by_severity[Severity.critical.value] == 0
    assert result.findings_by_severity[Severity.warning.value] == 0


def test_prohibited_terminology():
    """Prohibited terms must be flagged as critical violations with suggested replacements."""
    text = "These cheap headphones are virtually unbreakable and our design kills the competition."
    result = run_deterministic_review(text, DEMO_BRAND_RULES)

    prohib_findings = [
        f for f in result.findings
        if f.category == FindingCategory.prohibited_terminology
    ]
    assert len(prohib_findings) == 3

    # Verify "cheap headphones"
    f_cheap = next(f for f in prohib_findings if "cheap headphones" in f.matched_text.lower())
    assert f_cheap.severity == Severity.critical
    assert f_cheap.evidence_status == EvidenceStatus.confirmed_violation
    assert f_cheap.suggested_correction == "accessible high-fidelity audio"

    # Verify "unbreakable"
    f_unbr = next(f for f in prohib_findings if "unbreakable" in f.matched_text.lower())
    assert f_unbr.severity == Severity.critical
    assert f_unbr.evidence_status == EvidenceStatus.confirmed_violation

    assert result.is_compliant is False


def test_incorrect_approved_facts():
    """Contradictions with certified facts must be flagged with the exact approved value."""
    # Price contradiction: $199 instead of approved $299
    text_price = "Get the NovaSound Apex Wireless today for an exclusive price of $199 with 40 hours runtime."
    res_price = run_deterministic_review(text_price, DEMO_BRAND_RULES)
    fact_findings = [f for f in res_price.findings if f.category == FindingCategory.fact_accuracy]
    assert len(fact_findings) == 1
    assert fact_findings[0].matched_text == "$199"
    assert fact_findings[0].suggested_correction == "$299"
    assert fact_findings[0].severity == Severity.critical
    assert fact_findings[0].evidence_status == EvidenceStatus.confirmed_violation

    # Water resistance contradiction: IPX8 / 100% waterproof instead of approved IPX7
    text_water = "NovaSound Pulse Earphones are 100% waterproof with IPX8 submersion protection."
    res_water = run_deterministic_review(text_water, DEMO_BRAND_RULES)
    water_findings = [f for f in res_water.findings if f.category == FindingCategory.fact_accuracy]
    assert len(water_findings) >= 1
    assert any("IPX7" in f.explanation for f in water_findings)


def test_unmentioned_claim_is_never_claimed_false():
    """CRITICAL RULE: Never claim a statement is false merely because no supporting fact was found."""
    # This text mentions features not defined in approved facts (leather case, rose gold accents).
    # Since they do not contradict any approved fact, they MUST NOT be flagged as violations.
    neutral_copy = (
        "NovaSound Apex Wireless features an Italian leather headband and comes with a sapphire carrying pouch. "
        "It retails at $299 with 40 hours battery life."
    )
    result = run_deterministic_review(neutral_copy, DEMO_BRAND_RULES)
    fact_findings = [f for f in result.findings if f.category == FindingCategory.fact_accuracy]
    # No fact violation should be raised for the leather headband or sapphire pouch
    assert len(fact_findings) == 0
    assert result.is_compliant is True


def test_required_disclaimers():
    """Mandatory disclaimers must be flagged when triggers appear without required disclosure."""
    # Trigger present, disclosure missing
    text_missing = "Our audio products include a lifetime warranty for all registered owners."
    res_missing = run_deterministic_review(text_missing, DEMO_BRAND_RULES)
    disclaimer_findings = [
        f for f in res_missing.findings
        if f.category == FindingCategory.required_disclaimer
    ]
    assert len(disclaimer_findings) == 1
    assert disclaimer_findings[0].severity == Severity.warning
    assert "Limited Lifetime Warranty Terms" in disclaimer_findings[0].suggested_correction

    # Trigger present AND disclosure included -> compliant
    text_with_disclosure = (
        "Our audio products include a lifetime warranty for all registered owners. "
        "*Subject to NovaSound Limited Lifetime Warranty Terms and fair usage policy."
    )
    res_with_disclosure = run_deterministic_review(text_with_disclosure, DEMO_BRAND_RULES)
    disclaimer_findings_resolved = [
        f for f in res_with_disclosure.findings
        if f.category == FindingCategory.required_disclaimer
    ]
    assert len(disclaimer_findings_resolved) == 0


def test_preferred_wording():
    """Preferred brand vocabulary flags colloquial terms and suggests technical equivalents."""
    text = "These earbuds feature cutting-edge noise cancellation."
    result = run_deterministic_review(text, DEMO_BRAND_RULES)

    pref_findings = [
        f for f in result.findings
        if f.category == FindingCategory.preferred_wording
    ]
    assert len(pref_findings) == 2
    terms_avoided = [f.matched_text.lower() for f in pref_findings]
    assert "earbuds" in terms_avoided
    assert "noise cancellation" in terms_avoided


def test_multiple_findings():
    """Multi-issue text produces ordered, multi-category findings with sequential IDs."""
    dirty_text = (
        "Our cheap headphones and earbuds feature a lifetime warranty. "
        "The NovaSound Apex Wireless costs $199 and will prevent hearing loss."
    )
    result = run_deterministic_review(dirty_text, DEMO_BRAND_RULES)

    assert result.total_findings >= 4
    categories = {f.category for f in result.findings}
    assert FindingCategory.prohibited_terminology in categories
    assert FindingCategory.preferred_wording in categories
    assert FindingCategory.fact_accuracy in categories
    assert FindingCategory.required_disclaimer in categories

    # Verify ID sequence
    ids = [f.id for f in result.findings]
    assert ids == [f"finding-{i}" for i in range(1, len(ids) + 1)]


def test_fastapi_review_endpoint():
    """POST /api/review returns complete ReviewResponse."""
    payload = {
        "text": "These cheap headphones cost $199.",
        "rules": None  # Will default to demo rules
    }
    response = client.post("/api/review", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "findings" in data
    assert data["total_findings"] >= 1
    assert data["is_compliant"] is False
    assert data["brand_name"] == "NovaSound Audio (Demo Data)"
    assert data["is_demo_data"] is True


def test_fastapi_custom_rules_endpoint():
    """POST /api/review accepts and enforces custom brand rules."""
    custom_rules = BrandRulesConfig(
        brand_name="CustomBrand",
        is_demo=False,
        prohibited_terms=[
            ProhibitedTermRule(
                id="c-01",
                term_or_pattern="subpar",
                explanation="Subpar is unacceptable.",
                severity=Severity.critical,
                suggested_replacement="exceptional"
            )
        ]
    )
    payload = {
        "text": "This widget is subpar.",
        "rules": custom_rules.model_dump()
    }
    response = client.post("/api/review", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["total_findings"] == 1
    assert data["brand_name"] == "CustomBrand"
    assert data["is_demo_data"] is False
    assert data["findings"][0]["suggested_correction"] == "exceptional"


def test_fastapi_demo_rules_endpoint():
    """GET /api/demo-rules returns full sample configuration."""
    response = client.get("/api/demo-rules")
    assert response.status_code == 200
    data = response.json()
    assert data["brand_name"] == "NovaSound Audio (Demo Data)"
    assert data["is_demo"] is True
    assert len(data["prohibited_terms"]) > 0
    assert len(data["approved_facts"]) > 0
