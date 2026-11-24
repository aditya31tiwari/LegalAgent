"""
Choose the pair judge the demo serves — using ONLY tests that do not depend on teacher labels.

    venv/bin/python scripts/select_judge.py            -> results/judge_selection.json

Score = checklist binary accuracy (bad pairs caught AND fixed twins cleared — has false-alarm
control), tie-break by CUAD lawyer-pair recall. Agreement with the teacher is reported for
context but never used to choose. start_demo.sh / seed_demo.py read the selection.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"

# results key -> what to serve
RUNS = {
    "kev_base_zero_shot": {"run": "jaredpalmer/kev-0.8b", "threshold_file": "models/kev_base_threshold.json", "tau": False},
    "kev_base_zero_shot_tau": {"run": "jaredpalmer/kev-0.8b", "threshold_file": "models/kev_base_threshold.json", "tau": True},
    "kev_finetuned": {"run": "models/kev_judge", "threshold_file": "models/kev_judge/threshold.json", "tau": False},
    "kev_finetuned_tau": {"run": "models/kev_judge", "threshold_file": "models/kev_judge/threshold.json", "tau": True},
    "rules": {"run": None, "threshold_file": None, "tau": False},
}


def spec_for(key):
    """Generic mapping for archived fine-tuned runs: kev_finetuned_v2(_tau) -> models/kev_judge_v2."""
    if key in RUNS:
        return RUNS[key]
    import re
    m = re.fullmatch(r"kev_finetuned_(v\d+[a-z_]*?)(_tau)?", key)
    if m:
        d = f"models/kev_judge_{m.group(1)}"
        return {"run": d, "threshold_file": f"{d}/threshold.json", "tau": bool(m.group(2))}
    return None


def load(name):
    p = RES / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else {}


def main():
    ck, cu, jd = load("eval_checklist"), load("eval_cuadpairs"), load("eval_judge")
    rows = []
    for key in ck:
        spec = spec_for(key)
        if spec is None or not isinstance(ck[key], dict) or "binary_accuracy" not in ck[key]:
            continue
        if spec["run"] and spec["run"].startswith("models/") and not (ROOT / spec["run"]).exists():
            continue   # model no longer on disk
        rows.append({"judge": key, "checklist_accuracy": ck[key]["binary_accuracy"],
                     "checklist_bad_caught": ck[key].get("risky_detected_on_bad"), "checklist_fixed_cleared": ck[key].get("no_issue_on_fixed"),
                     "cuad_recall": (cu.get(key) or {}).get("recall"), "teacher_risky_f1": (jd.get(key) or {}).get("risky_f1"), **spec})
    if not rows:
        sys.exit("no checklist results yet — run scripts/eval_all.py checklist first")
    rows.sort(key=lambda r: (r["checklist_accuracy"], r["cuad_recall"] or 0), reverse=True)
    best = rows[0]
    tau = None
    if best["tau"] and best["threshold_file"] and (ROOT / best["threshold_file"]).exists():
        tau = json.loads((ROOT / best["threshold_file"]).read_text())["threshold"]
    sel = {"judge": best["judge"], "serve": best["run"], "threshold": tau,
           "criterion": "checklist binary accuracy, tie-break CUAD lawyer-pair recall (no teacher labels)",
           "candidates": rows}
    (RES / "judge_selection.json").write_text(json.dumps(sel, indent=2))
    for r in rows:
        print(f"{r['judge']:26s} checklist {r['checklist_accuracy']:.3f}  CUAD {r['cuad_recall'] if r['cuad_recall'] is not None else '—'}  teacher-F1 {r['teacher_risky_f1']}")
    print(f"\nselected: {best['judge']}  serve={best['run']}  threshold={tau}")


if __name__ == "__main__":
    main()
