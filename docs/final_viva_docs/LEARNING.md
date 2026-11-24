# LegalAgent — understanding guide (for us, for the viva)

For each part: **what** it is, **how** it works, **why** we chose it, **why not** the alternatives, and the
questions the panel is likely to ask. A glossary of every term is at the end. Numbers: `docs/final_viva_docs/PROCESS.md`.

---

## The project in 30 seconds

Contracts are risky not only because of single bad clauses but because clauses **interact**: a liability cap
in clause 12 is quietly undone by an "uncapped indemnity" in clause 18; a termination clause refers to a notice
period that another clause changes. LegalAgent reads an Indian contract (even a 300-page scan), splits it into
clauses, labels each clause, picks the clause **pairs** worth checking, asks a local decision model (Kev)
whether each pair conflicts, checks single clauses against Indian law, and attaches the real India Code
sections, all on one laptop GPU, so the contract never leaves the machine.

Two kinds of checking:
1. **Clause ↔ clause** inside one contract (conflict, dependency, overlap, ambiguity).
2. **Clause ↔ Indian law** (e.g. a non-compete after employment → Indian Contract Act s.27, void).

---

## 1. Ingestion: PDF → text

**What.** Turns PDF/DOCX/TXT into clean text with headings.
**How.** `pymupdf4llm` (built on PyMuPDF) converts digital PDF pages to Markdown, keeping headings, lists and
tables. If a page has almost no text layer it is a scan → render the page image → **Tesseract OCR**. Pages are
OCR'd in parallel (one process per page) and cached by the file's hash, so the second open is instant.
**Why.** Indian concession agreements are often scanned. pymupdf4llm keeps structure that plain text loses.
**Why not** plain `PyPDF2`/`pdfminer`? They lose headings/tables and cannot read scans. Cloud OCR (Google
Vision)? Contract would leave the machine. Bigger OCR models (docTR, Surya)? Slower on our GPU and the GPU is
reserved for the judge; Tesseract is good enough on printed text.
**Viva Q:** *What do you use to convert PDF to text?* → PyMuPDF via pymupdf4llm for digital pages, Tesseract
OCR for scanned pages, parallel and cached.

## 2. Extraction: text → clauses

**What.** Splits text into numbered clauses (`14`, `14.2`, `14.2(a)`), groups them into parts
(ARTICLE / SCHEDULE), links each sub-clause to its parent, and resolves cross-references ("subject to
Clause 14.2").
**How.** Regular expressions for numbering patterns, a table-of-contents detector (a run of short numbered
lines with page numbers is a TOC, not clauses), and a parser for reference phrases.
**Why.** Every later step works on clauses; cross-references are the strongest signal that two clauses interact.
**Result.** Pune Metro 305-page scan → 580 clauses, 99 parts, 137 resolved cross-references.

## 3. Classification: what kind of clause is this?

> **Labels in one line:** CLAUSE-22 = 22 trained types + `other`, plus 7 rule-based Indian labels (force majeure,
> liquidated damages, data protection, stamp duty, performance security, change in law, step-in rights).
> The full list with meanings, the 40 clash pairs and why it changed from CLAUSE-20 are in **LEARN_EVERYTHING.md §1**.

**What.** Multi-label tags from **CLAUSE-22** (termination, limitation_of_liability, arbitration, …).
**How.** **InLegalBERT** (BERT pre-trained on Indian legal text by IIT Kharagpur) fine-tuned on 74,374 labelled
clauses (CUAD + LEDGAR + our mapping). Sigmoid output per label, threshold 0.5. Plus a keyword backstop, a
heading prior (heading "ARBITRATION" → arbitration) and 7 rule-based Indian labels (stamp duty, DPDP, …).
**Why.** Labels decide which pairs are worth judging (the clash matrix) → better labels = better shortlist.
**Why not** MiniLM + logistic regression (our mid-term model)? 0.828 vs 0.931 test micro-F1. Why not an LLM to
label? Slow, costly, and data leaves the machine.
**Why CLAUSE-22, not 20?** A research pass found arbitration and remedies were hidden inside other labels;
splitting them made the clash matrix sharper.
**Viva Q:** *Why is Indian accuracy (0.41) so much lower than test (0.93)?* → Test is the same distribution as
training (US/SEC contracts); Indian PPP contracts are longer, OCR'd, use different drafting, and the Indian set
is silver-labelled (teacher), so it is a harder and noisier test.

## 4. Shortlisting candidate pairs

**What.** A 300-clause contract has ~45,000 pairs; we pick ~60.
**How.** Three signals: (1) explicit **cross-references**; (2) a **type matrix** of 40 clause-type pairs known
to clash (cap × indemnity, termination × survival, …); (3) **hybrid retrieval**: BM25 (keywords) + dense
embeddings, merged with **reciprocal rank fusion**. Optional GNN re-scoring.
**Why.** The judge costs ~0.3 s per pair; judging all pairs would take hours.
**Why hybrid?** BM25 wins on OCR'd Indian text, dense wins on paraphrase; fusion is robust to both.

## 5. The pair judge: Kev

**What.** **Kev-0.8B**, an open reconstruction of the "Jev"/System One *decision model*: a small Qwen3.5
language model with a **pointer head** that answers typed questions (choice / score) with calibrated
probabilities instead of free text.
**How.** For each pair we send a "state" (both clauses) and three questions: relation (conflict / dependency /
overlap / ambiguity / no_issue), severity (score), statute (choose one of 4 retrieved sections or none).
It runs on our GPU behind a local HTTP server (`kev.serve`, port 8008).
**Why.** Local (privacy), fast (~0.3 s/pair), outputs probabilities (we can set thresholds and show confidence),
and no hallucinated prose to verify.
**Why not Gemini?** Contract leaves the machine and it is slower; kept only as the teacher and as an opt-in
"Expand" explanation. **Why not a bigger local LLM (Llama 8B)?** Does not fit in 6 GB next to everything else.
**What happened with fine-tuning?** v1 collapsed (imbalance); v2 (balanced + focal loss) agreed more with the
teacher but scored worse on the independent tests than the untouched base, so the demo uses the **base model,
zero-shot**. This is a real finding: 440 silver labels taught the teacher's habits, not the task.
**Viva Q:** *Why didn't you use your fine-tuned model?* → We chose by tests we did not create (checklist, CUAD
lawyer labels). The base won 71 % vs 54 %. Choosing by teacher agreement would have been circular.

## 6. Teacher–student distillation

**What.** A big model (teacher: Gemini 4) labels data; a small model (student: Kev) learns from it.
**How.** `agy` (Antigravity CLI) runs the teacher with a strict JSON schema: relation, severity, rationale,
cited section, clause types. 1,000 + 740 Gemini pairs, 300 + 320 Claude pairs as a second opinion.
**How do we know the teacher is right?** We checked it against things it did not produce: known-answer checklist
(92.9 %), CUAD lawyer clause labels (75 %), citations exist in India Code (85.7 %), agreement with Claude
(κ = 0.57, moderate).

## 7. Clause vs Indian law

**What.** Single-clause check: does this clause break an Indian statute?
**How.** (a) regex rules for obvious patterns; (b) **Kev single-clause check**: choose among 7 plain-language
risk categories, each mapped to a section (restraint of trade → ICA s.27; penalty/forfeiture → s.74; restricting
legal remedies → s.28; one-sided arbitrator → A&C Act s.12; termination at will → s.23; unstamped → Stamp Act
s.35; personal data without consent → DPDP s.6).
**Result.** Regex caught 0/9 clauses the Supreme Court struck down; Kev caught 6/9 but also flagged clauses the
court upheld → we show **confidence labels** (high ≥ 0.7, medium ≥ 0.45, low) rather than hiding weak signals.

## 8. Statute RAG (retrieval-augmented grounding)

**What.** For every finding, retrieve the actual text of relevant India Code sections and attach it.
**How.** Library of **4,408 sections from 37 Acts** (India Code via the Open India Law mirror + Nyaya datasets
for BNS/BNSS/BSA, Constitution, etc.). Hybrid BM25 + **fine-tuned InLegal-SBERT** (trained with contrastive
loss on 2,967 clause→section pairs) + an **Act prior** (contract clauses usually concern contract-law Acts).
Every section number a model cites is **verified** to exist.
**Result.** Exact section in top-5: 0.105 (BM25) → 0.316 (fine-tuned hybrid + prior).
**Why not a reranker?** We tried bge-reranker-v2-m3: worse (0.263) and needs more GPU.
**Why not the 11 GB Qdrant index of all Acts?** Size and an extra embedding model on the GPU; future work.
**Why "RAG" if we don't generate text?** The retrieved sections are given to Kev as choices (statute question),
and shown to the user as evidence; the generation step (Gemini Expand) is optional.

## 9. GNN

**What.** GraphSAGE over the clause graph (nodes = clauses, edges = xrefs / similarity) to predict risky pairs.
**Result.** ROC-AUC 0.742 vs 0.748 without the graph → no gain. **Why?** Sparse graph, only 172 labelled pairs.
We report it as an ablation; it is optional in the shortlist.

## 10. Evaluation: why five kinds of ground truth

| Test | Ground truth comes from | Tests |
|---|---|---|
| CLAUSE-22 test / OOD | CUAD/LEDGAR human annotations | classifier |
| Checklist (28 twins) | We wrote a bad and a fixed version of each clause pair | judge, both detection and false alarms |
| CUAD interaction pairs (280) | Lawyer clause labels whose categories interact by definition | judge recall |
| Supreme Court casebook (18) | Court outcome (void / upheld) | clause-vs-law, statute retrieval |
| Pune Metro injections (15) | We planted the faults ourselves | end-to-end |
| Held-out teacher pairs (172) | Teacher (silver) | reported, never used to choose |

## 10b. The results page (`/report`, `results/REPORT.html`): what each table tests

Built by `venv/bin/python scripts/build_report.py` from `results/*.json`. Green cell = best in that column.

| # | Table | The question it answers | Input → what is compared | How to read it |
|---|---|---|---|---|
| 1 | Clause classification | Does the model name a clause's type correctly? | one clause → predicted CLAUSE-22 labels vs human labels | micro-F1 (all labels pooled); OOD = contracts unlike training; ms/clause = speed |
| 1b | Indian classifier variants | Does it still work on Indian contracts? | Indian clauses → labels vs teacher labels | lower (0.4–0.5) because OCR + different drafting + noisy labels |
| 2 | Related-clause retrieval | Does search find the clause a clause is linked to? | a clause → top-k other clauses vs its real cross-references | R@5 = linked clause appears in top 5 |
| 3 | Clause ↔ clause judge | Does the judge spot two clauses that create a risk together, without crying wolf? | a pair → risky / not vs checklist answers, CUAD lawyer categories, teacher | checklist acc = catches + clean passes; CUAD recall = catches; ms/pair = speed |
| 4 | Clause ↔ Indian law | Looking at one clause, can we tell it breaks Indian law? | a clause → flag vs court outcome / planted fault / normal clause | "caught" high is good; "false alarms" low is good |
| 5 | Statute retrieval | Does RAG fetch the exact section that applies? | a risky clause → top India Code sections vs the section a court applied | R@5 exact section; "Act in top 3" is the easier version |
| 6 | GNN ablation | Does the clause graph help rank risky pairs? | pairs → risk score vs teacher labels | ROC-AUC 0.5 random, 1.0 perfect; GNN ≈ no graph → no gain |
| 7 | Teacher validation | Can we trust Gemini 4's labels? | teacher output vs answers it did not make | 93 % checklist, 75 % lawyer types, 86 % real citations, κ 0.57 |
| 8 | Training runs | What did each model cost to train? | — | minutes on the RTX 4050 |
| 9 | Kev speed | How fast is the local judge? | benchmark requests | decisions/s, input tokens/s, p50/p95 latency |
| 10 | End-to-end runs | How long does a whole contract take, and where does the time go? | contract → findings | seconds per stage; first OCR run of a scan is the slowest |

**Kev speed:** Kev does not generate text. It reads the clauses plus the question (≈300 input tokens), then a pointer head
outputs a probability over the given answers. So its speed is measured in **input tokens read per second** and
**decisions per second**, not "output tokens per second" as for a chatbot. On our RTX 4050 one decision takes about
0.15–0.5 s. Our judge issues 2 in parallel: about 4 decisions/s, roughly 1,000+ tokens read per second (see table 9).

**Why one big scanned contract takes minutes, not hours:** the shortlist keeps every explicit cross-reference
(113 on Pune Metro) plus the 60 best other pairs. Earlier the clause-type matrix alone produced 13,940 pairs for
580 clauses, about an hour of judging; capping and ranking them brought it to 173 pairs and 4.4 minutes for 305 pages.

## 11. Engineering

- **GPU sharing:** 6 GB card. Kev owns the GPU in the demo; the encoders run on CPU (`LEGALAGENT_DEVICE`),
  with automatic CPU fallback on out-of-memory.
- **Web:** FastAPI, server-sent events for live progress, SQLite. `/app` dashboard, `/scores` under-the-hood
  page (Chart.js), Workbench desktop window.
- **Reproducibility:** every number in the report is regenerated by `scripts/eval_all.py tables`.

---

## Likely viva questions (short answers)

1. **Novelty?** Cross-clause (pair) risk, not just single clauses; local decision model; Indian law grounding;
   evaluation on independent ground truth including Supreme Court outcomes.
2. **Why local?** Contracts are confidential; DPDP Act 2023; zero per-contract cost.
3. **How do you avoid hallucinated law?** Sections are retrieved from India Code text and every citation is
   verified to exist; Kev chooses among retrieved sections rather than writing them.
4. **What is LoRA?** Train small low-rank matrices added to the frozen weights → fits a 0.8B model on 6 GB.
5. **What is focal loss?** Cross-entropy that down-weights easy examples (γ=2) so the majority class
   (no_issue) does not dominate.
6. **What is the threshold τ?** Flag a pair when P(no_issue) < τ instead of taking the argmax; tuned on
   training contracts only.
7. **Why BM25 still matters?** OCR noise and exact legal terms ("Section 74", "earnest money") favour lexical match.
8. **Biggest limitation?** No lawyer-labelled Indian pair set; Kev over-flags in clause-vs-law; small tests.
9. **What failed?** Fine-tuned Kev (v1 collapse, v2 worse than base), regex for law, reranker, GNN. See PROCESS.md §4.
10. **How does it scale?** Shortlist keeps pairs ~O(clauses); OCR cached; ~0.3 s per judged pair.

---

## Glossary

| Term | Meaning |
|---|---|
| **PyMuPDF (fitz)** | Fast C-based PDF library: text, images, page rendering |
| **pymupdf4llm** | PyMuPDF add-on that outputs Markdown (headings, lists, tables) for LLM/NLP pipelines |
| **OCR** | Optical Character Recognition: image of text → text |
| **Tesseract** | Open-source OCR engine (Google), LSTM-based |
| **Clause** | Numbered provision of a contract (e.g. 14.2) |
| **Cross-reference (xref)** | Text in one clause pointing to another ("subject to Clause 14.2") |
| **Multi-label classification** | A clause can have several labels at once; one sigmoid per label |
| **BERT** | Transformer encoder pre-trained with masked-word prediction |
| **InLegalBERT** | BERT further pre-trained on Indian legal text (law-ai, IIT Kharagpur) |
| **SBERT / sentence embeddings** | Model mapping a sentence to a vector so similar meaning → close vectors |
| **InLegal-SBERT** | Sentence-embedding version of InLegalBERT |
| **MiniLM** | Small, fast sentence-embedding model (our mid-term baseline) |
| **Fine-tuning** | Continue training a pre-trained model on our task's data |
| **Contrastive loss / MNRL** | Multiple-Negatives Ranking Loss: pull matching pairs together, push other items in the batch apart |
| **BM25** | Classic keyword ranking (term frequency × inverse document frequency, length-normalised) |
| **Dense retrieval** | Search by embedding similarity (cosine) |
| **Hybrid retrieval** | Combine BM25 and dense results |
| **RRF (reciprocal rank fusion)** | Merge ranked lists by summing 1/(k + rank) |
| **Reranker / cross-encoder** | Model reading query and document together to rescore top results (more accurate, slower) |
| **RAG** | Retrieval-augmented generation: fetch real documents and give them to the model as evidence |
| **Qdrant** | Vector database (used by Open India Law for all Indian Acts) |
| **LLM** | Large language model |
| **Decision model (Jev / Kev)** | LM with a pointer head that answers choice/score questions with probabilities |
| **Pointer head** | Output layer that points to one of the given options instead of generating text |
| **Qwen3.5-0.8B** | Small open LLM that Kev is built on |
| **LoRA** | Low-Rank Adaptation: train small adapter matrices, keep base weights frozen |
| **bf16** | 16-bit floating point format, halves memory vs fp32 |
| **Gradient checkpointing** | Recompute activations during backprop to save GPU memory |
| **OOM** | Out of memory (GPU) |
| **Focal loss** | Loss that focuses on hard examples; helps class imbalance |
| **Class imbalance / collapse** | When one class dominates, a model may predict only that class |
| **Calibration / threshold τ** | Choosing the probability cut-off for a decision |
| **Teacher–student distillation** | Big model labels data, small model learns from those labels |
| **Silver labels** | Labels made by a model, not by experts (gold = expert/court) |
| **Cohen's κ** | Agreement between two labellers corrected for chance (0.57 = moderate) |
| **Precision / Recall / F1** | Correct among flagged / found among true / harmonic mean |
| **Micro vs macro F1** | Pooled over all labels vs averaged per label (macro punishes rare-label mistakes) |
| **R@k (recall at k)** | Is the right answer in the top k results? |
| **ROC-AUC** | Probability a random positive is ranked above a random negative |
| **Ablation** | Remove one component to measure its contribution |
| **OOD** | Out-of-distribution: test data unlike the training data |
| **GNN / GraphSAGE** | Neural network on graphs; GraphSAGE aggregates neighbour features |
| **CUAD** | Contract Understanding Atticus Dataset: 510 US contracts, 41 lawyer-labelled clause categories |
| **LEDGAR** | 80k+ contract provisions from SEC filings with labels |
| **CLAUSE-22** | Our 22-label clause taxonomy |
| **India Code** | Official Government of India repository of central Acts |
| **ICA s.27 / s.74 / s.28** | Indian Contract Act: restraint of trade void / compensation for breach (penalty) / restraint of legal proceedings void |
| **A&C Act s.12** | Arbitration and Conciliation Act: arbitrator independence (Perkins Eastman, 2019) |
| **DPDP Act 2023** | Digital Personal Data Protection Act |
| **PPP / concession agreement** | Public-private partnership contract (e.g. metro, highway) |
| **FastAPI** | Python web framework for APIs |
| **SSE** | Server-sent events: server pushes progress to the browser |
| **SQLite** | File-based SQL database |
| **uv** | Fast Python package/environment manager |
| **CUDA** | NVIDIA GPU computing platform |
| **Antigravity CLI (agy)** | Command-line tool we used to run Gemini 4 / Claude as the teacher |
| **Cloudflare quick tunnel** | Temporary public HTTPS link to a local server (for the teammate's screen) |
