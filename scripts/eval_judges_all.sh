#!/usr/bin/env bash
# Calibrate + evaluate both Kev judges on every independent test, one server at a time (6 GB GPU),
# then select the judge and leave it serving on :8008.
#   bash scripts/eval_judges_all.sh        (log: logs/eval_judges_all.log)
set -uo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"; cd "$REPO"
PY="$REPO/venv/bin/python"; KEV="$HOME/Projects/kev"; KPY="$KEV/.venv/bin/python"
log() { echo "[$(date +%T)] $*"; }
wait_port() { for _ in $(seq 1 150); do curl -sf "http://127.0.0.1:$1/v1/models" >/dev/null && return 0; sleep 2; done; return 1; }
stop_kev() { for p in $(pgrep -f "kev[.]serve"); do kill "$p"; done; sleep 4; }
serve() { (cd "$KEV" && setsid nohup "$KPY" -m kev.serve --run "$1" --port "$2" > "/tmp/kev_serve_$2.log" 2>&1 < /dev/null &); wait_port "$2"; }

log "== fine-tuned Kev (current models/kev_judge) on :8008"
curl -sf http://127.0.0.1:8008/v1/models >/dev/null || serve "$REPO/models/kev_judge" 8008
"$PY" train/calibrate_kev.py --url http://127.0.0.1:8008/v1/systemone --out models/kev_judge/threshold.json
for w in checklist cuadpairs litigated judge; do log "eval $w (fine-tuned)"; "$PY" scripts/eval_all.py "$w" | grep -E '^kev|^rules|wrote' | cut -c1-200; done
stop_kev

log "== base Kev on :8009"
serve jaredpalmer/kev-0.8b 8009 || { log "base did not start"; }
"$PY" train/calibrate_kev.py --url http://127.0.0.1:8009/v1/systemone --out models/kev_base_threshold.json
for w in checklist cuadpairs litigated judge; do log "eval $w (base)"; "$PY" scripts/eval_all.py "$w" | grep -E '^kev|wrote' | cut -c1-200; done
stop_kev

log "== select judge"
"$PY" scripts/select_judge.py
log "== serve the selected judge on :8008 (+ restart dashboard)"
bash scripts/start_demo.sh --no-gui
log "done"
