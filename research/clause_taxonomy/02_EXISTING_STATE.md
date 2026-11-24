# What exists today (as of 2026-11-24, branch `final`)

Repo: `aryan@192.168.1.10:/home/aryan/Projects/LegalAgent/LegalAgent`, venv `venv/` (Python 3.12,
torch 2.15 + CUDA, RTX 4050 6 GB). Read the files named here before proposing changes.

## Pipeline (where labels are used)

```
ingest (PDF/DOCX/TXT/MD, OCR fallback)          legalagent/core/ingestion.py
 → extract clauses + cross-refs                 legalagent/core/extraction.py
 → classify (CLAUSE-20, multi-label)            legalagent/core/classification.py
 → candidate pairs: xref + TYPE_MATRIX + BM25/dense/hybrid retrieval (+GNN)
                                                legalagent/core/candidate_selection.py
 → judge each pair: rules | local Kev | Gemini  legalagent/core/pipeline.py
 → ground in Indian statutes (2,436 sections)   legalagent/core/statutes.py
```

`TYPE_MATRIX` is loaded from `clause20/labels.yaml → conflict_pairs` (17 pairs) plus
`force_majeure+termination` and `force_majeure+payment_and_fees`.

## Taxonomy: CLAUSE-20 (`clause20/labels.yaml`)

20 labels + `other`. Selection criteria: (1) appears in a clash pair, (2) ≥ 300 examples.
Known gap: `force_majeure` (in neither source) — added by keyword rule in classification.py.

Mapping from sources: `clause20/label_map.yaml` (all 41 CUAD + 100 LEDGAR labels mapped,
`unmapped_policy: fail`). Notable mapping decisions worth questioning:
- CUAD "Uncapped Liability", "Cap On Liability", "Liquidated Damages" → `limitation_of_liability`
- CUAD "Non-Compete", "Exclusivity", "No-Solicit…", "Non-Disparagement", "ROFR/ROFO/ROFN",
  "Most Favored Nation" → `exclusivity_and_restraint`
- LEDGAR "Jurisdictions", "Venues", "Waiver Of Jury Trials", "Remedies", "Specific Performance",
  "Releases", "Arbitration" → `dispute_resolution`
- LEDGAR "Representations" + "Warranties" → `warranty`
- LEDGAR "Definitions", "Severability", "Counterparts", "Employment", "Vesting" … → `other`

## Dataset: CLAUSE-20 build (`clause20/build.py`, run today)

- Sources: CUAD v1 (510 contracts, `dataset/data.zip`), LEDGAR from LexGLUE (80k provisions,
  `dataset/ledgar_*.csv.zip`).
- CUAD: 20,412 clauses cut by our extractor; **66/510 contracts yield no clauses** (ARTICLE /
  (a) numbering not supported yet); highlight miss rate 6.5%.
- After dedup: **74,295 rows** (73,173 gold, 1,122 silver heading-rule rows).
- Splits: train 55,853 / validation 9,334 / test 8,415 (LexGLUE official) / test_ood 693
  (unseen CUAD contracts). `test` is missing limitation_of_liability and license_grant
  (they come only from CUAD).
- Label counts after dedup:

| label | rows | | label | rows |
|---|---:|---|---|---:|
| other | 20,515 | | confidentiality | 2,446 |
| compliance_and_law | 7,316 | | survival | 1,807 |
| amendment_and_integration | 7,148 | | termination | 1,763 |
| payment_and_fees | 5,657 | | indemnification | 1,725 |
| dispute_resolution | 5,284 | | insurance | 1,487 |
| governing_law | 4,194 | | audit_and_records | 1,408 |
| assignment_change_of_control | 3,489 | | warranty | 1,395 |
| term_and_renewal | 2,691 | | exclusivity_and_restraint | 1,041 |
| notices | 2,646 | | ip_ownership | 755 |
| tax | 2,548 | | license_grant | 514 |
| | | | limitation_of_liability | 474 |

## Models (training now / done)

- `minilm_lr`: all-MiniLM-L6-v2 frozen + one-vs-rest logistic regression, val micro-F1 0.758
  (`models/clause20_labeller.joblib`, `clause20/train.py`).
- `inlegalbert`: law-ai/InLegalBERT full fine-tune, multi-label BCE, 3 epochs, threshold tuned
  on validation (`train/finetune_classifier.py` → `models/clause20_inlegalbert/`,
  metrics → `results/classifier_clause20_inlegalbert.json`). Re-running with a new taxonomy
  costs ~45 min GPU.
- Any taxonomy change = edit yaml → `for st in labels cuad ledgar merge dedup split; do
  venv/bin/python clause20/build.py $st; done` (~1 min) → retrain.

## Indian data on disk

- `data/demo/india/official/`: NHAI model concession (4-laning) PDF, Pune Metro Line-3 signed
  concession PDF (both real government contracts).
- `data/demo/samples/`: 6 markdown contracts incl. a Pune Metro version with 15 planted
  irregularities (`data/demo/india/adversarial/INJECTIONS.json`) — held out for evaluation.
- `data/demo/india/custom_benchmark/`: 5 synthetic Indian contracts with expected findings.
- `data/derived/india_clause_eval.jsonl`: ~220 Indian clauses with Gemini silver CLAUSE-20
  labels (being generated now).
- `data/statutes/india_commercial_sections.jsonl`: 2,436 sections from 23 central Acts (ICA,
  SRA, A&C, SoGA, DPDP, IT Act, Competition, Stamp, Limitation, TPA, Companies, IBC, CPA,
  MSMED, Copyright, Patents, TM, ID Act, Commercial Courts, Mediation, NI, FEMA, Partnership)
  from Open India Law (vaquill.ai mirror; HF copy is gated).

## Other prior docs

- `docs/CUAD.md` — why CUAD spans → clause labels is defensible.
- `tests/old_examples/docs/INDIAN_LAW_RESEARCH.md`, `01_LEGAL_STATUTORY_RESEARCH.md`,
  `03_CROSS_CLAUSE_GRAPH_AND_RISK_DETECTION.md` — earlier research notes (also under
  `research/` on branch `origin/aditya-tiwari`).
- Draft report: `/home/aryan/Downloads/LegalAgent_Final_Report.docx` (Section 3.2.3 / 4.1.3 /
  Appendix A describe CLAUSE-20).
