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
  second) venv/bin/python -u scripts/label_with_agy.py --model "$SECOND" --limit 300 --workers 2 ;;
  types)  venv/bin/python -u scripts/label_with_agy.py --model "$TEACHER" --types --workers 3 ;;
  check)  # known-answer validation of the teacher (and, with SECOND, of the second model)
          venv/bin/python scripts/make_checklist.py
          venv/bin/python -u scripts/label_with_agy.py --model "${CHECK_MODEL:-$TEACHER}" --pairs research/teacher_labels/checklist_pairs.jsonl \
              --out-prefix checklist_ --batch 7 --workers 2 --verbose ;;
  *) echo "usage: $0 smoke|full|second|types|check"; exit 1 ;;
esac 2>&1 | tee -a "$LOG"
