#!/bin/sh
''''exec "$(dirname "$0")/../venv/bin/python" "$0" "$@" #'''
"""
Terminal playground: paste two clauses, see what every LegalAgent component computes.

    venv/bin/python scripts/playground.py                       # interactive: paste A, blank line, paste B, blank line
    venv/bin/python scripts/playground.py --example cap         # built-in example (cap | survival | arbitration | clean)
    venv/bin/python scripts/playground.py --a "12.1 ..." --b "14.2 ..." [--gemini] [--json]

Kev servers: fine-tuned on :8008, base on :8009 (bash scripts/start_demo.sh starts :8008;
`cd ~/Projects/kev && .venv/bin/python -m kev.serve --run jaredpalmer/kev-0.8b --port 8009` for base).
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

EXAMPLES = {
    "cap": ("12.1 The aggregate liability of the Supplier under this Agreement shall not exceed the fees paid in the preceding twelve months.",
            "14.2 The Supplier shall indemnify the Customer against all losses arising from third-party IP claims, without limit and notwithstanding Clause 12.1."),
    "survival": ("18.4 On expiry or termination, only Clauses 9 (Payment) and 21 (Governing Law) shall survive.",
                 "11.1 Each party shall keep the other's Confidential Information confidential for five years from disclosure."),
    "arbitration": ("22.1 All disputes shall be finally resolved by arbitration seated in New Delhi under the Arbitration and Conciliation Act, 1996.",
                    "22.4 The courts at Mumbai shall have exclusive jurisdiction to decide all disputes arising out of this Agreement on their merits."),
    "clean": ("12.1 The aggregate liability of the Supplier shall not exceed the fees paid in the preceding twelve months.",
              "14.2 Subject to the limitation in Clause 12.1, the Supplier shall indemnify the Customer against third-party IP claims."),
}


def read_block(prompt):
    print(prompt + " (end with an empty line):")
    lines = []
    for line in sys.stdin:
        if not line.strip():
            break
        lines.append(line.rstrip("\n"))
    return " ".join(lines)


def bar(p, width=24):
    p = max(0.0, min(1.0, float(p)))
    return "█" * int(round(p * width)) + "·" * (width - int(round(p * width)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--a"); ap.add_argument("--b")
    ap.add_argument("--example", choices=list(EXAMPLES))
    ap.add_argument("--gemini", action="store_true", help="also ask Gemini (sends both clauses to Google)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if args.example:
        a, b = EXAMPLES[args.example]
    else:
        a = args.a or read_block("Clause A")
        b = args.b or read_block("Clause B")

    from legalagent.core.playground import compare_pair
    r = compare_pair(a, b, use_gemini=args.gemini)
    if args.json:
        print(json.dumps(r, indent=2, default=str)); return

    print("\n=== clause types ===")
    for name, rows in r["classifiers"].items():
        if isinstance(rows, dict):
            print(f"  {name}: {rows}"); continue
        for tag, row in zip("AB", rows):
            print(f"  {name:12s} {tag}: " + ", ".join(f"{x['label']} {x['p']:.2f}" for x in row[:3]))
    print("  final labels  A:", [l["label"] for l in r["labels"]["A"]], " B:", [l["label"] for l in r["labels"]["B"]])

    print("\n=== similarity / shortlisting signals ===")
    for k, v in r["similarity"].items():
        print(f"  {k:22s} {v}")

    print("\n=== judges ===")
    for name, j in r["judges"].items():
        if j.get("available") is False:
            print(f"  {name:14s} (server not running)"); continue
        if "error" in j:
            print(f"  {name:14s} error: {j['error']}"); continue
        print(f"  {name:14s} → {j.get('relation')}" + (f"   ({j['ms']} ms)" if j.get("ms") else ""))
        for rel, p in (j.get("relation_probs") or {}).items():
            print(f"      {rel:11s} {bar(p)} {float(p):.3f}")
        if j.get("statute"):
            print(f"      statute pick: {j['statute']}")
        if j.get("rationale"):
            print(f"      {j['rationale'][:160]}")
        for s in j.get("statutory_flags", []):
            print(f"      statutory: {s[:160]}")

    print("\n=== GNN ===")
    print("  ", r["gnn"])
    print("\n=== Indian law retrieved (RAG) ===")
    if isinstance(r["statutes"], list):
        for s in r["statutes"]:
            print(f"  {s['fused']:.4f}  {s['act']}, s.{s['section']} {s['heading'][:50]}   (BM25 #{s['bm25_rank']}, dense #{s['dense_rank']})")
    print(f"\n({r['seconds']} s)")


if __name__ == "__main__":
    main()
