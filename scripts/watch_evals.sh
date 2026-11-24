#!/usr/bin/env bash
# Watch the background CPU evaluations (statutes -> classifier -> retrieval).
#   bash scripts/watch_evals.sh
# Shows which eval is running, results as they arrive, CPU load; beeps when all are done.
cd "$(dirname "$0")/.." || exit 1
QUEUE=/tmp/cpu_evals.log

notify() {
  command -v notify-send >/dev/null && notify-send -u normal "$1" "$2" 2>/dev/null
  command -v paplay >/dev/null && paplay /usr/share/sounds/freedesktop/stereo/complete.oga 2>/dev/null
  printf '\a'
}

export TERM="${TERM:-xterm}"
while pgrep -f "/tmp/cpu_evals.sh" >/dev/null; do
  clear
  echo "══ CPU evaluations — $(date +%T) ══════════════════════════════════"
  echo "queue:"; sed 's/^/  /' "$QUEUE"
  cur=$(grep -E 'eval [a-z]+$' "$QUEUE" | tail -n 1 | awk '{print $NF}')
  started=$(grep -E "eval $cur\$" "$QUEUE" | tail -n 1 | sed -E 's/^\[([0-9:]+)\].*/\1/')
  [[ -n "$started" ]] && echo "running: $cur  (since $started, $(( ($(date +%s) - $(date -d "$started" +%s)) / 60 )) min)"
  echo
  case "$cur" in
    classifier)
      echo "classifier results so far (backend · split · micro-F1 · macro-F1 · top-1 · exact · ms/clause):"
      python3 - /tmp/eval_classifier.log <<'EOF'
import ast, re, sys
for line in open(sys.argv[1], errors="replace"):
    m = re.match(r"^(keyword|minilm_lr|inlegalbert) (\S+) (\{.*\})", line)
    if not m:
        continue
    d = ast.literal_eval(m.group(3))
    print("  %-12s %-13s n=%5d  micro %.3f  macro %.3f  top1 %.3f  exact %.3f  %s ms"
          % (m.group(1), m.group(2), d["n"], d["micro_f1"], d["macro_f1"], d["top1_acc"], d["exact_match"], d["ms_per_clause"]))
EOF
      n=$(grep -c -E "^(keyword|minilm_lr|inlegalbert) " /tmp/eval_classifier.log 2>/dev/null)
      echo "  progress: $n / 9 (3 classifiers × test, test_ood, india_silver)";;
    retrieval)
      echo "retrieval results so far:"; grep -v -i -E 'warn|loading|batches' /tmp/eval_retrieval.log 2>/dev/null | tail -n 10 | cut -c1-160 | sed 's/^/  /';;
    *) tail -n 5 "/tmp/eval_$cur.log" 2>/dev/null | cut -c1-160 | sed 's/^/  /';;
  esac
  echo
  echo "CPU load: $(cut -d' ' -f1-3 /proc/loadavg) · GPU: $(nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader 2>/dev/null) (Kev training)"
  sleep 20
done
clear
echo "CPU evaluations finished at $(date +%T)"; sed 's/^/  /' "$QUEUE"
grep -q '(0)' "$QUEUE" && echo "✅ results in results/eval_*.json" || echo "❌ check /tmp/eval_*.log"
notify "LegalAgent evals done" "statutes / classifier / retrieval finished"
