# Datasets

🇮🇳 = Indian. Everything is public; nothing private or client data is used.

| Dataset | Source / licence | Size | Used for |
|---|---|---|---|
| **CUAD v1** | Atticus Project, CC BY 4.0 (github.com/TheAtticusProject/cuad) | 510 contracts, 41 lawyer-annotated categories | CLAUSE-22 rows, out-of-distribution test split, retrieval evaluation, teacher pairs |
| **LEDGAR** (LexGLUE) | coastalcph/lex_glue, CC BY-SA 4.0 | 80,000 provisions, 100 labels | CLAUSE-22 rows (official LexGLUE train/val/test split kept) |
| **CLAUSE-22** (ours) | `clause20/build.py` from CUAD + LEDGAR | 74,374 clauses · train 55,915 / val 9,341 / test 8,415 / test_ood 703 | clause classifier training + evaluation |
| 🇮🇳 **Open India Law — central legislation** | vaquill.ai mirror of India Code (official), HF copy gated | 74,484 section chunks → **2,436 sections, 23 commercial Acts** | statute library (RAG grounding, citation verification) |
| 🇮🇳 **BNS / BNSS / BSA 2023, CPC 1908, landmark precedents** | curated in `research/clause_taxonomy/indian_law_docs/` | +706 records | statute library → 3,142 sections, 33 Acts |
| 🇮🇳 **NHAI Model Concession Agreement (4-laning)** | Government of India, scanned PDF | 276 pages → 632 clauses (OCR) | Indian clause eval set, teacher pairs, demo |
| 🇮🇳 **Pune Metro Line-3 Concession (signed)** | Government of Maharashtra / PMRDA, scanned PDF | 300 pages → 565 clauses (OCR) | Indian clause eval set, false-alarm control |
| 🇮🇳 **Pune Metro + 15 planted irregularities** | ours (`data/demo/india/adversarial/INJECTIONS.json`) | 305 pages | **held-out** end-to-end detection test |
| 🇮🇳 **Indian benchmark contracts** | ours (`data/demo/india/custom_benchmark/`) | 5 contracts with expected findings | **held-out** regression benchmark |
| 🇮🇳 **Indian clause eval (silver)** | 220 clauses from the two concessions, Gemini-labelled; re-labelled by Gemini 4 in `types` mode | 220 (+364) clauses | Indian transfer of the classifier |
| **Teacher-labelled pairs** | ours: pairs shortlisted by our selector from 316 contracts, labelled by Gemini 4 Hydrogen via Antigravity CLI | 2,522 exported, **1,000 labelled** (123 Indian) | Kev judge fine-tuning, GNN, judge evaluation (held-out split by contract) |
| **Checklist pairs** | ours (`scripts/make_checklist.py`) | 28 known-answer minimal pairs | teacher validation + judge evaluation independent of the teacher |
| **Human gold set** | team, blind (`scripts/review_gold.py`) | up to 120 pairs (72 held-out) | teacher accuracy, judge accuracy vs humans |

## Honest gaps
- There is **no public Indian contract-clause dataset** and **no public dataset of labelled
  clause-to-clause conflicts** (in any jurisdiction). We therefore (a) train clause types on
  CUAD/LEDGAR (US filings) and measure transfer to Indian text, (b) build pair labels by
  distillation from a large model and validate the teacher against independent ground truth.
- 66 of 510 CUAD contracts use `ARTICLE V` / `(a)`-only numbering that the extractor does not split.
- OCR of scanned concessions introduces errors (e.g. "29.4" for "29.1") which lower retrieval on Indian text.
