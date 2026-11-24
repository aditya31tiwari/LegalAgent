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

case "${1:-smoke}" in
  smoke)  venv/bin/python -u scripts/label_with_agy.py --model "$TEACHER" --limit 20 --workers 1 --verbose ;;
  full)   venv/bin/python -u scripts/label_with_agy.py --model "$TEACHER" --workers 5 ;;
  second) venv/bin/python -u scripts/label_with_agy.py --model "$SECOND" --limit 300 --workers 2 ;;
  *) echo "usage: $0 smoke|full|second"; exit 1 ;;
esac
