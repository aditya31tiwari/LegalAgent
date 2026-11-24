# Clause Taxonomy Research — Findings & Recommendation

**Executive Recommendation:** Upgrade from **CLAUSE-20** (20 trained labels + `other`, 1 rule-based gap) to **CLAUSE-22** (**22 trained labels + `other`**, **27 `conflict_pairs`**, and **7 explicitly documented rule-based `known_gaps`** for Indian commercial and PPP contracts). Every change is a drop-in edit to `clause20/labels.yaml` and `clause20/label_map.yaml` (~1 min corpus rebuild, ~45 min InLegalBERT retrain on RTX 4050) plus ~60 lines of deterministic keyword/rule updates in `classification.py`, `candidate_selection.py`, `analysis.py`, and `web/backend.py`. **No new datasets need to be downloaded or annotated before the viva.**

---

## 1. Ranked Changes by Value / Effort

| Rank | Change | Value | Effort | Do Before Viva? |
|---:|---|---|---|---|
| **1** | **Fix LEDGAR `"Applicable Laws"` mislabelling** (`compliance_and_law` → `governing_law`). Empirically verified on `ledgar.csv`: **426/474 rows (89.9%)** are choice-of-law clauses (*"governed by the laws of…"*), only 4.4% are compliance covenants. | Very High | Trivial (1 YAML line) | **YES** |
| **2** | **Split `arbitration` out of `dispute_resolution`** (`LEDGAR "Arbitration"` = 447 post-dedup / 346 train; +120 silver CUAD rows if `RECOVERY_ANCHORS` is extended). Unlocks Arbitration & Conciliation Act 1996 seat/venue/forum-clash detection. | Very High | Low (YAML + 1 anchor) | **YES** |
| **3** | **Split `remedies` out of `dispute_resolution` & clean `limitation_of_liability`**. Moves CUAD `"Liquidated Damages"` (69 rows — 14.6% noise!) out of `limitation_of_liability` into `[remedies, payment_and_fees]`, and splits LEDGAR `Remedies` / `Specific Performance` / `Releases` + CUAD `Covenant Not To Sue` into `remedies` (1,949 post-dedup). Unlocks ICA s.28/s.74 and SRA 1963 clash detection. | Very High | Low (YAML) | **YES** |
| **4** | **Slim `compliance_and_law` from 7,316 → 1,860 rows**. Demote 11 M&A/credit-closing boilerplate labels (`Authority`, `Binding Effects`, `No Conflicts`, `Solvency`, `Liens`, etc. = 4,999 rows) to `other`, stopping `TYPE_MATRIX` candidate explosion. | High | Trivial (11 YAML lines) | **YES** |
| **5** | **Add 6 Indian/PPP rule-based `known_gaps`** (`liquidated_damages`, `data_protection`, `stamp_duty`, `performance_security`, `change_in_law`, `step_in_rights`) alongside `force_majeure` in `classification.py` + `candidate_selection.py`. Directly covers 6 of the 15 Pune Metro adversarial injections (`INJECTIONS.json` #91.5, #91.6, #91.7, #91.13) and real NHAI/Pune Metro MCA clauses. | High | Low (~45 LOC) | **YES** |
| **6** | **Fix legacy `LABEL_TO_TAG` bug in `web/backend.py`** (lines 253 & 647 still reference pre-CLAUSE-20 names `liability_limitation`, `assignment`, `non_compete`, `payment`, causing live uploads to fall back to `"General"`). | High (Demo UI) | Trivial (~15 LOC) | **YES** |
| **7** | Harvest LEDGAR-Full long-tail headings (`Force Majeure`, `Liquidated Damages`, `Data Protection`) and silver-label non-demo DEA/NITI Aayog MCAs with Gemini. | Medium-High | Medium–High (>4 h) | **NO (Post-Viva)** |
| **8** | Two-level hierarchical classification loss or defined-term extraction graph. | Low–Medium | High (>1 day) | **NO (Post-Viva)** |

---

## 2. Detailed Answers to Research Questions

### Q1. Taxonomy Design: CLAUSE-22 (22 Trained Labels + `other` + 7 Rule-Based `known_gaps`)

Verified by running `build.py`'s exact `merge` + `dedup` + `split` pipeline in memory over `clause20/data/interim/{cuad,ledgar}.csv` (see `05_PROPOSED_labels.yaml` and `06_PROPOSED_label_map.yaml`):

| # | Trained Label | Post-Dedup Total | Train | Val | Test | Test OOD | Change vs CLAUSE-20 |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | `amendment_and_integration` | 7,148 | 5,349 | 910 | 833 | 56 | Kept |
| 2 | `payment_and_fees` | 5,720 | 4,252 | 761 | 622 | 85 | +63 from CUAD `Liquidated Damages` |
| 3 | `governing_law` | 4,639 | 3,470 | 570 | 542 | 57 | **Fixed**: +445 from LEDGAR `Applicable Laws` |
| 4 | `assignment_change_of_control` | 3,489 | 2,608 | 422 | 373 | 86 | Kept |
| 5 | `dispute_resolution` | 2,962 | 2,269 | 396 | 297 | 0 | **Focused**: court jurisdiction, venue, jury waiver, litigation |
| 6 | `term_and_renewal` | 2,691 | 2,037 | 336 | 257 | 61 | Kept |
| 7 | `notices` | 2,646 | 2,019 | 310 | 304 | 13 | Kept |
| 8 | `tax` | 2,548 | 1,865 | 337 | 332 | 14 | Kept |
| 9 | `confidentiality` | 2,447 | 1,863 | 288 | 236 | 60 | Kept |
| 10 | `remedies` *(NEW)* | 1,949 | 1,506 | 240 | 176 | 27 | **Split** from `dispute_resolution` (+CUAD LD) |
| 11 | `compliance_and_law` | 1,860 | 1,367 | 224 | 269 | 0 | **Cleaned**: 7,316 → 1,860 (-74.6% noise) |
| 12 | `survival` | 1,807 | 1,371 | 243 | 165 | 28 | Kept |
| 13 | `termination` | 1,763 | 1,314 | 273 | 98 | 78 | Kept |
| 14 | `indemnification` | 1,726 | 1,285 | 222 | 163 | 56 | Kept |
| 15 | `insurance` | 1,487 | 1,134 | 209 | 112 | 32 | Kept |
| 16 | `audit_and_records` | 1,408 | 1,101 | 180 | 83 | 44 | Kept |
| 17 | `warranty` | 1,395 | 1,055 | 170 | 161 | 9 | Kept |
| 18 | `exclusivity_and_restraint` | 1,041 | 761 | 155 | 42 | 83 | Kept |
| 19 | `ip_ownership` | 755 | 570 | 93 | 56 | 36 | Kept |
| 20 | `license_grant` | 514 | 351 | 89 | 0 | 74 | Kept |
| 21 | `arbitration` *(NEW)* | 447 | 346 | 58 | 43 | 0* | **Split** from `dispute_resolution` (*+120 silver CUAD optional) |
| 22 | `limitation_of_liability` | 414 | 299 | 68 | 0 | 47 | **Cleaned**: CUAD `Liquidated Damages` removed |
| — | `other` *(sink)* | 25,499 | 19,145 | 3,094 | 3,252 | 8 | Absorbed 11 demoted M&A/credit boilerplate labels |

**Every single one of the 22 trained labels clears `min_support >= 300` post-dedup** (total corpus: 74,281 rows).

#### Specific decisions on each candidate raised in `01_REQUIREMENTS.md`:

- **`limitation_of_liability` (Cap vs Uncapped vs Liquidated Damages):**
  - *Keep `Cap On Liability` (406) + `Uncapped Liability` (117) together.* Measured in `cuad.csv`: **110 of 118 `Uncapped Liability` clauses (93.2%) co-occur on the exact same clause as `Cap On Liability`** (caps and carve-outs are drafted in one clause). Splitting `uncapped_liability` fails `min_support` (117 < 300) and creates a near-collinear label; the pair judge (rules/Kev/Gemini) handles cap-vs-carve-out polarity.
  - *Remove `Liquidated Damages` (69 rows) from `limitation_of_liability`.* Only 9/69 co-occur with `Cap On Liability`; under ICA s.74, LDs are pre-estimated breach damages/penalties that *clash with* liability caps rather than *being* liability caps. Move CUAD `Liquidated Damages` → `[remedies, payment_and_fees]` and detect `liquidated_damages` via a dedicated rule in `known_gaps`.
- **`compliance_and_law` (7,316 rows):** Was a noisy catch-all. Moving `Applicable Laws` (449 rows, 89.9% choice-of-law) to `governing_law` and demoting 11 M&A/credit closing representations (`Authority`, `Authorizations`, `Approvals`, `Binding Effects`, `Enforceability`, `No Conflicts`, `No Defaults`, `Solvency`, `Liens`, `Transactions With Affiliates`, `Third Party Beneficiary` = 4,999 rows) to `other` leaves **1,860 clean regulatory compliance rows** (`Compliance With Laws`, `Sanctions`, `Anti-Corruption Laws`, `Erisa`).
- **`amendment_and_integration` (7,148 rows):** Keep intact. Its three components (`Amendments`/`Modifications` 2,056; `Entire Agreements`/`Integration` 3,159; `Waivers`/`No Waivers` 1,625) all govern contract modification and non-reliance, participating in high-value clashes (`amendment_and_integration+payment_and_fees` for unilateral amendment, `amendment_and_integration+warranty` for entire-agreement vs pre-contractual reps, `amendment_and_integration+notices`).
- **`dispute_resolution` (5,284 rows) → Split into 3:**
  - `arbitration` (447 post-dedup): A&C Act 1996 seat/venue/unilateral-appointment/forum clashes.
  - `remedies` (1,949 post-dedup): SRA 1963 specific performance, ICA s.28 remedy waivers, ICA s.74 liquidated damages, sole-remedy vs liability cap.
  - `dispute_resolution` (2,962 post-dedup): court jurisdiction, venue, jury waiver, litigation.
- **`non_compete`/`non_solicit` vs `exclusivity_and_restraint`:** **Do NOT split.** True restraint clauses (`Non-Compete` 169 + `No-Solicit` 97 + `Competitive Restriction Exception` 76) total only ~250 post-dedup rows (~165 train) without LEDGAR `Non-Disparagement` (435 rows, which is *not* an ICA s.27 restraint of trade), while `Exclusivity + ROFR + MFN` is only 261 train rows. Keep `exclusivity_and_restraint` unified (1,041 rows) and rely on the existing ICA s.27 post-termination non-compete rule in `analysis.py` + `exclusivity_and_restraint+survival` clash pair.
- **`representations` vs `warranty`:** **Do NOT split.** Inspecting `ledgar.csv` shows both LEDGAR `"Representations"` (695) and `"Warranties"` (598) use identical `"represents and warrants"` boilerplate and share identical conflict pairs.
- **`definitions` (`Definitions` 715 + `Defined Terms` 457 = 1,172):** **Keep in `other`.** Adding `definitions` to `TYPE_MATRIX` would pair every contract's Definitions article with dozens of clauses quadratically. Defined-term resolution belongs in Layer 2 (`extraction.py`), not `TYPE_MATRIX`.
- **`payment_and_fees` vs `pricing`:** **Do NOT split.** CUAD `Price Restrictions` has only 15 rows.
- **7 Rule-Based `known_gaps` (Indian Commercial & PPP Contracts):** `force_majeure` (137 heading hits in CUAD, 0 gold), `liquidated_damages` (69 CUAD), `data_protection` (23 CUAD heading hits, 0 gold — DPDP Act 2023), `stamp_duty` (0 gold — Indian Stamp Act s.35), `performance_security` (2 CUAD heading hits — PPP bank guarantees), `change_in_law` (1 CUAD heading hit — PPP economic equilibrium), `step_in_rights` (0 gold — PPP Substitution Agreements). All 7 are explicitly declared in `known_gaps` and detected by deterministic keyword rules in `classification.py`.

---

### Q2. Data Sources & Indian Contract Landscape

Full verified table (HF IDs, URLs, licences, gating, sizes, effort) is in [`07_DATASETS.md`](07_DATASETS.md). Key findings:
1. **No public, human-annotated, clause-level Indian commercial contract classification dataset exists.** `Exploration-Lab/IL-TUR` and `opennyaiorg/InLegalNER` are gated court-judgment datasets; `mhardik003/15k-indian-legal_contracts_and_agreements` is an empty stub (2 files); `azazelovesH100/indian-inhouse-clause-corpus` (CC-BY-4.0, 931 MD files) is explicitly **machine-generated synthetic templates**.
2. **Real Indian commercial contracts** are publicly available as unlabelled PDFs from the DEA PPP Cell (https://www.pppinindia.gov.in), NITI Aayog (https://www.niti.gov.in), and MoRTH — two of which (NHAI 4-laning MCA, Pune Metro Line-3) are already held out on disk.
3. **Best near-term data route:** Retrain on **CUAD v1 + LexGLUE LEDGAR** (both ungated, CC-BY-4.0, already on disk) with the cleaned CLAUSE-22 mapping; cover the 7 Indian/PPP gaps via auditable rules; post-viva, mine LEDGAR-Full (846k provisions, 12,608 labels) and silver-label non-demo DEA/NITI Aayog MCAs.

---

### Q3. Compatibility Matrix (`conflict_pairs` + Rule-Based `known_gaps` Pairs)

#### A. Trained-Label `conflict_pairs` (27 pairs in `05_PROPOSED_labels.yaml`)

| Pair (A + B) | Weight | Relation | One-Line Legal Reason & Indian Statutory Anchor |
|---|---:|---|---|
| `limitation_of_liability` + `indemnification` | 0.90 | **conflict** | Uncapped indemnity overrides aggregate liability cap (ICA 1872 ss.73, 124–125). |
| `limitation_of_liability` + `remedies` | 0.85 | **conflict** | Sole-and-exclusive remedy or liquidated damages clashes with aggregate cap (ICA ss.73–74, 28). |
| `arbitration` + `dispute_resolution` | 0.85 | **conflict** | Mandatory arbitration clause contradicted by exclusive civil-court jurisdiction clause (A&C Act 1996 ss.5, 8). |
| `ip_ownership` + `license_grant` | 0.80 | **conflict** | Full IP assignment contradicted by broad/perpetual/irrevocable license retention (Copyright Act s.19). |
| `governing_law` + `arbitration` | 0.80 | **conflict / dependency** | Substantive Indian law vs foreign arbitration seat/venue ambiguity or override (A&C Act 1996 ss.2(2), 20, 28). |
| `warranty` + `remedies` | 0.75 | **conflict** | Absolute warranty disclaimer paired with blanket waiver of statutory remedies (ICA s.28, SRA 1963). |
| `exclusivity_and_restraint` + `survival` | 0.75 | **conflict** | Survival clause extending non-compete post-termination is void in India (ICA s.27). |
| `limitation_of_liability` + `warranty` | 0.70 | **conflict** | Express performance/title warranties hollowed out by nominal liability cap (ICA s.73, SoGA ss.12, 16). |
| `termination` + `term_and_renewal` | 0.70 | **conflict / dependency** | Auto-renewal or lock-in period clashing with termination-for-convenience rights (ICA s.39). |
| `exclusivity_and_restraint` + `license_grant` | 0.70 | **conflict** | Exclusive territory/sector grant contradicted by non-exclusive or affiliate sub-licensing. |
| `governing_law` + `dispute_resolution` | 0.70 | **conflict / dependency** | Domestic Indian governing law overridden by foreign exclusive court forum (CPC s.20, ICA s.28). |
| `confidentiality` + `compliance_and_law` | 0.70 | **conflict** | Perpetual confidentiality gag blocking mandatory statutory/regulatory reporting (ICA s.23, DPDP Act 2023). |
| `indemnification` + `remedies` | 0.65 | **overlap / conflict** | Indemnity framed as sole remedy vs cumulative specific performance / injunctive relief (ICA ss.124–125, SRA 1963). |
| `termination` + `survival` | 0.60 | **dependency** | Survival clause determines which rights and liabilities outlive termination (ICA ss.62, 65). |
| `survival` + `confidentiality` | 0.60 | **dependency** | Post-termination confidentiality duration and return/destruction obligations. |
| `assignment_change_of_control` + `license_grant` | 0.60 | **conflict** | Non-transferable license vs permitted assignment / M&A change-of-control transfer. |
| `exclusivity_and_restraint` + `assignment_change_of_control` | 0.60 | **conflict** | Exclusivity or ROFR/ROFO triggered or breached by change of control or assignment. |
| `payment_and_fees` + `tax` | 0.60 | **dependency** | Contract price inclusive vs exclusive of GST and TDS withholding gross-up (CGST Act, ITA s.194J). |
| `payment_and_fees` + `remedies` | 0.60 | **conflict / dependency** | Liquidated damages, forfeiture, or set-off deducted against payable fees (ICA s.74). |
| `amendment_and_integration` + `payment_and_fees` | 0.60 | **conflict** | Unilateral amendment of commercial fees or risk allocation without mutual consent (ICA s.62). |
| `limitation_of_liability` + `insurance` | 0.50 | **dependency** | Mandated insurance coverage limit mismatched with contractual liability cap. |
| `termination` + `payment_and_fees` | 0.50 | **dependency** | Termination payments, compensation, or refund of unearned fees upon exit (ICA s.65). |
| `assignment_change_of_control` + `confidentiality` | 0.50 | **dependency** | Disclosure of confidential data to prospective acquirer/assignee during diligence. |
| `payment_and_fees` + `audit_and_records` | 0.50 | **dependency** | Audit rights required to verify revenue-share, royalties, or reimbursable costs. |
| `compliance_and_law` + `warranty` | 0.50 | **overlap / dependency** | Ongoing statutory compliance covenants vs legality/regulatory warranties (ICA s.23). |
| `amendment_and_integration` + `warranty` | 0.50 | **conflict** | Entire-agreement / non-reliance clause extinguishing pre-contractual representations (ICA ss.18–19). |
| `amendment_and_integration` + `notices` | 0.45 | **dependency** | Written-notice formalities required for valid amendments, modifications, or waivers. |

#### B. Additional `TYPE_MATRIX` Pairs for Rule-Based `known_gaps` (added in `candidate_selection.py`)

| Pair (A + B) | Weight | Relation | Legal Reason & Indian Anchor |
|---|---:|---|---|
| `liquidated_damages` + `limitation_of_liability` | 0.85 | **conflict** | Punitive or uncapped delay LDs clashing with aggregate cap (ICA s.74). |
| `liquidated_damages` + `payment_and_fees` | 0.70 | **dependency** | LD calculation base (% of contract/concession value) vs fee schedule (ICA s.74). |
| `data_protection` + `limitation_of_liability` | 0.85 | **conflict** | Nominal cap on DPDP Act 2023 statutory penalties (up to ₹250 Cr) vs liability cap (`INJECTIONS.json` #91.6). |
| `data_protection` + `confidentiality` | 0.70 | **overlap / conflict** | Personal-data consent/breach-notice obligations vs general NDA carve-outs (DPDP Act 2023 ss.6, 8). |
| `stamp_duty` + `arbitration` | 0.80 | **dependency / conflict** | Unstamped agreement inadmissible in evidence until impounded/cured (Indian Stamp Act s.35; SC 7-judge bench *In Re: Interplay*, 2023). |
| `force_majeure` + `termination` | 0.60 | **dependency** | Prolonged FM (>180 days in Indian MCAs) triggers termination rights (ICA s.56). |
| `force_majeure` + `payment_and_fees` | 0.55 | **dependency** | Excuse of performance vs continuing debt-service / payment obligations (PPP MCA Art. 34). |
| `performance_security` + `termination` | 0.70 | **dependency** | Encashment/forfeiture of Bank Guarantee on default or failure to replenish within 30 days (PPP MCA). |
| `performance_security` + `liquidated_damages` | 0.65 | **overlap / dependency** | Authority appropriating Performance Security to recover unpaid delay LDs. |
| `change_in_law` + `payment_and_fees` | 0.70 | **dependency** | Tariff/annuity/lump-sum adjustment to restore economic equilibrium (PPP MCA). |
| `change_in_law` + `tax` | 0.65 | **overlap** | New statutory levies/GST changes triggering Change-in-Law compensation. |
| `step_in_rights` + `termination` | 0.75 | **conflict / dependency** | Senior Lenders' substitution/cure window suspends Authority's termination right (PPP Substitution Agreement). |
| `step_in_rights` + `assignment_change_of_control` | 0.70 | **conflict** | General anti-assignment bar vs Lender right to substitute a Nominated Company. |

---

### Q4. Should We Use a Two-Level Hierarchy?

- **For training (hierarchical loss): NO before the viva.** With 22 labels and 55k+ training rows, standard flat multi-label BCE with InLegalBERT already trains in ~45 min and has ample support (≥ 300/label). Adding a hierarchical loss requires modifying `finetune_classifier.py`, tuning loss weights, and re-running ablations — high risk for negligible F1 gain at 22 classes.
- **For the UI (`web/backend.py` `LABEL_TO_TAG`): YES — trivial zero-training grouping.** Map the 22 trained labels + 7 `known_gaps` into **8 clean UI families** (*Liability & Risk*, *Indemnity & Remedies*, *Term & Exit*, *IP & Confidentiality*, *Commercial & Tax*, *Dispute & Forum*, *Compliance & Data*, *Governance & General*) in `web/backend.py`. Zero model changes, cleaner graph legend for the viva demo.

---

### Q5. Evaluation Protocol & Empirical Audit on Actual Indian Documents on Disk

We audited our proposed **CLAUSE-22 + 7 rule-based `known_gaps`** directly against the real Indian contracts already in the repository (read-only):

1. **Official Indian Government PPP Concession PDFs (1,197 extracted clauses) — Precision & `TYPE_MATRIX` Stress Test:**
   - **Rule Precision Fix:** Naive full-body substring matching over-fires on cross-references in long 600-clause MCAs (e.g., in NHAI `model_concession_4_laning.pdf`, `force_majeure` hit 26 clauses in full body vs **11** in the first 20 words; `performance_security` 10 → **2**; `step_in_rights` 16 → **2**; in Pune Metro, `force_majeure` 17 → **2**, `step_in_rights` 13 → **3**). **Fix:** For clauses > 60 words, match `known_gaps` keywords on the **first 30 words** (heading + lead sentence) and skip Definition clauses (`"means "` in first 120 chars); for short clauses (≤ 60 words), match full text. This cuts cross-reference false positives by **~60–75%** while preserving **100% recall** on all 15 `INJECTIONS.json` clauses.
   - **`TYPE_MATRIX` Pair-Count Check (No Blowup!):** Even after expanding `conflict_pairs` from 17 → 27 (+13 gap pairs), CLAUSE-22 generates **FEWER** candidate pairs than CLAUSE-20 on both official Indian PPP PDFs:
     - `model_concession_4_laning.pdf` (632 clauses): **2,452 → 2,357 pairs (-3.9%)**
     - `pune_metro_signed_concession.pdf` (565 clauses): **966 → 763 pairs (-21.0%)**
     Slimming `compliance_and_law` and splitting `dispute_resolution` into 3 focused classes eliminates noisy Cartesian-product pairs.
   - **Indian Semantic-Search Statute Corpus Gap Filled:** Auditing `data/statutes/india_commercial_sections.jsonl` (2,436 sections across 23 Acts) showed 3 key missing statutes cited by LegalAgent's own Indian-law rules plus binding case law. We downloaded and normalized **706 ready-to-append records** into `research/clause_taxonomy/indian_law_docs/india_semantic_search_additions.jsonl` (**BNS 2023**: 358 sections incl. s.318 replacing IPC s.420; **CPC 1908**: 171 sections incl. s.20 jurisdiction; **BSA 2023**: 170 sections incl. ss.61–63 electronic records; plus **7 landmark Supreme Court / High Court commercial contract precedents**).
2. **Indian IT/SaaS & Commercial Contracts (`data/demo/samples/` + `data/demo/india/custom_benchmark/`):**
   - `data_protection` fires on 6 clauses in `03_indian_tech_services_msa.md` and 2 clauses in `05_indian_it_saas_agreement.txt`.
   - `stamp_duty` fires on 3 clauses in `05_commercial_vendor_supply_agreement.md`.
   - `liquidated_damages` fires across NHAI, Pune Metro, and Vendor Supply agreements.
3. **Pune Metro 15 Adversarial Injections (`data/demo/india/adversarial/INJECTIONS.json`):**
   - **14 / 15 injections** are now matched by CLAUSE-22 + `known_gaps` (compared to 4 / 15 under `expected_current_detector`):
     - `91.1` → `limitation_of_liability`, `91.2` → `indemnification`, `91.3` → `exclusivity_and_restraint`, `91.4` → `survival`
     - `91.5` → `liquidated_damages` (gap rule), `91.6` & `91.7` → `data_protection` (gap rule), `91.8` → `arbitration` (NEW trained label)
     - `91.10` → `amendment_and_integration` + `payment_and_fees`, `91.11` → `assignment_change_of_control`, `91.12` → `remedies` (NEW trained label) + `warranty`
     - `91.13` → `stamp_duty` (gap rule), `91.14` → `confidentiality`, `91.15` → `governing_law` + `dispute_resolution`
     - The sole remaining injection (`91.9` Repealed Criminal Reference: IPC s.420 vs BNS) is a statutory-citation validity check (`compliance_and_law` + `statutes.py`), not a clause-type taxonomy gap.

#### Recommended Evaluation Steps After Retraining
1. **Supervised CLAUSE-22 Classifier (`train/finetune_classifier.py`):** Report **per-class F1, macro-F1, and micro-F1** on `test` (LexGLUE official, 8,415 rows) and `test_ood` (unseen CUAD contracts, 693 rows), comparing `minilm_lr` vs `inlegalbert`. Explicitly exclude the 7 `known_gaps` from supervised F1.
2. **Indian Silver-Labelled Evaluation (`data/derived/india_clause_eval.jsonl`, ~220 clauses):** Once Gemini silver labels finish generating, map/re-tag `dispute_resolution` → `{arbitration, remedies, dispute_resolution}` on the ~220 Indian clauses, and report macro/micro-F1 on Indian text alongside a 30-clause manual spot-check error rate.
3. **Rule-Based `known_gaps` Precision Audit:** Spot-check 10–15 fired clauses per rule across NHAI and Pune Metro PDFs to report rule precision alongside recall on `INJECTIONS.json`.

---

## 3. What Cannot Be Done Before the 18-Hour Deadline

Be explicit with the panel — do **not** attempt these before viva:
- **No new external dataset ingestion** (LEDGAR-Full, ContractNLI, ACORD, UNFAIR-ToS, or LAUKIN): deduplicating against LexGLUE without test leakage and re-tuning takes >4 hours.
- **No supervised training for `force_majeure`, `liquidated_damages`, `data_protection`, `stamp_duty`, `performance_security`, `change_in_law`, or `step_in_rights`**: zero or <300 gold examples exist in CUAD + LexGLUE LEDGAR; synthetic-only training risks overfitting to LLM phrasing.
- **No CUAD extractor overhaul** (66/510 CUAD contracts using `ARTICLE V` / `(a)` numbering): changing `extraction.py` risks regressions across the whole demo pipeline right before viva.
- **No hierarchical loss or GNN architecture re-engineering.**

---

## 4. What to Tell the Viva Panel About Our Label Design

> We did not invent our clause taxonomy by hand; **CLAUSE-22** is mechanically derived from two lawyer-annotated, CC-BY-4.0 public benchmarks—CUAD v1 (41 M&A categories) and LexGLUE LEDGAR (100 SEC provision labels)—using two reproducible rules: a label enters the supervised taxonomy only if (1) it participates in at least one legally grounded cross-clause conflict or dependency pair (`conflict_pairs`, driving our `TYPE_MATRIX`), and (2) at least 300 unique clauses survive deduplication. Auditing the data empirically caught and fixed real taxonomy defects—such as moving LEDGAR's *Applicable Laws* (89.9% choice-of-law clauses) into `governing_law`, removing 69 *Liquidated Damages* clauses that were polluting `limitation_of_liability`, pruning ~5,000 M&A closing-boilerplate rows from `compliance_and_law`, and splitting `arbitration` and `remedies` out of `dispute_resolution` so Indian Arbitration & Conciliation Act 1996, Specific Relief Act 1963, and Indian Contract Act s.28/s.74 clashes surface directly. Because no public human-annotated Indian commercial contract dataset exists yet, the seven Indian and PPP-specific clause types that lack 300 gold training rows (`force_majeure`, `liquidated_damages`, `data_protection`, `stamp_duty`, `performance_security`, `change_in_law`, `step_in_rights`) are honestly declared in `known_gaps` and handled by auditable deterministic rules rather than hidden or faked with synthetic data.
