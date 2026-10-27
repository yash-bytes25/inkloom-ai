import difflib
import re
from typing import Dict, List, Tuple
from fastapi import HTTPException

from ..models.workflow import (
    DiffChunkType,
    DiffLine,
    DiffSegment,
    RevisionDiffResponse,
    ReviewStatus,
    Submission,
    SubmissionVersionSnapshot,
)
from ..models.rules import Finding
from .evaluator import run_deterministic_review
from .rules_service import get_active_brand_rules


def _tokenize_line(line: str) -> List[str]:
    """Tokenize line into words, spaces, and punctuation to support fine-grained word diffs."""
    if not line:
        return []
    return re.findall(r"\w+|\s+|[^\w\s]", line)


def compute_inline_segments(line_a: str, line_b: str) -> Tuple[List[DiffSegment], List[DiffSegment]]:
    """Compute word/token-level diff segments between two lines for highlighted inline changes."""
    if not line_a and not line_b:
        return [], []
    if not line_a:
        return [], [DiffSegment(type=DiffChunkType.insert, text=line_b)]
    if not line_b:
        return [DiffSegment(type=DiffChunkType.delete, text=line_a)], []

    tokens_a = _tokenize_line(line_a)
    tokens_b = _tokenize_line(line_b)

    matcher = difflib.SequenceMatcher(None, tokens_a, tokens_b)
    segments_a: List[DiffSegment] = []
    segments_b: List[DiffSegment] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        chunk_a = "".join(tokens_a[i1:i2])
        chunk_b = "".join(tokens_b[j1:j2])
        if tag == "equal":
            if chunk_a:
                segments_a.append(DiffSegment(type=DiffChunkType.equal, text=chunk_a))
            if chunk_b:
                segments_b.append(DiffSegment(type=DiffChunkType.equal, text=chunk_b))
        elif tag == "delete":
            if chunk_a:
                segments_a.append(DiffSegment(type=DiffChunkType.delete, text=chunk_a))
        elif tag == "insert":
            if chunk_b:
                segments_b.append(DiffSegment(type=DiffChunkType.insert, text=chunk_b))
        elif tag == "replace":
            if chunk_a:
                segments_a.append(DiffSegment(type=DiffChunkType.delete, text=chunk_a))
            if chunk_b:
                segments_b.append(DiffSegment(type=DiffChunkType.insert, text=chunk_b))

    return segments_a, segments_b


def compute_text_diff(text_a: str, text_b: str) -> Tuple[List[DiffLine], Dict[str, int]]:
    """Compute structured line-by-line diff between original (text_a) and newer (text_b)."""
    lines_a = text_a.splitlines()
    lines_b = text_b.splitlines()

    matcher = difflib.SequenceMatcher(None, lines_a, lines_b)
    diff_lines: List[DiffLine] = []
    additions = 0
    deletions = 0
    modifications = 0

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for offset in range(i2 - i1):
                diff_lines.append(
                    DiffLine(
                        line_number_orig=i1 + offset + 1,
                        line_number_newer=j1 + offset + 1,
                        type=DiffChunkType.equal,
                        orig_text=lines_a[i1 + offset],
                        newer_text=lines_b[j1 + offset],
                    )
                )
        elif tag == "delete":
            for offset in range(i2 - i1):
                deletions += 1
                diff_lines.append(
                    DiffLine(
                        line_number_orig=i1 + offset + 1,
                        line_number_newer=None,
                        type=DiffChunkType.delete,
                        orig_text=lines_a[i1 + offset],
                        newer_text="",
                        orig_segments=[DiffSegment(type=DiffChunkType.delete, text=lines_a[i1 + offset])],
                        newer_segments=[],
                    )
                )
        elif tag == "insert":
            for offset in range(j2 - j1):
                additions += 1
                diff_lines.append(
                    DiffLine(
                        line_number_orig=None,
                        line_number_newer=j1 + offset + 1,
                        type=DiffChunkType.insert,
                        orig_text="",
                        newer_text=lines_b[j1 + offset],
                        orig_segments=[],
                        newer_segments=[DiffSegment(type=DiffChunkType.insert, text=lines_b[j1 + offset])],
                    )
                )
        elif tag == "replace":
            count_a = i2 - i1
            count_b = j2 - j1
            max_count = max(count_a, count_b)
            for offset in range(max_count):
                modifications += 1
                has_a = offset < count_a
                has_b = offset < count_b
                la = lines_a[i1 + offset] if has_a else ""
                lb = lines_b[j1 + offset] if has_b else ""
                seg_a, seg_b = compute_inline_segments(la, lb)
                diff_lines.append(
                    DiffLine(
                        line_number_orig=i1 + offset + 1 if has_a else None,
                        line_number_newer=j1 + offset + 1 if has_b else None,
                        type=DiffChunkType.replace,
                        orig_text=la,
                        newer_text=lb,
                        orig_segments=seg_a,
                        newer_segments=seg_b,
                    )
                )

    stats = {
        "additions": additions,
        "deletions": deletions,
        "modifications": modifications,
        "total_lines_orig": len(lines_a),
        "total_lines_newer": len(lines_b),
    }
    return diff_lines, stats


def get_finding_rule_signature(f: Finding) -> str:
    """Extract a canonical identifier for the underlying governance rule/fact.
    
    CRITICAL: Does not rely solely on matched text so that superficial text edits
    (e.g. changing an erroneous price from $199 to $189) are not falsely marked as resolved.
    """
    cat = f.category.value if hasattr(f.category, "value") else str(f.category)
    rule_or_fact = (f.rule_name_or_fact or "").strip().lower()
    rule_id = (f.rule_id or "").strip().lower()
    return f"{cat}::{rule_id}::{rule_or_fact}"


def compare_findings(
    orig_findings: List[Finding],
    newer_findings: List[Finding],
) -> Tuple[List[Finding], List[Finding], List[Finding], Dict[str, int]]:
    """Compare findings between original and newer revisions.
    
    A finding is:
    - Resolved: was present in orig_findings, but its underlying rule violation is
      completely absent in newer_findings as determined by the governance engine.
    - Unresolved: was present in orig_findings and STILL violated in newer_findings.
    - Introduced: was NOT violated in orig_findings, but newly triggered in newer_findings.
    """
    orig_counts: Dict[str, int] = {}
    for f in orig_findings:
        sig = get_finding_rule_signature(f)
        orig_counts[sig] = orig_counts.get(sig, 0) + 1

    newer_counts: Dict[str, int] = {}
    for f in newer_findings:
        sig = get_finding_rule_signature(f)
        newer_counts[sig] = newer_counts.get(sig, 0) + 1

    resolved: List[Finding] = []
    unresolved: List[Finding] = []
    introduced: List[Finding] = []

    seen_unresolved_counts: Dict[str, int] = {}

    for f in orig_findings:
        sig = get_finding_rule_signature(f)
        count_in_newer = newer_counts.get(sig, 0)
        already_assigned = seen_unresolved_counts.get(sig, 0)

        if already_assigned < count_in_newer:
            unresolved.append(f)
            seen_unresolved_counts[sig] = already_assigned + 1
        else:
            resolved.append(f)

    seen_orig_counts: Dict[str, int] = {}
    for f in newer_findings:
        sig = get_finding_rule_signature(f)
        count_in_orig = orig_counts.get(sig, 0)
        already_paired = seen_orig_counts.get(sig, 0)

        if already_paired < count_in_orig:
            seen_orig_counts[sig] = already_paired + 1
        else:
            introduced.append(f)

    summary = {
        "resolved_count": len(resolved),
        "unresolved_count": len(unresolved),
        "introduced_count": len(introduced),
        "orig_total": len(orig_findings),
        "newer_total": len(newer_findings),
        "net_change": len(newer_findings) - len(orig_findings),
    }

    return resolved, unresolved, introduced, summary


class DiffService:
    """Provides revision comparison, text diffing, and governance finding resolution analysis."""

    def build_revision_diff(
        self,
        submission: Submission,
        orig_version: int,
        newer_version: int,
    ) -> RevisionDiffResponse:
        """Construct full side-by-side diff and governance finding resolution breakdown."""
        snapshots_by_version: Dict[int, SubmissionVersionSnapshot] = {}

        # 1. Gather all snapshots from version_history
        for snap in submission.version_history:
            snapshots_by_version[snap.version] = snap

        # 2. Gather snapshots from decision history
        for dec in submission.decision_history:
            if dec.content_version not in snapshots_by_version:
                snapshots_by_version[dec.content_version] = SubmissionVersionSnapshot(
                    version=dec.content_version,
                    content=dec.content_snapshot,
                    timestamp=dec.timestamp,
                    title=submission.title,
                    status_at_save=ReviewStatus(dec.decision.value),
                    creator_name=submission.creator_name,
                )

        # 3. Ensure current version is registered
        if submission.version not in snapshots_by_version:
            snapshots_by_version[submission.version] = SubmissionVersionSnapshot(
                version=submission.version,
                content=submission.content,
                timestamp=submission.updated_at,
                title=submission.title,
                status_at_save=submission.status,
                creator_name=submission.creator_name,
            )

        # 4. Ensure v1 is registered if current version == 1
        if 1 not in snapshots_by_version:
            snapshots_by_version[1] = SubmissionVersionSnapshot(
                version=1,
                content=submission.content,
                timestamp=submission.created_at,
                title=submission.title,
                status_at_save=ReviewStatus.draft,
                creator_name=submission.creator_name,
            )

        available_versions = sorted(snapshots_by_version.keys())

        if orig_version not in snapshots_by_version:
            raise HTTPException(
                status_code=404,
                detail=f"Original version {orig_version} not found for submission '{submission.id}'. Available versions: {available_versions}",
            )

        if newer_version not in snapshots_by_version:
            raise HTTPException(
                status_code=404,
                detail=f"Newer version {newer_version} not found for submission '{submission.id}'. Available versions: {available_versions}",
            )

        snap_orig = snapshots_by_version[orig_version]
        snap_newer = snapshots_by_version[newer_version]

        # 5. Evaluate findings on both versions using the active brand guidelines
        active_rules = get_active_brand_rules()
        review_orig = run_deterministic_review(snap_orig.content, rules=active_rules)
        review_newer = run_deterministic_review(snap_newer.content, rules=active_rules)

        # 6. Compute line-by-line diff and word segments
        lines, stats = compute_text_diff(snap_orig.content, snap_newer.content)

        # 7. Compare findings between original and newer versions
        resolved, unresolved, introduced, findings_summary = compare_findings(
            review_orig.findings,
            review_newer.findings,
        )

        return RevisionDiffResponse(
            submission_id=submission.id,
            orig_version=orig_version,
            newer_version=newer_version,
            orig_timestamp=snap_orig.timestamp,
            newer_timestamp=snap_newer.timestamp,
            orig_content=snap_orig.content,
            newer_content=snap_newer.content,
            orig_creator=snap_orig.creator_name,
            newer_creator=snap_newer.creator_name,
            stats=stats,
            lines=lines,
            resolved_findings=resolved,
            unresolved_findings=unresolved,
            introduced_findings=introduced,
            findings_summary=findings_summary,
            available_versions=available_versions,
        )


diff_service = DiffService()
