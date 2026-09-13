"""
Smoke test: pipeline works end-to-end.
Tests: types → ingestion → extraction → classification → candidate selection
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.pipeline import analyse
from core.types import Clause, Finding, Run


def test_smoke():
    """
    Load a fixture contract, run the full pipeline, validate structure.
    """
    # Minimal fixture contract text
    fixture_text = """
    1. Term and Termination

    This Agreement shall commence on the Effective Date and continue for one (1) year.
    Either party may terminate this Agreement upon thirty (30) days' written notice.
    The termination provisions shall survive termination of this Agreement.

    2. Limitation of Liability

    In no event shall either party be liable for any consequential damages.
    The aggregate liability of either party shall not exceed the fees paid in the prior year.

    3. Indemnification

    Each party shall indemnify and hold harmless the other from any claims.
    This indemnification shall survive termination.

    4. Confidentiality

    Confidential information shall be protected by the receiving party.
    Non-disclosure obligations shall survive termination.
    """

    # Write fixture to temp file
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(fixture_text)
        fixture_path = f.name

    try:
        # Run pipeline
        run, clauses, findings = analyse(fixture_path, config={"top_k": 3})

        # Validate structure
        assert isinstance(run, Run), "Run should be Run instance"
        assert isinstance(clauses, list), "Clauses should be list"
        assert isinstance(findings, list), "Findings should be list"
        assert len(clauses) > 0, "Should extract at least one clause"

        # Validate clause structure
        for clause in clauses:
            assert isinstance(clause, Clause)
            assert clause.id, "Clause should have id"
            assert clause.number, "Clause should have number"
            assert clause.char_start >= 0, "char_start should be non-negative"
            assert clause.char_end >= clause.char_start, "char_end should be >= char_start"

        # Validate run stats
        assert run.stats["clauses"] == len(clauses)
        assert run.stats["pairs"] >= 0
        assert run.stats["findings"] + run.stats["no_issue"] == run.stats["pairs"]

        print(f"[OK] Extracted {len(clauses)} clauses")
        print(f"[OK] Generated {run.stats['pairs']} candidate pairs")
        print(f"[OK] Found {run.stats['findings']} findings, {run.stats['no_issue']} no_issue")
        print(f"[OK] Clauses: {[c.number for c in clauses]}")
        print(f"[OK] Labels detected:")
        for clause in clauses:
            if clause.labels:
                print(f"  Clause {clause.number}: {[l['label'] for l in clause.labels]}")

    finally:
        import os
        os.unlink(fixture_path)


if __name__ == "__main__":
    test_smoke()
    print("\n[OK] Smoke test passed")
