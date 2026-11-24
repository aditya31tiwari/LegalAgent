#!/usr/bin/env python
"""
CLI entry point.

Usage:
  python -m legalagent analyse contract.pdf
  python -m legalagent analyse contract.pdf --judge local --retrieval hybrid -o out/run.json
  python -m legalagent analyse contract.pdf --judge gemini --max-candidates all
  python -m legalagent eval tests/fixtures/sample_msa.txt --methods bm25,dense,hybrid --k 1,3,5,10
"""

import argparse
import json
import sys
from pathlib import Path

from legalagent.core.pipeline import analyse, JUDGES
from legalagent.core.classification import BACKENDS
from legalagent.core.types import Clause, Finding
from legalagent.core.ingestion import ingest
from legalagent.core.extraction import extract
from legalagent.core.evaluation import compare, format_table


def format_finding(finding: Finding, clauses_by_id: dict) -> dict:
    """Convert Finding to JSON-serializable dict."""
    target = clauses_by_id.get(finding.target_clause_id, Clause("?", "?"))
    related = [clauses_by_id.get(cid, Clause("?", "?")) for cid in finding.related_clause_ids]
    return {
        "id": finding.id,
        "relation_type": finding.relation_type,
        "severity": finding.severity,
        "risk_score": finding.risk_score,
        "rationale": finding.rationale,
        "surfaced_by": finding.surfaced_by,
        "target_clause": {"id": target.id, "number": target.number, "heading": target.heading},
        "related_clauses": [{"id": c.id, "number": c.number, "heading": c.heading} for c in related],
        "evidence": finding.evidence,
        "refs": finding.refs,
        "scores": finding.scores,
    }


def _max_candidates(value: str):
    return None if value.lower() in {"all", "none", "unset", "0"} else int(value)


def main():
    parser = argparse.ArgumentParser(description="LegalAgent: cross-clause contract review", prog="legalagent")
    subparsers = parser.add_subparsers(dest="command", help="Command")

    ap = subparsers.add_parser("analyse", help="Analyse a contract")
    ap.add_argument("file", help="Contract file (PDF, DOCX, TXT, MD)")
    ap.add_argument("--top-k", type=int, default=5, help="Retrieval neighbours per clause")
    ap.add_argument("--output", "-o", help="Output JSON file (default: stdout)")
    ap.add_argument("--contract-id", default="local", help="Contract identifier")
    ap.add_argument("--retrieval", default="hybrid", choices=["bm25", "dense", "hybrid"])
    ap.add_argument("--embedding-model", default=None, help="Sentence encoder for dense/hybrid retrieval")
    ap.add_argument("--judge", default="local", choices=JUDGES, help="Pair judge (default: local, falls back to rules)")
    ap.add_argument("--classifier", default="auto", choices=BACKENDS)
    ap.add_argument("--gnn", action="store_true", help="Add GNN link-prediction pairs to the shortlist")
    ap.add_argument("--max-candidates", default="30", type=_max_candidates, help="Pair cap, or 'all'")

    ep = subparsers.add_parser("eval", help="Compare retrieval methods against gold cross-reference pairs")
    ep.add_argument("file", help="Contract file (PDF, DOCX, TXT)")
    ep.add_argument("--methods", default="bm25,dense,hybrid")
    ep.add_argument("--k", default="1,3,5,10")
    ep.add_argument("--contract-id", default="local")
    ep.add_argument("--output", "-o", help="Write results JSON here")

    args = parser.parse_args()

    if args.command == "eval":
        path = Path(args.file)
        if not path.exists():
            print(f"Error: {args.file} not found", file=sys.stderr)
            sys.exit(1)
        methods = tuple(m.strip() for m in args.methods.split(",") if m.strip())
        k_values = tuple(int(k) for k in args.k.split(",") if k.strip())
        clauses = extract(ingest(str(path)), args.contract_id)
        print(f"Evaluating retrieval on {args.file} ({len(clauses)} clauses)...", file=sys.stderr)
        results = compare(clauses, methods=methods, k_values=k_values)
        print(format_table(results, k_values))
        if args.output:
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.output).write_text(json.dumps(results, indent=2))
            print(f"Wrote {args.output}", file=sys.stderr)
        return

    if args.command != "analyse":
        parser.print_help()
        sys.exit(1)

    path = Path(args.file)
    if not path.exists():
        print(f"Error: {args.file} not found", file=sys.stderr)
        sys.exit(1)

    config = {
        "retrieval_method": args.retrieval,
        "top_k": args.top_k,
        "judge": args.judge,
        "classifier": args.classifier,
        "use_gnn": args.gnn,
        "max_candidates": args.max_candidates,
    }
    if args.embedding_model:
        config["embedding_model"] = args.embedding_model

    print(f"Analyzing {args.file}...", file=sys.stderr)
    run, clauses, findings = analyse(str(path), config, args.contract_id)

    clauses_by_id = {c.id: c for c in clauses}
    output = {
        "run": {"id": run.id, "contract_id": run.contract_id, "config": run.config, "stats": run.stats},
        "items": [format_finding(f, clauses_by_id) for f in findings],
    }
    output_str = json.dumps(output, indent=2)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(output_str)
        print(f"Wrote {args.output}", file=sys.stderr)
    else:
        print(output_str)

    s = run.stats
    print(f"\nExtracted  {s['clauses']} clauses", file=sys.stderr)
    print(f"Classified {len([c for c in clauses if c.labels])} labelled ({run.config['classifier']})", file=sys.stderr)
    print(f"Candidates {s['pairs']} pairs ({args.retrieval})", file=sys.stderr)
    print(f"Judged     {s['pairs']} -> {s['findings']} findings, {s['no_issue']} no_issue (judge={s['judge']})", file=sys.stderr)
    for f in findings[:3]:
        target = clauses_by_id.get(f.target_clause_id)
        print(f"  {f.severity.upper()} {target.number} <-> {f.related_clause_ids}", file=sys.stderr)


if __name__ == "__main__":
    main()
