import re
from typing import List
from ..models.rules import (
    PreferredWordingRule,
    Finding,
    FindingCategory,
    EvidenceStatus,
)


def evaluate_preferred_wording(text: str, rules: List[PreferredWordingRule]) -> List[Finding]:
    """Inspect text for non-preferred vocabulary and suggest approved brand nomenclature."""
    findings: List[Finding] = []

    for rule in rules:
        flags = 0 if rule.case_sensitive else re.IGNORECASE
        escaped = re.escape(rule.avoid_term)
        pattern = rf"\b{escaped}\b"

        for match in re.finditer(pattern, text, flags):
            matched_str = match.group(0)
            findings.append(
                Finding(
                    id=f"pref-{len(findings) + 1}",
                    category=FindingCategory.preferred_wording,
                    severity=rule.severity,
                    matched_text=matched_str,
                    start_index=match.start(),
                    end_index=match.end(),
                    explanation=rule.explanation,
                    rule_id=rule.id,
                    rule_name_or_fact=f"Preferred Wording: Use '{rule.preferred_term}' over '{rule.avoid_term}'",
                    suggested_correction=rule.preferred_term,
                    evidence_status=EvidenceStatus.potential_issue,
                )
            )

    return findings
