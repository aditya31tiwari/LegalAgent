# LegalAgent

**An Agentic Contract Review System for Cross-Clause Risk Detection**

Most contract review tools read one clause at a time. LegalAgent reads clauses *against each other* — because a liability cap in Section 5 can be quietly cancelled out by an indemnity clause in Section 12, and no clause-by-clause tool will ever catch that.

---

## What it does

Upload a contract. LegalAgent finds clause pairs that conflict, depend on each other, overlap, or leave a loophole — then explains why in plain language, with sources.

## Pipeline

```
Contract
   ↓
Clause Extraction        split by numbering/section patterns (1.1, (a), Section 5)
   ↓
Clause Classification    label each clause via fine-tuned LegalBERT
   ↓
Related-Clause Retrieval find other clauses in the same contract that matter
   ↓
Cross-Clause Analysis    compare them: conflict / dependency / overlap / ambiguity
   ↓
Risk Detection           flag the pair, assign severity
   ↓
RAG Explanation          explain the risk, grounded in retrieved references
   ↓
Results
```

## Retrieval: three methods, compared

Step 3 is the core research contribution. Three approaches are built and evaluated against each other using precision/recall at varying *k*:

| Method | How it works | Catches |
|---|---|---|
| **BM25** | keyword overlap | shared legal terms, explicit references |
| **Dense** | embedding similarity | related meaning, different wording |
| **Hybrid** | combined scores | ideally both |

## Output

Every finding carries:

- the target clause and the related clause(s) it was compared against
- relation type and severity (Low / Medium / High)
- a plain-language reason
- supporting references
- a suggested revision *(very well could be future scope)*

A flag without a reason isn't useful to a reviewer, so nothing ships without one.

---

## Tech Stack

**Core** — Python 3.10+, PyTorch, HuggingFace Transformers
**Retrieval** — rank-bm25, Sentence-Transformers, FAISS / ChromaDB
**Generation** — LLM API for RAG-based explanation
**Product layer** — login, document storage, dashboard, history, delete account/data

## Dataset

- **CUAD** — 500+ contracts, 13,000+ expert-annotated clauses (training + baseline evaluation)
- **Held-out set** — a small curated set of publicly documented loophole-exploited contracts, treated as illustrative case studies rather than a statistical benchmark

## Phase 1 target (end-to-end)

```
User → Frontend → Demo Login → Upload Contract → Backend API
     → Storage → LegalAgent Core (6 stages) → Results → Frontend
```

Core system first. Advanced components later.

## Why LegalAgent

**Existing tools review clauses. LegalAgent reviews the contract.**

### 1. Cross-clause risk, not single-clause labels
Every mainstream contract review tool is single-pass: it reads clause 5, tells you it's a
limitation-of-liability clause, scores it, and moves on. It never asks whether clause 12
cancels it out. LegalAgent's entire pipeline is built around that question. The unit of
analysis is the **clause pair**, not the clause.

### 2. It finds the pairs worth comparing
A 60-clause contract has ~1,800 possible pairs — too many to analyse blindly. LegalAgent
narrows them using three signals:
- **Retrieval** (BM25 / dense / hybrid) surfaces semantically related clauses
- **Cross-references** parsed from the text ("subject to Section 8.2") give explicit links
- **A risk type matrix** encodes known dangerous combinations — liability cap × indemnity,
  termination × survival, exclusivity × non-compete

Only the shortlist gets deep analysis. That's what makes it run in seconds, not minutes.

### 3. Every flag comes with its reasoning
A severity score with no explanation is a dead end for a reviewer. Each finding carries the
*specific* clause it was compared against, the relation type, verbatim evidence from both
clauses, and a plain-language reason grounded in retrieved references — not an unaided
model guess.

### 4. Severity is transparent, not a black box
Risk levels come from a tunable rubric over relation type, clause-type pairing, and analysis
confidence — readable, auditable, and adjustable. The model finds the issue; a documented
rule decides how serious it is.

### 5. The retrieval comparison is a real result
BM25 vs dense vs hybrid are evaluated against gold clause pairs derived from the contracts'
own cross-references — a measurable deliverable, not a benchmark bolted on the side.

### 6. Modular by construction
Every stage reads and writes the same clause data structure. LangGraph orchestration, the
MCP interface, and the clause-graph GNN can be added later without rewriting anything that
already works.

---

> **In one line:** LegalAgent catches the risks that only appear when two clauses are read
> together — and tells you exactly why.

---

## Scope

LegalAgent is a research and assistive tool for surfacing clauses worth a closer look. **It does not replace a lawyer's review.**

