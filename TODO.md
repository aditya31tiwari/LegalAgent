# TODO — LegalAgent final sprint (updated 21:20)

Owner key: **[C]** Claude session · **[U]** you · **[GPU]** queued job on the laptop.
Plan: [`docs/PLAN.md`](docs/PLAN.md) · Morning: [`docs/final_viva_docs/MORNING_RUNBOOK.md`](docs/final_viva_docs/MORNING_RUNBOOK.md)

## In progress (21:20)
- [ ] [GPU] Kev v2 — balanced 440 pairs + focal loss, 2 epochs (ends ≈ 21:48); then calibrate τ, evaluate, select judge
- [ ] [C] CPU evals: classifier (running) → retrieval with fine-tuned rows

## Next (before 23:00)
- [ ] [C] v2: calibrate τ → eval judge / checklist / CUAD pairs / litigated → `select_judge.py`
- [ ] [C] base Kev on CUAD pairs + litigated (serve :8009 briefly)
- [ ] [C] GNN on GPU (+ no-graph ablation)
- [ ] [C] Seed demo DB from real runs with the selected judge; Pune Metro e2e eval
- [ ] [C] Browser-test all `/scores` tabs, upload, Expand; launch Workbench once
- [ ] [C] `eval_all tables`; update EVALUATION.md, VIVA_NOTES.md with final numbers; README; commit; push `final`

## 23:00 — learning & documentation pack (requested)
- [ ] [C] **Process write-up (Markdown)** — `docs/final_viva_docs/PROCESS.md`: the whole journey in order — starting state,
      every phase (merge, GPU, data, taxonomy research, ingestion/OCR, extraction, classifier, retrieval,
      statute library, teacher labelling, Kev, GNN, evaluation, demo), with **results**, the
      **schema/structure** (Clause / Finding / Run records, DB tables, files and folders, data formats,
      API endpoints), and **every failed attempt and why it likely failed**:
      - Gemini API 503s / retired models → switched teacher to Antigravity CLI
      - Kev trained on the wrong default backbone (Qwen3-0.6B) → caught before training
      - Kev out-of-memory on 6 GB → bf16 weights + gradient checkpointing + stop web server
      - flash-linear-attention: v0.6 incompatible with Triton 3.4; v0.3.2 recompiled per sequence length
        (GPU starved at 26 %) → reverted to reference kernels, 1 epoch
      - Kev v1 collapsed to "no_issue" (73 % majority class) → balanced data + focal loss + τ calibration
      - Hand-written rules: 0/13 Supreme Court struck-down clauses, 7.5 % CUAD → why learned judges
      - Statute eval on teacher citations meaningless (94 % ICA; "always ICA" beats the model) → litigated gold
      - CPU GNN run hogged 7 cores → moved to GPU
      - TOC lines extracted as clauses; part regex matched "PARTY"; OCR hung single-threaded → fixes
      - Fake PDF upload in the old dashboard (sent a placeholder) and XSS → fixed
      - Second teacher κ only 0.57; s.37 citation bias from the prompt example
- [ ] [C] **Viva learning artifact** (interactive page) explaining each part of the project: what it is,
      **how** we did it, **why**, **why not** the alternatives (LLM-only, GNN-only, rules-only, Gemini at runtime,
      LangGraph, bigger models…), likely panel questions with answers, and the numbers to quote.
- [ ] [C] **Glossary of terms** to know (in the artifact + `docs/GLOSSARY.md`): PyMuPDF, pymupdf4llm, Tesseract / OCR,
      normalisation, regex, BM25, TF-IDF, dense embeddings / sentence-transformers, cosine similarity,
      reciprocal rank fusion, InLegalBERT / InLegal-SBERT, fine-tuning, multi-label classification, micro/macro-F1,
      precision / recall, ROC-AUC, LoRA, bf16 / fp16, gradient checkpointing, focal loss, class imbalance,
      calibration / decision threshold, knowledge distillation, teacher–student, silver vs gold labels,
      Cohen's κ, contrastive learning / MNRL, GraphSAGE / GNN / link prediction, RAG, CUAD, LEDGAR / LexGLUE,
      India Code, ICA s.27 / s.74 / s.124, A&C Act, DPDP Act, Kev / Jev / decision model, SSE, FastAPI, SQLite.

## Overnight (you start before sleeping)
- [ ] [U] ≥22:05 (Gemini quota reset): `bash research/teacher_labels/run_teacher.sh more-gemini`
- [ ] [U] then: `nohup bash scripts/overnight.sh > logs/overnight.log 2>&1 &` (waits for the labelling; trains Kev v3,
      evaluates, re-selects the judge, re-seeds demo only if it changed, commits)

## Morning
- [ ] [U] follow `docs/final_viva_docs/MORNING_RUNBOOK.md` (check overnight → start demo → click-through → copy numbers → push → rehearse)

## Done
- [x] Merge branches → `final`; GPU fixed; uv envs (project + Kev)
- [x] Data: CUAD, LEDGAR, India Code legislation (+BNS/CPC/BSA/precedents) → CLAUSE-20 → **CLAUSE-22**
- [x] Ingestion (parallel cached OCR, pymupdf4llm), extraction (TOC filter, parts, hierarchy)
- [x] InLegalBERT v1 0.925/0.715 → **v2 0.931/0.750**; MiniLM-LR v2 0.828/0.591
- [x] Retrieval study (Table 5.3); InLegal-SBERT clause + statute retrievers fine-tuned
- [x] Teacher: 1,000 Gemini + 300 Claude second opinion + 320 Claude extra; validation (checklist 92.9 %,
      lawyer types 85 %, citations 86 %, κ 0.57)
- [x] Test sets: checklist (28), CUAD lawyer pairs (280), Supreme Court litigated clauses (18), Pune Metro injections
- [x] Kev base evaluated (checklist 71 %); Kev v1 trained + diagnosed (collapse)
- [x] Web: real upload, judge picker, Expand, XSS fix, `/scores` under-the-hood, playground (web/CLI), Workbench
- [x] GPU-safe device fallback; judge calibration + selection on independent tests; overnight pipeline
- [x] Docs: ARCHITECTURE, DATASETS, MODELS_AND_TRAINING, EVALUATION, DEMO_GUIDE, MORNING_RUNBOOK, VIVA_NOTES, REPORT_CHANGES
