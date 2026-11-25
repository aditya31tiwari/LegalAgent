#!/bin/sh
''''exec "$(dirname "$0")/../venv/bin/python" "$0" "$@" #'''
"""
Experiment: RAG-based judgement of clause vs Indian law.

For each clause:
  1. Kev's category check (statutory_kev.assess) → most likely risk type + the section it maps to (e.g. ICA s.27)
  2. candidate sections = that mapped section + the top-3 retrieved India Code sections (hybrid RAG)
  3. for EACH section, Kev reads the clause AND the full section text and answers one question:
     violates / complies / not_relevant
  4. RAG verdict = the clause violates some retrieved/mapped section (violates is Kev's top answer for it)

Same ground truth as eval_all.py statutory: 9 struck-down + 4 upheld Supreme Court clauses, 6 planted Pune faults,
30 ordinary CUAD clauses. Writes results/eval_rag_check.json. Does not change the pipeline.
"""
import csv
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from legalagent.core import local_judge as lj
from legalagent.core import statutory_kev as sk
from legalagent.core.statutes import load_library, retrieve_sections


def items():
    out = []
    for c in map(json.loads, (ROOT / "research/litigated_clauses/cases.jsonl").read_text(encoding="utf-8").splitlines()):
        if c["kind"] == "single_clause":
            out.append({"source": "supreme_court", "id": c["case_id"], "text": c["clause_a"]["text"], "risky": c["expected_flag"]})
    inj = {i["number"]: i["text"] for i in json.loads((ROOT / "data/demo/india/adversarial/INJECTIONS.json").read_text())["injections"]}
    for n in ("91.3", "91.5", "91.6", "91.7", "91.13", "91.9"):
        out.append({"source": "pune_injection", "id": n, "text": f"{n} {inj[n]}", "risky": True})
    csv.field_size_limit(10**9)
    benign = {"Governing Law", "Notice Period To Terminate Renewal", "Insurance", "Audit Rights", "Renewal Term", "Expiration Date"}
    rows = [r for r in csv.DictReader(open(ROOT / "clause20/data/interim/cuad.csv", encoding="utf-8"))
            if set(r["src_labels"].split("|")) <= benign and 15 < int(r["n_words"]) < 150]
    for r in random.Random(5).sample(rows, min(30, len(rows))):
        out.append({"source": "cuad_ordinary", "id": r["uid"], "text": r["text"], "risky": False})
    return out


def verdict_request(clause: str, s: dict) -> dict:
    law = " ".join(s["text"].split())[:1800]
    return {
        "state": (f"A clause from a contract governed by Indian law:\n\n{clause[:1500]}\n\n"
                  f"Indian law — {s['act']}, Section {s['section']} ({s['heading']}):\n{law}"),
        "questions": {"verdict": {
            "type": "choice",
            "instructions": "Read the clause and the law. Does the clause violate this section of Indian law?",
            "criteria": {
                "violates": "the clause does what this section prohibits or makes void, so a court applying this section would not enforce it as written",
                "complies": "the section is about this kind of clause, but the clause stays within what the section allows",
                "not_relevant": "this section does not govern what the clause is about",
            },
        }},
    }


def main():
    lib = {(s["act"], str(s["section"])): s for s in load_library()}
    rows = []
    for it in items():
        cat = sk.assess(it["text"])["probabilities"]
        top = max((k for k in cat if k != "none"), key=lambda k: float(cat[k]))
        p_risk = 1 - float(cat.get("none", 0))
        _, act, sec = sk.CATEGORIES[top]
        cands = []
        if act and (act, sec.replace("Section ", "")) in lib:
            cands.append(("mapped", lib[(act, sec.replace("Section ", ""))]))
        for s, _ in retrieve_sections(it["text"][:900], k=3):
            if all(s is not c[1] for c in cands):
                cands.append(("retrieved", s))
        checks = []
        for how, s in cands:
            a = lj._post(verdict_request(it["text"], s))["answers"]["verdict"]
            checks.append({"how": how, "section": f"{s['act']} s.{s['section']}", "choice": a["choice"],
                           "p": {k: round(float(v), 4) for k, v in a["probabilities"].items()}})
        viol = [c for c in checks if c["choice"] == "violates"]
        best = max(checks, key=lambda c: c["p"].get("violates", 0)) if checks else None
        rows.append({**{k: it[k] for k in ("source", "id", "risky")}, "category": top, "p_risk": round(p_risk, 4),
                     "kev_category_flag": p_risk >= 0.5, "rag_flag": bool(viol),
                     "rag_violated": [c["section"] for c in viol],
                     "rag_mapped_violates": any(c["how"] == "mapped" and c["choice"] == "violates" for c in checks),
                     "max_p_violates": best["p"].get("violates", 0) if best else 0, "checks": checks})
        print(f"{it['source'][:6]:6s} {it['id'][:28]:28s} risky={it['risky']!s:5s} cat={p_risk:.2f} rag={bool(viol)!s:5s} "
              f"{'; '.join(c['section'] for c in viol)[:70]}", flush=True)

    def summ(key):
        s = {}
        for src in ("supreme_court", "pune_injection", "cuad_ordinary"):
            r = [x for x in rows if x["source"] == src]
            s[src] = {"caught": sum(x[key] for x in r if x["risky"]), "risky": sum(x["risky"] for x in r),
                      "false_alarms": sum(x[key] for x in r if not x["risky"]), "safe": sum(not x["risky"] for x in r)}
        return s
    for r in rows:
        r["both"] = r["kev_category_flag"] and r["rag_flag"]
    res = {"rules": {k: summ(k) for k in ("kev_category_flag", "rag_flag", "both")}, "items": rows}
    (ROOT / "results" / "eval_rag_check.json").write_text(json.dumps(res, indent=2))
    print()
    for k, v in res["rules"].items():
        print(f"{k:18s} " + " | ".join(f"{src}: caught {x['caught']}/{x['risky']}, false {x['false_alarms']}/{x['safe']}" for src, x in v.items()))


if __name__ == "__main__":
    main()
