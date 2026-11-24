# LegalAgent — completion plan (updated 2026-11-24, ~18:45)

Viva in ~16 h. Branch `final` on the laptop (`aryan@192.168.1.10:~/Projects/LegalAgent/LegalAgent`).
Live checklist: [`TODO.md`](../TODO.md).

## Design decisions (settled)

1. **Local-first.** Every stage of the demo pipeline runs on the laptop (RTX 4050, 6 GB). No
   contract text leaves the machine unless the user clicks an explicit cloud action.
2. **Gemini's role.** *Teacher* (offline labelling of public contracts) and *optional cloud
   assist* ("Expand" on a finding, grounded in locally retrieved statutes). Never required.
3. **Teacher.** Gemini-API Flash was overloaded (503s), so labelling runs through the
   Antigravity CLI (`agy -p`, `gemini-4-hydrogen-high`). A second model family
   (`claude-sonnet-5-5-medium`, 300 pairs) measures inter-teacher agreement.
4. **Citations are never "from model memory".** All statute references resolve to real
   section text in the local India Code library (3,142 sections, 33 Acts), or are marked
   unverified.
5. **Honest evaluation.** Every number in the report comes from `scripts/eval_all.py`
   and `results/*.json`. Ablations are kept (taxonomy v1 vs v2, GNN vs no-graph, base vs
   fine-tuned Kev, base vs fine-tuned InLegal-SBERT).

## Architecture

```
PDF (native → pymupdf4llm | scanned → parallel Tesseract OCR, cached) / DOCX / image / TXT
 → normalise (header/footer strip, page breaks)
 → extract clauses (numbering, TOC filter, ARTICLE/SCHEDULE parts, parent hierarchy, xrefs)
 → classify  CLAUSE-22: InLegalBERT fine-tuned | MiniLM+LR | keyword  + 7 Indian rule labels
 → candidate pairs: xrefs + 40-pair type matrix + BM25/dense/hybrid(RRF) retrieval (+ GNN)
 → judge each pair: Kev-0.8B fine-tuned (local)  → fallback rules   [Gemini only if chosen]
 → Indian statutory rules (ICA s.27, s.74, Stamp Act s.35, DPDP) + statute RAG grounding
 → SQLite → FastAPI SSE → dashboard (upload, graph, findings, Expand-with-Gemini)
```

## Models

| Component | Model | Training data | Status |
|---|---|---|---|
| Clause classifier | law-ai/InLegalBERT, full fine-tune | CLAUSE-22 (74,374 clauses: LEDGAR + CUAD) | v1 (CLAUSE-20) finishing; v2 queued |
| Baseline classifier | MiniLM + one-vs-rest LogReg | same | retrain on CLAUSE-22 queued |
| Clause retriever | InLegal-SBERT, contrastive (MNRL) | CUAD cross-reference pairs (eval contracts excluded) | queued |
| Statute retriever | InLegal-SBERT, contrastive | teacher citations + section headings | after teacher labels |
| Pair judge | Kev-0.8B (Qwen3.5 + LoRA + pointer head), LoRA delta fine-tune | ~2.5k teacher-labelled pairs | after teacher labels |
| Risky-pair GNN | GraphSAGE link prediction | same pairs, contract graphs | after teacher labels |
| Teacher | Gemini 4 Hydrogen via agy CLI | — | running (2,522 pairs) |

## Data

LEDGAR (LexGLUE), CUAD v1, CLAUSE-22 (ours), Open India Law central legislation (India Code),
BNS/BNSS/BSA/CPC additions + precedents, NHAI model concession + Pune Metro Line-3 concession
(scanned, OCR'd), Pune Metro with 15 planted irregularities (held out), 5-contract Indian
benchmark (held out), 220 Indian clauses silver-labelled, 2,522 teacher-labelled pairs.

## Timeline (remaining)

| When | GPU | CPU / human |
|---|---|---|
| now → +1 h | InLegalBERT v1 → clause retriever → InLegalBERT v2 (45 min) | agy teacher labelling (user's terminal) · UI done |
| +1 h → +2 h | Kev fine-tune → serve; base Kev zero-shot; statute retriever; GNN | import labels; judge-set export |
| +2 h → +3 h | eval_all: classifier, retrieval, statutes, judge, e2e | regenerate demo DB from real runs; README |
| +3 h → +4 h | buffer | `results/REPORT_TABLES.md` → report; gold-set spot check (team, ~30 min) |
| then | — | sleep; viva prep from `docs/VIVA_NOTES.md` |

Cut order if late: second teacher → statute-retriever fine-tune → GNN → base-Kev row.
Never cut: InLegalBERT v2, Kev judge, e2e eval on Pune Metro, working demo.

## Verification

- `venv/bin/python -m pytest -q tests clause20` green (one test needs a free GPU).
- `python -m legalagent analyse data/demo/samples/02_pune_metro_adversarial_15_injections.md --judge local`
  flags the planted 91.x clauses; `results/eval_e2e.json` reports recall on the 305-page PDF.
- Dashboard: upload the adversarial PDF → OCR (cached) → findings with India Code links;
  status line shows Kev running + GPU; Expand works when Gemini answers, degrades cleanly when not.
