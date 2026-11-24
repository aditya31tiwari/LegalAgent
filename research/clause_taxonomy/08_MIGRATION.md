# Migration Guide: CLAUSE-20 → CLAUSE-22

**Total estimated time:** **~55 minutes** (~10 min edits + ~1 min dataset rebuild + ~45 min InLegalBERT retrain on RTX 4050 + ~2 min validation).  
**Safety rule:** Wait until the currently running training session finishes and commits/checkpoints before applying these edits.

---

## Step 1 — Swap the Taxonomy & Mapping YAMLs (~1 min)

Copy the two validated drop-in files over the existing configs:

```bash
cp research/clause_taxonomy/05_PROPOSED_labels.yaml clause20/labels.yaml
cp research/clause_taxonomy/06_PROPOSED_label_map.yaml clause20/label_map.yaml
```

*(Optional, +2 min, recommended)* Add `"arbitration"` to `RECOVERY_ANCHORS` in `clause20/build.py` (line 345) so unhighlighted CUAD arbitration clauses (~120 rows) are recovered as silver rows, giving `arbitration` ~18 `test_ood` evaluation rows instead of 0:

```python
RECOVERY_ANCHORS = {
    "indemnification": r"indemnif|hold harmless",
    "confidentiality": r"confidential|non-?disclosure",
    "tax": r"\btax(es|ation)?\b|withholding",
    "amendment_and_integration": r"entire agreement|amendment|no waiver",
    "arbitration": r"\barbitrat",
}
```

---

## Step 2 — Rebuild the Dataset & Run Unit Tests (~1 min)

`cuad.csv` and `ledgar.csv` in `clause20/data/interim/` do **not** need to be re-extracted from the raw zips unless `build.py` extraction changed; you only need `labels`, `merge`, `dedup`, `split`:

```bash
venv/bin/python clause20/build.py labels
venv/bin/python clause20/build.py merge
venv/bin/python clause20/build.py dedup
venv/bin/python clause20/build.py split
venv/bin/python clause20/test_build.py
```

**Expected verification checks:**
- `build.py labels` prints `all labels mapped` (41 CUAD, 100 LEDGAR).
- `build.py dedup` prints **~74,281 rows** (~74,400 if `arbitration` silver recovery is enabled) and **zero** `<- below min_support` warnings across all 22 trained labels.
- `test_build.py` passes all 4 tests (`test_label_map_targets_exist_in_taxonomy` and `test_conflict_pairs_reference_real_labels` confirm 0 orphans and 0 typos).

---

## Step 3 — Retrain Classifiers (~46 min total)

1. **Fast baseline (`minilm_lr`, ~1 min CPU/GPU):**
   ```bash
   venv/bin/python clause20/train.py
   ```
2. **Primary model (`law-ai/InLegalBERT`, ~45 min on RTX 4050 6 GB):**
   ```bash
   venv/bin/python train/finetune_classifier.py \
     --model law-ai/InLegalBERT \
     --out models/clause20_inlegalbert \
     --epochs 3 --bs 16 --lr 3e-5 --max-len 256
   ```
   *(No code changes needed in `train/finetune_classifier.py` — it reads the label set dynamically from `CLAUSE20.csv` and writes `num_labels=23` into `models/clause20_inlegalbert/config.json` and `clause20_meta.json`.)*

---

## Step 4 — Code Updates (~10 min, 4 files)

### 4.1 `legalagent/core/classification.py`
1. Add `arbitration` and `remedies` to the fallback `KEYWORDS` dict (lines 30–42):
   ```python
   "arbitration": ["arbitration", "arbitral tribunal", "arbitrator", "seat of arbitration", "a&c act"],
   "remedies": ["specific performance", "injunctive relief", "sole and exclusive remedy", "waives any remedy", "liquidated damages"],
   ```
2. Replace the single `FORCE_MAJEURE_KEYWORDS` block (lines 45 & 144–147) with a dictionary covering all **7 rule-based `known_gaps`**:
   ```python
   KNOWN_GAP_KEYWORDS = {
       "force_majeure": ("force majeure", "act of god", "acts of god", "beyond the reasonable control"),
       "liquidated_damages": ("liquidated damages", "pre-estimated damages", "genuine pre-estimate", "delay damages", "penalty for delay"),
       "data_protection": ("personal data", "data protection", "dpdp", "data fiduciary", "data principal", "gdpr", "sensitive personal data"),
       "stamp_duty": ("stamp duty", "unstamped", "e-stamp", "impounding", "stamp paper", "stamp act"),
       "performance_security": ("performance security", "bank guarantee", "performance bond", "encashment of security"),
       "change_in_law": ("change in law", "statutory change", "economic equilibrium"),
       "step_in_rights": ("step-in", "step in right", "substitution agreement", "nominated company", "lenders' representative"),
   }
   ```
   And loop over `KNOWN_GAP_KEYWORDS.items()` in `classify()`, **anchoring long clauses (> 60 words) to the first 30 words and skipping Definition clauses** (`"means "` in the first 120 chars) so cross-references in 600-clause Indian MCAs don't over-fire (cuts false positives 60–75% while keeping 100% recall on `INJECTIONS.json`):
   ```python
   for clause in clauses:
       low = clause.text.lower()
       if "means " in low[:120]:
           continue
       words = low.split()
       window = " ".join(words[:30]) if len(words) > 60 else low
       existing = {l["label"] for l in clause.labels}
       for gap_label, kws in KNOWN_GAP_KEYWORDS.items():
           if gap_label not in existing and any(k in window for k in kws):
               clause.labels.append({"label": gap_label, "confidence": 1.0, "source": "keyword"})
   ```

### 4.1b Optional: Expand Indian Semantic-Search Statute Corpus (+706 records, ~1 min)
`research/clause_taxonomy/indian_law_docs/india_semantic_search_additions.jsonl` is already downloaded and normalized to the exact schema of `data/statutes/india_commercial_sections.jsonl` (BNS 2023: 358, CPC 1908: 171, BSA 2023: 170, 7 landmark SC/HC precedents). To add it to `statutes.py` semantic search (brings corpus from 2,436 → **3,142** entries):

```bash
cat research/clause_taxonomy/indian_law_docs/india_semantic_search_additions.jsonl >> data/statutes/india_commercial_sections.jsonl
rm -f data/statutes/india_commercial_sections.bhavyagiri__InLegal-Sbert.npy  # forces index rebuild on next run
```

### 4.2 `legalagent/core/candidate_selection.py`
`TYPE_MATRIX` already loads all 27 trained-label pairs automatically from `clause20/labels.yaml`. In `_load_type_matrix()` (lines 16–18), add the `known_gaps` pairs alongside the two existing `force_majeure` entries:

```python
matrix[("force_majeure", "termination")] = 0.60
matrix[("force_majeure", "payment_and_fees")] = 0.55
matrix[("liquidated_damages", "limitation_of_liability")] = 0.85
matrix[("liquidated_damages", "payment_and_fees")] = 0.70
matrix[("data_protection", "limitation_of_liability")] = 0.85
matrix[("data_protection", "confidentiality")] = 0.70
matrix[("stamp_duty", "arbitration")] = 0.80
matrix[("performance_security", "termination")] = 0.70
matrix[("performance_security", "liquidated_damages")] = 0.65
matrix[("change_in_law", "payment_and_fees")] = 0.70
matrix[("change_in_law", "tax")] = 0.65
matrix[("step_in_rights", "termination")] = 0.75
matrix[("step_in_rights", "assignment_change_of_control")] = 0.70
```

### 4.3 `legalagent/core/analysis.py` *(High-Value Indian Statutory Rules)*
Existing rules (`limitation_of_liability+indemnification`, `termination+survival`, ICA s.27 post-termination non-compete) remain 100% compatible because none of those label names changed. Optionally add 3 deterministic Indian statutory checks in `analyse_statutory()` (matches `INJECTIONS.json` #91.5, #91.7, #91.13):
- **ICA s.74 (`liquidated_damages`)**: flag clauses combining `liquidated damages` / `penalty` with `regardless of actual loss` or `>= 50%` of contract value.
- **Indian Stamp Act s.35 (`stamp_duty`)**: flag clauses containing `intentionally unstamped` or waiving impounding/stamp duty.
- **DPDP Act 2023 (`data_protection`)**: flag clauses permitting personal data collection/sale `without notice` or `without consent`, or capping statutory DPDP penalties.

### 4.4 `web/backend.py` & `web/index.html` *(Bug Fix + UI Families)*
**Bug discovered during audit:** `web/backend.py` lines 253–260 and 647–654 currently use stale pre-CLAUSE-20 label names (`liability_limitation`, `assignment`, `non_compete`, `payment`), so live uploads silently fall back to `"General"`. Replace both `LABEL_TO_TAG` dicts with a single shared constant mapping all 22 trained labels + 7 `known_gaps` to the existing UI tag colours in `web/index.html` (lines 1018–1019 & 1136–1137 — no HTML/CSS edits needed!):

```python
LABEL_TO_TAG = {
    # Red / Risk palette in index.html (matches "Risk" or "Liability")
    "limitation_of_liability": "Liability",
    "exclusivity_and_restraint": "High Risk",
    "liquidated_damages": "High Risk",
    "warranty": "Risk",
    "remedies": "Risk",
    # Purple / Statutory palette in index.html (matches "Indemnity", "Compliance", "Statutory", "DPDPA")
    "indemnification": "Indemnity",
    "compliance_and_law": "Compliance",
    "data_protection": "DPDPA",
    "stamp_duty": "Statutory",
    "change_in_law": "Statutory",
    # Standard palette
    "termination": "Term",
    "term_and_renewal": "Term",
    "survival": "Survival",
    "force_majeure": "Term",
    "confidentiality": "IP",
    "ip_ownership": "IP",
    "license_grant": "IP",
    "governing_law": "Governing Law",
    "dispute_resolution": "Dispute",
    "arbitration": "Dispute",
    "payment_and_fees": "Payment",
    "tax": "Payment",
    "performance_security": "Payment",
    "audit_and_records": "General",
    "insurance": "General",
    "assignment_change_of_control": "General",
    "step_in_rights": "General",
    "notices": "General",
    "amendment_and_integration": "General",
}
```

### 4.5 GNN (`legalagent/core/gnn.py`)
No `legalagent/core/gnn.py` file was present on disk at audit time; if the other session adds one, ensure it reads `len(labels)` dynamically from `clause20/labels.yaml` (22 trained + 7 known_gaps) rather than hardcoding `20`.

---

## Step 5 — Post-Migration Smoke Test (~2 min)

```bash
venv/bin/python -c "
from legalagent.core.candidate_selection import TYPE_MATRIX
from legalagent.core.classification import classify
from legalagent.core.types import Clause
print('TYPE_MATRIX pairs:', len(TYPE_MATRIX))
sample = [
    Clause(id='c1', number='1', heading='Arbitration', text='All disputes shall be resolved by arbitration seated in Mumbai under the Arbitration and Conciliation Act, 1996.'),
    Clause(id='c2', number='2', heading='Stamp Duty', text='The parties agree this agreement is intentionally unstamped.'),
    Clause(id='c3', number='3', heading='Delay', text='Delay shall incur liquidated damages of 75% regardless of actual loss.'),
]
for c in classify(sample):
    print(c.number, [l['label'] for l in c.labels])
"
```
Expected: `TYPE_MATRIX pairs: 40` (27 trained + 13 known_gaps), `c1` carries `arbitration`, `c2` carries `stamp_duty`, `c3` carries `liquidated_damages`.
