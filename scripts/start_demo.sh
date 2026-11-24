#!/usr/bin/env bash
# One command to bring up the whole local demo:
#   bash scripts/start_demo.sh            -> Kev judge on :8008 (if not running) + dashboard on :8080
#   bash scripts/start_demo.sh stop
set -uo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"; cd "$REPO"
KEV="$HOME/Projects/kev"; KPY="$KEV/.venv/bin/python"
mkdir -p logs

if [[ "${1:-start}" == "stop" ]]; then
  pkill -f "kev.serve .*--port 8008"; pkill -f "web/server.py"; echo "stopped"; exit 0
fi

# Which judge to serve: results/judge_selection.json (scripts/select_judge.py, chosen on independent tests).
RUN=$(venv/bin/python - <<'EOF'
import json
try:
    s = json.load(open("results/judge_selection.json"))
    print(s.get("serve") or "")
except Exception:
    print("jaredpalmer/kev-0.8b")
EOF
)
[[ "$RUN" == models/* ]] && RUN="$REPO/$RUN"
echo "selected judge: $(venv/bin/python -c "import json;s=json.load(open('results/judge_selection.json'));print(s['judge'],'threshold',s.get('threshold'))" 2>/dev/null || echo 'none (default base Kev)')"
if [[ -z "$RUN" ]]; then echo "selection is the rules judge — Kev not started"; fi
if [[ -n "$RUN" ]] && ! curl -sf http://127.0.0.1:8008/v1/models >/dev/null; then
  echo "starting Kev judge ($RUN) on 127.0.0.1:8008 …"
  # 6 GB card: Kev's state-prefix cache (default 64k tokens) grows until long PDF clauses run out of memory.
  # A small cache + expandable segments keeps Kev under ~4 GB with no measurable slowdown for our requests.
  export KEV_PREFIX_CACHE="${KEV_PREFIX_CACHE:-2}" KEV_PREFIX_MAX_TOKENS="${KEV_PREFIX_MAX_TOKENS:-6000}" KEV_TRUNCATE_STATES=1
  export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-expandable_segments:True}"
  (cd "$KEV" && setsid nohup "$KPY" -m kev.serve --run "$RUN" --port 8008 > /tmp/kev_demo_serve.log 2>&1 < /dev/null &)
  for _ in $(seq 1 90); do curl -sf http://127.0.0.1:8008/v1/models >/dev/null && break; sleep 2; done
fi
curl -sf http://127.0.0.1:8008/v1/models >/dev/null && echo "Kev judge: up" || echo "Kev judge: DOWN (pipeline will fall back to rules)"

pkill -f "web/server.py" 2>/dev/null; sleep 1
# The GPU belongs to Kev (peaks ~3.8 GB of 6 GB on long inputs). The small encoders (InLegalBERT,
# InLegal-SBERT) run on CPU in the demo so they can never push Kev out of memory.
export LEGALAGENT_DEVICE="${LEGALAGENT_DEVICE:-cpu}"
setsid nohup venv/bin/python web/server.py > logs/web.log 2>&1 < /dev/null &
for _ in $(seq 1 30); do curl -sf http://127.0.0.1:8080/api/system/status >/dev/null && break; sleep 1; done
echo "dashboard: http://$(hostname -I | awk '{print $1}'):8080/app   (status: $(curl -s http://127.0.0.1:8080/api/system/status))"
echo "under the hood: http://localhost:8080/scores"

# The "engine room" window next to the browser (needs the laptop's own desktop session).
if [[ "${1:-}" != "--no-gui" ]]; then
  export DISPLAY="${DISPLAY:-:0}"
  setsid nohup venv/bin/python scripts/workbench.py > logs/workbench.log 2>&1 < /dev/null &
  echo "workbench GUI launched on display $DISPLAY (log: logs/workbench.log)"
fi
