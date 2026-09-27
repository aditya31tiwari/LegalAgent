"""Run the planted-irregularity Indian contract benchmark."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from legalagent.core.pipeline import analyse


ROOT = Path(__file__).parent.parent
BENCHMARK = ROOT / "data" / "demo" / "india" / "custom_benchmark"
OUTPUT = ROOT / "runs" / "indian" / "custom_benchmark.json"


def categories(findings) -> set[str]:
    result = set()
    for finding in findings:
        if finding.relation_type == "conflict":
            result.add("cross_clause_conflict")
        elif finding.relation_type == "statutory_violation":
            result.add("section_27_statutory_violation")
        elif finding.relation_type == "dependency":
            result.add("termination_survival_dependency")
    return result


def main() -> None:
    manifest = json.loads((BENCHMARK / "MANIFEST.json").read_text(encoding="utf-8"))
    report = []
    failed = False

    for item in manifest["contracts"]:
        path = BENCHMARK / item["file"]
        run, clauses, findings = analyse(
            str(path),
            {"retrieval_method": "hybrid", "top_k": 5, "jurisdiction": "India"},
            contract_id=path.stem,
        )
        expected = set(item["expected"])
        detected = categories(findings)
        missing = sorted(expected - detected)
        unexpected = sorted(detected - expected)
        passed = not missing and not unexpected
        failed = failed or not passed
        report.append({
            "file": item["file"],
            "passed": passed,
            "expected": sorted(expected),
            "detected": sorted(detected),
            "missing": missing,
            "unexpected": unexpected,
            "stats": run.stats,
            "findings": [
                {
                    "relation_type": finding.relation_type,
                    "severity": finding.severity,
                    "target_clause_id": finding.target_clause_id,
                    "related_clause_ids": finding.related_clause_ids,
                    "rationale": finding.rationale,
                    "refs": finding.refs,
                }
                for finding in findings
            ],
        })
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] {item['file']}: expected={sorted(expected)} detected={sorted(detected)}")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps({"manifest": manifest, "results": report}, indent=2), encoding="utf-8")
    print(f"Report: {OUTPUT}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()