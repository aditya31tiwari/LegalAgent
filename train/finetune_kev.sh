#!/usr/bin/env bash
# Fine-tune Kev-0.8B (LoRA + pointer head, warm-started from jaredpalmer/kev-0.8b) as the
# LegalAgent pair judge, then serve it. Kev lives in its own uv environment (~/Projects/kev,
# torch 2.8) because it pins torch<2.9; LegalAgent talks to it over HTTP on localhost.
#
#   bash train/finetune_kev.sh            # export data, train, write models/kev_judge
#   bash train/finetune_kev.sh serve      # serve fine-tuned judge on :8008 (+ base model on :8009)
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
KEV="${KEV_HOME:-$HOME/Projects/kev}"
PY="$KEV/.venv/bin/python"
OUT="$REPO/models/kev_judge"

if [[ "${1:-train}" == "serve" ]]; then
  cd "$KEV"
  nohup "$PY" -m kev.serve --run "$OUT" --port 8008 > /tmp/kev_ft_serve.log 2>&1 &
  if [[ "${2:-}" == "--with-base" ]]; then
    nohup "$PY" -m kev.serve --run jaredpalmer/kev-0.8b --port 8009 > /tmp/kev_base_serve.log 2>&1 &
  fi
  echo "Kev judge serving on 127.0.0.1:8008 (logs /tmp/kev_ft_serve.log)"
  exit 0
fi

"$REPO/venv/bin/python" "$REPO/train/export_kev_data.py"
cd "$KEV"
start=$(date +%s)
"$PY" -m kev.train \
  --data "$REPO/data/derived/kev/train.jsonl" \
  --init_from jaredpalmer/kev-0.8b \
  --lr 1e-4 --epochs 2 --accum 8 \
  --max_state 1536 \
  --out "$OUT" 2>&1 | tee /tmp/kev_train.log
echo "{\"base\": \"jaredpalmer/kev-0.8b\", \"lr\": 1e-4, \"epochs\": 2, \"accum\": 8, \"train_seconds\": $(( $(date +%s) - start ))}" > "$REPO/results/kev_train.json"
echo "trained -> $OUT"
