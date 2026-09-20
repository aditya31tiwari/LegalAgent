# 01 - Legal & Statutory Research: Indian Commercial Law

## 1. Overview
This document compiles the exhaustive legal research governing commercial agreements in India, establishing the exact statutory basis for our rule engine, clause classification, and conflict detection system.

---

## 2. Fundamental Statutory Prohibitions (Indian Contract Act, 1872)

Unlike US/Delaware jurisdictions where covenants in restraint of trade are assessed under a "reasonableness" balancing test, Indian contract law is strictly codal.

### 2.1 Section 27 — Agreements in Restraint of Trade Void
> *"Every agreement by which any one is restrained from exercising a lawful profession, trade or business of any kind, is to that extent void."*

* **Statutory Rule:** All post-termination non-compete clauses (whether in employment, consulting, or vendor agreements) are **void *ab initio***.
* **Key Precedents:**
  * *Percept D'Mark (India) (P) Ltd. v. Zaheer Khan (2006) 4 SCC 227*: The Supreme Court held that the doctrine of restraint of trade applies to all post-contract covenants, and Indian courts will not enforce post-termination non-competes regardless of how limited in geography or time.
  * *Niranjan Shankar Golikari v. Century Spg. & Mfg. Co. Ltd. (1967) 2 SCR 378*: Negative covenants operating *during* the term of the contract are generally valid, but extinguish immediately upon termination.
* **Sole Statutory Exception:** Sale of Goodwill (where a party sells business goodwill and covenants not to carry on a similar business within specified local reasonable limits).
* **Impact on LegalAgent:**
  * Target pair: `("non_compete", "survival")` or `("non_compete", "governing_law_india")`.
  * Detection rule: If an agreement contains a covenant barring competitive activity post-termination under Indian governing law, flag as **High Severity — Statutory Voidness under Section 27**.

---

### 2.2 Sections 73 & 74 — Liquidated Damages vs. Penalties
* **Section 73 (Unliquidated Damages):** Compensation for loss or damage caused by breach of contract; must be natural and direct, not remote or indirect.
* **Section 74 (Liquidated Damages):**
  * India does not follow the rigid English common-law distinction between liquidated damages and penalties.
  * Even if a contract specifies a sum payable upon breach, the court awards only **"reasonable compensation not exceeding the amount so named"**.
  * *Kailash Nath Associates v. DDA (2015) 4 SCC 136*: Proof of actual damage is not dispensed with unless it is impossible or difficult to prove. A stipulated sum operates only as a statutory ceiling, never an automatic windfall.
* **Impact on LegalAgent:**
  * Target pair: `("liquidated_damages", "limitation_of_liability")` or arbitrary fee forfeiture clauses.
  * Detection rule: Flag clauses imposing punitive sums or unconditional deposit forfeitures without requiring proof of loss as **Medium/High Severity — Vulnerable under Section 74**.

---

### 2.3 Sections 124 & 125 — Indemnity vs. Damages
* **Section 124 (Definition):** A contract by which one party promises to save the other from loss caused by the conduct of the promisor or third party.
* **Key Distinction:** Unlike damages under Section 73 (which require actual accrued loss), Indian courts (*Gajanan Moreshwar v. Moreshwar Madan, AIR 1942 Bom 302*) hold that an indemnity holder is entitled to be indemnified once liability becomes absolute, even before making payment out-of-pocket.
* **Impact on LegalAgent:**
  * Target pair: `("indemnification", "limitation_of_liability")`.
  * Detect whether the limitation of liability clause improperly caps indemnity obligations or restricts indemnification to "actual paid losses" contrary to Indian judicial interpretation.

---

## 3. The 2023–2024 Legal Overhaul

### 3.1 Bharatiya Sakshya Adhiniyam (BSA), 2023 — Digital Contracts & Evidence
* Replaced the Indian Evidence Act, 1872 on **July 1, 2024**.
* **Sections 61 to 63:** Elevates electronic records to primary evidence when proper hash validation, system metadata, and digital signature criteria are fulfilled.
* **Impact on LegalAgent:**
  * Scan counterpart execution, e-signatures, and clickwrap clauses.
  * Ensure digital execution mechanisms cite valid Information Technology Act, 2000 (Certifying Authorities) and BSA standards.

### 3.2 Digital Personal Data Protection Act (DPDPA), 2023 & Rules
* Imposes statutory obligations on **Data Fiduciaries** and **Data Processors**.
* **Statutory Fines:** Penalties up to **₹250 Crore** for significant non-compliance.
* **Non-Waivability:** Parties cannot contractually contract out of statutory duties (e.g. data breach intimation, data principal consent revocation).
* **Impact on LegalAgent:**
  * Detect attempts by vendor/processor to cap liability for DPDPA statutory penalties.
  * Flag data processing clauses lacking statutory data principal grievance redressal mechanisms.

### 3.3 The Mediation Act, 2023
* Institutionalizes pre-litigation commercial mediation.
* Section 27: Mediated Settlement Agreements (MSAs) have the status of a decree of the court.
* **Impact on LegalAgent:**
  * Audit dispute resolution escalation clauses (`"dispute_resolution"`).
  * Flag escalation paths that bypass mandatory pre-litigation mediation when mandated by statute.

---

## 4. Stamp Duty & Arbitration Interplay (Dec 2023 Landmark Ruling)
* **Pre-2023 Conflict:** Under *NN Global*, courts held that an unstamped contract containing an arbitration clause was void and unenforceable, stalling hundreds of arbitrations.
* **7-Judge Constitution Bench Judgment (Dec 13, 2023):**
  * *In Re: Interplay between Arbitration Agreements under the Arbitration and Conciliation Act, 1996 and the Indian Stamp Act, 1899*.
  * Held: Non-stamping or insufficient stamping is a **curable defect** under Section 35 of the Stamp Act.
  * The arbitration agreement itself is valid and separable; the issue of stamp duty is for the arbitral tribunal to resolve, not the referral court.
* **Impact on LegalAgent:**
  * Stamping clauses should be audited for state-specific schedules (e.g. Maharashtra Stamp Act, Karnataka Stamp Act) without incorrectly flagging the whole contract as void.

