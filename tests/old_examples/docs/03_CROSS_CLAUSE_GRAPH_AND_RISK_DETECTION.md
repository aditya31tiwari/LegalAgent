# 03 - Cross-Clause Knowledge Graph & Risk Detection Engine

## 1. Concept: Contracts as Directed Attributed Graphs

Traditional contract review tools treat contracts as a linear sequence of isolated paragraphs. LegalAgent converts the contract into an **Attributed Knowledge Graph**:

$$G = (V, E)$$

* **Vertices ($V$):** Clauses ($v_i \in V$), annotated with:
  * Section Number (e.g., `5.2`, `12.1`)
  * Heading (e.g., `"Limitation of Liability"`, `"Indemnity"`)
  * Clause Label / Category (e.g., `indemnification`, `governing_law`, `non_compete`)
  * Character span offsets (`[char_start, char_end]`)
  * Semantic embedding vector $\vec{e}_i$
* **Edges ($E$):** Cross-clause relationships, categorized into four explicit relation types:
  1. `xref` (Explicit Cross-Reference): *"Subject to Section 8.2"*, *"Notwithstanding Clause 14"*.
  2. `semantic_similarity`: Unlinked clauses with high embedding cosine similarity ($\ge 0.70$).
  3. `contractual_conflict`: Clauses that contradict or nullify each other (e.g., blanket indemnity vs. liability cap).
  4. `statutory_violation`: A clause that contradicts an Indian legal statute (e.g., post-term non-compete vs. Section 27 ICA 1872).

---

## 2. Graph Topology & Edge Taxonomy

```
                     Contract Graph Representation
                                   │
      ┌────────────────────┬───────┴────────┬───────────────────┐
      ▼                    ▼                ▼                   ▼
    [XREF]           [SEMANTIC]        [CONFLICT]          [STATUTORY]
  Section 4.1 ───►  Indemnity 12.1   Liability Cap 8.1   Non-Compete 14.2
  explicitly cites  semantically     nullified by        void under
  Section 9.3       pairs with 12.3  Indemnity 11.2      Section 27 ICA 1872
```

### Edge Attributes Schema
```json
{
  "source": "cls_08_limitation_of_liability",
  "target": "cls_12_indemnification",
  "relation_type": "contractual_conflict",
  "severity": "high",
  "risk_score": 0.92,
  "rationale": "Section 8 caps liability at 12 months' fees, but Section 12 mandates uncapped indemnity without carveout.",
  "statutory_ref": null,
  "confidence": 0.95
}
```

---

## 3. The 3-Stage Risk Detection Algorithm

```
  All Clauses
      │
      ▼
1. Candidate Selection Filter (Reduces N*(N-1)/2 pairs)
   ├── Tier 1: Explicit regex xrefs (100% kept)
   ├── Tier 2: Indian Statutory Violations (100% kept)
   ├── Tier 3: Known Type Matrix pairs (e.g., Liability x Indemnity)
   └── Tier 4: Dense SBERT Embedding Top-K retrieval
      │
      ▼  (Candidate Pairs <= 30)
2. Cross-Clause Logic Engine
   ├── Rule-based statutory filters (Section 27, Section 74, DPDPA)
   └── LLM or Cross-Encoder Contradiction Classifier
      │
      ▼
3. Severity Rubric & Evidence Grounding
   └── Low, Medium, High severity with character offset highlights
```

---

## 4. Frontend Visualizer Integration

The knowledge graph directly drives our prototype frontend:
* **Interactive Network Canvas:** Force-directed layout where nodes represent clauses and edges represent connections.
* **Color-Coded Nodes:** Distinct colors per clause family (Risk/Liability = Red, Commercial/Payment = Green, Term/Termination = Blue, Boilerplate = Grey).
* **Highlighted Conflict Edges:** Red pulsating or dashed edges showing dangerous clause contradictions.
* **Side-by-Side Clause Inspector:** Clicking an edge opens both clauses side-by-side with exact offending phrases highlighted.

