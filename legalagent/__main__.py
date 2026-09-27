#!/usr/bin/env python
"""
CLI entry point: python -m legalagent <contract> [--config ...]

Usage:
  python -m legalagent analyse tests/fixtures/acme.pdf
  python -m legalagent analyse contracts/acme.pdf --top-k 5 --output out/run.json
  python -m legalagent eval tests/fixtures/sample_msa.txt
  python -m legalagent eval contracts/acme.pdf --methods bm25,hybrid --k 1,5
"""

import sys
import json
import argparse
from pathlib import Path
from legalagent.core.pipeline import analyse
from legalagent.core.types import Run, Clause, Finding
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
        "target_clause": {
            "id": target.id,
            "number": target.number,
            "heading": target.heading,
        },
        "related_clauses": [
            {"id": c.id, "number": c.number, "heading": c.heading}
            for c in related
        ],
        "evidence": finding.evidence,
        "refs": finding.refs,
        "scores": finding.scores,
    }


def main():
    parser = argparse.ArgumentParser(
        description="LegalAgent v0: Contract clause analysis",
        prog="legalagent"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command")

    # analyse subcommand
    analyse_parser = subparsers.add_parser("analyse", help="Analyze a contract")
    analyse_parser.add_argument("file", help="Contract file (PDF, DOCX, TXT)")
    analyse_parser.add_argument("--top-k", type=int, default=5, help="BM25 top-k candidates per clause")
    analyse_parser.add_argument("--output", "-o", help="Output JSON file (default: stdout)")
    analyse_parser.add_argument("--contract-id", default="local", help="Contract identifier")
    analyse_parser.add_argument(
        "--retrieval", default="bm25", choices=["bm25", "dense", "hybrid"],
        help="Retrieval method for candidate selection (default: bm25)")

    # eval subcommand
    eval_parser = subparsers.add_parser(
        "eval", help="Compare retrieval methods against gold cross-reference pairs")
    eval_parser.add_argument("file", help="Contract file (PDF, DOCX, TXT)")
    eval_parser.add_argument(
        "--methods", default="bm25,dense,hybrid",
        help="Comma-separated methods to compare (default: bm25,dense,hybrid)")
    eval_parser.add_argument(
        "--k", default="1,3,5,10", help="Comma-separated k values (default: 1,3,5,10)")
    eval_parser.add_argument("--contract-id", default="local", help="Contract identifier")
    eval_parser.add_argument("--output", "-o", help="Write results JSON here")

    args = parser.parse_args()

    if args.command == "eval":
        path = Path(args.file)
        if not path.exists():
            print(f"Error: {args.file} not found", file=sys.stderr)
            sys.exit(1)

        methods = tuple(m.strip() for m in args.methods.split(",") if m.strip())
        k_values = tuple(int(k) for k in args.k.split(",") if k.strip())

        clauses = extract(ingest(str(path)), args.contract_id)
        print(f"Evaluating retrieval on {args.file} ({len(clauses)} clauses)...",
              file=sys.stderr)

        results = compare(clauses, methods=methods, k_values=k_values)
        print(format_table(results, k_values))

        if args.output:
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.output).write_text(json.dumps(results, indent=2))
            print(f"Wrote {args.output}", file=sys.stderr)
        return

    if not args.command or args.command == "analyse":
        file_path = args.file if hasattr(args, 'file') else sys.argv[1] if len(sys.argv) > 1 else None
        if not file_path:
            parser.print_help()
            sys.exit(1)

        path = Path(file_path)
        if not path.exists():
            print(f"Error: {file_path} not found", file=sys.stderr)
            sys.exit(1)

        # Run pipeline
        config = {
            "retrieval_method": getattr(args, 'retrieval', 'bm25'),
            "top_k": getattr(args, 'top_k', 5),
        }
        contract_id = getattr(args, 'contract_id', 'local')

        print(f"Analyzing {file_path}...", file=sys.stderr)
        run, clauses, findings = analyse(str(path), config, contract_id)

        # Build output
        clauses_by_id = {c.id: c for c in clauses}
        output = {
            "run": {
                "id": run.id,
                "contract_id": run.contract_id,
                "config": run.config,
                "stats": run.stats,
            },
            "items": [format_finding(f, clauses_by_id) for f in findings],
        }

        # Write output
        output_str = json.dumps(output, indent=2)
        if hasattr(args, 'output') and args.output:
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.output).write_text(output_str)
            print(f"Wrote {args.output}", file=sys.stderr)
        else:
            print(output_str)

        # Summary
        print(f"\nExtracted  {run.stats['clauses']} clauses", file=sys.stderr)
        print(f"Classified {len([c for c in clauses if c.labels])} (labelled)", file=sys.stderr)
        print(f"Candidates {run.stats['pairs']} pairs", file=sys.stderr)
        print(f"Analysed   {run.stats['pairs']} → {run.stats['findings']} findings, {run.stats['no_issue']} no_issue", file=sys.stderr)

        if findings:
            print(f"\nTop findings:", file=sys.stderr)
            for f in findings[:3]:
                target = clauses_by_id.get(f.target_clause_id)
                print(f"  {f.severity.upper()} {target.number} <-> {f.related_clause_ids}", file=sys.stderr)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
