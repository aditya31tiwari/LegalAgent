"""
Blind human review of teacher-labelled clause pairs -> research/gold_set/gold.jsonl

    venv/bin/python scripts/review_gold.py --reviewer aryan          # in a terminal; Ctrl-C any time
    venv/bin/python scripts/review_gold.py --prepare --n 120          # (re)build the review sample

The teacher's answer is NOT shown, so the human label is independent. Each answer is saved
immediately; re-running resumes. scripts/validate_teacher.py and eval_all.py judge read the file.

Keys: 1 conflict  2 dependency  3 overlap  4 ambiguity  5 no_issue   s skip   q quit
"""
import argparse
import json
import random
import sys
import textwrap
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLD_DIR = ROOT / "research" / "gold_set"
SAMPLE = GOLD_DIR / "to_review.jsonl"
GOLD = GOLD_DIR / "gold.jsonl"
KEYS = {"1": "conflict", "2": "dependency", "3": "overlap", "4": "ambiguity", "5": "no_issue"}


def prepare(n: int):
    """Stratified sample: ~55% teacher-risky, ~45% teacher-no_issue, Indian pairs included."""
    lab = ROOT / "research" / "teacher_labels"
    pairs = {json.loads(l)["pair_id"]: json.loads(l) for l in (lab / "pairs_to_label.jsonl").read_text(encoding="utf-8").splitlines()}
    labels = {}
    for f in sorted((lab / "labels").glob("agy_*.jsonl")):
        for l in f.read_text(encoding="utf-8").splitlines():
            r = json.loads(l)
            labels.setdefault(r["pair_id"], r)
    rnd = random.Random(42)
    ids = [p for p in labels if p in pairs]
    # Held-out (test-split) pairs first: those are the only ones Kev can be scored on against
    # human labels without leakage. Then Indian pairs (teacher check on our domain), then the rest.
    test = [p for p in ids if pairs[p].get("split") == "test"]
    india = [p for p in ids if pairs[p]["contract"].startswith("india:")]
    rest = [p for p in ids if p not in set(test) | set(india)]

    def strat(pool, k):
        risky = [p for p in pool if labels[p]["relation"] != "no_issue"]
        clean = [p for p in pool if labels[p]["relation"] == "no_issue"]
        a = rnd.sample(risky, min(len(risky), int(k * 0.55)))
        return a + rnd.sample(clean, min(len(clean), k - len(a)))

    pick = strat(test, int(n * 0.6))
    pick += strat(india, min(len(india), n // 5))
    pick += strat([p for p in rest if p not in pick], n - len(pick))
    rnd.shuffle(pick)
    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    with SAMPLE.open("w", encoding="utf-8") as f:
        for p in pick[:n]:
            q = pairs[p]
            f.write(json.dumps({k: q[k] for k in ("pair_id", "contract", "a_id", "b_id", "a_text", "b_text")}, ensure_ascii=False) + "\n")
    print(f"wrote {min(n, len(pick))} pairs to review -> {SAMPLE}")


def show(i, n, p):
    w = 100
    print("\n" + "=" * w)
    print(f"[{i}/{n}]  {p['pair_id']}   ({p['contract'][:60]})")
    for tag in ("a", "b"):
        print(f"\n--- Clause {tag.upper()} ---")
        print(textwrap.fill(p[f"{tag}_text"][:1500], w))
    print("\nHow do A and B relate?  1 conflict  2 dependency  3 overlap  4 ambiguity  5 no_issue   s skip  q quit")


def review(reviewer: str):
    if not SAMPLE.exists():
        prepare(120)
    todo = [json.loads(l) for l in SAMPLE.read_text(encoding="utf-8").splitlines() if l.strip()]
    done = {json.loads(l)["pair_id"] for l in GOLD.read_text(encoding="utf-8").splitlines()} if GOLD.exists() else set()
    todo = [p for p in todo if p["pair_id"] not in done]
    total = len(todo) + len(done)
    for i, p in enumerate(todo, len(done) + 1):
        show(i, total, p)
        while True:
            k = input("> ").strip().lower()
            if k in KEYS or k in ("s", "q"):
                break
        if k == "q":
            break
        if k == "s":
            continue
        with GOLD.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"pair_id": p["pair_id"], "human_relation": KEYS[k], "reviewer": reviewer,
                                "at": time.strftime("%Y-%m-%dT%H:%M:%S")}) + "\n")
    n = sum(1 for _ in GOLD.open(encoding="utf-8")) if GOLD.exists() else 0
    print(f"\nsaved {n} human labels in {GOLD}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prepare", action="store_true")
    ap.add_argument("--n", type=int, default=120)
    ap.add_argument("--reviewer", default="team")
    args = ap.parse_args()
    if args.prepare:
        prepare(args.n)
    else:
        try:
            review(args.reviewer)
        except (KeyboardInterrupt, EOFError):
            print("\nstopped — progress saved")


if __name__ == "__main__":
    main()
