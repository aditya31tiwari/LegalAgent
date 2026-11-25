# Decisions — what we chose, why, and why not the alternatives

Each row is a decision a panel can question. **Chose** = what the system does now. **Why** = the reason, with the
measured number where there is one. **Why not** = the alternatives we considered or tried, and what happened.
Numbers come from `results/` (see `/report`).

---

## A. Overall approach

| # | Decision | Chose | Why | Why not the alternatives |
|---|---|---|---|---|
| A1 | Unit of analysis | **Clause pairs** (+ single clauses vs law) | Most contract risk is in interactions (cap vs indemnity, termination vs survival); single-clause tools miss them | Single-clause scoring only: that's what existing tools do, and it can't see "clause 18 undoes clause 12" |
| A2 | Where models run | **Locally on one laptop GPU** | Contracts are confidential; DPDP Act 2023; ₹0 per contract; works offline | Cloud LLM for every pair: data leaves the machine, costs per call, rate limits (we hit 503s from Gemini repeatedly) |
| A3 | Role of the big LLM (Gemini) | **Teacher (offline) + opt-in "Explain" button** | Its labels train our small model; users choose if text goes to the cloud | Gemini as the default judge: privacy, cost and latency, and its availability was unreliable (503 / retired models) |
| A4 | Jurisdiction | **Indian contracts and Indian law** | Our users and the project's purpose; Indian law has strong special rules (ICA s.27 voids post-term non-competes) | Generic/US-style analysis: would get Indian law wrong (e.g. "reasonable" non-competes are enforceable in the US, void in India) |

## B. Reading documents

| # | Decision | Chose | Why | Why not |
|---|---|---|---|---|
| B1 | PDF → text | **PyMuPDF via pymupdf4llm** | Fast, keeps headings/lists/tables as Markdown, so "ARTICLE 12" structure survives | PyPDF2 / pdfminer: lose structure. Commercial parsers: cloud, cost |
| B2 | Scanned pages | **Tesseract OCR, parallel per page, cached by file hash** | Free, local, good on printed text; parallel + cache turned a "hung" 305-page OCR into ~2 min first time, instant after | Cloud OCR (Google Vision): data leaves the machine. Neural OCR (docTR/Surya): slower, would need the GPU that Kev uses |
| B3 | Clause splitting | **Rules (numbering patterns, TOC filter, parts, parents)** | Numbering is regular; rules are exact and explainable; 580 clauses / 99 parts / 137 cross-refs on Pune Metro | An ML segmenter: needs labelled segmentation data we don't have; harder to debug |

## C. Understanding clauses

| # | Decision | Chose | Why | Why not |
|---|---|---|---|---|
| C1 | Taxonomy | **CLAUSE-22** (22 types + other + 7 Indian rule labels) | Every label can clash with another label, and has ≥ 300 examples; arbitration and remedies split out because they clash differently | CLAUSE-20 (mid-term): mixed arbitration/remedies/courts in one label. CUAD's 41 labels: many are not clash-relevant and are too rare |
| C2 | Classifier | **Fine-tuned InLegalBERT** | 0.931 test / 0.750 out-of-domain micro-F1; pre-trained on Indian legal text; 4 ms/clause on GPU | MiniLM + logistic regression (mid-term): 0.828 / 0.590. Keyword rules: 0.275. An LLM to label each clause: slow, cloud |
| C3 | Rare Indian clause types | **Keyword rules** (stamp duty, DPDP, step-in…) | < 300 examples exist, too few to train; rules are precise for fixed legal phrases | Training on tiny data: unreliable labels |
| C4 | Ensemble / headings | Ensemble + heading prior **available, InLegalBERT as default** | Ensemble helps the Indian silver set slightly (0.443 vs 0.411), headings help macro-F1 | Making the ensemble default: slower, small gain on noisy silver labels |

## D. Choosing which pairs to check

| # | Decision | Chose | Why | Why not |
|---|---|---|---|---|
| D1 | Shortlist signals | **Cross-references + 40-pair clash matrix + hybrid retrieval** | Each catches different pairs: explicit links, known risky type combinations, similar wording | Judging all pairs: 580 clauses = 167,910 pairs ≈ hours. Retrieval only: misses type-based clashes |
| D2 | Retrieval method | **Hybrid BM25 + dense (RRF)** | BM25 is best on OCR'd Indian text (R@5 0.165 vs dense 0.126); dense helps paraphrase on clean text | Dense only: weak on OCR noise. BM25 only: misses paraphrases |
| D3 | Pair cap | **All cross-reference pairs + 60 best others, ranked** | 305-page scan: 14,025 pairs → 173 pairs, ≈1 h → 4.4 min | Uncapped type-matrix pairs (old behaviour): an hour per big contract |
| D4 | GNN | **Built and evaluated, off by default** | Ablation: GNN ROC-AUC 0.742 vs 0.748 without the graph, so no gain | Keeping it on: costs time, adds nothing measurable. Not building it: we'd have no answer to "did you try graphs?" |

## E. Judging pairs

| # | Decision | Chose | Why | Why not |
|---|---|---|---|---|
| E1 | Judge model type | **Kev, a decision model** (reads, points at an option, gives probabilities) | Fits 6 GB, ~0.1–0.3 s/decision, probabilities for confidence labels, can't hallucinate prose | Generative local LLM (Llama 8B): doesn't fit next to everything else; free text needs parsing and checking |
| E2 | Which Kev | **Base Kev-0.8B, zero-shot** | Best on independent tests: checklist 71 %, CUAD lawyer recall 75 % | Fine-tuned v2: 54 % / 31 % (better only vs the teacher, 0.62 F1). Fine-tuned v1: collapsed to "no_issue" (43 %, caught 0 bad pairs) |
| E3 | How to pick the judge | **Independent tests only** (checklist, CUAD lawyer pairs) | A model can match the teacher by copying its mistakes; independent tests measure the task | Teacher agreement: circular (it would have picked v2, which is worse on real tests) |
| E4 | Decision rule | **Argmax** for the served base model | Calibrated threshold τ lowered base Kev's checklist score (54 %) | τ for base: worse. τ for v2: helped v2 (recall 31 % vs 21 %), but v2 still lost |
| E5 | Rules judge | **Kept as fallback** | Never crashes, no model needed; the demo keeps working if Kev is down | Rules as the main judge: 46 % checklist, 7.5 % recall |
| E6 | Over-flagging | **Accept, show severity + confidence, group low-confidence** | For a reviewer, missing a void clause costs more than a second look | Hiding weak signals: the user asked to show low-confidence connections rather than hide them |

## F. Indian law

| # | Decision | Chose | Why | Why not |
|---|---|---|---|---|
| F1 | Clause-vs-law check | **Kev single-clause check (7 risk categories) + regex rules** | Kev caught 6/9 clauses the Supreme Court struck down; regex 0/9 | Regex only: fails on real drafting ("from the date you leave", "earnest money shall stand forfeited") |
| F2 | Showing law | **Retrieve real India Code text (RAG); verify every citation exists** | No invented sections; the user can read the actual law | Letting a model write the law from memory: hallucinated or wrong sections |
| F3 | Statute library | **4,408 sections from the Acts that matter for contracts** (India Code mirror + Nyaya datasets + key precedents) | Small, fast, local, covers ICA, A&C, SRA, Stamp, DPDP, Companies, IBC… | 11 GB Open India Law index of all Acts: big download + another embedding model on the GPU, mostly irrelevant Acts. Future work |
| F4 | Statute retriever | **Hybrid BM25 + fine-tuned InLegal-SBERT + Act prior** | Exact section in top 5: 0.105 (BM25) → 0.316; Act in top 3: 0.53 | Base InLegal-SBERT: 0.053. Cross-encoder reranker (bge-reranker-v2-m3): worse (0.263) and needs GPU. Nyaya embedding: slow, competes with Kev, stopped (no time) |
| F5 | Confidence | **high / medium / low labels on every law finding and reference** | Kev also flags upheld clauses (4/4 false alarms on SC upheld); labels make that visible | Hard verdicts: would overstate certainty |

## G. Training and data

| # | Decision | Chose | Why | Why not |
|---|---|---|---|---|
| G1 | Pair training labels | **Teacher–student distillation** (Gemini 4 labels, Claude as second opinion) | No public dataset of labelled Indian clause *pairs* exists; lawyers were not available | Hand-labelling: too slow. No training: we'd have nothing to fine-tune or compare |
| G2 | Trusting the teacher | **Validated against independent truth** | 92.9 % checklist, 75 % lawyer clause types, 85.7 % real citations, κ 0.57 vs Claude | Trusting it blindly: unknown error rate |
| G3 | Teacher tool | **Antigravity CLI (`agy`) with a strict JSON schema** | Reliable access to Gemini 4 within an existing subscription; structured output | Gemini API free tier: 503s and retired models |
| G4 | Fine-tuning method | **LoRA r=16, bf16, gradient checkpointing** | Fits a 0.8B model on 6 GB | Full fine-tuning: doesn't fit |
| G5 | Imbalance | **Balanced set + focal loss + threshold** | v1 (imbalanced) collapsed to always "no_issue" | Plain cross-entropy on 73 % no_issue data: the collapse |

## H. Evaluation

| # | Decision | Chose | Why | Why not |
|---|---|---|---|---|
| H1 | Ground truth | **Five independent kinds**: lawyer labels (CUAD), lawyer-grounded pairs, bad/fixed checklist, Supreme Court outcomes, planted faults | Each checks a different claim; none was produced by our teacher | Only teacher-labelled test data: circular |
| H2 | Statute retrieval gold | **Section a court applied + our injections (19 queries)** | Teacher citations were 94 % ICA (s.37 over-cited), so they made every method look the same | Teacher citations as gold: an "always say ICA" baseline scored 0.94 |
| H3 | Honest negatives | **Reported** (v1 collapse, v2 < base, GNN no gain, reranker worse, regex 0/9) | They are findings; they justify every choice above | Hiding them: the choices would look arbitrary |

## I. Engineering

| # | Decision | Chose | Why | Why not |
|---|---|---|---|---|
| I1 | GPU sharing | **Kev owns the GPU; small encoders on CPU in the demo** | Kev must never run out of memory; a single 6 GB card | Everything on GPU: out-of-memory crashes during the demo (happened) |
| I2 | Kev serving | **No CUDA graphs, small prefix cache, 2 parallel requests, retries** | Memory 5.7 GB → 1.8 GB, 0 out-of-memory errors, still ~11 decisions/s | Defaults: CUDA graphs filled the card and caused HTTP 500s |
| I3 | App | **FastAPI + SSE + SQLite; dashboard + /scores + /report + Workbench** | Simple, local, live progress, every number inspectable | Heavier stack (React app, Postgres, cloud hosting): nothing to gain for a single-laptop system |
| I4 | Showing the demo | **Backend on the GPU laptop, frontend on another laptop over a hotspot** | Shows "model runs locally"; keeps the GPU laptop free | Public tunnel: needs internet + install; everything on one laptop: one cramped screen (still the fallback) |
