import uuid
from legalagent.core.types import Run, Clause, Finding
from legalagent.core.ingestion import ingest
from legalagent.core.extraction import extract
from legalagent.core.classification import classify
from legalagent.core.candidate_selection import select_candidates
from legalagent.core.analysis import analyse_pair, analyse_statutory, validate_findings


def analyse(file_path: str, config: dict, contract_id: str = "local") -> tuple[Run, list[Clause], list[Finding]]:
    """
    The pipeline skeleton: every stage callable.
    Day 1–8 implementation.
    """
    # Ingestion
    text = ingest(file_path)

    # Extraction
    clauses = extract(text, contract_id)

    # Classification
    clauses = classify(clauses)

    # Candidate selection
    pairs = select_candidates(clauses, config)

    # Cross-clause analysis. This deterministic adapter is the testable baseline;
    # a Gemini adapter can later implement the same Finding contract.
    findings = []
    no_issue_count = 0

    for clause_a_id, clause_b_id, surfaced_by in pairs:
        clause_a = next(c for c in clauses if c.id == clause_a_id)
        clause_b = next(c for c in clauses if c.id == clause_b_id)

        finding = analyse_pair(clause_a, clause_b, surfaced_by)
        if finding is None:
            no_issue_count += 1
        else:
            findings.append(finding)

    findings.extend(analyse_statutory(clauses, config.get("jurisdiction", "India")))
    validate_findings(findings, clauses)

    # Build run metadata
    run_id = f"run_{uuid.uuid4().hex[:8]}"
    run = Run(
        id=run_id,
        contract_id=contract_id,
        config=config or {"retrieval_method": "bm25", "top_k": 5},
        stats={
            "clauses": len(clauses),
            "pairs": len(pairs),
            "findings": len(findings),
            "no_issue": no_issue_count,
        }
    )

    # Rank findings (stub: by severity then retrieval score)
    findings.sort(
        key=lambda f: ({"high": 0, "medium": 1, "low": 2}.get(f.severity, 3), -f.risk_score)
    )

    return run, clauses, findings
