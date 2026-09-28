# 02 - Model Selection, Benchmarking & Fine-Tuning Strategy

## 1. Core Question: Out-of-the-Box Models vs. Fine-Tuning

### Do we need to fine-tune our own model immediately?
**No.** For the prototype and initial assessment, **fine-tuning our own model is not recommended and unnecessary**. 

Here is why:
1. **Lack of Labeled Pair Data:** Fine-tuning a Siamese network (like SBERT) for clause retrieval requires thousands of contrastive triples `(anchor_clause, positive_related_clause, negative_unrelated_clause)`. Fabricating synthetic pairs before validating real-world performance risks overfitting to artificial patterns.
2. **High-Quality Domain Pre-training Already Exists:** Pretrained legal models like **InLegalBERT** (from IIT Kharagpur) were already trained on 5.4 million Indian Supreme Court and High Court legal documents (27 GB of raw legal text).
3. **Prototype Speed & Maintainability:** Out-of-the-box sentence transformers allow zero-latency iteration, rapid experimentation, and deterministic evaluation against gold contract cross-references.
4. **When Fine-Tuning DOES Make Sense (Phase 2):** Once our prototype is demonstrated and we annotate ~100 Indian commercial contracts with real clause cross-dependencies, we can fine-tune `InLegal-Sbert` using Multiple Negatives Ranking Loss (MNRL).

---

## 2. Model Candidates for Benchmarking

We evaluate four primary models across domain fit, resource consumption, and inference speed:

| Model | Source | Size | Parameters | Domain Specialization | Compute Cost |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`bhavyagiri/InLegal-Sbert`** | IIT Kharagpur / Community | ~420 MB | ~110M | **Indian Supreme Court & High Courts** | **$0** (Local CPU/GPU) |
| **`law-ai/InLegalBERT`** | IIT Kharagpur | ~440 MB | ~110M | **Indian Statutory & Case Law** | **$0** (Local CPU/GPU) |
| **`BAAI/bge-small-en-v1.5`** | BAAI (Hugging Face) | ~130 MB | ~33M | General High-Performance Embedding | **$0** (Ultra-fast CPU) |
| **`text-embedding-3-small`** | OpenAI API | Cloud | Unknown | General Semantic | ~$0.02 / 1M tokens |

### 2.1 Model Profiles

#### 1. `bhavyagiri/InLegal-Sbert` (Primary Recommendation for Prototype)
* **Architecture:** BERT-base fine-tuned as a bi-encoder for semantic similarity on Indian legal texts.
* **Pros:** Native awareness of Indian legal jargon (e.g., "vacate stay", "suo motu", "restraint of trade", "stamped instrument", "memorandum of understanding").
* **Output:** 768-dimensional dense vectors with cosine similarity mapping.

#### 2. `BAAI/bge-small-en-v1.5` (Fast Baseline)
* **Architecture:** 384-dimensional compact transformer.
* **Pros:** Consistently scores in top tier on the Massive Text Embedding Benchmark (MTEB). Inference latency is ~5ms per clause on standard laptop CPU.
* **Use Case:** Fallback and speed baseline.

#### 3. `law-ai/InLegalBERT` (Classification / Cross-Encoder)
* **Architecture:** Masked language model (not sentence-transformer pooled).
* **Use Case:** Ideal as a **Cross-Encoder reranker** for clause pairs rather than bi-encoder vector search.

---

## 3. Clustering Strategy: Why K-Means Fails for Contracts

### The Limitations of K-Means in Contract Review
1. **Unknown $k$:** A 15-page NDA might contain 4 main topics, while a 70-page Master Services Agreement might contain 22. Setting a fixed $k$ produces arbitrary groupings.
2. **Forced Assignment of Noise:** Contracts contain preamble, recital boilerplate, signature blocks, and transitional clauses. K-Means forces every preamble into an artificial topic cluster, degrading purity.

### Recommended Approach: Agglomerative Clustering with Cosine Distance Threshold
We group clauses by semantic density using hierarchical agglomerative clustering:

```python
from sklearn.cluster import AgglomerativeClustering

clustering = AgglomerativeClustering(
    n_clusters=None,
    metric="cosine",
    linkage="average",
    distance_threshold=0.35  # Clauses with cosine similarity >= 0.65 cluster together
)
cluster_ids = clustering.fit_predict(clause_embeddings)
```

**Benefits:**
* Naturally groups related sections (e.g., all indemnities, liabilities, and insurance clauses converge).
* Outlier clauses remain unclustered (`-1` or singleton clusters).
* Generates an intuitive dendrogram showing macro-topics (Commercial Terms, IP & Confidentiality, Risk Allocation, Boilerplate).

