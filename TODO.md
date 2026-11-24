# TODO — LegalAgent final sprint

Owner key: **[C]** Claude session · **[U]** you (Aryan / team) · **[GPU]** queued job on the laptop.
Plan: [`docs/PLAN.md`](docs/PLAN.md).

## Done
- [x] Merge `aditya-tiwari` (CLAUSE-20 classifier, RRF retrieval, P/R@k eval) into `aryan-sethi` → branch `final`
- [x] GPU fixed (nvidia 595.99 on kernel 7.0.0-44), CUDA torch via uv; Kev env (`~/Projects/kev`, uv)
- [x] Datasets: CUAD v1, LEDGAR, Open India Law central legislation (mirror), CLAUSE-20 rebuilt
- [x] Ingestion: parallel cached Tesseract OCR (881 scanned pages in ~5 min), pymupdf4llm for native PDFs, DOCX tables, images
- [x] Extraction: TOC filter, ARTICLE/SCHEDULE parts, parent hierarchy, top-level `1.` numbering
- [x] Indian statute library + hybrid retrieval + citation verification (3,142 sections, 33 Acts)
- [x] Pluggable judge (local Kev → rules; Gemini optional), local_judge.py (System One API)
- [x] Clause-taxonomy research → **CLAUSE-22** migration applied (arbitration, remedies + 7 Indian rule labels, 40 clash pairs, 3 new statutory rules)
- [x] Gemini client: key rotation, model probing (3-flash-preview / 3.5-flash-lite), timeouts
- [x] Teacher pipeline via Antigravity CLI: export (2,522 pairs), `label_with_agy.py` (heartbeat, ETA, graceful quota stop, resume)
- [x] Web: `/api/contracts/upload/stream` (real file upload + OCR), local-first SSE stream, `/api/findings/{id}/expand`, `/api/system/status`
- [x] Dashboard: real upload (was sending a placeholder!), judge/retrieval selectors, Expand button, **XSS fixed** (TC13) in findings/clauses/viewer
- [x] Retrieval eval (Table 5.3) on 120 CUAD + 3 Indian contracts → `results/eval_retrieval.json`
- [x] Commit `9480f95` on `final`

## In progress
- [ ] [U] agy teacher labelling — `bash research/teacher_labels/run_teacher.sh full` (2,522 pairs, ~50 min)
- [ ] [GPU] InLegalBERT v1 (CLAUSE-20) finishing → kept as `models/clause20_inlegalbert_v1`
- [ ] [GPU] queue: clause retriever → InLegalBERT v2 (CLAUSE-22) → MiniLM+LR v2 (`/tmp/gpu_queue.log`)

## Next (after teacher labels land)
- [ ] [C] `build_judge_set.py import-labels` → `data/derived/judge_pairs.jsonl`
- [ ] [C] Kev: `train/finetune_kev.sh` (export + LoRA delta fine-tune) → serve on :8008; base Kev on :8009
- [ ] [C] Statute retriever fine-tune (`train/finetune_retriever.py statutes`)
- [ ] [C] GNN: `train/train_gnn.py` (with no-graph ablation)
- [ ] [C] Evals: `eval_all.py classifier | retrieval (+FT rows) | statutes | judge | e2e | tables`
- [ ] [C] Regenerate demo DB from real pipeline runs (seeded findings in `db.py` are hand-written)
- [ ] [C] Re-run full test suite with free GPU; add tests (upload endpoint, escaping, Indian rules, statute verify)
- [ ] [C] README rewrite (truthful), `docs/VIVA_NOTES.md` (Q&A: why Kev, why not Gemini, GNN result, limits)
- [ ] [C] Commit; ask before pushing to GitHub

## Needs you
- [ ] [U] Optional: `bash research/teacher_labels/run_teacher.sh second` (300-pair cross-check, other model family)
- [ ] [U] ~30 min: spot-check ~150 pairs in `research/gold_set/` (file will be prepared) → human-verified accuracy row
- [ ] [U] Fill report tables from `results/REPORT_TABLES.md`; update chapters 4–6 with what actually shipped
- [ ] [U] Decide: push `final` to GitHub (and whether to tell Aditya/Anish first)

## Known limitations (say them in the viva)
- No public Indian contract-clause dataset → Indian classification is evaluated on silver labels + spot check
- 66/510 CUAD contracts use ARTICLE V / (a)-only numbering → extractor yields too few clauses there
- Teacher labels are model labels; human gold set is small
- OCR noise on scanned concessions (e.g. "29.4" for "29.1") lowers retrieval on Indian text
