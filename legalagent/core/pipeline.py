import logging
import uuid

from legalagent.core.types import Run, Clause, Finding
from legalagent.core.ingestion import ingest
from legalagent.core.extraction import extract
from legalagent.core.classification import classify
from legalagent.core.candidate_selection import select_candidates
from legalagent.core.analysis import analyse_pair, analyse_statutory, validate_findings

logger = logging.getLogger(__name__)


def _run_gemini_analysis(
    pairs_data: list[tuple[str, str, list[str]]],
    clauses: list[Clause],
    config: dict,
) -> tuple[list[Finding], int]:
    """Send all shortlisted pairs to Gemini for structured analysis.

    Returns (findings, no_issue_count).
    Falls back to deterministic analysis if Gemini is unavailable or fails.
    """
    from legalagent.core.gemini import GeminiConfigurationError
    from legalagent.core.gemini_analysis import analyse_pairs_with_gemini

    clauses_by_id = {c.id: c for c in clauses}
    pair_objects = [
        (clauses_by_id[a_id], clauses_by_id[b_id], surfaced_by)
        for a_id, b_id, surfaced_by in pairs_data
    ]

    try:
        results = analyse_pairs_with_gemini(pair_objects, model=config.get("gemini_model"))
        findings = [f for f in results if f is not None]
        no_issue_count = sum(1 for f in results if f is None)
        logger.info("Gemini analysis complete: %d findings, %d no-issue pairs", len(findings), no_issue_count)
        return findings, no_issue_count
    except GeminiConfigurationError as exc:
        logger.warning("Gemini unavailable (%s) — falling back to deterministic analysis", exc)
        return _run_deterministic_analysis(pair_objects)


def _run_deterministic_analysis(
    pair_objects: list[tuple[Clause, Clause, list[str]]],
) -> tuple[list[Finding], int]:
    """Deterministic baseline: pattern-match rules, no API calls."""
    findings = []
    no_issue_count = 0
    for clause_a, clause_b, surfaced_by in pair_objects:
        finding = analyse_pair(clause_a, clause_b, surfaced_by)
        if finding is None:
            no_issue_count += 1
        else:
            findings.append(finding)
    return findings, no_issue_count


def analyse(file_path: str, config: dict, contract_id: str = "local") -> tuple[Run, list[Clause], list[Finding]]:
    """
    Full analysis pipeline.

    Set ``config["use_gemini"] = True`` to route candidate pairs through
    Gemini for structured conflict classification.  Falls back to the
    deterministic baseline automatically when the API key is absent or any
    network / parse error occurs.

    Pipeline stages:
        ingest -> extract -> classify -> select_candidates
        -> [Gemini | deterministic] analysis
        -> analyse_statutory (deterministic, always runs)
        -> validate_findings
    """
    # Ingestion
    text = ingest(file_path)

    # Extraction
    clauses = extract(text, contract_id)

    # Classification
    clauses = classify(clauses)

    # Candidate selection (BM25 + SBERT + xrefs + type matrix)
    pairs = select_candidates(clauses, config)

    # Cross-clause analysis
    use_gemini = config.get("use_gemini", False)
    if use_gemini:
        logger.info("Gemini analysis enabled — sending %d pairs to Gemini", len(pairs))
        pair_findings, no_issue_count = _run_gemini_analysis(pairs, clauses, config)
    else:
        clauses_by_id = {c.id: c for c in clauses}
        pair_objects = [
            (clauses_by_id[a_id], clauses_by_id[b_id], surfaced_by)
            for a_id, b_id, surfaced_by in pairs
        ]
        pair_findings, no_issue_count = _run_deterministic_analysis(pair_objects)

    findings = list(pair_findings)

    # Statutory checks (always deterministic — no Gemini needed for clear-cut rules)
    findings.extend(analyse_statutory(clauses, config.get("jurisdiction", "India")))
    validate_findings(findings, clauses)

    # Build run metadata
    run_id = f"run_{uuid.uuid4().hex[:8]}"
    run = Run(
        id=run_id,
        contract_id=contract_id,
        config={**{"retrieval_method": "bm25", "top_k": 5}, **(config or {})},
        stats={
            "clauses": len(clauses),
            "pairs": len(pairs),
            "findings": len(findings),
            "no_issue": no_issue_count,
            "gemini_powered": use_gemini,
        },
    )

    # Rank by severity then risk score
    findings.sort(
        key=lambda f: ({"high": 0, "medium": 1, "low": 2}.get(f.severity, 3), -f.risk_score)
    )

    return run, clauses, findings
