# Panel viva prep: numbers to say, questions to expect, answers to give

Short answers first, detail after. Say numbers exactly as written here; they match `/report`.

---

## 1. The 10 numbers to know by heart

| # | Number | Say it like this |
|---|---|---|
| 1 | **0.931 / 0.750** | "Our fine-tuned InLegalBERT classifies clause types at 0.93 F1, and 0.75 on contract types it never saw. The mid-term MiniLM model got 0.83 / 0.59." |
| 2 | **71 % vs 46 %** | "On 28 bad/fixed clause twins, Kev decides correctly 71 % of the time; rules 46 %." |
| 3 | **75 % vs 7.5 %** | "On 280 lawyer-annotated interacting pairs from CUAD, Kev finds 75 %; rules 7.5 %." |
| 4 | **13/15 · 1/30** | "Our clause-vs-law check, as deployed, surfaces 13 of 15 real violations (Supreme Court struck-down + planted faults) and flags only 1 of 30 ordinary clauses. Keyword rules alone caught 4 of 15. A finding is *law-confirmed* when our India Code search independently finds the same section; those were right 4 times out of 5." (Kev alone on Supreme Court clauses: 6/9 vs regex 0/9; the 4 upheld ones are still flagged, hence confidence labels.) |
| 5 | **0.32 (from 0.11)** | "For a risky clause, the exact Indian law section is in our top 5 for 32 % of cases, up from 11 % with plain keyword search; the right Act is in the top 3 for 53 %." |
| 6 | **4,408 sections / 37 sources** | "Our Indian law library: 4,408 India Code sections." |
| 7 | **92.9 % / 85.7 % / κ 0.57** | "We validated the teacher: 92.9 % on known answers, 85.7 % of its citations exist in India Code, moderate agreement with Claude (κ 0.57)." |
| 8 | **11 decisions/s, ~3,500 tokens/s, 1.8 GB** | "Kev runs at about 11 decisions a second on a 6 GB laptop GPU, using 1.8 GB." |
| 9 | **305 pages → 580 clauses → 4.4 min** | "A 305-page scanned concession: 580 clauses, 173 pairs judged, 4.4 minutes, fully offline." |
| 10 | **14,025 → 173 pairs** | "Smart shortlisting: from 14,025 candidate pairs to 173, which is what makes big contracts practical." |

Bonus: training times on the laptop: InLegalBERT 48 min, Kev LoRA 58 min, retrievers 1–2 min, GNN 19 min.

---

## 2. Opening questions

**Q: What does your project do, in one minute?**
It reviews Indian contracts for risk in two ways: clause against clause (e.g. an uncapped indemnity that undoes a
liability cap) and clause against Indian law (e.g. a post-employment non-compete, void under ICA s.27). It reads PDFs
including scans, splits clauses, labels them, picks the pairs worth checking, judges them with a small local model,
and attaches the real India Code text, all on one laptop GPU.

**Q: What is new compared with existing tools?**
Pairs instead of single clauses; Indian law grounding with real section text; everything local; and evaluation on
ground truth we did not create (lawyer labels, Supreme Court outcomes).

**Q: Is it complete?**
Yes, end to end: any PDF/DOCX/TXT in, ranked findings with Indian law out, stored and browsable, every stage measured.
What it lacks is lawyer-verified Indian training data, which is the main future work.

---

## 3. Technical questions (with answers)

**Q: How do you convert PDF to text?**
PyMuPDF through pymupdf4llm for digital pages (keeps headings and tables as Markdown); Tesseract OCR for scanned
pages, in parallel and cached by file hash.

**Q: Why InLegalBERT and not BERT / LegalBERT / an LLM?**
InLegalBERT was pre-trained on Indian legal text. Fine-tuned it got 0.93 F1; our MiniLM baseline 0.83. An LLM per
clause is slow and sends data to the cloud.

**Q: How many labels? Why 22?**
22 trained clause types plus "other", and 7 rule-based Indian labels (force majeure, liquidated damages, data
protection, stamp duty, performance security, change in law, step-in). A label exists only if it can clash with
another and has ≥ 300 examples. We moved from 20 to 22 by splitting arbitration and remedies out of dispute
resolution.

**Q: What is Kev? Is it an LLM?**
A small decision model (0.8 billion parameters, Qwen3.5 base) with a pointer head: it reads the clauses and a
question with fixed options and returns a probability for each option. It doesn't write text, so it can't invent
an explanation. It's an open reconstruction of the "Jev" / System One decision-model idea.

**Q: Why didn't you use your fine-tuned Kev?**
We fine-tuned it twice. v1 collapsed to always saying "no issue" (class imbalance). v2 agreed more with the teacher
but scored worse on independent tests: 54 % vs 71 % checklist, 31 % vs 75 % CUAD recall. We chose by independent
tests, so the base model is served. This is one of our findings.

**Q: What is the token rate of Kev?**
It doesn't generate tokens; it reads them. About 3,500 input tokens per second, 11 decisions per second, 82 ms median
latency for a ~311-token request on the RTX 4050. Inside the full pipeline, with longer requests and CPU stages,
about 4 decisions per second.

**Q: How do you choose which pairs to check?**
Three signals: explicit cross-references ("subject to Clause 14.2"), a 40-pair matrix of clause types that commonly
clash (cap × indemnity 0.9), and hybrid keyword + meaning search fused with reciprocal rank fusion. Cross-referenced
pairs are always kept; the rest are ranked and capped at 60.

**Q: How exactly do you check a clause against Indian law?**
Four signals, each measured. (1) Our classifier decides which clauses could carry a legal risk (this cut false alarms on
ordinary clauses from 11/30 to 1/30). (2) Kev reads the clause and picks one of 7 plain-language legal risks, each mapped
to its section (restraint of trade → ICA s.27, forfeiture → s.74, one-sided arbitrator → A&C s.12 …). (3) RAG searches
the 4,408 India Code sections for that clause; if it independently finds the same section, the finding is
*law-confirmed* and its confidence goes up. (4) If our deterministic rules also fire, it is *rule-confirmed*. The real
section text is always attached and verified. Result: 13 of 15 real violations surfaced, 1 of 30 ordinary clauses flagged.

**Q: Why doesn't Kev just read the statute text and decide?**
We tested exactly that: zero-shot, Kev judged worse from statute text (AUC 0.64) than from its own risk-type reading
(0.74), and retrieval finds the exact section only 32 % of the time, so the decision would inherit retrieval misses.
So retrieval *corroborates* (precise, 4/5) instead of *deciding*. Training Kev on teacher labels that include the
retrieved law is our next step.

**Q: What is RAG here?**
For each finding we retrieve the real India Code sections (BM25 + our fine-tuned InLegal-SBERT, fused, with a small
prior for contract-related Acts). Kev chooses among 4 retrieved sections; the optional Gemini explanation may cite only
retrieved sections; every cited section is checked to exist.

**Q: Explain the GNN. Did it help?**
GraphSAGE over a clause graph (nodes = clauses; edges = cross-references, parent links, neighbours, 5 most similar).
Each clause averages its neighbours' vectors over 2 hops; a small network scores pairs. The ablation (same model
without the graph) was as good (0.748 vs 0.742 ROC-AUC), so the graph added nothing: contracts have few links per
clause and we had only 172 test pairs. It's built and evaluated but off by default.

**Q: How did you get training data for pairs?**
Teacher–student distillation: Gemini 4 labelled 1,740 pairs (relation, severity, rationale, Indian citation), Claude
Sonnet 620 as a second opinion. Example of a real teacher label: on "cap of 12 months' fees" vs "indemnify without
limit and notwithstanding any other provision", Gemini answered: conflict, high, risk 0.85, Indian Contract Act
s.124, with a drafted fix.

**Q: How do you know the teacher is right?**
We checked it against things it didn't produce: 92.9 % on our known-answer checklist, 75 % agreement with CUAD
lawyers on clause types, 85.7 % of its citations exist in India Code, κ 0.57 with Claude.

---

## 4. Hard questions (prepare these)

**Q: Your system flags too much. The clean contract also gets dozens of findings.**
Yes, base Kev favours recall: missing a void clause costs more than a second look. That's why findings are ranked by
severity, low-confidence ones are grouped separately, and each law finding carries a confidence label. A fine-tuned
version flagged less but missed far more (31 % vs 75 % lawyer-pair recall). Precision is our main weakness and the
first thing lawyer-labelled data would fix.

**Q: Show me it distinguishing a bad clause from a fixed one.**
Be honest: on the cap-vs-indemnity twin Kev says "ambiguity" for both versions (P(no_issue) 0.20 vs 0.21). Across all
28 twins it gets 71 % right: it catches 69 % of bad ones and clears 75 % of fixed ones. The teacher gets 93 %. Small
models need better training data for fine distinctions; our fine-tunes on silver labels didn't fix it.

**Q: Kev flagged a clause the Supreme Court upheld. Isn't that wrong?**
Yes, it flags all 4 upheld clauses: it recognises the *type* of risk (restraint of trade) but not the legal exception
(e.g. restraint during employment is allowed). That's why it's a reviewer's assistant with confidence labels, not a
judge.

**Q: The casebook headings say what the court held. Isn't that leaking the answer?**
The headings are for the panel. The clause-vs-law check reads only the clause text, and the 6/9 number was measured on
clause text alone (`results/eval_statutory.json`).

**Q: Your training labels come from an LLM. Isn't that circular?**
That's why we never select or report on teacher labels alone. Every headline number uses independent ground truth.

**Q: Only 28 / 280 / 18 test items. Is that enough?**
They are small but independent and of different kinds; together they point the same way (Kev ≫ rules, base ≥
fine-tuned). A larger lawyer-labelled Indian set is future work.

**Q: Why not just use GPT/Gemini for everything?**
Confidentiality (contracts leave the machine), cost per contract, rate limits (Gemini returned 503s repeatedly while we
built this), and no control over versions. We use it where it helps without those costs: offline teaching and an
opt-in explanation.

**Q: What happens with a 300-page contract?**
Pune Metro: 305 scanned pages → OCR (cached) → 580 clauses → 173 pairs → 4.4 minutes end to end on the laptop.

**Q: What failed?**
Fine-tuning Kev (v1 collapse, v2 worse than base), regex for law (0/9), the reranker (worse), the GNN (no gain), and an
uncapped shortlist (14,025 pairs, about an hour). Each failure is documented with the reason in PROCESS.md.

**Q: What would you do with more time?**
Lawyer-verified Indian clause-pair data; a larger Kev (4B); contrastive bad/fixed training pairs; the full Indian Acts
vector index; case-law retrieval; precision tuning.

---

## 5. Questions about specific terms (one-liners)
- **BM25:** keyword ranking weighted by word rarity and length.
- **Embedding:** a vector representing meaning; cosine similarity compares them.
- **RRF:** merge rankings by summing 1/(60 + rank).
- **LoRA:** train small add-on matrices instead of the whole model.
- **Focal loss:** down-weights easy examples so rare classes matter.
- **F1:** harmonic mean of precision and recall. **Recall@5:** right answer in the top 5. **ROC-AUC:** chance a
  risky pair scores above a safe one.
- **Cohen's κ:** agreement corrected for chance.
- **Zero-shot:** using a model without task-specific training.
- **OCR:** reading text from images (Tesseract).
More: `LEARN_EVERYTHING.md`.

## 6. Things not to do in front of the panel
- Don't click **Export** (old "GraphRAG" wording) or open `/findings`, `/injections`.
- Don't click **Explain with Gemini** unless it worked this morning.
- On the casebook, show **Clause ↔ Law**, not Clause ↔ Clause.
- Quote the statute number as **0.32**, never 0.50 (older 10-query result).
- Don't open the old docs in `docs/` (stale numbers); only `docs/final_viva_docs/`.
