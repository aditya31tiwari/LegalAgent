import uuid
from core.types import Run, Clause, Finding
from core.ingestion import ingest
from core.extraction import extract
from core.classification import classify
from core.candidate_selection import select_candidates


def analyse_pair_stub(clause_a: Clause, clause_b: Clause) -> Finding | None:
    """
    Stub analysis: returns no_issue for now.
    ponytail: stub until LLM layer is built; returns None to skip finding.
    """
    return None


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

    # Analysis (stub: always returns findings list)
    findings = []
    no_issue_count = 0

    for clause_a_id, clause_b_id, surfaced_by in pairs:
        clause_a = next(c for c in clauses if c.id == clause_a_id)
        clause_b = next(c for c in clauses if c.id == clause_b_id)

        finding = analyse_pair_stub(clause_a, clause_b)
        if finding is None:
            no_issue_count += 1
        else:
            findings.append(finding)

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
