"""Evidence-backed prototype analysis for clause pairs and Indian-law rules."""

import re
import uuid

from legalagent.core.types import Clause, Finding


def _evidence(clause: Clause) -> dict:
    return {"clause_id": clause.id, "start": 0, "end": len(clause.text)}


def _finding(
    target: Clause,
    related: list[Clause],
    relation_type: str,
    severity: str,
    risk_score: float,
    rationale: str,
    surfaced_by: list[str],
    refs: list[dict] | None = None,
) -> Finding:
    return Finding(
        id=f"finding_{uuid.uuid4().hex[:8]}",
        target_clause_id=target.id,
        related_clause_ids=[clause.id for clause in related],
        relation_type=relation_type,
        severity=severity,
        risk_score=risk_score,
        rationale=rationale,
        surfaced_by=surfaced_by,
        evidence=[_evidence(target), *(_evidence(clause) for clause in related)],
        refs=refs or [],
        scores={"analysis_confidence": 0.82},
    )


def analyse_pair(clause_a: Clause, clause_b: Clause, surfaced_by: list[str]) -> Finding | None:
    """Return a high-confidence prototype finding for a relevant clause pair."""
    labels = {
        label["label"]
        for clause in (clause_a, clause_b)
        for label in clause.labels
    }

    liability = next(
        (clause for clause in (clause_a, clause_b)
         if any(label["label"] == "limitation_of_liability" for label in clause.labels)),
        None,
    )
    indemnity = next(
        (clause for clause in (clause_a, clause_b)
         if clause is not liability and any(label["label"] == "indemnification" for label in clause.labels)),
        None,
    )
    if liability and indemnity and "limitation_of_liability" in labels and "indemnification" in labels:
        return _finding(
            liability,
            [indemnity],
            "conflict",
            "high",
            0.9,
            "The liability clause sets an aggregate ceiling, while the indemnity clause does not clearly state whether indemnity obligations are subject to that ceiling.",
            surfaced_by,
            [{
                "source": "Indian Contract Act, 1872",
                "section": "Sections 124-125",
                "snippet": "Indemnity obligations should be expressly coordinated with contractual liability limits.",
            }],
        )

    termination = next(
        (clause for clause in (clause_a, clause_b)
         if any(label["label"] == "termination" for label in clause.labels)
         and not any(label["label"] == "survival" for label in clause.labels)),
        None,
    )
    survival = next(
        (clause for clause in (clause_a, clause_b)
         if any(label["label"] == "survival" for label in clause.labels)),
        None,
    )
    # A survival clause that cites another clause by number ("Section 8.1 shall
    # survive") makes that clause's post-termination life depend on it, whatever
    # the cited clause's own type.
    if survival and "xref" in surfaced_by:
        cited = clause_b if survival is clause_a else clause_a
        if any(xref["resolved"] and xref["clause_id"] == cited.id for xref in survival.xrefs):
            return _finding(
                cited,
                [survival],
                "dependency",
                "medium",
                0.62,
                "The survival clause names this clause, so whether its obligations continue after termination depends on the survival clause.",
                surfaced_by,
            )

    if termination and survival:
        return _finding(
            termination,
            [survival],
            "dependency",
            "medium",
            0.62,
            "The termination clause depends on the survival clause to determine which obligations continue after termination.",
            surfaced_by,
        )

    # A survival clause that cites another clause by number ("Section 8.1 shall
    # survive") makes that clause's post-termination life depend on it, whatever
    # the cited clause's own type.
    if survival and "xref" in surfaced_by:
        cited = clause_b if survival is clause_a else clause_a
        if any(xref["resolved"] and xref["clause_id"] == cited.id for xref in survival.xrefs):
            return _finding(
                cited,
                [survival],
                "dependency",
                "medium",
                0.62,
                "The survival clause names this clause, so whether its obligations continue after termination depends on the survival clause.",
                surfaced_by,
            )

    return None


_PCT_RE = re.compile(r"(\d{2,3})\s*(?:%|per\s*cent|percent)")


def _indian_rules(clause: Clause, text: str) -> list[Finding]:
    """Deterministic, high-precision Indian statutory checks (research/clause_taxonomy/08_MIGRATION.md 4.3)."""
    out = []
    # ICA s.74: liquidated damages that are a penalty (no link to actual loss, or >= 50% of value).
    if re.search(r"liquidated damages|penalt", text):
        big = any(int(p) >= 50 for p in _PCT_RE.findall(text))
        if re.search(r"regardless of (?:any )?actual loss|irrespective of (?:any )?(?:actual )?loss|whether or not any loss", text) or big:
            out.append(_finding(clause, [], "statutory_violation", "high", 0.88,
                                "The damages stipulation is untethered from actual loss (or is disproportionate). Under Section 74 of the Indian Contract Act, 1872 a court awards only reasonable compensation up to the stated sum, so this figure is unlikely to be enforceable as written.",
                                ["statutory_rule"], [{"source": "The Indian Contract Act, 1872", "section": "Section 74",
                                                      "snippet": "Compensation for breach of contract where penalty stipulated for."}]))
    # Indian Stamp Act s.35: unstamped instruments are inadmissible in evidence.
    if re.search(r"intentionally unstamped|shall not be stamped|waive[sd]? (?:any )?(?:requirement of )?stamp|without (?:payment of )?stamp duty|not be impounded", text):
        out.append(_finding(clause, [], "statutory_violation", "high", 0.9,
                            "The parties agree to leave the instrument unstamped or waive stamping. Under Section 35 of the Indian Stamp Act, 1899 an unstamped instrument is inadmissible in evidence until duty and penalty are paid; parties cannot contract out of this.",
                            ["statutory_rule"], [{"source": "The Indian Stamp Act, 1899", "section": "Section 35",
                                                  "snippet": "Instruments not duly stamped inadmissible in evidence, etc."}]))
    # DPDP Act 2023: processing personal data without notice/consent, or capping statutory penalties.
    if re.search(r"personal data|data principal", text) and re.search(
            r"without (?:any )?(?:notice|consent)|sell (?:any )?(?:customer |user )?(?:personal )?data|no (?:notice|consent) (?:shall be )?required|cap(?:ped)? .{0,40}penalt", text):
        out.append(_finding(clause, [], "statutory_violation", "high", 0.86,
                            "The clause permits processing or sale of personal data without notice/consent (or limits statutory penalties). The Digital Personal Data Protection Act, 2023 requires notice and consent (Sections 5-6) and its penalties cannot be contracted away.",
                            ["statutory_rule"], [{"source": "The Digital Personal Data Protection Act, 2023", "section": "Section 6",
                                                  "snippet": "Consent of the Data Principal."}]))
    return out


def analyse_statutory(clauses: list[Clause], jurisdiction: str = "India") -> list[Finding]:
    """Apply deterministic, high-confidence Indian-law checks for the prototype."""
    if "india" not in jurisdiction.lower():
        return []

    findings = []
    for clause in clauses:
        text = clause.text.lower()
        findings.extend(_indian_rules(clause, text))
        if re.search(r"post[- ]termination|following termination|after termination", text) and re.search(
            r"non[- ]compete|competing business|restraint of trade|shall not\s+compete", text
        ):
            findings.append(_finding(
                clause,
                [],
                "statutory_violation",
                "high",
                0.94,
                "This clause appears to restrain trade or profession after termination. Post-termination employment restraints are generally void under Section 27 of the Indian Contract Act, 1872.",
                ["statutory_rule"],
                [{
                    "source": "Indian Contract Act, 1872",
                    "section": "Section 27",
                    "snippet": "Agreements restraining a lawful profession, trade, or business are void to that extent.",
                }],
            ))
    return findings


def validate_findings(findings: list[Finding], clauses: list[Clause]) -> None:
    """Fail fast if a finding points outside the analyzed contract."""
    clauses_by_id = {clause.id: clause for clause in clauses}
    for finding in findings:
        ids = [finding.target_clause_id, *finding.related_clause_ids]
        for clause_id in ids:
            if clause_id not in clauses_by_id:
                raise ValueError(f"Finding references unknown clause: {clause_id}")
        for evidence in finding.evidence:
            clause = clauses_by_id.get(evidence["clause_id"])
            if clause is None or not clause.text[evidence["start"]:evidence["end"]].strip():
                raise ValueError(f"Finding contains invalid evidence: {evidence}")