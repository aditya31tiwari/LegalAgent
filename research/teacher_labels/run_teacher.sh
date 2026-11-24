#!/usr/bin/env bash
# Teacher labelling with the Antigravity CLI. Run in YOUR laptop terminal (where `agy` is signed in):
#
#   bash research/teacher_labels/run_teacher.sh smoke     # 20 pairs, ~1-3 min  -> tell Claude to check
#   bash research/teacher_labels/run_teacher.sh full      # all 2,522 pairs, ~30-60 min (resumable)
#   bash research/teacher_labels/run_teacher.sh second    # 300-pair cross-check with a 2nd model family
#
# Output: research/teacher_labels/labels/agy_<model>.jsonl (append-only; re-run the same
# command to resume after any interruption).
set -euo pipefail
cd "$(dirname "$0")/../.."

TEACHER="gemini-4-hydrogen-high"       # primary teacher (from `agy models`)
SECOND="claude-sonnet-5-5-medium"      # independent second opinion on a sample

MODE="${1:-smoke}"
mkdir -p logs
LOG="logs/teacher_${MODE}.log"
echo "logging to $LOG  (tail -f $PWD/$LOG)"
case "$MODE" in
  smoke)  venv/bin/python -u scripts/label_with_agy.py --model "$TEACHER" --limit 20 --workers 1 --verbose ;;
  full)   venv/bin/python -u scripts/label_with_agy.py --model "$TEACHER" --workers 5 --priority --max-total "${MAX_TOTAL:-1000}" ;;
  second) # 300 pairs the PRIMARY teacher already labelled (stratified), so agreement can be measured
          venv/bin/python - <<'EOF'
import json, random
from pathlib import Path
d = Path("research/teacher_labels")
done = {json.loads(l)["pair_id"]: json.loads(l)["relation"] for l in (d / "labels/agy_gemini-4-hydrogen-high.jsonl").read_text().splitlines() if l.strip()}
pairs = [json.loads(l) for l in (d / "pairs_to_label.jsonl").read_text().splitlines() if json.loads(l)["pair_id"] in done]
rnd = random.Random(11)
risky = [p for p in pairs if done[p["pair_id"]] != "no_issue"]; clean = [p for p in pairs if done[p["pair_id"]] == "no_issue"]
pick = rnd.sample(risky, min(len(risky), 150)) + rnd.sample(clean, min(len(clean), 300 - min(len(risky), 150)))
rnd.shuffle(pick)
(d / "second_pairs.jsonl").write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in pick))
print(len(pick), "pairs for the second teacher")
EOF
          venv/bin/python -u scripts/label_with_agy.py --model "$SECOND" --pairs research/teacher_labels/second_pairs.jsonl --workers 4 ;;
  types)  venv/bin/python -u scripts/label_with_agy.py --model "$TEACHER" --types --workers 3 ;;
  split)  # partition the still-unlabelled pairs, risky-first, so the two teachers never overlap
          venv/bin/python - <<'EOF'
import json, random
from pathlib import Path
d = Path("research/teacher_labels")
done = set()
for f in [*(d / "labels").glob("agy_*.jsonl"), *(d / "labels").glob("extra_agy_*.jsonl")]:   # pair labels only (not types_/checklist_)
    done |= {json.loads(l)["pair_id"] for l in f.read_text().splitlines() if l.strip()}
todo = [json.loads(l) for l in (d / "pairs_to_label.jsonl").read_text().splitlines() if json.loads(l)["pair_id"] not in done]
rank = {p["pair_id"]: random.Random(7).random() for p in todo}
todo.sort(key=lambda p: (not p["contract"].startswith("india:"), not ({"xref", "type_matrix"} & set(p["surfaced_by"])), rank[p["pair_id"]]))
(d / "more_claude.jsonl").write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in todo[0::2][:600]))
(d / "more_gemini.jsonl").write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in todo[1::2]))
print(len(todo), "unlabelled ->", len(todo[0::2][:600]), "for Claude,", len(todo[1::2]), "for Gemini (risky-first, interleaved)")
EOF
          ;;
  more-claude) [ -f research/teacher_labels/more_claude.jsonl ] || bash "$0" split
          venv/bin/python -u scripts/label_with_agy.py --model "$SECOND" --pairs research/teacher_labels/more_claude.jsonl \
              --out-prefix extra_ --workers 4 ;;
  more-gemini) [ -f research/teacher_labels/more_gemini.jsonl ] || bash "$0" split
          venv/bin/python -u scripts/label_with_agy.py --model "$TEACHER" --pairs research/teacher_labels/more_gemini.jsonl \
              --out-prefix extra_ --workers 5 --max-total "${MAX_TOTAL:-800}" ;;
  check)  # known-answer validation of the teacher (and, with SECOND, of the second model)
          venv/bin/python scripts/make_checklist.py
          venv/bin/python -u scripts/label_with_agy.py --model "${CHECK_MODEL:-$TEACHER}" --pairs research/teacher_labels/checklist_pairs.jsonl \
              --out-prefix checklist_ --batch 7 --workers 2 --verbose ;;
  *) echo "usage: $0 smoke|full|second|types|check|split|more-claude|more-gemini|contrastive"; exit 1 ;;
esac 2>&1 | tee -a "$LOG"
