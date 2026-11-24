# LegalAgent — the whole process: what we did, what worked, what failed and why

Written on the night before the viva (24 Nov 2026). This is the honest log of the final build: every stage,
the data structures, the measured results and **every failed attempt with the likely reason**.
Numbers are copied from `results/*.json` / `results/REPORT_TABLES.md`; if they differ, the results files win.

---

## 0. Starting point (mid-term state)

- A FastAPI dashboard showing a **hand-written seed database** (findings were typed in, not produced).
- Upload button was a placeholder; Gemini was the only "judge"; MiniLM + logistic regression classifier
  on a 20-label taxonomy (CLAUSE-20); regex rules for Indian law; no evaluation against real ground truth.
- Draft report `LegalAgent_Final_Report.docx` with placeholder tables.

Goal for the final build: **real pipeline, real models trained on our GPU (RTX 4050, 6 GB), local-first,
and numbers measured against ground truth we did not create ourselves.**

---

## 1. Timeline of the final build

| Phase | What we did | Result |
|---|---|---|
| Setup | Fixed the laptop GPU (kernel had no NVIDIA module; installed driver 595-open), torch CUDA via `uv` | GPU usable for training |
| Ingestion | pymupdf4llm for digital pages + parallel, cached Tesseract OCR for scanned pages | 305-page scanned Pune Metro PDF ingested; ~2 min first time, instant afterwards (cache) |
| Extraction | Clause splitter with TOC filter, ARTICLE/SCHEDULE "parts", parent hierarchy, cross-reference resolution | Pune Metro PDF → 580 clauses, 99 parts, 137 resolved cross-references |
| Taxonomy | Research job compared CLAUSE-20 with legal taxonomies → **CLAUSE-22** (arbitration and remedies split out, LD moved) | 74,374 labelled clauses, 22 trained labels + 7 rule-based Indian labels, 40 weighted clash pairs |
| Classifier | Fine-tuned **InLegalBERT** (multi-label) on CLAUSE-22 | test micro-F1 **0.931**, out-of-domain **0.750** |
| Retrievers | Fine-tuned **InLegal-SBERT** twice (clause↔clause 2,821 pairs; clause↔statute 2,967 pairs) | statute retrieval R@5 0.11 → **0.32** on independent gold |
| Teacher | Gemini 4 (via the Antigravity CLI `agy`) labelled 1,000 clause pairs + Claude Sonnet labelled 300 (second opinion); later +740 Gemini, +320 Claude | silver training data for Kev |
| Teacher validation | Checked the teacher against ground truth it did not produce | checklist 92.9 %, lawyer clause types 75 % first-type / 85 % overlap, citations 85.7 % real sections, Gemini–Claude κ 0.57 |
| Judge | Served **Kev-0.8B** (open reconstruction of the Jev/System One decision model) locally; LoRA fine-tuned twice | base zero-shot selected (see §4) |
| GNN | GraphSAGE link predictor over clause graph | no gain over no-graph (honest ablation) |
| Statute RAG | India Code library (Open India Law mirror) + Nyaya Acts → **4,408 sections / 37 Acts**, hybrid BM25 + fine-tuned InLegal-SBERT + Act prior, citation verification | grounded statute references with confidence labels |
| Clause-vs-law | Kev single-clause check with 7 Indian-law risk categories | 6/9 struck-down SC clauses caught (regex: 0/9) |
| Demo | Real DB built by `scripts/seed_demo.py` from actual runs: Pune Metro (15 planted faults), Supreme Court casebook (18 real cases), a real CUAD contract, our samples, two full scanned PDFs | dashboard shows only real pipeline output |

---

## 2. Final structure and schema

### 2.1 Pipeline

```
PDF / DOCX / TXT / MD
  │ ingest      pymupdf4llm (digital) | Tesseract OCR, 1 process per page, cached by file hash (scanned)
  ▼
text ── extract   TOC filter → ARTICLE / SCHEDULE parts → numbered clauses (1, 1.1, 1.1(a)) → parent_id
  │               → cross-references ("subject to Clause 14.2") resolved to clause ids
  ▼
Clause[] ── classify   InLegalBERT (CLAUSE-22, multi-label) + keyword backstop + heading prior
  │                    + 7 Indian known-gap rules (stamp duty, DPDP, …)
  ▼
candidate pairs ── shortlist   cross-references + 40-pair clause-type clash matrix (TYPE_MATRIX)
  │                            + hybrid retrieval (BM25 + dense, reciprocal-rank fusion) [+ optional GNN]
  ▼
pair judge ── local Kev (default) → rules (fallback);  Gemini only if the user picks it
  │           Kev answers 3 typed questions: relation (choice), severity (score), statute (choice of 4 retrieved + none)
  ▼
clause vs Indian law ── regex rules + Kev single-clause check (7 risk categories → Act/section)
  ▼
statute grounding ── retrieve top India Code sections for each finding (hybrid + Act prior),
  │                  verify every cited section exists, attach confidence (high / medium / low)
  ▼
validate (evidence spans exist) → rank (severity, risk) → SQLite → FastAPI (SSE progress) → dashboard
```

### 2.2 Data records (`legalagent/core/types.py`)

| Record | Key fields |
|---|---|
| `Clause` | `id` (`contract::14.2`), `number`, `heading`, `text`, `part` (ARTICLE/SCHEDULE), `parent_id`, `labels` [{label, score}], `xrefs` [{target, resolved}] |
| `Finding` | `id`, `target_clause_id`, `related_clause_ids`, `relation_type` (conflict / dependency / overlap / ambiguity / statutory_violation), `severity`, `risk_score`, `rationale`, `surfaced_by` (xref / type_matrix / retrieval / kev_statutory / rule), `evidence` spans, `refs` [{source, section, snippet, confidence, retrieval_score}], `scores` |
| `Run` | `id`, `contract_id`, `config` (judge, retrieval, classifier), `stats` (clauses, pairs, findings, judge used, timings per stage) |

SQLite tables: `contracts`, `clauses`, `findings`, `finding_details` (all scores for the "Finding explained" view),
`graph_edges`, `clause_embeddings`.

### 2.3 Repository map

| Path | Purpose |
|---|---|
| `legalagent/core/` | ingestion, extraction, classification, retrieval, candidate_selection, local_judge, statutory_kev, statutes, gnn, pipeline, device |
| `web/` | `server.py`, `live.py` (API + SSE), `index.html` (dashboard `/app`), `scores.html` (under-the-hood `/scores`) |
| `train/` | `finetune_classifier.py`, `finetune_retriever.py`, `kev_pipeline.sh`, `export_kev_data.py`, `calibrate_kev.py`, `train_gnn.py` |
| `scripts/` | `eval_all.py` (all evaluations), `select_judge.py`, `seed_demo.py`, `start_demo.sh`, `overnight.sh`, teacher labelling scripts |
| `clause20/` | CLAUSE-22 dataset build, `labels.yaml`, `label_map.yaml` |
| `research/` | taxonomy research, teacher labels + validation, litigated Supreme Court clauses, legal-RAG survey |
| `results/` | every measured number (JSON) + `REPORT_TABLES.md` |
| `models/` | trained weights (not in git) |

---

## 3. Results (all measured)

### 3.1 Clause classification (CLAUSE-22)

| Classifier | Test micro-F1 (n=8,415) | Out-of-domain micro-F1 (n=703) | Indian silver micro-F1 (n=220) | ms/clause |
|---|---|---|---|---|
| Keyword rules | 0.275 | 0.404 | 0.329 | 0.05 |
| MiniLM + logistic regression (mid-term model) | 0.828 | 0.590 | 0.418 | 20 |
| **InLegalBERT fine-tuned (v2, CLAUSE-22)** | **0.931** | **0.750** | 0.411 | 4 |
| InLegalBERT v1 (CLAUSE-20 taxonomy) | 0.925 | 0.715 | — | 5.6 |
| Ensemble (InLegalBERT + MiniLM-LR) | — | — | **0.443** | — |

Indian contracts are much harder (0.41–0.44) than the US/CUAD-style test set: OCR noise, long PPP clauses,
Indian-specific clause types. Headings help macro-F1 (0.42 vs 0.37 on Gemini-4 labels).

### 3.2 Related-clause retrieval (gold = resolved cross-references, numbers masked)

| Method | CUAD R@5 | Indian R@5 |
|---|---|---|
| BM25 | 0.347 | 0.165 |
| MiniLM dense | 0.371 | 0.126 |
| bge-small dense | **0.384** | 0.143 |
| InLegal-SBERT (base) | 0.265 | 0.088 |
| Hybrid MiniLM (RRF) | 0.366 | **0.167** |

Lexical matching holds up best on OCR'd Indian text; this is why the shortlist is hybrid.

### 3.3 Pair judge (cross-clause)

| Judge | Checklist accuracy (28 bad/fixed twins) | CUAD lawyer-pair recall (280) | Held-out vs teacher risky-F1 (172) |
|---|---|---|---|
| Rules | 46 % | 7.5 % | 0.04 |
| **Kev base, zero-shot (selected)** | **71 %** | **75 %** | 0.46 |
| Kev v1 fine-tuned (imbalanced) | 43 % (collapsed) | — | — |
| Kev v2 fine-tuned (balanced + focal) | 54 % | 21 % | 0.57 |
| Kev v2 + calibrated threshold τ=0.378 | 54 % | 31 % | **0.62** |
| Teacher (Gemini 4) | 93 % | — | (reference) |

Selection rule (`scripts/select_judge.py`): checklist accuracy first, CUAD recall as tie-break — **never the
teacher labels**, because a model can score well against the teacher by copying its mistakes.

### 3.4 Clause vs Indian law

| Method | Supreme Court struck-down clauses caught | Pune Metro single-clause injections caught | False alarms |
|---|---|---|---|
| Regex rules | 0 / 9 | 4 / 6 | 0 |
| **Kev single-clause check** | **6 / 9** | **5 / 6** | 9 (incl. all 4 upheld clauses) |

Kev finds what regex cannot read, but over-flags → findings are shown with **high / medium / low confidence**
labels instead of being hidden or presented as verdicts.

### 3.5 Statute retrieval (gold = the section a court or our injection actually applies; 19 queries)

| Retriever | R@5 (exact section) | Act in top-3 |
|---|---|---|
| BM25 | 0.105 | 0.42 |
| Dense InLegal-SBERT (base) | 0.053 | 0.21 |
| Hybrid | 0.053 | 0.21 |
| Hybrid + Act prior | 0.211 | 0.32 |
| **Fine-tuned hybrid + Act prior (default)** | **0.316** | **0.53** |
| Fine-tuned + bge-reranker-v2-m3 | 0.263 | 0.47 |

### 3.6 GNN ablation (172 held-out pairs, 52 risky)

| Ranker | ROC-AUC | Avg precision |
|---|---|---|
| GraphSAGE GNN | 0.742 | 0.494 |
| Same features, no graph | **0.748** | **0.539** |
| Cosine similarity only | 0.738 | 0.515 |
| Type matrix only | 0.517 | 0.369 |

### 3.7 Teacher validation

| Check | Gemini 4 | Claude Sonnet |
|---|---|---|
| Checklist (known answers) | 92.9 % | — |
| Clause types vs CUAD lawyer labels (first type / any overlap) | 75 % / 85 % | 70 % / 79 % |
| Cited sections that really exist in India Code | 85.7 % | 76.7 % |
| Agreement Gemini vs Claude (risky / not), Cohen's κ | 0.57 (moderate) | |

---

## 4. Failed attempts and why they (likely) failed

| # | Attempt | What happened | Likely reason | What we did |
|---|---|---|---|---|
| 1 | Gemini API as teacher | 503 errors, retired model names | Free-tier load, preview models rotated | Probed live model list; moved teacher to Antigravity `agy` (Gemini 4) |
| 2 | First `agy` JSON schema | `INVALID_ARGUMENT` | Empty string `""` not allowed as an enum value | Used `"none"` |
| 3 | Serial OCR | Looked "hung" for many minutes on 305 pages | One page at a time, no cache | ProcessPool per page + cache keyed by file hash |
| 4 | First extractor | Dropped real clauses as TOC; "PARTY" matched as PART | Single-line TOC heuristic; regex lacked a separator | Run-based TOC detection; require separator after PART/ARTICLE |
| 5 | Kev training (first tries) | Wrong base model, "refusing to overwrite", OOM, dtype error | Trainer defaults assume larger GPU | Pinned base revision, bf16 weights + gradient checkpointing, stopped other GPU users |
| 6 | Fast linear-attention kernels (fla) | Version clash with Triton; older fla recompiled for every shape and starved the GPU | Qwen3.5 linear attention kernels are new and fragile | Uninstalled; used reference kernels |
| 7 | **Kev v1 fine-tune** | Collapsed: predicts no_issue almost always, 0 % of bad checklist pairs caught | 73 % of training pairs were no_issue; cross-entropy rewards always saying "no_issue" | v2: balanced 440 pairs, focal loss γ=2, lr 2e-4, 2 epochs, calibrated threshold |
| 8 | **Kev v2 fine-tune** | Better than v1 and best vs the teacher (risky-F1 0.62), but **worse than the untouched base** on checklist (54 % vs 71 %) and CUAD (31 % vs 75 %) | 440 silver pairs teach the teacher's style (and its errors) more than the task; the base model's general reasoning is lost on a tiny set | Kept the base model; documented v2 as a finding |
| 9 | Statute eval using teacher citations as gold | Every method looked the same | 94 % of teacher citations were Indian Contract Act s.37 — the gold was biased | Built independent gold: statute a court applied + our injections; added "always-ICA" baseline |
| 10 | Regex for clause-vs-law | 0/9 Supreme Court struck-down clauses | Real drafting ("from the date you leave", "earnest money shall stand forfeited") does not match keywords | Added Kev single-clause check + statute RAG |
| 11 | Cross-encoder reranker (bge-reranker-v2-m3) | R@5 0.316 → 0.263 | Multilingual general reranker does not know Indian statute language; also costs ~1 GB GPU next to Kev | Rejected |
| 12 | GNN | No gain over no-graph features | Graph is sparse (few xrefs per contract) and labels are only 172 pairs | Kept as optional, reported as ablation |
| 13 | Encoders on the GPU during the demo | Kev returned HTTP 500 (CUDA out of memory) | Kev peaks ~3.8 GB; InLegalBERT + SBERT took another 1.85 GB of a 6 GB card | Encoders run on CPU during the demo (`LEGALAGENT_DEVICE=cpu`); GPU reserved for Kev |
| 14 | Retrieval/GNN on CPU while training | CPU at 100 %, laptop sluggish | Heavy jobs fell back to CPU when the GPU was busy | Queue jobs one at a time on the GPU (`train/gpu_queue.sh`, `overnight.sh`) |
| 15 | Large Qdrant index of all Indian Acts (11.2 GB) | Not used | Download size + needs a separate embedding model on the same GPU; time before the viva | Future work; our 4,408-section library covers the Acts that matter for contracts |
| 16 | Nyaya embedding model comparison | Stopped unfinished | Slow on CPU, would compete with Kev for the GPU; user asked for no more experiments | Kept fine-tuned InLegal-SBERT |
| 17 | Editing a running shell script | Training run crashed with a syntax error | bash reads scripts incrementally | Never edit scripts while running |
| 18 | `results/` was in `.gitignore` | Results were not committed | Old ignore rule | `!results/` |
| 19 | Shortlist on a 580-clause scanned contract | 14,025 pairs, ≈1 hour of judging for one PDF | Clause-type-matrix pairs were "never capped": every liability × indemnity × payment clause combination became a pair | Cross-references always kept; other pairs ranked (signals agreeing → clash weight → retrieval rank) and capped at 60 → 173 pairs, **4.4 min for 305 pages** |
| 20 | Kev on long OCR'd clauses | HTTP 500 (CUDA out of memory), contract fell back to rules | Kev's state-prefix cache (64k tokens by default) + 4 parallel requests filled the 6 GB card | Prefix cache capped (2 states / 6k tokens), expandable CUDA segments, 2 parallel requests, retry per pair, skip a single failing pair instead of dropping the whole contract |
| 21 | Demo excerpt with answer-key notes | Planted clauses carried "*(Statutory Conflict: …)*" notes inside the text | The adversarial sample was written for humans | The dashboard analyses a clean copy with the notes stripped (`data/demo/generated/pune_metro_15_planted_clean.md`) |

---

## 5. What is left / future work

- Lawyer-reviewed Indian clause-pair test set (current pair labels are silver).
- Larger Kev (4B) or contrastive bad/fixed training pairs; ContractNLI as auxiliary data.
- Full Indian Acts index (Open India Law Qdrant) with a small local embedding model.
- Overnight run (`scripts/overnight.sh`): Kev v3 with all teacher labels; replaces the demo judge only if it
  beats the base on the independent tests.
