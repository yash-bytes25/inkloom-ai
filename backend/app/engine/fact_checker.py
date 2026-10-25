import re
from typing import List
from ..models.rules import (
    ApprovedFact,
    Finding,
    FindingCategory,
    EvidenceStatus,
)


def evaluate_approved_facts(text: str, facts: List[ApprovedFact]) -> List[Finding]:
    """Inspect text for direct contradictions with approved brand facts.

    CRITICAL GOVERNANCE PRINCIPLE:
    Never claim a statement is false merely because no supporting fact was found.
    Findings are ONLY raised when an approved entity/attribute is identified
    and positively contradicts the certified approved fact.
    """
    findings: List[Finding] = []

    for fact in facts:
        # Check if the entity is referenced in the submission (case-insensitive)
        entity_pattern = re.escape(fact.entity)
        entity_matches = list(re.finditer(rf"\b{entity_pattern}\b", text, re.IGNORECASE))

        # If entity is not referenced, skip this fact check
        if not entity_matches:
            continue

        # Check if attribute context keywords appear in the text
        has_context = True
        if fact.context_keywords:
            has_context = any(
                re.search(rf"\b{re.escape(kw)}\b", text, re.IGNORECASE)
                for kw in fact.context_keywords
            )

        if not has_context:
            continue

        # Check for explicit contradictions against the approved fact
        for conflict_pattern in fact.conflicting_patterns:
            try:
                for match in re.finditer(conflict_pattern, text, re.IGNORECASE):
                    matched_str = match.group(0)

                    # Do not flag if matched string is actually identical to the approved value
                    if matched_str.strip().lower() == fact.approved_value.strip().lower():
                        continue

                    findings.append(
                        Finding(
                            id=f"fact-{len(findings) + 1}",
                            category=FindingCategory.fact_accuracy,
                            severity=fact.severity,
                            matched_text=matched_str,
                            start_index=match.start(),
                            end_index=match.end(),
                            explanation=(
                                f"{fact.explanation} Approved {fact.attribute} for {fact.entity} is "
                                f"'{fact.approved_value}', but found conflicting claim '{matched_str}'."
                            ),
                            rule_id=fact.id,
                            rule_name_or_fact=f"Approved Fact: {fact.entity} {fact.attribute} = '{fact.approved_value}'",
                            suggested_correction=fact.approved_value,
                            evidence_status=EvidenceStatus.confirmed_violation,
                        )
                    )
            except re.error:
                continue

    return findings
