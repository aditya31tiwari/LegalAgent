# LegalAgent — Panelist Demo Guide & Manual Review Manual

> **Audience**: Assessment panel presentation and exhaustive manual verification.
> **Duration**: 10–15 minutes live demo + 5 minutes Q&A.
> **Environment**: Always use `venv/bin/python` from `/home/aryan/Projects/LegalAgent/LegalAgent`.

---

## 1. Quick Verification: Clean vs Broken Samples Note

### Status of Converted PDF Samples
* **Scanned Government Source PDFs**: The official documents (`pune_metro_signed_concession.pdf` and `model_concession_4_laning.pdf`) are low-resolution scanned paper documents with physical watermarks and stamps from 2019.
* **Removal of Broken OCR Conversions**: The earlier automated `.md` conversions (`pune_metro_first_20_pages.md`, `pune_metro_signed_concession.md`, and `model_concession_4_laning.md`) produced garbled character noise and repetitive watermarks. They have been permanently removed.
* **Pristine Verified Sample Contracts**: We have created 6 clean, verified, 100% human-legible contract instruments in `data/demo/samples/` ready for manual review, panel inspection, and live file upload.

---

## 2. Verified Sample Contracts Directory (Actual File Paths)

| # | Contract Sample | Absolute Path | Description / Planted Issues |
|---|---|---|---|
| 1 | **Pune Metro PPP (Clean Baseline)** | `/home/aryan/Projects/LegalAgent/LegalAgent/data/demo/samples/01_pune_metro_concession_baseline.md` | Clean, authentic 2019 concession agreement baseline (Articles 1 through 48) without adversarial clauses. |
| 2 | **Pune Metro PPP (15 Injections)** | `/home/aryan/Projects/LegalAgent/LegalAgent/data/demo/samples/02_pune_metro_adversarial_15_injections.md` | Authentic baseline with Article 91 (all 15 synthetic adversarial test clauses) appended for detection testing. |
| 3 | **Indian Tech Services MSA** | `/home/aryan/Projects/LegalAgent/LegalAgent/data/demo/samples/03_indian_tech_services_msa.md` | Cloud/SaaS contract with INR 15L liability cap vs uncapped IP indemnity, DPDPA 2023 cap, and Mediation Act exclusion. |
| 4 | **Executive Employment Agreement** | `/home/aryan/Projects/LegalAgent/LegalAgent/data/demo/samples/04_executive_employment_agreement.md` | Executive CTO contract with void 24-month nationwide post-termination non-compete under Section 27 ICA. |
| 5 | **Commercial Vendor Supply** | `/home/aryan/Projects/LegalAgent/LegalAgent/data/demo/samples/05_commercial_vendor_supply_agreement.md` | Procurement contract with 30% liquidated delay damages penalty (Section 74) vs 10% cap, and unstamped execution. |
| 6 | **NHAI 4-Laning Highway Concession** | `/home/aryan/Projects/LegalAgent/LegalAgent/data/demo/samples/06_nhai_highway_concession_agreement.md` | Model BOT-Toll highway concession with asymmetric termination compensation ratios (90% debt due vs 150% equity). |

### Regression Benchmark Test Contracts
* **01 MSA Cap & Indemnity**: `/home/aryan/Projects/LegalAgent/LegalAgent/data/demo/india/custom_benchmark/01_msa_cap_indemnity.txt`
* **02 Employment Non-Compete**: `/home/aryan/Projects/LegalAgent/LegalAgent/data/demo/india/custom_benchmark/02_employment_non_compete.txt`
* **03 Clean Services Control**: `/home/aryan/Projects/LegalAgent/LegalAgent/data/demo/india/custom_benchmark/03_clean_services_control.txt`
* **Benchmark Manifest**: `/home/aryan/Projects/LegalAgent/LegalAgent/data/demo/india/custom_benchmark/MANIFEST.json`
* **Adversarial Injections Register**: `/home/aryan/Projects/LegalAgent/LegalAgent/data/demo/india/adversarial/INJECTIONS.json`

---

## 3. Server Startup & Web Endpoints

### Step 0: Start the Server

```bash
cd /home/aryan/Projects/LegalAgent/LegalAgent
venv/bin/python web/server.py
```

*Expected Terminal Banner:*
```
LegalAgent Enterprise Intelligence Engine
Web Application  : http://localhost:8080/app
Injections Dossier: http://localhost:8080/injections
Product Landing  : http://localhost:8080
Swagger REST API : http://localhost:8080/docs
SQLite Database  : contracts.db
```

### URLs for Panel Demonstration
* **Interactive Dashboard**: `http://localhost:8080/app`
* **Adversarial Injections Dossier & Side-by-Side Comparator**: `http://localhost:8080/injections`
* **Landing Page**: `http://localhost:8080`
* **Interactive REST API Documentation**: `http://localhost:8080/docs`

---

## 4. Step-by-Step Panel Presentation Script

### Step 1: High-Level Overview on Landing Page (`/`)
1. Open `http://localhost:8080`.
2. **What to say**:
   > "LegalAgent is an Indian contract intelligence platform. Rather than reviewing isolated clauses with standard generative LLMs, our engine models agreements as inter-clause knowledge graphs G=(V,E). We detect cross-clause contradictions, statutory non-compliance under Indian law, and hidden risks that only emerge when two separate clauses are read together."
3. Highlight the 3 core pillars:
   * **Cross-Clause Contradiction Graph** (e.g. Liability Cap vs Uncapped Indemnity).
   * **Indian Statutory Grounding** (Indian Contract Act 1872, DPDPA 2023, Mediation Act 2023, BNS 2023, Stamp Act).
   * **InLegal-SBERT Embeddings** trained specifically on Indian judicial precedent.

### Step 2: Open Dashboard (`/app`) and Demonstrate Graph Visualization
1. Open `http://localhost:8080/app`.
2. Notice the graph canvas in the center:
   * **Spacious Radial Layout**: Nodes settle into clear, spacious orbits with comfortable clearance.
   * **Zero Interception**: Node boxes never overlap (`avoidOverlap: 1.0`, `springLength: 195px`).
   * **Curved Smooth Edges**: Directed connections curve smoothly clockwise (`type: 'curvedCW'`), eliminating straight-line collisions and overlapping lines.
3. Use the filter chips in the toolbar (`All`, `Conflicts`, `Statutory`, `Cross-Refs`). Click `Fit` to center the network.

### Step 3: Test "View Full" Whole-Contract Viewer
1. In the left panel (Clause Explorer), click the **"View Full"** button.
2. The **Full Contract Instrument Modal** opens:
   * **Formal Preamble & Parties**: Official reference ID, execution city, registered corporate offices, and party definitions.
   * **Formal Recitals**: `WHEREAS (A)...`, `(B)...`, `NOW, THEREFORE...`
   * **All Sections in Full**: Every clause is displayed in full multi-paragraph legal text with indented subsections `(a)`, `(b)`, Roman numerals `(i)`, `(ii)`, and statutory tags.
   * **Execution & Signatures**: `IN WITNESS WHEREOF...` block with signatures, authorized representatives, and witness lines.
   * **Live Keyword Search**: Type "indemnity" or "DPDPA" in the search input to instantly filter and highlight matching clauses.
   * **Copy Full Text**: Click "Copy Full Text" to copy the formatted contract to the clipboard.

### Step 4: Review Pune Metro PPP & The 15 Injections (`/injections`)
1. Switch to **"Pune Metro Line III — PPP Concession Agreement (2019)"** in the contract selector.
2. Note the health score of **15/100** and critical findings:
   * Red edge: **INR 1,000 Cap vs Unlimited Indemnity** (Sections 23, 124–125 ICA).
   * Purple edge: **Post-Termination Non-Compete** (Void ab initio under Section 27 ICA).
   * Purple edge: **DPDPA 2023 Penalty Cap** (Private cap on statutory ₹250 Crore regulatory fines).
3. Click **"Injections"** in the top navigation bar (or open `http://localhost:8080/injections`).
4. Click **"Compare Clean vs Injected Contract (Side-by-Side)"**:
   * **Left Column**: Clean authentic PMRDA 2019 concession agreement baseline across 13 complete articles.
   * **Right Column**: Adversarially modified agreement with synthetic clauses highlighted in redline boxes with statutory analysis.
   * **Article Quick-Jump Bar**: Click any article pill (`Article 41: Liability`, `Article 44: Dispute Resolution`, `Article 18: Data Governance`) to jump directly to that article in both panes.
   * **Bottom Navigator**: Use Previous / Next buttons or `Left` / `Right` arrow keys to step through Injections 1 to 15.

### Step 5: Live File Upload Demo (Showstopper!)
1. Click **"Upload / Analyze"** in the top navigation bar.
2. Choose one of two live demonstration methods:
   * **Method A (Instant Demo Button)**: Click **"Insert Sample Contract with Planted Traps"**.
   * **Method B (File Upload)**: Drag and drop `/home/aryan/Projects/LegalAgent/LegalAgent/data/demo/samples/03_indian_tech_services_msa.md` into the upload zone.
3. Click **"Run Live Analysis"**:
   * Watch the real-time Server-Sent Events (SSE) progress counter.
   * The 8 pipeline stages turn green in sequence: Ingestion -> Normalization -> Extraction -> Tagging -> Candidate Selection -> Conflict Analysis -> Statutory Audit -> Graph Storage.
4. When complete, click **"View Contract Graph"** to load the newly analyzed contract live onto the screen.

---

## 5. Command-Line Testing & Verification

### Run Automated Regression Benchmark
```bash
cd /home/aryan/Projects/LegalAgent/LegalAgent
venv/bin/python scripts/run_custom_benchmark.py
```
*Expected: 3/3 tests pass with 0 false positives on clean control.*

### Run CLI Pipeline Analysis on Any Sample
```bash
venv/bin/python -m legalagent analyse data/demo/samples/03_indian_tech_services_msa.md --contract-id tech-test --output runs/tech_test.json
cat runs/tech_test.json | grep -A 5 "findings"
```

### Verify REST API Endpoints
```bash
curl -s http://localhost:8080/api/contracts | grep -o '"id":"[^"]*"'
curl -s http://localhost:8080/api/contracts/tech_msa | grep -o '"title":"[^"]*"'
```

---

## 6. Panel Q&A Defense Summary

| Question | Strong Panel Answer |
|---|---|
| **"Is this legal advice?"** | No. It is an explainable decision-support tool. Every flag cites exact Indian statutory sections (e.g. Section 27 ICA, DPDPA 2023 Schedule 1) and landmark case law (e.g. *Kailash Nath*, *Percept D'Mark*) with auditable evidence trails. |
| **"How do you avoid $O(N^2)$ cross-clause comparison?"** | We use a two-tier filter: (1) Category compatibility matrix (only compare Liability with Indemnity, etc.); (2) BM25 keyword overlap + dense InLegal-SBERT similarity. This cuts candidate pairs by 85–92%. |
| **"Why InLegal-SBERT instead of standard BERT?"** | Standard BERT is trained on Wikipedia/general English and fails on legal vocabulary (*subrogation, indemnification, novation, force majeure*). InLegal-SBERT is pre-trained on Indian Supreme Court and High Court judgments. |
| **"What about scanned PDFs?"** | Raw paper scans require high-resolution OCR (Tesseract / EasyOCR). For digital PDFs, PyMuPDF extracts text directly with character offset tracking. |
| **"What Indian statutes are currently encoded?"** | Indian Contract Act 1872 (Sec 23, 27, 28, 62, 73, 74, 124, 125), DPDPA 2023, The Mediation Act 2023, Bharatiya Nyaya Sanhita 2023 (replacing IPC), Arbitration and Conciliation Act 1996, Maharashtra Stamp Act 1958. |
