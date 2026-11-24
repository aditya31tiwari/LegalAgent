#!/usr/bin/env bash
# Sequential GPU queue (6 GB card: one job at a time). Logs in /tmp/q_*.log.
set -uo pipefail
cd "$(dirname "$0")/.."
PY=venv/bin/python

echo "[$(date +%T)] waiting for InLegalBERT v1 (CLAUSE-20) to finish"
while pgrep -f "train/finetune_classifier.py --epochs 3" >/dev/null; do sleep 20; done

# Keep the CLAUSE-20 run as the taxonomy-v1 ablation.
if [[ -d models/clause20_inlegalbert && ! -d models/clause20_inlegalbert_v1 ]]; then
  mv models/clause20_inlegalbert models/clause20_inlegalbert_v1
  [[ -f results/classifier_clause20_inlegalbert.json ]] && mv results/classifier_clause20_inlegalbert.json results/classifier_clause20_inlegalbert_v1_clause20.json
  cp models/clause20_labeller.joblib models/clause20_labeller_v1.joblib 2>/dev/null || true
fi

echo "[$(date +%T)] 1/3 InLegal-SBERT clause retriever (contrastive)"
$PY -u train/finetune_retriever.py clauses > /tmp/q_retriever_clauses.log 2>&1

echo "[$(date +%T)] 2/3 InLegalBERT on CLAUSE-22"
$PY -u train/finetune_classifier.py --model law-ai/InLegalBERT --out models/clause20_inlegalbert \
    --epochs 3 --bs 16 --lr 3e-5 --max-len 256 > /tmp/q_inlegalbert_v2.log 2>&1

echo "[$(date +%T)] 3/3 MiniLM + LogReg baseline on CLAUSE-22"
$PY -u clause20/train.py > /tmp/q_minilm_lr.log 2>&1

echo "[$(date +%T)] queue done"
