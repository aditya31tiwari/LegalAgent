# Fine-Tuning & Temporal Legal Model Architecture Plan

> **Goal**: Build a suite of domain-specialised legal embedding models that can detect cross-clause contradictions, temporal conflicts (e.g., contracts referencing repealed IPC provisions post-BNS 2023), and jurisdiction-specific risks in Indian commercial contracts.

---

## 1. Available Datasets — Inventory

| Dataset | Records | Format | License | Best Use |
|:--------|--------:|:-------|:--------|:---------|
| **Vaquill-AI/open-india-law** | 32.5M judgment chunks + 1.1M legislation provisions | JSONL/Parquet | CC BY 4.0 | Massive pre-training corpus, temporal metadata for period-specific models |
| **KanoonGPT/indian-case-laws** | ~10M+ case law records | Parquet/HF | Apache 2.0 | Structured metadata (court, date, bench), good for temporal filtering |
| **Indian SC Judgments (AWS)** | 1950–2025 raw PDFs + metadata | PDF/JSON/Parquet | Open Data | Gold-standard SC corpus, but needs OCR/extraction |
| **Indian HC Judgments (AWS)** | 25 High Courts | PDF/Metadata | Open Data | Jurisdiction-specific training |
| **therajasekhar/sc-judgments-indic-v1** | SC judgments extracted text | Parquet | Open | Already extracted text, includes Hindi/Telugu translations |
| **rishiai/indian-court-judgements-and-its-summaries** | 6,900 judgment+summary pairs | HF Dataset | Open | Summarisation training, judgment understanding |
| **NyayaAnumana** (paper 2412.08385) | 702K cases | Research corpus | Research | Judgment prediction methodology |
| **CUAD** (existing in project) | 510 contracts, 41 categories | JSON/Span annotations | CC BY 4.0 | Clause classification baseline (US contracts, need Indian adaptation) |

---

## 2. Baseline Model — InLegal-SBERT

**Model**: `bhavyagiri/InLegal-Sbert` (already downloaded)
- Architecture: MPNet-base (110M params, 768-dim embeddings)
- Pre-trained on: Indian Supreme Court & High Court judgments
- Strengths: Already understands Indian legal language, section references, statutory citations
- Weaknesses: Trained on judgments not contracts; no temporal awareness; no clause-pair contradiction training

**This is our starting point for all fine-tuning.**

---

## 3. Multi-Model Architecture — Specialist Models

### 3.1 Model Suite Design

Rather than one monolithic model, we train **task-specific adapters** (LoRA) on the same InLegal-SBERT base:

```
InLegal-SBERT (frozen base)
├── Adapter 1: clause-similarity      — "Are these two clauses semantically related?"
├── Adapter 2: contradiction-detector  — "Do these two clauses contradict each other?"
├── Adapter 3: statutory-compliance    — "Does this clause violate Indian statute X?"
└── Adapter 4: temporal-classifier     — "What legal era does this clause belong to?"
```

### 3.2 Why LoRA Adapters?

| Approach | VRAM (6GB RTX 4050) | Disk per Model | Trainable Params |
|:---------|:-------------------:|:--------------:|:----------------:|
| Full fine-tune | ❌ ~18GB needed | 440MB | 110M |
| LoRA (r=16) | ✅ ~3.5GB | 2–5MB | ~1.2M |
| QLoRA (r=16, 4-bit) | ✅ ~2.5GB | 2–5MB | ~1.2M |

**We use QLoRA on local RTX 4050 for fast iteration, full LoRA on Colab A100/T4 for final training.**

---

## 4. Training Data Preparation

### 4.1 Clause Similarity Pairs (Adapter 1)

**Source**: CUAD + open-india-law legislation provisions
**Format**: `(anchor, positive)` pairs for `MultipleNegativesRankingLoss`

How to generate:
1. From CUAD: clauses with the same label (e.g., two "Indemnity" clauses) → positive pair
2. From open-india-law: sections from same Act that cross-reference each other → positive pair
3. In-batch negatives are automatic (clauses from different categories)

**Target**: ~50K–100K pairs

### 4.2 Contradiction Pairs (Adapter 2)

**Source**: Manual annotation + heuristic generation
**Format**: `(clause_A, clause_B, label)` where label ∈ {0: compatible, 1: contradicts}

How to generate:
1. **Synthetic contradictions**: Take a liability cap clause, pair with uncapped indemnity → label 1
2. **Judgment mining**: From open-india-law, find judgments where court identified conflicting contract clauses
3. **Template-based**: Generate clause pairs with known conflict patterns:
   - Cap (Rs X Lakhs) + Unlimited Indemnity → contradiction
   - Non-compete (post-termination) + Employment freedom → statutory conflict
   - Exclusive jurisdiction (Mumbai) + Arbitration (Delhi) → procedural conflict

**Target**: ~10K–20K pairs (can be heavily augmented)

### 4.3 Statutory Compliance Dataset (Adapter 3)

**Source**: open-india-law legislation + KanoonGPT
**Format**: `(contract_clause, statute_section, label)` where label ∈ {0: compliant, 1: violates}

How to generate:
1. Take Indian Contract Act sections (27, 73, 74, 124, 125) text from open-india-law
2. Pair with contract clauses that trigger them
3. Mine judgments where courts struck down contract clauses citing specific statutes

**Target**: ~5K–15K pairs

### 4.4 Temporal Legal Era Classification (Adapter 4)

**Source**: open-india-law (has date metadata for every judgment/legislation)
**Format**: `(text, era_label)` classification

This is the **novel contribution** — see Section 5.

---

## 5. Temporal Models — The Key Innovation

### 5.1 Major Indian Law Transition Points

| # | Date | Event | Contract Impact |
|:-:|:-----|:------|:----------------|
| 1 | **1 Apr 2014** | Companies Act 2013 fully enforced | Board composition, related-party transaction clauses |
| 2 | **1 Dec 2016** | IBC 2016 corporate insolvency provisions | Termination-on-insolvency clauses (ipso facto), assignment restrictions |
| 3 | **1 Jul 2017** | GST rollout | Pricing clauses, tax indemnity, "taxes included/excluded" provisions |
| 4 | **25 Dec 2023** | BNS enacted (assent) | Criminal penalty references (IPC → BNS section mapping) |
| 5 | **1 Jul 2024** | BNS enforced (IPC repealed) | Any contract referencing IPC sections is now citing dead law |
| 6 | **11 Aug 2023** | DPDPA 2023 assent | Data processing consent clauses, data retention terms |
| 7 | **14 Nov 2025** | DPDPA Phase 1 enforcement | Data Protection Board established |
| 8 | **14 Nov 2026** | DPDPA Phase 2 (Consent Manager) | Consent manager provisions in contracts |
| 9 | **14 May 2027** | DPDPA Phase 3 (core obligations) | Full data fiduciary duties enforceable |
| 10 | **2023** | Mediation Act | Pre-litigation mediation mandatory; affects dispute resolution clauses |

### 5.2 Era-Based Model Concept

We define legal "eras" based on which statutes are in force:

```
Era 0: Pre-2014     — IPC + old Companies Act + no GST
Era 1: 2014-2016    — Companies Act 2013 in force
Era 2: 2016-2017    — IBC 2016 in force
Era 3: 2017-Jul2024 — GST regime, IPC still valid
Era 4: Jul2024-2025 — BNS replaces IPC, DPDPA assented but not enforced
Era 5: 2025-2027    — DPDPA Phase 1, BNS in force
Era 6: 2027+        — Full DPDPA enforcement
```

### 5.3 Temporal Conflict Detection — How It Works

**The key use case**: User uploads a contract drafted in 2022. Our system:

1. Classifies the contract's "era" based on language/references (e.g., mentions "IPC Section 420" → Era 3 or earlier)
2. Compares against current law (Era 5)
3. Flags temporal conflicts:
   - "This clause references IPC Section 420, which has been replaced by BNS Section 318 since 1 July 2024"
   - "This non-compete clause was always void under Section 27 ICA, but the Mediation Act 2023 now also requires pre-litigation mediation before enforcement"
   - "This data processing clause lacks DPDPA-compliant consent mechanisms required since Nov 2025"

### 5.4 Training the Temporal Classifier

**Data source**: open-india-law (32.5M chunks with date metadata)

```python
# Filter by date ranges to create era-specific training sets
era_filters = {
    "pre_2014":   lambda d: d < "2014-04-01",
    "2014_2016":  lambda d: "2014-04-01" <= d < "2016-12-01", 
    "2016_2017":  lambda d: "2016-12-01" <= d < "2017-07-01",
    "2017_2024":  lambda d: "2017-07-01" <= d < "2024-07-01",
    "post_2024":  lambda d: d >= "2024-07-01",
}
```

For each era, train the model to understand what language/references are characteristic:
- **Pre-BNS**: "IPC Section 420", "Indian Penal Code", "cheating under Section 415"
- **Post-BNS**: "BNS Section 318", "Bharatiya Nyaya Sanhita", "snatching under Section 304"

### 5.5 Statute Section Mapping Table

Build a deterministic mapping for cross-era comparison:

| Old Reference | New Reference | Transition Date |
|:-------------|:-------------|:---------------|
| IPC Section 420 (Cheating) | BNS Section 318 | 1 Jul 2024 |
| IPC Section 415 (Cheating definition) | BNS Section 316 | 1 Jul 2024 |
| IPC Section 406 (Criminal Breach of Trust) | BNS Section 316 | 1 Jul 2024 |
| IPC Section 34 (Common Intention) | BNS Section 3(5) | 1 Jul 2024 |
| CrPC Section 154 (FIR) | BNSS Section 173 | 1 Jul 2024 |
| Indian Evidence Act | Bharatiya Sakshya Adhiniyam 2023 | 1 Jul 2024 |

*This table will be expanded to 100+ sections relevant to commercial contracts.*

---

## 6. Hardware & Training Strategy

### 6.1 Local (RTX 4050 6GB VRAM)

| Setting | Value |
|:--------|:------|
| Quantisation | QLoRA 4-bit (NF4 via bitsandbytes) |
| LoRA rank | r=16, alpha=32 |
| Batch size | 2 (per device) |
| Gradient accumulation | 16 steps (effective batch = 32) |
| Max sequence length | 256 tokens |
| Training time (50K pairs) | ~2–4 hours |
| VRAM usage | ~3–3.5GB |

**Use for**: rapid iteration, hyperparameter tuning, adapter experiments.

### 6.2 Google Colab (T4 16GB / A100 40GB)

| Setting | Value |
|:--------|:------|
| Quantisation | LoRA (no quant on T4) or full precision (A100) |
| LoRA rank | r=32, alpha=64 |
| Batch size | 16–32 |
| Max sequence length | 512 tokens |
| Training time (100K pairs) | ~1–2 hours (A100) |

**Use for**: final training runs, larger datasets, evaluation sweeps.

### 6.3 Required Libraries

```bash
pip install sentence-transformers>=3.0 peft bitsandbytes accelerate datasets
```

---

## 7. Training Pipeline — Step by Step

### Phase 1: Data Preparation (Week 1)

```
1. Download & filter open-india-law (legislation provisions only = ~1.1M, manageable)
2. Download KanoonGPT case laws (filter to commercial/contract cases)
3. Build clause similarity pairs from CUAD + legislation cross-refs
4. Build contradiction pairs (synthetic + template-based)
5. Build statutory compliance pairs
6. Build temporal classification dataset from date-filtered judgments
```

### Phase 2: Baseline Evaluation (Week 1)

```
1. Create evaluation benchmark:
   - 200 clause pairs (manually labelled: similar/contradictory/unrelated)
   - 50 statute-clause pairs (compliant/violating)
   - 50 temporal classification examples
2. Run InLegal-SBERT (no fine-tuning) on all benchmarks → baseline scores
3. Run BGE-small on same → compare
```

### Phase 3: Adapter Training (Week 2)

```
1. Train Adapter 1 (clause-similarity) on local RTX 4050
   - Loss: MultipleNegativesRankingLoss
   - Data: 50K clause pairs
   - Eval: cosine similarity on held-out pairs
   
2. Train Adapter 2 (contradiction-detector) on Colab
   - Loss: CosineSimilarityLoss with binary labels
   - Data: 20K contradiction pairs
   - Eval: F1 on contradiction detection
   
3. Train Adapter 3 (statutory-compliance)
   - Loss: CosineSimilarityLoss
   - Data: 10K statute-clause pairs
   - Eval: accuracy on statutory violation detection
   
4. Train Adapter 4 (temporal-classifier)
   - Loss: SoftmaxLoss (multi-class: 6 eras)
   - Data: 30K date-labelled judgment chunks
   - Eval: era classification accuracy
```

### Phase 4: Integration & Temporal Conflict Engine (Week 3)

```
1. Build IPC→BNS section mapping table (100+ entries)
2. Implement era detection: run Adapter 4 on uploaded contract
3. Implement temporal diff: compare clause references against current law
4. Surface temporal conflicts in the dashboard findings panel
5. Add "Legal Era" badge to contract metadata
```

### Phase 5: Evaluation & Demo Polish (Week 4)

```
1. Run full evaluation suite on all adapters
2. Compare: base InLegal-SBERT vs fine-tuned vs BGE-small
3. Update dashboard to show temporal conflicts with before/after law references
4. Prepare assessment panel demo with 3-4 real Indian contracts
```

---

## 8. Novel Contribution — What Makes This Different

| Feature | Existing Tools (Harvey, Spellbook, Robin AI) | LegalAgent |
|:--------|:---------------------------------------------|:-----------|
| Jurisdiction | US/UK focused | **Indian law native** |
| Temporal awareness | None (analyse as-is) | **Era-based conflict detection** |
| Cross-clause | Some (single-clause risk) | **Graph-based cross-clause topology** |
| Statute mapping | Manual | **Automated IPC↔BNS mapping** |
| Model architecture | Single monolithic | **Task-specific LoRA adapters** |
| Open data | Proprietary | **Built on open Indian legal corpora** |

---

## 9. Risk & Mitigation

| Risk | Mitigation |
|:-----|:-----------|
| 6GB VRAM too small for larger experiments | Use Colab A100 for final training; QLoRA keeps local feasible |
| Synthetic contradiction data may not generalise | Validate against real judgment-extracted contradictions from open-india-law |
| IPC→BNS mapping is large and error-prone | Start with top 50 commercial-relevant sections; expand incrementally |
| Temporal classifier may confuse era boundaries | Use hard date cutoffs from legislation enforcement dates, not fuzzy boundaries |
| CUAD is US contracts, not Indian | Use it for clause structure understanding; fine-tune on Indian-specific patterns |

---

## 10. Immediate Next Steps

- [ ] Set up training data pipeline script (`scripts/prepare_training_data.py`)
- [ ] Download filtered subset of open-india-law (legislation provisions only, ~2GB)
- [ ] Create evaluation benchmark (200 manually labelled clause pairs)
- [ ] Train first adapter (clause-similarity) on local GPU as proof-of-concept
- [ ] Build IPC→BNS section mapping table (start with 50 entries)
- [ ] Set up Colab notebook for larger training runs

