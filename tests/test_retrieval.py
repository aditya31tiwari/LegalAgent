"""
Retrieval + evaluation tests.

The load-bearing one is test_index_text_removes_gold_signal: the gold set is built
from cross-references, so if cross-reference text survives into the indexed text,
every method is scored on a label it was handed. That failing quietly would not
break the pipeline — it would just produce impressive numbers that mean nothing.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from legalagent.core.ingestion import ingest
from legalagent.core.extraction import extract
from legalagent.core.retrieval import retrieve, index_text, METHODS
from legalagent.core.evaluation import gold_pairs, score_method, compare

FIXTURE = Path(__file__).parent / "fixtures" / "sample_msa.txt"


@pytest.fixture(scope="module")
def clauses():
    return extract(ingest(str(FIXTURE)), "acme_msa")


def test_fixture_has_enough_signal(clauses):
    """A handful of clauses cannot distinguish three retrieval methods."""
    assert len(clauses) >= 20
    gold = gold_pairs(clauses)
    assert sum(len(v) for v in gold.values()) // 2 >= 10


def test_index_text_removes_gold_signal(clauses):
    """
    Indexed text must contain neither the clause's own number nor any
    cross-reference phrase — both hand the retriever the gold label directly.
    """
    citing = [c for c in clauses if c.xrefs]
    assert citing, "fixture must contain cross-references"

    for clause in citing:
        indexed = index_text(clause)
        for xref in clause.xrefs:
            assert xref["raw"] not in indexed, f"{clause.id} leaks {xref['raw']!r}"
        # The cited number must not survive on its own either ("8.2" is as
        # much of a giveaway as "Section 8.2").
        for xref in clause.xrefs:
            cited = xref["clause_id"].split("::")[1]
            assert cited not in indexed.split(), f"{clause.id} leaks bare {cited!r}"

    for clause in clauses:
        assert not index_text(clause).startswith(clause.number)


def test_bm25_ranking_shape(clauses):
    ranked = retrieve(clauses, method="bm25", k=5)
    assert set(ranked) == {c.id for c in clauses}
    for qid, neighbours in ranked.items():
        assert len(neighbours) <= 5
        assert qid not in [cid for cid, _ in neighbours]
        scores = [s for _, s in neighbours]
        assert scores == sorted(scores, reverse=True), "must be ordered best-first"


def test_retrieve_rejects_unknown_method(clauses):
    with pytest.raises(ValueError):
        retrieve(clauses, method="magic")


def test_retrieve_is_deterministic(clauses):
    """Two runs must agree, or no reported number is reproducible."""
    assert retrieve(clauses, method="bm25", k=5) == retrieve(clauses, method="bm25", k=5)


def test_gold_pairs_are_symmetric_and_resolved(clauses):
    gold = gold_pairs(clauses)
    ids = {c.id for c in clauses}
    for qid, targets in gold.items():
        assert qid in ids
        for target in targets:
            assert target in ids, "gold pairs must only contain resolved references"
            assert qid in gold[target], "relatedness must be symmetric"
            assert target != qid


def test_metrics_are_well_formed_and_recall_grows(clauses):
    result = score_method(clauses, "bm25", k_values=(1, 3, 5, 10))
    assert result["queries"] > 0

    recalls = []
    for k in (1, 3, 5, 10):
        m = result["at_k"][k]
        for name in ("precision", "recall", "f1"):
            assert 0.0 <= m[name] <= 1.0, f"{name}@{k} out of range"
        recalls.append(m["recall"])

    # Deeper k can only ever find more of the gold set, never less.
    assert recalls == sorted(recalls), f"recall must be non-decreasing in k: {recalls}"


def test_compare_survives_a_missing_backend(clauses):
    """
    A method that cannot run is reported, not raised — one missing arm must not
    cost the arms that do work.
    """
    results = compare(clauses, methods=METHODS, k_values=(1, 5))
    assert set(results) == set(METHODS)
    for method, result in results.items():
        assert "error" in result or result["at_k"], f"{method} returned nothing"


@pytest.mark.parametrize("method", ["dense", "hybrid"])
def test_dense_and_hybrid_when_available(clauses, method):
    pytest.importorskip("sentence_transformers")
    ranked = retrieve(clauses, method=method, k=5)
    assert set(ranked) == {c.id for c in clauses}
    for qid, neighbours in ranked.items():
        assert qid not in [cid for cid, _ in neighbours]
        assert len(neighbours) <= 5
