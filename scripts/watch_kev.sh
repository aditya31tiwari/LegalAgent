#!/usr/bin/env bash
# Watch the Kev fine-tune + evaluation pipeline until it finishes or fails.
#   bash scripts/watch_kev.sh
# Every 30 s: model / LoRA / data / plan numbers, loss trend, speed + ETA, GPU telemetry.
# On finish or error: verdict + scores, desktop notification and a sound.
cd "$(dirname "$0")/.." || exit 1
LOG=/tmp/kev_train.log; PIPE=logs/kev_pipeline.log; CFG=models/kev_judge/training_config.json

notify() {
  command -v notify-send >/dev/null && notify-send -u critical "$1" "$2" 2>/dev/null
  command -v paplay >/dev/null && paplay /usr/share/sounds/freedesktop/stereo/complete.oga 2>/dev/null
  printf '\a'
}
err_seen() { grep -q -E 'Traceback|OutOfMemoryError|RuntimeError|error:' "$LOG" 2>/dev/null; }

panel() {
python3 - "$LOG" "$CFG" <<'EOF'
import json, re, sys, time, os
log, cfg = sys.argv[1], sys.argv[2]
text = open(log, errors="replace").read() if os.path.exists(log) else ""
a = {}
try: a = json.load(open(cfg))["args"]
except Exception: pass
g = lambda rx, d="?": (re.search(rx, text) or [None, d])[1]
print("MODEL")
print(f"  backbone        {a.get('base','?')}  (rev {str(a.get('base_revision','?'))[:8]}) — frozen, {a.get('weights_dtype','?')} weights")
print( "  architecture    24 decoder layers = 18 Gated-DeltaNet (linear attention) + 6 full attention; ~0.8 B params")
print(f"  adapter         LoRA rank {a.get('lora','?')} on all projections (attention, MLP, DeltaNet) · pointer head dim {a.get('head_dim','?')}")
print(f"  trainable       {g(r'trainable params=([0-9.]+[MKB]?)')} parameters  (warm start: {g(r'(\d+) lora tensors')} LoRA tensors + pointer head from {a.get('init_from','?')})")
print("DATA")
print(f"  requests        {g(r'(\d+) training requests')} clause pairs · questions {g(r'questions by type (\{[^}]*\})')}")
print( "  per pair        relation (5-way choice) · severity (3-level score) · statute (choice of 4 retrieved India Code sections + none)")
print("TRAINING")
print(f"  optimiser       lr {a.get('lr','?')} · weight decay {a.get('weight_decay','?')} · batch {a.get('batch','?')} × grad-accum {a.get('accum','?')} = {int(a.get('batch',1))*int(a.get('accum',1))} records/step")
print(f"  precision       autocast {a.get('dtype','?')} · gradient checkpointing {a.get('checkpointing','?')} · max state {a.get('max_state','?')} tokens · epochs {a.get('epochs','?')}")
steps = re.findall(r"ep(\d+) step (\d+)/(\d+) loss ([0-9.]+) kl ([0-9.]+) anchor ([0-9.]+) ([0-9.]+)s/rec", text)
if steps:
    ep, s, tot, loss, kl, anc, spr = steps[-1]
    s, tot, spr = int(s), int(tot), float(spr)
    recs = s * int(a.get("accum", 8)) * int(a.get("batch", 1))
    eta = (tot - s) * int(a.get("accum", 8)) * spr / 60
    print("PROGRESS")
    bar = "█" * int(30 * s / tot) + "·" * (30 - int(30 * s / tot))
    print(f"  step            {s}/{tot}  [{bar}] {100*s/tot:.0f}%   records seen {recs}")
    print(f"  speed           {spr:.2f} s/record  →  ~{eta:.0f} min left (ETA {time.strftime('%H:%M', time.localtime(time.time()+eta*60))})")
    losses = [float(x[3]) for x in steps]
    spark = "▁▂▃▄▅▆▇█"
    lo, hi = min(losses), max(losses)
    line = "".join(spark[int((l - lo) / (hi - lo + 1e-9) * 7)] for l in losses)
    print(f"  loss (CE)       {loss}   first {losses[0]:.3f} → now {losses[-1]:.3f}   trend {line}")
    print(f"  kl / anchor     {kl} / {anc}")
else:
    print("PROGRESS\n  starting up (loading backbone, warm start, first 10 steps)…")
EOF
}

running() {   # the pipeline is running until its log says it is done (a stray shell must not keep us waiting)
  pgrep -f "bash train/kev_pipeline" >/dev/null && ! grep -q "kev pipeline done" "$PIPE" 2>/dev/null
}
while running; do
  clear
  echo "══ Kev judge fine-tune — $(date +%T) ══════════════════════════════════════"
  panel
  echo "GPU"
  nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu,clocks.sm,power.draw \
    --format=csv,noheader 2>/dev/null | awk -F', ' '{printf "  %s · util %s · mem %s / %s · %s°C · SM %s · %s\n",$1,$2,$3,$4,$5,$6,$7}'
  echo "PIPELINE"; tail -n 3 "$PIPE" | cut -c1-120 | sed 's/^/  /'
  if err_seen; then echo; echo "!!! ERROR in training log:"; grep -E 'Traceback|Error|error:' "$LOG" | tail -n 3; fi
  sleep 30
done

clear
echo "Kev pipeline finished at $(date +%T)"; echo
tail -n 6 "$PIPE"; echo
if grep -q '"exit": 0' results/kev_train.json 2>/dev/null && curl -sf http://127.0.0.1:8008/v1/models >/dev/null; then
  echo "✅ SUCCESS — Kev trained, evaluated, and serving on :8008"
  python3 - <<'EOF'
import json
for f in ("results/kev_train.json", "results/eval_checklist.json", "results/eval_judge.json"):
    try:
        d = json.load(open(f))
        if "train_seconds" in d:
            print(f"  training: {d['train_records']} records in {d['train_seconds']//60} min"); continue
        for k, v in d.items():
            if isinstance(v, dict) and ("binary_accuracy" in v or "accuracy" in v):
                print(f"  {f.split('/')[-1]:22s} {k:22s}", {kk: round(vv, 3) for kk, vv in v.items() if isinstance(vv, float)})
    except Exception as e:
        print(f, e)
EOF
  notify "Kev: done ✅" "Trained, evaluated and serving on :8008 — tell Claude"
else
  echo "❌ FAILED or incomplete — last training log lines:"; grep -v -i warn "$LOG" | tail -n 8
  notify "Kev: FAILED ❌" "See the terminal and tell Claude"
fi
