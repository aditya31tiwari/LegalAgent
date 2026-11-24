# Evaluation

Every number below is produced by a script (`scripts/eval_all.py`, `scripts/validate_teacher.py`,
`train/*`) into `results/*.json`; `results/REPORT_TABLES.md` is regenerated from those files and is
the authoritative version. This document explains the protocol and how to read each result.

## Principles
1. **Headline numbers never depend on teacher labels.** Classifier: lawyer-annotated test splits.
   Retrieval: the contract's own cross-references. End-to-end: 15 irregularities planted by us.
   Checklist: answers known by construction. Teacher labels are used for training and one
   intermediate comparison, and the teacher itself is validated against independent ground truth.
2. **Held-out by contract.** Pair data is split by contract; the GNN and Kev never see a test contract.
3. **No leakage in retrieval.** Clause numbers and "Section x.y" phrases are masked before indexing,
   because the gold pairs are derived from exactly those references.
4. **Ablations kept.** taxonomy v1 vs v2 · Kev base vs fine-tuned · GNN vs no-graph · base vs
   fine-tuned InLegal-SBERT · act prior on/off.

## 1. Clause classification (CLAUSE-22)
| Classifier | test micro-F1 | test_ood micro-F1 |
|---|---|---|
| MiniLM + LogReg (original report, CLAUSE-20) | 0.81 | 0.46 |
| MiniLM + LogReg (CLAUSE-22) | 0.828 | 0.591 |
| InLegalBERT fine-tuned, CLAUSE-20 (v1) | 0.925 | 0.715 |
| **InLegalBERT fine-tuned, CLAUSE-22 (v2)** | **0.931** | **0.750** |

test = LexGLUE official LEDGAR test (8,415) + no CUAD; test_ood = 703 clauses from CUAD contracts
never seen in training — the closer match to real use. Indian transfer: `eval_all.py classifier`
also scores the Indian silver set (teacher-labelled; see §6 for how far the teacher can be trusted).

## 2. Related-clause retrieval (recall@10; gold = resolved cross-references)
| Method | CUAD (120 contracts) | Indian concessions (3) |
|---|---|---|
| BM25 | 0.464 | **0.224** |
| Dense MiniLM | 0.514 | 0.168 |
| Dense bge-small | **0.516** | 0.189 |
| Dense InLegal-SBERT (base) | 0.374 | 0.127 |
| Hybrid MiniLM (RRF) | 0.491 | 0.213 |
| InLegal-SBERT fine-tuned (contrastive) | see REPORT_TABLES | see REPORT_TABLES |

Reading: general sentence encoders win on US filings; BM25 wins on OCR'd Indian concessions
(domain shift + OCR noise). Base InLegal-SBERT — trained on judgments — is weakest for contract
cross-references, which motivated the contrastive fine-tune. Hybrid is the robust default.

## 3. Pair judges
Held-out teacher-labelled pairs (172 pairs from test contracts; 70 % no_issue):

| Judge | accuracy | risky recall | risky F1 | runs locally |
|---|---|---|---|---|
| Rules | 0.698 | 0.02 | 0.04 | yes |
| Kev-0.8B base, zero-shot | 0.198 | 0.85 | 0.46 | yes |
| Kev-0.8B fine-tuned | see REPORT_TABLES | | | yes |
| Gemini 4 Hydrogen (teacher) | reference | | | no |

Reading: hand rules are precise but narrow (they only know two patterns); off-the-shelf Kev
flags almost everything. Fine-tuning is what turns a general decision model into a contract judge.

## 4. Known-answer checklist (28 pairs; independent of the teacher)
12 classic cross-clause risks, each as a *bad* pair and a minimally *fixed* twin (the fix must
clear it), plus 4 planted Pune Metro injections. Neutral ids; twins never share a prompt.

| Judge | binary accuracy | bad pairs caught | fixed pairs cleared |
|---|---|---|---|
| Rules | 0.464 | 0.125 | 0.917 |
| Kev base | 0.714 | 0.688 | 0.750 |
| Kev fine-tuned | see REPORT_TABLES | | |
| Teacher (Gemini 4 Hydrogen) | **0.929** | 1.000 | 0.833 |

Note: one teacher "miss" (`noncompete_survival_fixed`) is arguably a checklist design flaw — the
shared clause still makes Clause 15 survive termination, so flagging it is defensible. Kept as-is
(not edited after seeing results).

## 5. End-to-end on the Pune Metro concession (305 scanned pages, 15 planted irregularities)
`eval_all.py e2e`: recall of the 15 planted clauses among findings, findings on the clean signed
concession (false-alarm control), runtime per stage, and a single-clause baseline (labels +
statutory rules only, no pairing) for the cross-clause vs single-clause comparison (report Table 5.5).

## 6. Teacher validation (how far can the distilled labels be trusted?)
| Check | Ground truth | Result |
|---|---|---|
| Clause types vs lawyer labels (428 CUAD/LEDGAR clauses) | CUAD/LEDGAR annotations | 85 % overlap, 75 % first type exact |
| Citations resolvable in India Code (266 cited) | local India Code library | 86 % verified |
| Known-answer checklist | construction | 92.9 % |
| Second model family (Claude Sonnet 5.5, 300 pairs) | inter-annotator κ | after quota reset (optional) |
| Blind human review | team, `scripts/review_gold.py` | when completed |

Known bias: ICA s.37 is over-cited (118 / 228 verified citations) — the prompt's example anchored
it. Demo citations therefore come from the local retriever + verification, not teacher memory.

## 7. Clause-graph GNN
`train/train_gnn.py`: ROC-AUC / average precision / P@5 on held-out contracts for GNN vs the same
scorer without message passing vs type-matrix weight vs cosine — see REPORT_TABLES.

## Limitations
- No public Indian contract-clause or clause-conflict dataset → Indian results use silver labels.
- Teacher labels are model judgements; validated, not gold. Human gold set is small.
- OCR noise on scanned concessions; ARTICLE V / (a)-only numbering not split (66/510 CUAD).
- Small judge test set (172 pairs): differences of a few points are within noise.
