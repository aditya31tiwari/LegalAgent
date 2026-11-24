"""
Turn the Gemini-labelled clause pairs (data/derived/judge_pairs.jsonl) into Kev
training records (System One request + labels), using the exact request builder the
live judge uses (legalagent.core.local_judge.pair_request).

    venv/bin/python train/export_kev_data.py
    -> data/derived/kev/train.jsonl, data/derived/kev/test.jsonl

Then fine-tune in Kev's own environment (see train/finetune_kev.sh).

Statute label: the teacher's free-text citation is resolved against the statute
library (core.statutes.verify_citation). If it resolves, that section is the label
(inserted into the options if retrieval missed it); otherwise the label is "none".
"""
import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from legalagent.core.types import Clause  # noqa: E402
from legalagent.core.local_judge import pair_request, statute_options, _statute_key, SEVERITIES  # noqa: E402
from legalagent.core.statutes import verify_citation  # noqa: E402

SRC = ROOT / "data" / "derived" / "judge_pairs.jsonl"
OUT = ROOT / "data" / "derived" / "kev"


def clause(cid, text, labels):
    number = cid.split("::")[1] if "::" in cid else cid
    return Clause(id=cid, contract_id=cid.split("::")[0], number=number, text=text,
                  labels=[{"label": l} for l in labels])


def current_types(rows: list[dict]) -> dict[tuple[str, str], list[str]]:
    """
    Clause types from the CURRENT production classifier (CLAUSE-22: best backend on disk +
    Indian known-gap rules) for every clause in `rows`. The exported pairs carry the type
    hints computed at export time (CLAUSE-20); re-classifying keeps Kev's training input in
    the same label vocabulary it will see at inference.
    """
    from legalagent.core.classification import classify
    uniq = {}
    for r in rows:
        for side in ("a", "b"):
            uniq.setdefault((r[f"{side}_id"], r[f"{side}_text"]), None)
    keys = list(uniq)
    cl = classify([Clause(id=f"k{i}", contract_id="x", text=t) for i, (_, t) in enumerate(keys)], backend="auto")
    return {k: [l["label"] for l in c.labels] for k, c in zip(keys, cl)}


def main():
    rows = [json.loads(l) for l in SRC.read_text(encoding="utf-8").splitlines() if l.strip()]
    OUT.mkdir(parents=True, exist_ok=True)
    rnd = random.Random(0)
    files = {s: (OUT / f"{s}.jsonl").open("w", encoding="utf-8") for s in ("train", "test")}
    stats = Counter()
    types = current_types(rows)
    for r in rows:
        a = clause(r["a_id"], r["a_text"], types[(r["a_id"], r["a_text"])])
        b = clause(r["b_id"], r["b_text"], types[(r["b_id"], r["b_text"])])
        sections = statute_options(a, b)
        cited = verify_citation(r.get("citation", "")) if r["relation"] != "no_issue" else None
        if cited and _statute_key(cited) not in {_statute_key(s) for s in sections}:
            sections = [*sections[:-1], cited] if sections else [cited]
            rnd.shuffle(sections)
        req = pair_request(a, b, r["surfaced_by"], sections)
        q = req["questions"]
        q["relation"]["label"] = r["relation"]
        q["severity"]["label"] = 0 if r["relation"] == "no_issue" else SEVERITIES.index(r["severity"])
        q["statute"]["label"] = _statute_key(cited) if cited else "none"
        req["_meta"] = {"group_id": r["contract"]}
        files[r["split"]].write(json.dumps(req, ensure_ascii=False) + "\n")
        stats[(r["split"], r["relation"])] += 1
        stats[(r["split"], "statute_labelled" if cited else "statute_none")] += 1
    for f in files.values():
        f.close()
    for k, v in sorted(stats.items()):
        print(f"{k[0]:5s} {k[1]:18s} {v}")


if __name__ == "__main__":
    main()
