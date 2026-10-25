import re
from typing import List
from ..models.rules import (
    ProhibitedTermRule,
    Finding,
    FindingCategory,
    EvidenceStatus,
)


def evaluate_prohibited_terms(text: str, rules: List[ProhibitedTermRule]) -> List[Finding]:
    """Inspect text for prohibited phrases and terminology using exact or regex matching."""
    findings: List[Finding] = []

    for rule in rules:
        flags = 0 if rule.case_sensitive else re.IGNORECASE

        if rule.is_regex:
            pattern = rule.term_or_pattern
        else:
            # Word-boundary escaped pattern for literal string matching
            escaped = re.escape(rule.term_or_pattern)
            pattern = rf"\b{escaped}\b"

        try:
            for match in re.finditer(pattern, text, flags):
                matched_str = match.group(0)
                findings.append(
                    Finding(
                        id=f"prohib-{len(findings) + 1}",
                        category=FindingCategory.prohibited_terminology,
                        severity=rule.severity,
                        matched_text=matched_str,
                        start_index=match.start(),
                        end_index=match.end(),
                        explanation=rule.explanation,
                        rule_id=rule.id,
                        rule_name_or_fact=f"Prohibited Term: '{rule.term_or_pattern}'",
                        suggested_correction=rule.suggested_replacement,
                        evidence_status=EvidenceStatus.confirmed_violation,
                    )
                )
        except re.error:
            # Fallback to direct substring search if regex syntax is invalid
            lowered_text = text if rule.case_sensitive else text.lower()
            lowered_term = rule.term_or_pattern if rule.case_sensitive else rule.term_or_pattern.lower()
            idx = lowered_text.find(lowered_term)
            while idx != -1:
                findings.append(
                    Finding(
                        id=f"prohib-{len(findings) + 1}",
                        category=FindingCategory.prohibited_terminology,
                        severity=rule.severity,
                        matched_text=text[idx:idx + len(rule.term_or_pattern)],
                        start_index=idx,
                        end_index=idx + len(rule.term_or_pattern),
                        explanation=rule.explanation,
                        rule_id=rule.id,
                        rule_name_or_fact=f"Prohibited Term: '{rule.term_or_pattern}'",
                        suggested_correction=rule.suggested_replacement,
                        evidence_status=EvidenceStatus.confirmed_violation,
                    )
                )
                idx = lowered_text.find(lowered_term, idx + len(rule.term_or_pattern))

    return findings
