# 04 - Assessment Panel Prototype Specification

## 1. Goal & Objectives
The immediate objective is to build a **visually compelling interactive prototype** to present to the academic / technical assessment panel.

The presentation needs to clearly prove two core innovations:
1. **Clause-Pair Analysis vs. Single-Clause Labeling:** Showing that risks emerge from the *interplay* between clauses, not clauses in isolation.
2. **Indian Legal Grounding:** Demonstrating statutory invalidity checks (e.g., Section 27 ICA void non-competes, DPDPA fine carveouts) alongside inter-clause conflicts.

---

## 2. Interactive Prototype Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                             LegalAgent Header                               │
│  Contract Selector [ Indian Tech MSA | SaaS Agreement | Employment NDA ]    │
│  Filter: [ All Connections | Conflicts Only | Statutory Red Flags ]         │
├──────────────────────┬───────────────────────────────┬──────────────────────┤
│    Clause List       │    Interactive Clause Graph   │    Finding Details   │
│                      │                               │                      │
│ [1. Definitions]     │       (5.1) ───[conflict]───► │ ⚠️ HIGH SEVERITY      │
│ [2. Scope of Work]   │         │               (12.3)│ Liability Cap Void   │
│ [5.1 Liability Cap]  │         │                     │                      │
│ [8.2 Non-Compete]    │         ▼                     │ Section 5.1 caps at  │
│ [12.3 Indemnity]     │       (8.2)                   │ ₹10L, but Sec 12.3   │
│ [15. Governing Law]  │       [Sec 27 Void]           │ has uncapped claims. │
│                      │                               │                      │
│ Clicking a clause    │ D3 / Vis.js Force Directed    │ Statutory Citation:  │
│ scrolls and focuses  │ Red edges = Conflict          │ Sec 27 ICA / DPDPA   │
│ the graph node       │ Green edges = Semantic        │                      │
└──────────────────────┴───────────────────────────────┴──────────────────────┘
```

---

## 3. Core Visual Features for Assessment Impact

1. **Dual Synchronization (Text $\leftrightarrow$ Graph):**
   * Clicking a clause in the contract text centers and pulses the corresponding node in the graph.
   * Clicking an edge in the graph highlights both linked clauses side-by-side with exact verbatim risk evidence.
2. **Color-Coded Severity & Relations:**
   * 🔴 **Red Solid / Pulsing Edges:** High Risk Inter-Clause Conflicts (e.g., Liability Cap vs. Indemnity).
   * 🟠 **Orange Edges:** Indian Statutory Red Flags (e.g., Section 27 Restraint of Trade, Section 74 Penalty).
   * 🔵 **Blue Edges:** Explicit Cross-References (`"subject to Section 8.2"`).
   * 🟢 **Teal / Green Dashed Edges:** Semantic Clusters discovered via `InLegal-Sbert` embeddings.
3. **Demo Contracts Built In:**
   * Pre-packaged realistic sample contracts ready to demonstrate with one click:
     - **Sample 1:** Indian SaaS Master Services Agreement (featuring Liability vs Indemnity clash & DPDPA penalty attempt).
     - **Sample 2:** Executive Employment & IP Agreement (featuring illegal 2-year post-termination non-compete under Section 27).

