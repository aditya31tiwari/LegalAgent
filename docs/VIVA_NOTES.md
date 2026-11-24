# Viva notes — likely questions, short honest answers

Numbers: always quote from `results/REPORT_TABLES.md` (regenerated from `results/*.json`).

## The idea
**Q. What does LegalAgent do that existing tools don't?**
Existing tools label clauses one at a time. LegalAgent reads clauses *against each other*: a liability
cap can be silently undone by an indemnity "notwithstanding Clause 12.1". The unit of analysis is the
clause pair, plus Indian-law checks grounded in real India Code text.

**Q. Why not just send the contract to Gemini/ChatGPT?**
(1) Privacy: contracts are confidential, and the DPDP Act 2023 makes sending client data abroad a real
risk; our default path never leaves the laptop. (2) Cost and reliability: during development the
Gemini API returned 503s for hours — a demo cannot depend on that. (3) Verifiability: LLMs cite
plausible-but-wrong sections; every citation we show resolves to real India Code text or is marked
unverified. Gemini is used only as an offline *teacher* and an opt-in "Expand" button.

## Models
**Q. Which ML models did you train?**
- InLegalBERT, fully fine-tuned as a 22-label clause classifier (CLAUSE-22, 74k clauses from CUAD + LEDGAR):
  micro-F1 **0.931** test / **0.750** on contracts never seen (original prototype: 0.81 / 0.46).
- InLegal-SBERT, contrastively fine-tuned twice: for related-clause retrieval (cross-reference pairs) and
  for clause→statute retrieval (teacher citations verified against India Code).
- Kev-0.8B decision model (open Jev-style: Qwen3.5 + LoRA + pointer head), LoRA fine-tuned as the pair judge.
- A GraphSAGE GNN over each contract's clause graph (link prediction of risky pairs) with a no-graph ablation.

**Q. What is Kev and why not a normal LLM?**
Kev is an open-source reconstruction of TypeSafe's "Jev" System One model: it reads a document and
returns a *calibrated probability over the options of typed questions in one forward pass*, no text
generation. Our task is exactly that shape (which relation? how severe? which statute?), it runs on a
6 GB laptop GPU, and it is fast (~0.3–0.6 s per pair).

**Q. Your fine-tuned Kev collapsed — explain.**
The first fine-tune (v1) learned to answer "no_issue" because 73 % of training pairs were no_issue (only
30 conflicts). We diagnosed it (ranking AUC 0.76 on held-out pairs but 0.47 on the checklist, probabilities
squashed), then fixed it three ways: class-balanced data, focal loss, and a decision threshold tuned on
training contracts only. [v2 / v3 results → REPORT_TABLES "Pair judges" and "Checklist".] The demo
serves whichever judge wins on the independent tests, chosen automatically (`scripts/select_judge.py`).

**Q. Why didn't you use a GNN / RAG / LangGraph?**
GNN: we did — see the GNN vs no-graph ablation. RAG: yes, over 3,142 India Code sections (33 Acts),
hybrid BM25 + InLegal-SBERT; Kev chooses among retrieved sections. Multi-agent orchestration was not
needed: each stage is a deterministic, measurable function; adding an agent loop would make results
harder to evaluate.

## Data
**Q. Isn't your training data synthetic?**
The *text* is real (CUAD SEC filings, NHAI and Pune Metro concessions). The *pair labels* are
distilled from a large model (Gemini 4 Hydrogen) — silver labels. We never trust them blindly:
teacher accuracy on known-answer pairs 92.9 %, its clause types match lawyer labels 85 %, 86 % of its
citations exist in India Code, agreement with a second model family κ = 0.57. Headline results use
ground truth that does not come from the teacher.

**Q. Is there Indian contract training data?**
No public Indian contract-clause dataset exists. We train clause types on US data (CUAD/LEDGAR), measure
transfer to Indian text, use InLegalBERT/InLegal-SBERT (pretrained on Indian legal text), and build the
statute library from official India Code.

## Results
**Q. How do you know it works on real contracts?**
Five kinds of ground truth: (1) lawyer-labelled clause test sets; (2) 280 CUAD clause pairs where lawyers
annotated both clauses and the interaction follows from the categories; (3) 28 known-answer bad/fixed
twins; (4) 18 real clauses from Supreme Court judgments (court outcome = truth, 5 upheld = negatives);
(5) the 305-page scanned Pune Metro concession with 15 planted irregularities + the clean original as a
false-alarm control.

**Q. What doesn't work?**
- Hand-written regex rules: 0 of 13 Supreme Court struck-down clauses, 7.5 % of CUAD interactions —
  real drafting ("from the date you leave", "forfeiture of earnest money") doesn't match the patterns we
  wrote from our own examples. That is why the system is built around trained models.
- 66/510 CUAD contracts use ARTICLE/(a)-only numbering the extractor doesn't split.
- OCR noise on scanned concessions lowers Indian retrieval.
- Pair labels are model judgements; no lawyer reviewed them (we measured the teacher instead).

**Q. What would you do next?**
Lawyer-verified Indian pair set; ContractNLI as auxiliary training; contrastive bad/fixed training pairs;
larger Kev (4B) on a bigger GPU; Hindi; redlining.

## Engineering
**Q. How does it handle scanned PDFs?**
PyMuPDF detects pages without a text layer → Tesseract OCR in parallel across CPU cores, cached by file
hash (305 pages ≈ 2 min once, then instant); born-digital pages go through pymupdf4llm.

**Q. Why does the GPU matter?** 6 GB RTX 4050: Kev (~3–4 GB) + classifier must share it; smaller models
fall back to CPU automatically when the GPU is full, so nothing crashes during the demo.
