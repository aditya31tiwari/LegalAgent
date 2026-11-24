"""
CUAD interaction pairs: a lawyer-grounded test of the pair judges, built WITHOUT any LLM.

CUAD lawyers annotated which clause in each contract carries which category. Some category
pairs interact by definition (an "Uncapped Liability" clause is a carve-out from the "Cap On
Liability" clause; "Change Of Control" is typically a deemed assignment under "Anti-Assignment").
For every CUAD contract that has both categories on two *different* clauses, the pair is an
expected interaction (risky = relation != no_issue). Clauses are cut by our own extractor
(clause20/build.py interim cuad.csv), exactly as the pipeline sees them.

    venv/bin/python scripts/make_cuad_pairs.py
    -> research/teacher_labels/cuad_interaction_pairs.jsonl   (scored by eval_all.py cuadpairs)
"""
import csv
import json
import random
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research" / "teacher_labels" / "cuad_interaction_pairs.jsonl"

PAIRS = [  # (category A, category B, expected relation family, why)
    ("Cap On Liability", "Uncapped Liability", "conflict/dependency", "uncapped liability is a carve-out from the cap"),
    ("Anti-Assignment", "Change Of Control", "dependency", "change of control is commonly a deemed assignment"),
    ("License Grant", "Ip Ownership Assignment", "dependency", "ownership vs right to use the same IP"),
    ("Termination For Convenience", "Post-Termination Services", "dependency", "obligations continuing after termination"),
    ("Non-Compete", "Post-Termination Services", "dependency", "restraint and duties continuing after the end"),
    ("Exclusivity", "Non-Compete", "overlap", "overlapping restraints on the same party"),
    ("Liquidated Damages", "Cap On Liability", "conflict/dependency", "agreed damages vs the liability ceiling"),
]


def main(per_pair=40, seed=3):
    csv.field_size_limit(10**9)
    rows = list(csv.DictReader(open(ROOT / "clause20" / "data" / "interim" / "cuad.csv", encoding="utf-8")))
    by_doc = defaultdict(list)
    for r in rows:
        by_doc[r["doc_id"]].append(r)
    rnd = random.Random(seed)
    out = []
    for a, b, rel, why in PAIRS:
        cands = []
        for doc, clauses in by_doc.items():
            ca = [c for c in clauses if a in c["src_labels"].split("|")]
            cb = [c for c in clauses if b in c["src_labels"].split("|")]
            for x in ca[:1]:
                y = next((c for c in cb if c["uid"] != x["uid"]), None)
                if y is not None:
                    cands.append((doc, x, y))
        for doc, x, y in rnd.sample(cands, min(per_pair, len(cands))):
            out.append({"pair_id": f"cuad_{len(out):04d}", "contract": f"cuad:{doc}", "split": "cuad_interaction",
                        "a_id": f"cuad::{x['uid']}", "b_id": f"cuad::{y['uid']}", "a_text": x["text"][:1500], "b_text": y["text"][:1500],
                        "a_labels": [], "b_labels": [], "surfaced_by": ["type_matrix"],
                        "cuad_categories": [a, b], "expected_risky": True, "expected_relation": rel, "why": why, "case": f"{a} x {b}"})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out), encoding="utf-8")
    from collections import Counter
    print(f"{len(out)} lawyer-grounded interaction pairs -> {OUT}")
    for k, v in Counter(r["case"] for r in out).items():
        print(f"  {v:3d}  {k}")


if __name__ == "__main__":
    main()
