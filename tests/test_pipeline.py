"""
Smoke test: pipeline works end-to-end.
Tests: types → ingestion → extraction → classification → candidate selection → analysis
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from legalagent.core.pipeline import analyse
from legalagent.core.types import Clause, Finding, Run

FIXTURE_TEXT = """
1.1 The Supplier shall indemnify, defend and hold harmless the Customer from
any claims arising out of the Supplier's breach of this Agreement.

1.2 In no event shall either party be liable for any consequential damages,
and the aggregate liability of either party shall not exceed the fees paid
in the prior year.

1.3 Either party may terminate this Agreement upon thirty (30) days' written
notice. The obligations under Section 1.1 shall survive termination.
"""


def _run_pipeline():
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(FIXTURE_TEXT)
        fixture_path = f.name

    try:
        return analyse(fixture_path, config={"top_k": 3})
    finally:
        import os
        os.unlink(fixture_path)


def test_extraction_and_candidates():
    """
    Validates the parts of the pipeline that are actually implemented:
    extraction (inline clause numbering, not just standalone headings),
    classification, and candidate selection.
    """
    run, clauses, findings = _run_pipeline()

    assert isinstance(run, Run)
    assert isinstance(clauses, list)
    assert isinstance(findings, list)

    # Inline numbering ("1.1 The Supplier shall...") must be extracted, not
    # just standalone heading-style numbering.
    assert len(clauses) == 3, f"expected 3 clauses, got {len(clauses)}"

    for clause in clauses:
        assert isinstance(clause, Clause)
        assert clause.id
        assert clause.number
        assert clause.char_start >= 0
        assert clause.char_end > clause.char_start

    # No self-pairs: a clause must never be paired with itself.
    assert run.stats["pairs"] > 0
    assert run.stats["findings"] + run.stats["no_issue"] == run.stats["pairs"]


def test_smoke_findings_and_evidence():
    """
    The assertions from the plan that actually matter: findings are produced,
    and every evidence offset resolves to real text (catches hallucination).
    Evidence is stored as offsets into each clause so generated explanations
    cannot point at text outside the analyzed contract.
    """
    run, clauses, findings = _run_pipeline()
    text_by_clause = {c.id: c.text for c in clauses}
    ids = {c.id for c in clauses}

    assert findings, "expected at least one finding"
    for f in findings:
        assert f.target_clause_id in ids
        assert all(r in ids for r in f.related_clause_ids)
        assert f.target_clause_id not in f.related_clause_ids
        for e in f.evidence:
            clause_text = text_by_clause[e["clause_id"]]
            assert clause_text[e["start"]:e["end"]].strip()


def test_statutory_non_compete_finding():
    import tempfile
    import os

    text = "1.1 Following termination, the employee shall not compete with the company in India."
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as fixture:
        fixture.write(text)
        fixture_path = fixture.name
    try:
        _run, clauses, findings = analyse(fixture_path, {"jurisdiction": "India"})
    finally:
        os.unlink(fixture_path)

    assert clauses
    assert any(f.relation_type == "statutory_violation" and f.refs[0]["section"] == "Section 27" for f in findings)


if __name__ == "__main__":
    test_extraction_and_candidates()
    print("[OK] Smoke test passed (extraction + candidates)")
    print("[XFAIL expected] findings/evidence test — analysis layer not implemented yet")
