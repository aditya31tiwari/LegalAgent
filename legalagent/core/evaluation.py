"""
Retrieval evaluation: BM25 vs dense vs hybrid, scored against gold clause pairs.

The gold set is derived from the contract's own cross-references. When clause 5.2
says "subject to Section 8.2", the drafter has asserted that those two clauses are
related — a ground-truth label the document labels for free, with no annotator.

Two limits worth stating before anyone quotes a number from this:

  1. Cross-references are *precise but incomplete*. Every gold pair is genuinely
     related; many genuinely related pairs are never cross-referenced. So recall
     here is recall against explicit links only, and a method is not penalised
     for surfacing an unreferenced pair that a lawyer would still care about.
  2. It follows that absolute values matter less than the ranking between the
     three methods, which all face the identical handicap.
"""
from legalagent.core.types import Clause
from legalagent.core.retrieval import retrieve, METHODS, DEFAULT_MODEL

DEFAULT_K_VALUES = (1, 3, 5, 10)


def gold_pairs(clauses: list[Clause]) -> dict[str, set[str]]:
    """
    {clause_id: {related_clause_id, ...}} from resolved cross-references.

    Symmetric: if 5.2 cites 8.2 then 8.2 is also treated as related to 5.2.
    Relatedness is the property being retrieved, and it does not have a direction
    — candidate_selection emits unordered pairs for exactly the same reason.
    """
    gold: dict[str, set[str]] = {}
    for clause in clauses:
        for xref in clause.xrefs:
            target = xref["clause_id"]
            if not xref["resolved"] or target == clause.id:
                continue
            gold.setdefault(clause.id, set()).add(target)
            gold.setdefault(target, set()).add(clause.id)
    return gold


def score_method(
    clauses: list[Clause],
    method: str,
    k_values=DEFAULT_K_VALUES,
    model_name: str = DEFAULT_MODEL,
) -> dict:
    """
    Precision/recall/F1 at each k for one retrieval method.

    Macro-averaged over query clauses that have at least one gold neighbour —
    a clause with no cross-reference gives no signal about whether retrieval
    got it right, so averaging it in as a zero would just measure how sparsely
    the contract happens to be cross-referenced.
    """
    gold = gold_pairs(clauses)
    queries = [c.id for c in clauses if gold.get(c.id)]

    if not queries:
        return {"method": method, "queries": 0, "gold_pairs": 0, "at_k": {}}

    # Retrieve once at the deepest k, then truncate — the ranking is a prefix,
    # so re-running the retriever per k would be identical work for identical results.
    max_k = max(k_values)
    ranked = retrieve(clauses, method=method, k=max_k, model_name=model_name)

    at_k = {}
    for k in k_values:
        precisions, recalls = [], []
        for qid in queries:
            retrieved = [cid for cid, _ in ranked.get(qid, [])[:k]]
            relevant = gold[qid]
            hits = len(set(retrieved) & relevant)
            precisions.append(hits / k)
            recalls.append(hits / len(relevant))

        precision = sum(precisions) / len(precisions)
        recall = sum(recalls) / len(recalls)
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        at_k[k] = {"precision": precision, "recall": recall, "f1": f1}

    return {
        "method": method,
        "queries": len(queries),
        "gold_pairs": sum(len(v) for v in gold.values()) // 2,
        "at_k": at_k,
    }


def compare(
    clauses: list[Clause],
    methods=METHODS,
    k_values=DEFAULT_K_VALUES,
    model_name: str = DEFAULT_MODEL,
) -> dict:
    """
    Run every method over the same clauses and the same gold set.

    A method that raises (dense without sentence-transformers installed, say) is
    recorded with its error rather than aborting the comparison — a missing arm
    should not cost you the two that do work.
    """
    results = {}
    for method in methods:
        try:
            results[method] = score_method(clauses, method, k_values, model_name)
        except Exception as exc:
            results[method] = {"method": method, "error": f"{type(exc).__name__}: {exc}"}
    return results


def format_table(results: dict, k_values=DEFAULT_K_VALUES) -> str:
    """Fixed-width P/R/F1 table, one row per method per k."""
    ok = {m: r for m, r in results.items() if "error" not in r and r.get("at_k")}

    lines = []
    if ok:
        sample = next(iter(ok.values()))
        lines.append(
            f"{sample['queries']} query clauses, {sample['gold_pairs']} gold pairs "
            f"(from resolved cross-references)"
        )
        lines.append("")
        lines.append(f"{'method':<10}{'k':>4}{'P@k':>9}{'R@k':>9}{'F1':>9}")
        lines.append("-" * 41)
        for method, result in ok.items():
            for k in k_values:
                m = result["at_k"][k]
                lines.append(
                    f"{method:<10}{k:>4}{m['precision']:>9.3f}"
                    f"{m['recall']:>9.3f}{m['f1']:>9.3f}"
                )
            lines.append("")

        # Best F1 per k, so the comparison has a readable verdict rather than
        # leaving the reader to eyeball twelve rows.
        lines.append("best F1 by k:")
        for k in k_values:
            winner = max(ok.items(), key=lambda kv: kv[1]["at_k"][k]["f1"])
            lines.append(f"  k={k}: {winner[0]} ({winner[1]['at_k'][k]['f1']:.3f})")

    for method, result in results.items():
        if "error" in result:
            lines.append(f"{method}: SKIPPED — {result['error']}")
        elif not result.get("at_k"):
            lines.append(f"{method}: no gold pairs — contract has no resolved cross-references")

    return "\n".join(lines)
