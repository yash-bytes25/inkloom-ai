import re
from typing import List
from ..models.rules import (
    RequiredDisclaimerRule,
    Finding,
    FindingCategory,
    EvidenceStatus,
)


def evaluate_required_disclaimers(text: str, rules: List[RequiredDisclaimerRule]) -> List[Finding]:
    """Inspect text for claims that mandate regulatory or brand disclaimers."""
    findings: List[Finding] = []

    for rule in rules:
        flags = 0 if rule.case_sensitive else re.IGNORECASE
        trigger_matches = list(re.finditer(rule.trigger_pattern, text, flags))

        if not trigger_matches:
            continue

        # Check if the required disclaimer text (or substantial substring) is already present
        clean_required = rule.required_disclaimer_text.strip().lower()
        clean_text = text.lower()

        # Check if the disclaimer (or core without leading asterisk) is present
        core_disclaimer = clean_required.lstrip("* ").strip()
        is_present = (clean_required in clean_text) or (core_disclaimer in clean_text)

        if not is_present:
            # First trigger occurrence highlights where the requirement is initiated
            primary_match = trigger_matches[0]
            findings.append(
                Finding(
                    id=f"disclaimer-{len(findings) + 1}",
                    category=FindingCategory.required_disclaimer,
                    severity=rule.severity,
                    matched_text=primary_match.group(0),
                    start_index=primary_match.start(),
                    end_index=primary_match.end(),
                    explanation=(
                        f"{rule.explanation} Text activates requirement: {rule.trigger_description}, "
                        f"but mandatory disclosure is missing."
                    ),
                    rule_id=rule.id,
                    rule_name_or_fact=f"Mandatory Disclaimer for: {rule.trigger_description}",
                    suggested_correction=f"Add disclosure: {rule.required_disclaimer_text}",
                    evidence_status=EvidenceStatus.potential_issue,
                )
            )

    return findings
