"""
Archive the current fine-tuned Kev run under a version tag before training the next one.

    venv/bin/python scripts/archive_kev_run.py v2

- moves models/kev_judge -> models/kev_judge_v2 (incl. threshold.json)
- renames result keys kev_finetuned / kev_finetuned_tau -> kev_finetuned_v2 / kev_finetuned_v2_tau
  in eval_judge / eval_checklist / eval_cuadpairs / eval_litigated / eval_judge_vs_human
- copies results/kev_train.json -> results/kev_train_v2.json
Idempotent: does nothing if the target already exists.
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(tag: str):
    src, dst = ROOT / "models" / "kev_judge", ROOT / "models" / f"kev_judge_{tag}"
    if src.exists() and not dst.exists():
        shutil.move(str(src), str(dst))
        print("moved", src, "->", dst)
    kt = ROOT / "results" / "kev_train.json"
    if kt.exists() and not (ROOT / "results" / f"kev_train_{tag}.json").exists():
        shutil.copy(kt, ROOT / "results" / f"kev_train_{tag}.json")
    for name in ("eval_judge", "eval_checklist", "eval_cuadpairs", "eval_litigated", "eval_judge_vs_human"):
        p = ROOT / "results" / f"{name}.json"
        if not p.exists():
            continue
        d = json.loads(p.read_text())
        changed = False
        for suffix in ("", "_tau"):
            if f"kev_finetuned{suffix}" in d:
                d[f"kev_finetuned_{tag}{suffix}"] = d.pop(f"kev_finetuned{suffix}")
                changed = True
        if name == "eval_litigated":
            for row in d.get("cases", []):
                for suffix in ("", "_tau"):
                    if f"kev_finetuned{suffix}" in row:
                        row[f"kev_finetuned_{tag}{suffix}"] = row.pop(f"kev_finetuned{suffix}")
                        changed = True
            for suffix in ("", "_tau"):
                if f"kev_finetuned{suffix}" in d.get("summary", {}):
                    d["summary"][f"kev_finetuned_{tag}{suffix}"] = d["summary"].pop(f"kev_finetuned{suffix}")
        if changed:
            p.write_text(json.dumps(d, indent=2))
            print("renamed keys in", p.name)
    sel = ROOT / "results" / "judge_selection.json"
    if sel.exists():   # keep the live selection pointing at the moved model
        s = json.loads(sel.read_text())
        if s.get("serve") == "models/kev_judge":
            s["serve"] = f"models/kev_judge_{tag}"
            s["judge"] = s["judge"].replace("kev_finetuned", f"kev_finetuned_{tag}")
            sel.write_text(json.dumps(s, indent=2))
            print("selection now serves", s["serve"])


if __name__ == "__main__":
    main(sys.argv[1])
