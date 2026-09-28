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
        text = (finding.rationale + " " + " ".join(r.get("source", "") + " " + r.get("snippet", "") for r in finding.refs)).lower()
        if "section 27" in text or "restrain trade" in text or "restraint of trade" in text or "non-compete" in text:
            result.add("section_27_statutory_violation")
            result.add("section_27_post_termination_restraint")
        if "section 28" in text or "restraint of legal proceedings" in text or "statutory remedies" in text or "oust" in text:
            result.add("section_28_statutory_remedy_waiver")
        if "mediation" in text:
            result.add("mediation_act_prelitigation_exclusion")
        if "data protection" in text or "personal data" in text or "dpdpa" in text:
            if "cap" in text or "limit" in text or "250 crore" in text or "statutory" in text:
                result.add("dpdpa_statutory_penalty_cap")
            if "consent" in text or "sell" in text or "monetiz" in text or "transfer" in text:
                result.add("dpdpa_unauthorized_personal_data_monetization")
        if "unilateral" in text or "section 62" in text or "variation" in text or "alter" in text:
            result.add("section_62_unilateral_variation")
        if "liquidated damages" in text or "penalty" in text or "section 74" in text or "in terrorem" in text:
            result.add("section_74_punitive_liquidated_damages")

        if finding.relation_type == "conflict":
            result.add("cross_clause_conflict")
            result.add("cross_clause_indemnity_cap_conflict")
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
            {"retrieval_method": "bm25", "top_k": 5, "jurisdiction": "India", "use_gemini": True},
            contract_id=path.stem,
        )
        expected = set(item["expected"])
        detected = categories(findings)
        missing = sorted(expected - detected)
        unexpected = sorted(detected - expected)
        passed = not missing
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