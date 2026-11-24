#!/usr/bin/env bash
# Overnight: expanded teacher data -> Kev v3 -> calibrate -> evaluate on independent tests ->
# pick the best judge -> (if it changed) re-seed the demo -> regenerate tables -> commit.
#
#   nohup bash scripts/overnight.sh > logs/overnight.log 2>&1 &
#
# Safe to start before the Gemini labelling finishes: it waits for it (max 4 h).
# Never pushes; the morning runbook does that after a look at the results.
set -uo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"; cd "$REPO"
PY="$REPO/venv/bin/python"; KEV="$HOME/Projects/kev"; KPY="$KEV/.venv/bin/python"
log() { echo "[$(date +%T)] $*"; }
wait_port() { for _ in $(seq 1 150); do curl -sf "http://127.0.0.1:$1/v1/models" >/dev/null && return 0; sleep 2; done; return 1; }
stop_kev() { for p in $(pgrep -f "kev[.]serve"); do kill "$p"; done; sleep 3; }

log "== overnight start"
log "waiting for teacher labelling and any running Kev pipeline (max 4 h)"
for _ in $(seq 1 480); do
  pgrep -f "label_with_agy[.]py" >/dev/null || pgrep -f "bash train/kev_pipeline" >/dev/null || break
  sleep 30
done

log "archive tonight's fine-tuned run (v2) so v3 cannot overwrite it"
"$PY" scripts/archive_kev_run.py v2
PREV=$("$PY" -c "import json;print(json.load(open('results/judge_selection.json')).get('serve'))" 2>/dev/null)
log "current selection serves: $PREV"

log "import all pair labels (primary Gemini first, then extra Gemini, then extra Claude)"
"$PY" scripts/build_judge_set.py import-labels \
  --label-glob "agy_gemini-4-hydrogen-high.jsonl,extra_agy_gemini-4-hydrogen-high.jsonl,extra_agy_claude-sonnet-5-5-medium.jsonl"
log "export Kev records (CLAUSE-22 types) + balanced training file"
"$PY" train/export_kev_data.py | tail -n 3

log "train Kev v3 (balanced, focal, 2 epochs) + serve + first evals"
KEV_DATA=train_balanced.jsonl KEV_EPOCHS=2 KEV_LR=2e-4 KEV_EXTRA="--focal_gamma 2" SKIP_EXPORT=1 SKIP_BASE=1 \
  bash train/kev_pipeline.sh
if ! curl -sf http://127.0.0.1:8008/v1/models >/dev/null; then
  log "!! v3 not serving — keeping the previous selection"; exit 1
fi

log "calibrate v3 threshold on training contracts"
"$PY" train/calibrate_kev.py --url http://127.0.0.1:8008/v1/systemone --out models/kev_judge/threshold.json
log "evaluate v3 on all judge tests"
for w in judge checklist cuadpairs litigated; do "$PY" scripts/eval_all.py "$w" | tail -n 3; done

log "select the judge (checklist + CUAD; no teacher labels)"
"$PY" scripts/select_judge.py
NOW=$("$PY" -c "import json;print(json.load(open('results/judge_selection.json')).get('serve'))")
if [[ "$NOW" != "$PREV" ]]; then
  log "selection changed ($PREV -> $NOW): restart demo with it and re-seed the demo database"
  stop_kev
  bash scripts/start_demo.sh --no-gui
  "$PY" scripts/seed_demo.py --judge local
else
  log "selection unchanged ($NOW): restoring it on :8008"
  stop_kev
  bash scripts/start_demo.sh --no-gui
fi

log "regenerate report tables"
"$PY" scripts/validate_teacher.py > /dev/null 2>&1
"$PY" scripts/eval_all.py tables
git add results models/*.json models/kev_judge*/threshold.json data/derived/judge_pairs.jsonl research/teacher_labels/labels 2>/dev/null
git commit -q -m "overnight: Kev v3 on expanded teacher data; calibrated, evaluated, judge re-selected ($NOW)" && log "committed $(git log --oneline -1)"
log "== overnight done"
