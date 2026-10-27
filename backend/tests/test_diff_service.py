import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.engine.diff_service import (
    compute_text_diff,
    compute_inline_segments,
    compare_findings,
    diff_service,
)
from backend.app.models.rules import Finding, FindingCategory, Severity, EvidenceStatus
from backend.app.models.workflow import DiffChunkType

client = TestClient(app)


def test_compute_text_diff_identical():
    """Identical text produces zero additions, deletions, or modifications."""
    text = "First line.\nSecond line."
    lines, stats = compute_text_diff(text, text)
    assert stats["additions"] == 0
    assert stats["deletions"] == 0
    assert stats["modifications"] == 0
    assert len(lines) == 2
    assert all(l.type == DiffChunkType.equal for l in lines)


def test_compute_text_diff_additions_and_deletions():
    """Text diff detects pure insertions and deletions."""
    orig = "Line 1\nLine 2"
    newer = "Line 1\nLine 1.5\nLine 2\nLine 3"
    lines, stats = compute_text_diff(orig, newer)
    assert stats["additions"] == 2
    assert stats["deletions"] == 0


def test_compute_inline_segments():
    """Word-level segment matching identifies replaced words while preserving unchanged words."""
    line_a = "These cheap headphones are great."
    line_b = "These luxury headphones are great."
    seg_a, seg_b = compute_inline_segments(line_a, line_b)

    # In seg_a, 'cheap' should be marked delete
    deleted = [s.text for s in seg_a if s.type == DiffChunkType.delete]
    assert "cheap" in deleted

    # In seg_b, 'luxury' should be marked insert
    inserted = [s.text for s in seg_b if s.type == DiffChunkType.insert]
    assert "luxury" in inserted


def test_compare_findings_resolution():
    """Findings in orig that are absent in newer are flagged as resolved."""
    f1 = Finding(
        id="f1",
        category=FindingCategory.prohibited_terminology,
        severity=Severity.critical,
        matched_text="cheap",
        start_index=6,
        end_index=11,
        explanation="Use accessible luxury",
        rule_id="p-cheap",
        rule_name_or_fact='Prohibited term "cheap"',
        suggested_correction="accessible luxury",
        evidence_status=EvidenceStatus.confirmed_violation,
    )
    f2 = Finding(
        id="f2",
        category=FindingCategory.prohibited_terminology,
        severity=Severity.critical,
        matched_text="kills the competition",
        start_index=20,
        end_index=41,
        explanation="Violates aggressive marketing policy",
        rule_id="p-kills",
        rule_name_or_fact='Prohibited term "kills the competition"',
        suggested_correction="leads the category",
        evidence_status=EvidenceStatus.confirmed_violation,
    )

    # In newer version, f1 is fixed, f2 remains
    orig_findings = [f1, f2]
    newer_findings = [f2]

    resolved, unresolved, introduced, summary = compare_findings(orig_findings, newer_findings)
    assert len(resolved) == 1
    assert resolved[0].rule_name_or_fact == 'Prohibited term "cheap"'
    assert len(unresolved) == 1
    assert unresolved[0].rule_name_or_fact == 'Prohibited term "kills the competition"'
    assert len(introduced) == 0
    assert summary["resolved_count"] == 1
    assert summary["unresolved_count"] == 1
    assert summary["net_change"] == -1


def test_compare_findings_does_not_falsely_resolve_on_text_change():
    """CRITICAL REQUIREMENT 7: Merely altering erroneous text does NOT resolve the finding."""
    # Orig: Fact says price is $199 (contradicts approved $249)
    f_orig = Finding(
        id="f-price-orig",
        category=FindingCategory.fact_accuracy,
        severity=Severity.critical,
        matched_text="$199",
        start_index=10,
        end_index=14,
        explanation="Price should be $249",
        rule_id=None,
        rule_name_or_fact="NovaSound Apex Wireless - Price",
        suggested_correction="$249",
        evidence_status=EvidenceStatus.confirmed_violation,
    )
    # Newer: User typed $189 instead of $199. Still contradicts $249!
    f_newer = Finding(
        id="f-price-newer",
        category=FindingCategory.fact_accuracy,
        severity=Severity.critical,
        matched_text="$189",
        start_index=10,
        end_index=14,
        explanation="Price should be $249",
        rule_id=None,
        rule_name_or_fact="NovaSound Apex Wireless - Price",
        suggested_correction="$249",
        evidence_status=EvidenceStatus.confirmed_violation,
    )

    resolved, unresolved, introduced, summary = compare_findings([f_orig], [f_newer])
    assert len(resolved) == 0  # NOT resolved!
    assert len(unresolved) == 1
    assert unresolved[0].rule_name_or_fact == "NovaSound Apex Wireless - Price"
    assert len(introduced) == 0


def test_compare_findings_detects_introduced_violations():
    """New rule violations in newer revision are accurately identified as introduced."""
    f_introduced = Finding(
        id="f3",
        category=FindingCategory.required_disclaimer,
        severity=Severity.warning,
        matched_text="all-day battery",
        start_index=0,
        end_index=15,
        explanation="Disclaimer required for battery claims",
        rule_id="d-battery",
        rule_name_or_fact="Battery claims disclaimer",
        suggested_correction="Add disclaimer",
        evidence_status=EvidenceStatus.potential_issue,
    )
    resolved, unresolved, introduced, summary = compare_findings([], [f_introduced])
    assert len(resolved) == 0
    assert len(unresolved) == 0
    assert len(introduced) == 1
    assert introduced[0].rule_name_or_fact == "Battery claims disclaimer"
    assert summary["introduced_count"] == 1
    assert summary["net_change"] == 1


def test_api_submission_diff_endpoint_e2e():
    """End-to-end test of GET /api/submissions/{id}/diff endpoint across version lifecycle."""
    # 1. Create a submission (v1) with multiple brand violations
    create_payload = {
        "title": "Headphones Launch Campaign",
        "content": "The NovaSound Apex Wireless has cheap headphones and costs $199. Our unbreakable build kills the competition.",
        "creator_name": "Jordan Lee (Demo Creator)",
    }
    create_res = client.post("/api/submissions", json=create_payload)
    assert create_res.status_code == 201
    sub = create_res.json()
    sub_id = sub["id"]
    assert sub["version"] == 1
    assert len(sub["version_history"]) == 1

    # 2. Query diff on single version (v1 vs v1)
    diff_v1 = client.get(f"/api/submissions/{sub_id}/diff")
    assert diff_v1.status_code == 200
    v1_data = diff_v1.json()
    assert v1_data["orig_version"] == 1
    assert v1_data["newer_version"] == 1
    assert v1_data["stats"]["additions"] == 0
    assert v1_data["stats"]["deletions"] == 0
    assert v1_data["available_versions"] == [1]

    # 3. Creator updates content to fix 'cheap' and '$199' -> creates v2
    update_res = client.put(f"/api/submissions/{sub_id}", json={
        "content": "The NovaSound Apex Wireless has accessible luxury headphones and costs $299. Our unbreakable build kills the competition."
    })
    assert update_res.status_code == 200
    sub_v2 = update_res.json()
    assert sub_v2["version"] == 2
    assert len(sub_v2["version_history"]) == 2

    # 4. Compare v1 with v2 via API
    diff_res = client.get(f"/api/submissions/{sub_id}/diff?orig=1&newer=2")
    assert diff_res.status_code == 200
    diff_data = diff_res.json()

    assert diff_data["orig_version"] == 1
    assert diff_data["newer_version"] == 2
    assert diff_data["available_versions"] == [1, 2]
    assert diff_data["stats"]["modifications"] >= 1

    # Check finding resolution: 'cheap' and '$199' (price) must be resolved
    resolved_names = [f["rule_name_or_fact"] for f in diff_data["resolved_findings"]]
    assert any("cheap" in name.lower() for name in resolved_names)
    assert any("price" in name.lower() for name in resolved_names)

    # Check unresolved: 'kills the competition' and 'unbreakable' must remain
    unresolved_names = [f["rule_name_or_fact"] for f in diff_data["unresolved_findings"]]
    assert any("kills" in name.lower() for name in unresolved_names)
    assert any("unbreakable" in name.lower() for name in unresolved_names)

    assert diff_data["findings_summary"]["resolved_count"] >= 2
    assert diff_data["findings_summary"]["unresolved_count"] >= 1


def test_api_submission_diff_invalid_version_returns_404():
    """Requesting non-existent version returns 404 with list of available versions."""
    create_res = client.post("/api/submissions", json={
        "title": "Version Test",
        "content": "Sample valid content.",
    })
    sub_id = create_res.json()["id"]

    res_missing_orig = client.get(f"/api/submissions/{sub_id}/diff?orig=99&newer=1")
    assert res_missing_orig.status_code == 404
    assert "Original version 99 not found" in res_missing_orig.json()["detail"]

    res_missing_newer = client.get(f"/api/submissions/{sub_id}/diff?orig=1&newer=88")
    assert res_missing_newer.status_code == 404
    assert "Newer version 88 not found" in res_missing_newer.json()["detail"]
