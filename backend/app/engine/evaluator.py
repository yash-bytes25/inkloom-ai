from typing import List, Dict
from ..models.rules import (
    BrandRulesConfig,
    ReviewResponse,
    Finding,
    Severity,
)
from .prohibited_terms import evaluate_prohibited_terms
from .preferred_wording import evaluate_preferred_wording
from .fact_checker import evaluate_approved_facts
from .disclaimers import evaluate_required_disclaimers
from .demo_data import DEMO_BRAND_RULES


def run_deterministic_review(text: str, rules: BrandRulesConfig = None) -> ReviewResponse:
    """Execute complete deterministic brand governance evaluation on submitted text."""
    if rules is None:
        from .rules_service import get_active_brand_rules
        rules = get_active_brand_rules()

    # Handle empty or whitespace-only text
    if not text or not text.strip():
        return ReviewResponse(
            text_length=len(text) if text else 0,
            total_findings=0,
            findings_by_severity={
                Severity.critical.value: 0,
                Severity.warning.value: 0,
                Severity.info.value: 0,
            },
            findings=[],
            is_compliant=True,
            brand_name=rules.brand_name,
            is_demo_data=rules.is_demo,
        )

    all_findings: List[Finding] = []

    # 1. Prohibited terms and phrases
    all_findings.extend(evaluate_prohibited_terms(text, rules.prohibited_terms))

    # 2. Preferred brand nomenclature
    all_findings.extend(evaluate_preferred_wording(text, rules.preferred_wording))

    # 3. Approved factual accuracy checks
    all_findings.extend(evaluate_approved_facts(text, rules.approved_facts))

    # 4. Mandatory regulatory & policy disclaimers
    all_findings.extend(evaluate_required_disclaimers(text, rules.required_disclaimers))

    # Sort findings by starting character offset for intuitive chronological presentation
    all_findings.sort(key=lambda f: (f.start_index if f.start_index is not None else 999999))

    # Re-index findings with clean sequential identifiers
    for idx, finding in enumerate(all_findings, start=1):
        finding.id = f"finding-{idx}"

    # Group tallies by severity
    findings_by_severity: Dict[str, int] = {
        Severity.critical.value: sum(1 for f in all_findings if f.severity == Severity.critical),
        Severity.warning.value: sum(1 for f in all_findings if f.severity == Severity.warning),
        Severity.info.value: sum(1 for f in all_findings if f.severity == Severity.info),
    }

    # Strict compliance requires 0 critical violations and 0 warning issues
    is_compliant = (
        findings_by_severity[Severity.critical.value] == 0
        and findings_by_severity[Severity.warning.value] == 0
    )

    return ReviewResponse(
        text_length=len(text),
        total_findings=len(all_findings),
        findings_by_severity=findings_by_severity,
        findings=all_findings,
        is_compliant=is_compliant,
        brand_name=rules.brand_name,
        is_demo_data=rules.is_demo,
        ai_status="not_requested",
        deterministic_count=len(all_findings),
        ai_count=0,
    )
