"""
Single-clause Indian-law risk check with the Kev decision model (zero-shot, no training).

The regex rules in analysis.analyse_statutory caught 0 of 13 clauses the Supreme Court struck
down: real drafting ("from the date you leave", "forfeiture of earnest money") does not match
keyword patterns. Here Kev reads the clause and chooses among plainly described legal risk
categories, each mapped to the statute a court would apply. Used as an extra statutory signal
in the pipeline (config["kev_statutory"]) and evaluated in scripts/eval_all.py statutory.
"""
import uuid

from legalagent.core.types import Clause, Finding

CATEGORIES = {
    "restraint_of_trade": ("stops a party from carrying on a lawful profession, trade or business, or from joining or "
                           "working with competitors, especially after the contract or employment ends",
                           "The Indian Contract Act, 1872", "Section 27"),
    "penalty_or_forfeiture": ("fixes a sum payable on breach, or forfeits a deposit, earnest money or security, or "
                              "imposes damages that do not depend on the actual loss suffered or are out of proportion to it",
                              "The Indian Contract Act, 1872", "Section 74"),
    "restricts_legal_remedies": ("bars or limits a party's right to go to court, shortens the time allowed to bring a claim, "
                                 "or extinguishes a party's rights after a fixed period",
                                 "The Indian Contract Act, 1872", "Section 28"),
    "one_sided_arbitrator": ("lets one party, its officer or its nominee alone appoint the arbitrator or act as arbitrator",
                             "The Arbitration and Conciliation Act, 1996", "Section 12"),
    "termination_at_will": ("lets the stronger party end an employee's service or the contract at any time without cause "
                            "or with only a short notice, with no protection for the other side",
                            "The Indian Contract Act, 1872", "Section 23"),
    "unstamped_or_invalid_form": ("says the document is unstamped, or waives stamp duty, registration or another legal formality",
                                  "The Indian Stamp Act, 1899", "Section 35"),
    "personal_data_without_consent": ("allows collecting, selling or using personal data without notice or consent",
                                      "The Digital Personal Data Protection Act, 2023", "Section 6"),
    "none": ("an ordinary clause an Indian court would enforce as written", None, None),
}

# Only clauses of these types (or with no label) are worth the extra Kev call in the pipeline.
RISK_TYPES = {"exclusivity_and_restraint", "remedies", "liquidated_damages", "dispute_resolution", "arbitration",
              "termination", "payment_and_fees", "data_protection", "stamp_duty", "compliance_and_law", "other"}


def request(clause_text: str) -> dict:
    return {
        "state": f"A clause from a commercial or employment contract governed by Indian law:\n\n{clause_text[:2000]}",
        "questions": {"risk": {
            "type": "choice",
            "instructions": "Which legal risk under Indian law does this clause carry, if any?",
            "criteria": {k: v[0] for k, v in CATEGORIES.items()},
        }},
    }


def assess(clause_text: str) -> dict:
    from legalagent.core.local_judge import post_with_retry
    ans = post_with_retry(request(clause_text))["answers"]["risk"]
    return {"choice": ans["choice"], "probabilities": ans["probabilities"], "confidence": ans.get("confidence")}


def flag(probs: dict, tau: float = 0.5) -> str:
    """Category if P(none) < tau (then the most likely risk), else 'none'."""
    if float(probs.get("none", 0.0)) >= tau:
        return "none"
    return max((k for k in probs if k != "none"), key=lambda k: float(probs[k]))


def confidence_label(p: float) -> str:
    return "high" if p >= 0.7 else "medium" if p >= 0.45 else "low"


def kev_statutory_findings(clauses: list[Clause], show_from: float = 0.3, max_clauses: int = 150) -> list[Finding]:
    """
    Pipeline hook: Kev-based clause-vs-Indian-law findings for risk-typed clauses.
    Weak signals are SHOWN with a confidence label rather than hidden: any clause whose
    P(some risk) >= show_from becomes a finding marked high / medium / low confidence.
    (Evaluation: 6/9 struck-down Supreme Court clauses caught at P>=0.5, but it also flags
    clauses the court upheld — hence confidence labels and a reviewer, not a verdict.)
    """
    from legalagent.core import local_judge
    if not local_judge.available():
        return []
    out = []
    cands = [c for c in clauses if ({l["label"] for l in c.labels} or {"other"}) & RISK_TYPES][:max_clauses]
    for c in cands:
        try:
            r = assess(c.text)
        except Exception:   # one clause Kev could not read must not drop the others
            continue
        probs = r["probabilities"]
        risk = round(1.0 - float(probs.get("none", 0.0)), 3)
        if risk < show_from:
            continue
        cat = max((k for k in probs if k != "none"), key=lambda k: float(probs[k]))
        desc, act, sec = CATEGORIES[cat]
        conf = confidence_label(risk)
        out.append(Finding(
            id=f"finding_{uuid.uuid4().hex[:8]}", target_clause_id=c.id, related_clause_ids=[],
            relation_type="statutory_violation",
            severity={"high": "high", "medium": "medium", "low": "low"}[conf], risk_score=risk,
            rationale=(f"[{conf} confidence, p={risk:.2f}] Kev reads this clause as one that {desc}. "
                       f"A court would test it under {act}, {sec}."),
            surfaced_by=["kev_statutory"], evidence=[{"clause_id": c.id, "start": 0, "end": len(c.text)}],
            refs=[{"source": act, "section": sec, "snippet": desc}],
            scores={"analysis_confidence": risk, "confidence_label": conf, "risk_probs": probs},
        ))
    return out
