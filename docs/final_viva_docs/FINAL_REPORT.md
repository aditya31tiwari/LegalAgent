# LegalAgent: Local-First Cross-Clause Risk Detection in Indian Contracts

*B.Tech Major Project, Jaypee Institute of Information Technology — final report (Markdown edition).*
*All figures are produced by `scripts/eval_all.py` and stored in `results/`; `results/REPORT_TABLES.md` is the
authoritative copy.*

---

## Abstract

Contract risk often lies not in a single clause but in how clauses interact: a liability cap undone by an
uncapped indemnity, a termination right that collides with a survival clause, a non-compete that Indian law
declares void. We present **LegalAgent**, a local-first system that reads Indian commercial contracts
(including scanned documents), extracts and classifies clauses, shortlists clause pairs likely to interact,
judges them with a locally served decision model, checks single clauses against Indian law, and grounds every
finding in retrieved India Code sections. The pipeline uses PyMuPDF/pymupdf4llm and parallel Tesseract OCR for
ingestion, a fine-tuned **InLegalBERT** classifier over our 22-label taxonomy **CLAUSE-22** (micro-F1 0.931 in
domain, 0.750 out of domain), hybrid BM25 + fine-tuned **InLegal-SBERT** retrieval, and **Kev-0.8B**, an open
decision model, as the pair judge. Training data for the judge was distilled from Gemini 4 and validated
against independent ground truth. We evaluate on five kinds of ground truth we did not generate with the
system: lawyer clause annotations (CUAD), lawyer-grounded interaction pairs, a bad/fixed checklist, clauses
from 18 Supreme Court of India judgments, and a 305-page scanned concession agreement with 15 planted
irregularities. The selected judge reaches 71 % checklist accuracy and 75 % recall on lawyer-grounded pairs
(rules baseline: 46 % / 7.5 %); a single-clause Indian-law check catches 6 of 9 clauses the Supreme Court
struck down, where keyword rules catch none. All inference runs on a 6 GB laptop GPU; no contract text leaves
the machine.

---

## 1. Introduction

### 1.1 Problem
Manual contract review in India is slow and expensive, and existing tools score clauses one at a time. Risks
created by the *combination* of clauses, and conflicts with Indian statutes such as the Indian Contract Act,
1872, are easy to miss in long infrastructure (PPP) contracts that are often available only as scans.

### 1.2 Objectives and final status

| # | Objective | Status |
|---|---|---|
| O1 | Extract and classify clauses from real (incl. scanned) Indian contracts | ✓ ingestion + OCR, CLAUSE-22 InLegalBERT (0.931 / 0.750) |
| O2 | Find related clause pairs efficiently; compare retrieval methods | ✓ xref + type matrix + hybrid retrieval; 6 methods compared, retrievers fine-tuned |
| O3 | Judge cross-clause risk | ✓ local Kev judge, selected on independent tests (71 % checklist, 75 % CUAD recall) |
| O4 | Ground findings in Indian law | ✓ 4,408 sections / 37 Acts, hybrid RAG, citation verification, Kev clause-vs-law check |
| O5 | Usable application | ✓ dashboard with real upload, live progress, under-the-hood scores page, desktop Workbench |

### 1.3 Scope and limitations
Central Acts only (no state amendments); pair labels for training are silver (model-generated, validated, not
lawyer-reviewed); Kev over-flags in clause-vs-law (shown with confidence labels); test sets are small
(28 / 280 / 18 / 15 items).

---

## 2. Literature survey (summary)

- **Legal language models:** LEGAL-BERT; **InLegalBERT** and InLegal-SBERT, pre-trained on Indian court text.
- **Contract datasets:** CUAD (510 contracts, 41 lawyer categories), LEDGAR (SEC provisions), ContractNLI.
- **Retrieval:** BM25; dense bi-encoders (Sentence-BERT); hybrid retrieval with reciprocal rank fusion;
  cross-encoder rerankers (bge-reranker).
- **Retrieval-augmented generation (RAG)** for grounding legal answers in statute text; Indian legal RAG
  resources (India Code, Open India Law, Nyaya datasets).
- **Decision models:** Jev / System One; **Kev**, an open reconstruction (Qwen3.5-0.8B + pointer head).
- **Training under constraints:** LoRA, bf16, gradient checkpointing; focal loss and threshold calibration for
  imbalance; knowledge distillation from LLM teachers (silver labels).
- **Graph learning:** GraphSAGE for link prediction.

---

## 3. System design

### 3.1 Pipeline

```
ingest → extract → classify → shortlist pairs → judge pairs (Kev) → clause-vs-law (rules + Kev)
       → statute RAG grounding + citation check → validate → rank → SQLite → dashboard
```

| Stage | Method |
|---|---|
| Ingestion | pymupdf4llm (digital pages); Tesseract OCR in parallel, cached by file hash (scanned pages) |
| Extraction | numbering patterns, TOC filter, ARTICLE/SCHEDULE parts, parent hierarchy, cross-reference resolution |
| Classification | InLegalBERT fine-tuned on CLAUSE-22 + keyword backstop + heading prior + 7 Indian rule labels |
| Shortlisting | cross-references; 40-pair clause-type clash matrix; hybrid BM25 + dense retrieval (RRF); optional GNN |
| Pair judge | Kev-0.8B served locally; typed questions: relation, severity, statute (choice among retrieved sections) |
| Clause vs law | regex rules + Kev single-clause check over 7 Indian-law risk categories |
| Grounding | 4,408 India Code sections; hybrid BM25 + fine-tuned InLegal-SBERT + Act prior; citations verified |
| Fallback | Gemini (opt-in) → Kev → rules; any unavailable component degrades, never crashes |

### 3.2 Data model
`Clause` (id, number, heading, text, part, parent_id, labels, xrefs); `Finding` (target and related clauses,
relation type, severity, risk score, rationale, surfaced_by, evidence spans, statute refs with confidence);
`Run` (config, per-stage timings, judge used).

### 3.3 Datasets

| Dataset | Use |
|---|---|
| CLAUSE-22 (74,374 clauses from CUAD + LEDGAR, mapped) | classifier training / test (55,915 / 9,341 / 8,415 / 703 OOD) |
| Indian contracts (Pune Metro, NHAI, our samples) | silver set (220 clauses), demo, end-to-end test |
| Teacher pairs (Gemini 4: 1,740; Claude: 620) | judge training (silver), held-out set of 172 |
| Checklist (28 bad/fixed twins) | judge test |
| CUAD interaction pairs (280) | judge recall test |
| Supreme Court litigated clauses (18 cases) | clause-vs-law and statute retrieval test |
| India Code + Nyaya Acts (4,408 sections, 37 Acts) | statute library |

---

## 4. Implementation

- **Hardware:** RTX 4050 Laptop (6 GB), Ubuntu; all training and inference local.
- **Classifier training:** InLegalBERT, 3 epochs, lr 3e-5, batch 16, max length 256, threshold tuned on validation (48 min).
- **Retriever training:** InLegal-SBERT with cached multiple-negatives ranking loss; 2,821 clause pairs and
  2,967 clause→section pairs; 1 epoch each (≈2 min).
- **Judge training:** Kev LoRA r=16, bf16 weights, gradient checkpointing; v1 828 imbalanced records; v2 440
  balanced records, focal loss γ=2, lr 2e-4, 2 epochs (58 min); decision threshold τ calibrated on training contracts.
- **Teacher:** Gemini 4 via Antigravity CLI with a strict JSON schema; Claude Sonnet as second opinion.
- **GPU sharing:** Kev (~3.8 GB peak) owns the GPU during demos; encoders run on CPU; automatic CPU fallback on out-of-memory.
- **Application:** FastAPI + server-sent events, SQLite, HTML/JS dashboard, Chart.js "under the hood" page, Tkinter Workbench.
- **Tests:** automated pytest suite (pipeline, extraction, XSS escaping, local-first defaults).

---

## 5. Results

### 5.1 Clause classification

| Classifier | Test micro-F1 | OOD micro-F1 | Indian silver micro-F1 |
|---|---|---|---|
| Keyword | 0.275 | 0.404 | 0.329 |
| MiniLM + LR | 0.828 | 0.590 | 0.418 |
| **InLegalBERT (CLAUSE-22)** | **0.931** | **0.750** | 0.411 |
| Ensemble | — | — | **0.443** |

### 5.2 Related-clause retrieval (R@5)

| Method | CUAD | Indian |
|---|---|---|
| BM25 | 0.347 | 0.165 |
| MiniLM | 0.371 | 0.126 |
| bge-small | 0.384 | 0.143 |
| InLegal-SBERT (base) | 0.265 | 0.088 |
| Hybrid MiniLM | 0.366 | 0.167 |

### 5.3 Cross-clause judge

| Judge | Checklist acc. | CUAD recall | Teacher risky-F1 |
|---|---|---|---|
| Rules | 46 % | 7.5 % | 0.04 |
| **Kev base (selected)** | **71 %** | **75 %** | 0.46 |
| Kev v1 fine-tuned | 43 % | — | — |
| Kev v2 fine-tuned + τ | 54 % | 31 % | **0.62** |

Fine-tuning improved agreement with the teacher but reduced performance on the independent tests; the
judge is therefore selected by the independent tests only.

### 5.4 Clause vs Indian law

| Method | SC struck-down caught | Planted single-clause faults caught | False alarms |
|---|---|---|---|
| Regex rules | 0 / 9 | 4 / 6 | 0 |
| Kev check | 6 / 9 | 5 / 6 | 9 |

### 5.5 Statute grounding (19 independent queries)

| Retriever | R@5 | Act@3 |
|---|---|---|
| BM25 | 0.105 | 0.42 |
| Hybrid + Act prior | 0.211 | 0.32 |
| **Fine-tuned hybrid + Act prior** | **0.316** | **0.53** |
| + reranker | 0.263 | 0.47 |

### 5.6 Teacher validation
Checklist 92.9 %; clause types vs lawyer labels 75 % (first type), 85 % (any overlap); cited sections existing
in India Code 85.7 %; Gemini–Claude agreement κ = 0.57.

### 5.7 GNN ablation
GraphSAGE ROC-AUC 0.742 vs 0.748 without the graph and 0.738 for cosine similarity: no measurable gain.

### 5.8 End-to-end
Pune Metro 305-page scan: 580 clauses, 99 parts, 137 resolved cross-references; the end-to-end detection of
the 15 planted irregularities and per-stage runtimes are in `results/REPORT_TABLES.md` (end-to-end section).

### 5.9 Economics
All inference is local: ₹0 per contract and no data leaves the machine. Teacher labelling used an existing
subscription quota.

---

## 6. Conclusion

### 6.1 Achievements
A working, local, end-to-end system for Indian contracts that goes from a scanned PDF to grounded cross-clause
and statutory findings, with every component measured against independent ground truth.

### 6.2 Lessons
1. Selecting models by agreement with the teacher is circular; independent tests changed our decision.
2. Small silver datasets can make a fine-tuned model worse than its base.
3. Keyword rules fail on real legal drafting; model-based checks need confidence labels, not verdicts.
4. On OCR'd Indian text, lexical retrieval (BM25) remains essential.

### 6.3 Limitations
Silver training labels; small test sets; over-flagging in clause-vs-law; central Acts only; no state law or
case-law retrieval.

### 6.4 Future work
Lawyer-verified Indian pair set; Kev-4B; contrastive bad/fixed training; ContractNLI auxiliary training; full
Indian Acts vector index (Open India Law Qdrant) and case-law retrieval.

---

## Appendix A — Reproduce

```bash
bash scripts/start_demo.sh            # Kev on :8008 + dashboard on :8080
venv/bin/python scripts/seed_demo.py  # real demo database
venv/bin/python scripts/eval_all.py tables   # regenerate every table
```
