#!/usr/bin/env bash
# Kev judge end to end: import teacher labels -> export (CLAUSE-22 types) -> LoRA fine-tune ->
# evaluate base (zero-shot) and fine-tuned on held-out pairs + checklist -> leave fine-tuned
# serving on :8008 for the demo. One GPU job at a time (6 GB card).
#   nohup bash train/kev_pipeline.sh > logs/kev_pipeline.log 2>&1 &
set -uo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
PY="$REPO/venv/bin/python"
KEV="$HOME/Projects/kev"; KPY="$KEV/.venv/bin/python"
log() { echo "[$(date +%T)] $*"; }
wait_port() { for _ in $(seq 1 120); do curl -sf "http://127.0.0.1:$1/v1/models" >/dev/null && return 0; sleep 2; done; return 1; }
stop_port() { pkill -f "kev.serve .*--port $1" 2>/dev/null; sleep 3; }

log "waiting for GPU queues to finish"
while pgrep -f "train/gpu_queue.sh|/tmp/queue2.sh" >/dev/null; do sleep 20; done

log "waiting for teacher labelling to finish (max 30 min)"
for _ in $(seq 1 90); do pgrep -f "label_with_agy.py" >/dev/null || break; sleep 20; done

if [[ -z "${SKIP_EXPORT:-}" ]]; then
  log "import teacher labels";  "$PY" scripts/build_judge_set.py import-labels --teacher antigravity-gemini-4-hydrogen-high
  log "export Kev records (re-classified with current CLAUSE-22 classifier)";  "$PY" train/export_kev_data.py
fi

log "fine-tune Kev-0.8B (log: logs/kev_train.log)"
rm -rf "$REPO/models/kev_judge"   # kev.train refuses to overwrite a run directory (e.g. a killed attempt)
start=$(date +%s)
# kev.train defaults to Qwen3-0.6B-Base; kev-0.8b is built on Qwen3.5-0.8B-Base (revision pinned
# in its model card), and warm_start() refuses a mismatched backbone.
(cd "$KEV" && "$KPY" -m kev.train --data "$REPO/data/derived/kev/train.jsonl" --init_from jaredpalmer/kev-0.8b \
   --base Qwen/Qwen3.5-0.8B-Base --base_revision dc7cdfe2ee4154fa7e30f5b51ca41bfa40174e68 \
   --lr 1e-4 --epochs 2 --accum 8 --max_state 1536 --out "$REPO/models/kev_judge") > /tmp/kev_train.log 2>&1
status=$?
echo "{\"base\": \"jaredpalmer/kev-0.8b\", \"lr\": 1e-4, \"epochs\": 2, \"accum\": 8, \"exit\": $status, \"train_seconds\": $(( $(date +%s) - start )), \"train_records\": $(wc -l < data/derived/kev/train.jsonl)}" > results/kev_train.json
log "train exit=$status: $(cat results/kev_train.json)"

if [[ -z "${SKIP_BASE:-}" ]]; then
  log "BASE Kev (zero-shot) on :8009"
  (cd "$KEV" && nohup "$KPY" -m kev.serve --run jaredpalmer/kev-0.8b --port 8009 > /tmp/kev_base_serve.log 2>&1 &)
  if wait_port 8009; then
    "$PY" scripts/eval_all.py judge; "$PY" scripts/eval_all.py checklist
  else log "base server did not start (/tmp/kev_base_serve.log)"; fi
  stop_port 8009
fi

if [[ $status -eq 0 ]]; then
  log "FINE-TUNED Kev on :8008"
  (cd "$KEV" && nohup "$KPY" -m kev.serve --run "$REPO/models/kev_judge" --port 8008 > /tmp/kev_ft_serve.log 2>&1 &)
  if wait_port 8008; then
    "$PY" scripts/eval_all.py judge; "$PY" scripts/eval_all.py checklist
    log "fine-tuned Kev left running on :8008"
  else log "fine-tuned server did not start (/tmp/kev_ft_serve.log)"; fi
fi
log "kev pipeline done"
