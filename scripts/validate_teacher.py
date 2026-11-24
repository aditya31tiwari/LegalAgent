"""
How much can we trust the teacher labels? Every check here uses ground truth that does NOT
come from the teacher.

    venv/bin/python scripts/validate_teacher.py      -> results/teacher_validation.json (+ printed table)

1. checklist      known-answer minimal pairs (scripts/make_checklist.py): BAD pairs must be
                  flagged, their minimally FIXED twins must be no_issue.
2. clause types   teacher's a_types/b_types vs lawyer labels for the same CUAD clauses
                  (CUAD highlights / LEDGAR via CLAUSE-22). Indian clauses have no gold.
3. citations      share of teacher citations that resolve to a real India Code section
                  in the local library (hallucination check).
4. agreement      Cohen's kappa between two teacher model families on shared pairs.
5. human gold     accuracy vs research/gold_set/gold.jsonl (team-verified), if present.
"""
import csv
import glob
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
LAB = ROOT / "research" / "teacher_labels"


def load_jsonl(p):
    p = Path(p)
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.exists() else []


def norm(t: str) -> str:
    from legalagent.core.retrieval import _LEADING_NUMBER_RE
    return re.sub(r"[^a-z0-9]+", " ", _LEADING_NUMBER_RE.sub("", t).lower()).strip()[:150]


def kappa(a, b):
    from sklearn.metrics import cohen_kappa_score
    return float(cohen_kappa_score(a, b)) if len(a) > 1 and len(set(a) | set(b)) > 1 else None


def main():
    out = {}
    label_files = sorted(f for f in glob.glob(str(LAB / "labels" / "agy_*.jsonl")))

    # 1. checklist
    ck_pairs = {r["pair_id"]: r for r in load_jsonl(LAB / "checklist_pairs.jsonl")}
    for f in sorted(glob.glob(str(LAB / "labels" / "checklist_agy_*.jsonl"))):
        labs = {r["pair_id"]: r for r in load_jsonl(f)}
        rows = [(ck_pairs[p], labs[p]) for p in labs if p in ck_pairs]
        if not rows:
            continue
        bad = [(e, l) for e, l in rows if e["expected_risky"]]
        fixed = [(e, l) for e, l in rows if not e["expected_risky"]]
        name = Path(f).stem.replace("checklist_agy_", "")
        out[f"checklist|{name}"] = {
            "pairs": len(rows),
            "risky_detected_on_bad": sum(l["relation"] != "no_issue" for _, l in bad) / max(1, len(bad)),
            "no_issue_on_fixed": sum(l["relation"] == "no_issue" for _, l in fixed) / max(1, len(fixed)),
            "binary_accuracy": sum((l["relation"] != "no_issue") == e["expected_risky"] for e, l in rows) / len(rows),
            "exact_relation_on_bad": sum(l["relation"] == e["expected_relation"] for e, l in bad) / max(1, len(bad)),
            "misses": [e["case"] for e, l in rows if (l["relation"] != "no_issue") != e["expected_risky"]],
        }

    # 2. clause types vs lawyer gold (CUAD/LEDGAR rows of CLAUSE-22)
    csv.field_size_limit(10**9)
    gold = {}
    with open(ROOT / "clause20" / "data" / "CLAUSE20.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            gold[norm(r["text"])] = set(r["labels"].split("|"))
    pairs = {r["pair_id"]: r for r in load_jsonl(LAB / "pairs_to_label.jsonl")}
    for f in label_files:
        hits = tot = top_ok = 0
        for l in load_jsonl(f):
            p = pairs.get(l["pair_id"])
            if not p or "a_types" not in l:
                continue
            for txt, pred in ((p["a_text"], l.get("a_types", [])), (p["b_text"], l.get("b_types", []))):
                g = gold.get(norm(txt))
                if not g or not pred:
                    continue
                tot += 1
                hits += bool(set(pred) & g)
                top_ok += pred[0] in g
        if tot:
            out[f"clause_types_vs_lawyer_gold|{Path(f).stem}"] = {"clauses": tot, "any_overlap": hits / tot, "first_type_correct": top_ok / tot}

    # 3. citation verification
    from legalagent.core.statutes import verify_citation
    for f in label_files:
        labs = [l for l in load_jsonl(f) if l["relation"] != "no_issue"]
        cited = [l for l in labs if l.get("citation")]
        ok = [l for l in cited if verify_citation(l["citation"])]
        out[f"citations|{Path(f).stem}"] = {"flagged_pairs": len(labs), "with_citation": len(cited),
                                            "verified_in_india_code": len(ok), "verified_rate": len(ok) / max(1, len(cited)),
                                            "top_cited": Counter(l["citation"] for l in ok).most_common(5)}

    # 4. agreement between teacher model families
    if len(label_files) >= 2:
        sets = {Path(f).stem: {l["pair_id"]: l["relation"] for l in load_jsonl(f)} for f in label_files}
        names = list(sets)
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                common = sorted(set(sets[names[i]]) & set(sets[names[j]]))
                if len(common) < 20:
                    continue
                a = [sets[names[i]][p] for p in common]
                b = [sets[names[j]][p] for p in common]
                out[f"agreement|{names[i]} vs {names[j]}"] = {
                    "pairs": len(common), "relation_agreement": sum(x == y for x, y in zip(a, b)) / len(common),
                    "relation_kappa": kappa(a, b),
                    "risky_kappa": kappa([x != "no_issue" for x in a], [y != "no_issue" for y in b])}

    # 5. human gold
    human = {g["pair_id"]: g for g in load_jsonl(ROOT / "research" / "gold_set" / "gold.jsonl") if g.get("human_relation")}
    for f in label_files:
        labs = {l["pair_id"]: l for l in load_jsonl(f)}
        common = [p for p in human if p in labs]
        if common:
            out[f"human_gold|{Path(f).stem}"] = {
                "pairs": len(common),
                "relation_accuracy": sum(labs[p]["relation"] == human[p]["human_relation"] for p in common) / len(common),
                "risky_accuracy": sum((labs[p]["relation"] != "no_issue") == (human[p]["human_relation"] != "no_issue") for p in common) / len(common)}

    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "teacher_validation.json").write_text(json.dumps(out, indent=2))
    for k, v in out.items():
        print(f"{k}\n    {json.dumps(v)}")


if __name__ == "__main__":
    main()
