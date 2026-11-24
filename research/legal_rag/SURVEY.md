# Legal RAG / clause-vs-statute survey for LegalAgent

Date: 2026-11-24. Read-only desk research: nothing was cloned or installed. Facts come from the repo and model pages, HF API and GitHub API at the time of writing. Items marked "unverified" could not be confirmed from a primary page.

## Problem restated

Given a contract clause, (a) retrieve the governing statute section(s) from our 3,142-section India Code library, then (b) decide whether the clause is void or violates that section, for example under ICA s.27, s.28 or s.74, or A&C s.12(5) with the Seventh Schedule. Step (a) mostly works already with hybrid BM25 + fine-tuned InLegal-SBERT. Step (b) is the weak spot. Hardware: 6 GB RTX 4050.

**Key finding:** No public repo, dataset or model does Indian contract-clause → statute-violation classification. The Indian statute-identification work (IL-TUR LSI, LeSICiN, AILA, ILSIC) maps fact descriptions or lay queries to statutes. It is mostly criminal (IPC), the licences are mostly non-commercial, and none of it is a legality decision. The reusable pieces are generic:
1. a modern instruction-aware reranker for (clause, section) relevance;
2. an NLI cross-encoder for the decision step, driven by hand-written per-section "violation hypotheses";
3. contract NLI and unfair-clause datasets for fine-tuning or calibrating that decision head.

---

## Top 3 recommendation

| # | Candidate | Role in pipeline | Effort | Why |
|---|---|---|---|---|
| 1 | **Qwen/Qwen3-Reranker-0.6B** (Apache-2.0), with **BAAI/bge-reranker-v2-m3** (Apache-2.0) as fallback or A/B | Rerank the top-k sections from the existing hybrid retriever, using an instruction such as "Given a contract clause, find the statute section that governs whether this clause is valid or void" | **S** | It is 0.6B parameters (about 1.2 GB fp16) and loads as a sentence-transformers `CrossEncoder`. It accepts a custom task instruction and a 32k context, so long sections like ICA s.74 with its explanations are not truncated. It plugs directly into the existing top-k step. |
| 2 | **MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli** (MIT), with **cross-encoder/nli-deberta-v3-base** (Apache-2.0) as a lighter alternative | Decision step. Premise = the clause. Hypotheses = 2-5 hand-written "violation" and "exception" statements per target section, for example s.27: "This clause prevents a party from carrying on a trade, profession or business after the contract ends" and the exception "The restriction is limited to not carrying on a similar business after selling goodwill". Entailment probabilities become features for Kev-0.8B or a small logistic head. | **M** | Zero-shot entailment is far more robust than regex on paraphrased clauses. It is about 435M parameters and fits in fp16. It is explainable, because the hypothesis that fired is shown to the user. It can later be fine-tuned on our own labelled clauses and on ContractNLI. |
| 3 | **ContractNLI dataset** (CC BY 4.0) + **LexGLUE UNFAIR-ToS** (CC BY 4.0 per card) as training and calibration data, with the `stanfordnlp/contract-nli-bert` code as reference only | Fine-tune or calibrate candidate #2 on real contract language (premise = contract span, hypothesis = obligation statement, labels entail / contradict / not-mentioned). Use UNFAIR-ToS (jurisdiction, arbitration, limitation-of-liability and unilateral-change labels) as weak supervision for s.28-style and arbitration clauses. | **M** to **L** | These are the only permissively licensed, contract-domain entailment and unfairness datasets found. They narrow the gap from MNLI's generic text to contract drafting. Neither is Indian law, so they help clause understanding, not the statutory judgement. |

The suggested pipeline is retrieve (existing) → rerank (#1) → for the top 1-3 sections that have hypothesis templates, run NLI (#2) → Kev-0.8B or a rule layer combines the entailment scores, exceptions and section metadata → verdict plus the triggering hypothesis as explanation. Peak VRAM is about 3 GB with the SBERT, reranker and DeBERTa-large models all in fp16.

A cheaper sanity baseline is to skip #2 and ask Qwen3-Reranker a yes/no "violation" question directly. Its yes/no logit head is a generic relevance judge, so expect worse calibration than NLI.

---

## Full findings

### 1. Indian statute identification and retrieval

| Candidate | Link | Licence | Last activity | Provides | Domain | Plug-in / effort | Risks |
|---|---|---|---|---|---|---|---|
| **IL-TUR (LSI task)**, Exploration-Lab | github.com/Exploration-Lab/IL-TUR ; huggingface.co/datasets/Exploration-Lab/IL-TUR | Repo: CC BY-NC 4.0. HF dataset: CC BY-NC-SA 4.0 (gated) | Last commit 2024-06-03; paper arXiv 2310.09765 (Oct 2023) | The repo is README-only. Data, LSI model and code are on OneDrive. HF has LSI train 43k / dev 10k / test 13k plus 100 statutes. | **Criminal.** All 100 labels are IPC sections (s.2–s.511). | Not usable for our label space. At most, a source of legal-text pretraining negatives. **L** with low payoff. | Facts→IPC is a domain mismatch. IPC has been replaced by BNS. NC licence. |
| **LeSICiN**, Law-AI (AAAI 2022) | github.com/Law-AI/LeSICiN | **No licence file** (the GitHub licence API returns 404) | Last commit 2022-02-12 | Code for a heterogeneous-graph statute identifier. Data is on Zenodo. No pretrained weights mentioned. | **Criminal** (IPC; facts from Indian courts) | **L.** It needs retraining on our own label graph, and we have no fact→section training data for ICA. | Unlicensed (all rights reserved by default), stale, criminal. |
| **ILSIC**, Law-AI (arXiv 2602.00881, Jan 2026) | github.com/Law-AI/ilsic | Repo MIT. Dataset CC BY-NC-SA 4.0 (per paper). | Last commit 2026-02-03 | Lay queries from kaanoon.com (about 8k) and court data mapped to 567 statutes. Includes Consumer Protection, Motor Vehicles, Easements, Hindu Marriage and CrPC. Baselines are BM25, SBERT, SAILER and LLM fine-tunes. Data is on Google Drive. | Mixed civil and criminal, query-side | Could be a source of extra (query, section) pairs for further SBERT fine-tuning, filtered to the Acts we hold. **M.** | It is unconfirmed whether the Contract Act is among the 567 statutes. Queries are lay questions, not clauses. Data is NC. |
| **AILA 2019/2020 statute retrieval** (FIRE) | zenodo.org/records/4063986 ; HF mirror mteb/AILA_statutes | Not checked | 2020 | 50 queries and 197 statute sections | Mostly criminal or situational | Eval-only. **S** to load, but not relevant. | Tiny dataset, wrong domain. |
| **law-ai/InLegalBERT** | huggingface.co/law-ai/InLegalBERT | MIT | Last modified 2023-05-11 | A 110M BERT pretrained on 5.4M Indian SC and HC judgments (1950-2019) | All domains (case law) | Already effectively in use, since our SBERT is InLegal-based. It could serve as the backbone if we train our own cross-encoder. **M.** | Not a retriever or reranker out of the box. 512-token limit. |
| **NyayaLabs98/nyaya-embed-v1** + **nyaya-statute-db** | huggingface.co/NyayaLabs98/nyaya-embed-v1 ; .../datasets/NyayaLabs98/nyaya-statute-db | Model MIT. DB labelled gov-india public domain. | Created 2026-09-04, modified 2026-09-05. 10 downloads. | A multilingual-e5-base (278M) bi-encoder fine-tuned on 4,412 question→section pairs (en/hi/Hinglish). The DB has 5,063 rows over 28 Acts, including **Contract Act 1872 (192 rows)**, BNS, BNSS, BSA, NI Act, TPA and Consumer Protection, sourced from India Code. | Mixed, citizen-query-oriented | It could be added as a third retriever in the ensemble, or the DB used to cross-check our section texts. **S.** | Very new and unproven (reported R@1 of 49% on 118 questions). Trained on questions, not clauses. It lacks the Specific Relief, A&C and Stamp Acts. |
| **Aalap** (OpenNyAI, Mistral-7B instruction-tuned) | huggingface.co/opennyaiorg/Aalap-Mistral-7B-v0.1-bf16 (gated) | Card says apache-2.0 / "other". The instruction dataset is CC BY-NC 4.0 (per search snippet). | 2024 (arXiv 2402.01758) | 7B weights plus an instruction set including contract-clause generation tasks | Indian, mixed | Would need 4-bit quantisation to fit 6 GB. As an LLM judge it is slow. **M** to **L.** | Its own card says it does no better than base Mistral-7B on AIBE/LegalBench. It is a generator, not a classifier. |
| **SAILER** (SIGIR'23) | github.com/CSHaitao/SAILER | MIT | Last commit 2023-05-09 | Retrieval-pretrained encoders: SAILER_en and SAILER_en_finetune (COLIEE) | Case retrieval (Chinese criminal / COLIEE) | Alternative dense backbone. **M.** | Case-to-case retrieval, not clause-to-statute. |
| ICAT (schematise) | huggingface.co/datasets/schematise/ICAT-version1 | CC BY-SA 4.0 | n/a | Fewer than 1K contract clauses from about 60 Indian judgments, expert-annotated (schema not documented on the card) | Indian contracts | Possible source of a few real Indian clauses for our eval set. **S** to inspect. | Labels unknown, tiny dataset. ShareAlike licence. |
| LEXAR (PyPI), NyayaSetu (HF Space), JusticeRAG | pypi.org/project/lexar-ai ; HF space CaffeinatedCoding/nyayasetu ; github.com/sassysohom48/JusticeRAG | unverified | unverified | Hobby RAG stacks with MiniLM over IPC, CrPC and IEA, or over case law | Criminal / case law | Nothing reusable beyond what we have. | Low quality, criminal focus. |

**Verdict for section 1:** Nothing here addresses contract-clause legality. Our existing 33-Act library plus fine-tuned SBERT is already ahead of these projects for commercial law. Optional extras are nyaya-embed-v1 as an ensemble member, and ILSIC pairs for further fine-tuning.

### 2. Contract-clause compliance, legal NLI and legal RAG frameworks

| Candidate | Link | Licence | Last activity | Provides | Domain | Plug-in / effort | Risks |
|---|---|---|---|---|---|---|---|
| **ContractNLI** dataset (Koreeda & Manning 2021) | stanfordnlp.github.io/contract-nli | **CC BY 4.0** | dataset 2021 | 607 NDAs × 17 fixed hypotheses. Labels Entailment / Contradiction / NotMentioned plus evidence spans. | US-style commercial contracts (NDAs) | Fine-tuning data for the NLI decision head. **M.** | Only 17 hypotheses, NDA-only, and no statutory content. |
| **contract-nli-bert** (Span NLI BERT baseline) | github.com/stanfordnlp/contract-nli-bert | Data Apache-2.0 per README. Code licence not stated on the page. | Last commit 2023-03-10 | Training and eval code only, **no released weights**. Python 3.8, PyTorch 1.8. | Contracts | Reference implementation only. Porting it to Py3.12 / modern torch is **L.** | Stale stack. Doc-level span model is overkill for single clauses. |
| **LexGLUE UNFAIR-ToS** (from CLAUDETTE) | huggingface.co/datasets/coastalcph/lex_glue | CC BY 4.0 (card metadata; licensing section says "more info needed") | 2021/22 | 9,414 sentences from 50 ToS documents. 8 multi-labels: limitation of liability, unilateral termination, unilateral change, content removal, contract by using, choice of law, jurisdiction, arbitration. | Consumer ToS (EU unfair-terms law) | Weak supervision for jurisdiction, arbitration and liability-cap clause detection (s.28 exception 1, s.74-adjacent). **S** to load, **M** to use. | EU consumer-fairness notion, not Indian voidness. |
| German employment-contract clauses (SEBIS, TUM) | github.com/sebischair/Employment-Contract-Clauses-German | CC BY-NC 4.0 | v3 tied to ICAIL'26 | Lawyer-annotated legality and fairness of clauses. Has a `data/rules.json` rule file. No code or models. | German employment law | Design reference: it is the closest public analogue of "clause vs statute legality", and the rules.json idea mirrors our per-section hypothesis templates. **S** to read. | German language and law, NC licence. |
| GDPR DPA compliance checking (Amaral, Abualhaija, Briand; arXiv 2209.09722, EMSE 2024) | arxiv.org/abs/2209.09722 | paper | 2022-2024 | Method: split the regulation into "shall" requirements, match clauses semantically, then classify satisfied or violated. Reports about 85% accuracy. **No public code found.** | EU data protection | Methodological template for DPDP Act 2023 checks. **n/a.** | No code. |
| COLIEE Task 3/4 (statute retrieval + entailment); CAPTAIN-COLIEE2023 | github.com/Nguyen2015/CAPTAIN-COLIEE2023 | MIT | 2023 (7 commits) | Code. For Task 4 it fine-tunes DeBERTa (MNLI/SNLI) for yes/no entailment against civil-code articles. No weights. Data must be requested from the organisers. | Japanese Civil Code (bar exam) | Validates the approach "NLI cross-encoder over (statement, statute article)", which is exactly recommendation #2. Code is not worth porting. **L.** | Japanese data, restricted access, Py3.8. |
| LegalBench / LegalBench-RAG | github.com/HazyResearch/legalbench ; zeroentropy-cc LegalBench-RAG (arXiv 2408.10343) | MIT / CC BY 4.0 (per third-party paper, unverified) | 2023 / 2024 | LLM reasoning tasks, and retrieval benchmarks over ContractNLI, CUAD, MAUD and PrivacyQA | US law | Optional retriever and reranker sanity eval on contracts. **S** to **M.** | US-centric. No Indian or statutory-voidness tasks. |
| ACORD (Atticus Clause Retrieval Dataset, ACL 2025) | arxiv.org/abs/2501.06582 | unverified | 2025 | 114 queries and 126k query-clause pairs graded 1-5 by experts. Bi-encoder plus pointwise LLM reranker baselines. | US commercial contracts | Eval or fine-tune data for clause-side retrieval (liability caps, indemnity). **M.** | Clause-to-clause retrieval, not clause-to-statute. |

### 3. Rerankers and cross-encoders that fit a 6 GB GPU

| Model | Link | Licence | Size | Notes | Plug-in / effort |
|---|---|---|---|---|---|
| **Qwen3-Reranker-0.6B** | huggingface.co/Qwen/Qwen3-Reranker-0.6B | Apache-2.0 | 0.6B | 32k context and 100+ languages. Supports a custom instruction, which the card says gives +1-5%. Loads via sentence-transformers `CrossEncoder` (`predict` / `rank`; sigmoid for 0-1 scores). Needs transformers ≥ 4.51. Scores are yes/no logits. | Drop-in after hybrid top-k. **S.** |
| **BAAI/bge-reranker-v2-m3** | huggingface.co/BAAI/bge-reranker-v2-m3 | Apache-2.0 | about 0.6B (bge-m3 base) | Multilingual. Examples use max_length 512. Works with `CrossEncoder` or `FlagReranker`. Fine-tune recipe provided. | Drop-in, or fine-tune on our (clause, section) pairs. **S** / **M.** |
| **MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli** | huggingface.co/MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli | MIT | about 435M (DeBERTa-v3-large) | Trained on 885k NLI pairs (MNLI, FEVER, ANLI, LingNLI, WANLI). MNLI accuracy 0.912, ANLI 0.702. Labels entailment / neutral / contradiction. | NLI decision step. **M**, mostly writing hypotheses. |
| **cross-encoder/nli-deberta-v3-base** | huggingface.co/cross-encoder/nli-deberta-v3-base | Apache-2.0 | about 184M | SNLI+MNLI. Label order [contradiction, entailment, neutral]. Plain `CrossEncoder` usage. | Faster or lighter NLI fallback. **S.** |
| SAILER_en_finetune | huggingface.co/CSHaitao/SAILER_en_finetune | MIT | BERT-base | COLIEE-tuned bi-encoder (case retrieval) | Not recommended. |

Not checked or not recommended: jina-reranker-v2 (its licence is CC BY-NC per prior knowledge, not re-verified, so avoid it), and commercial legal embedders (voyage-law) because they are not local.

---

## Integration sketch for #1 + #2 (for the implementer)

```python
from sentence_transformers import CrossEncoder
rr  = CrossEncoder("Qwen/Qwen3-Reranker-0.6B")   # needs transformers>=4.51; see model card for the prompt/instruction setup
nli = CrossEncoder("MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli")  # check id2label in config for label order

# 1) rerank hybrid top-20 sections for the clause
# 2) for top sections with templates in hypotheses.yaml (s27, s28, s74, s23, A&C 12(5), ...):
#    scores = nli.predict([(clause, h) for h in templates[sec]["violation"] + templates[sec]["exception"]])
# 3) features -> Kev-0.8B / logistic head -> {void, risky, ok} + triggering hypothesis as explanation
```

Writing the hypotheses is the real work: about 3-5 violation and 1-3 exception statements per section for the ~15-25 sections we care about. Then build a 100-300 clause labelled eval set (ICAT and our own contracts) to tune thresholds before fine-tuning anything.

## Caveats
- Last-activity dates come from the GitHub commits API and HF `lastModified`. Where a page showed no date, it is marked as such.
- The ILSIC statute list was not checked for the Contract Act. ACORD and LegalBench-RAG licences were not verified on primary pages.
- The NLI models are generic. They will not know Indian case-law nuance, such as reasonable-restraint tests that are inapplicable under s.27, or the s.74 "reasonable compensation" doctrine. That must be encoded in the hypotheses and exception templates, and checked by a lawyer.
