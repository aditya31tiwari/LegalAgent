# How to show LegalAgent to the panel (viva day)

Two screens, one story: **the product** (dashboard in a browser) and **the engine** (Aryan's laptop
running the models and printing every pipeline stage as tables). Total ≈ 12 minutes + questions.

---

## 0. Which laptop shows what (recommendation)

| Laptop | Role | What is on its screen |
|---|---|---|
| **Aryan's laptop** (RTX 4050) | Backend: Kev on the GPU, web server, database | Terminal with `show_steps.py` (stage tables), Kev server log, `nvidia-smi`, optionally the Workbench window |
| **Your / a teammate's laptop** (or the projector laptop) | Frontend only: a browser | `http://<aryan-ip>:8080/app` and `/scores` |

**Why not everything on one laptop?** Aryan's GPU is fully used by Kev (≈3.8–5.7 GB of 6 GB). A browser with the
graph + charts on the same machine competes for RAM/CPU and the panel only ever sees one screen. Two laptops
show clearly that the model runs locally on our hardware (privacy story) while the product is just a web page.

**Network: one phone hotspot, both laptops on it.** Same LAN → plain `http://<ip>:8080`, no internet needed,
nothing public. Do **not** rely on college Wi-Fi (client isolation is common).

- If the frontend laptop cannot open the page (hotspot isolates clients): open everything on Aryan's laptop
  (browser on one half of the screen, terminal on the other). This always works.
- Cloudflare quick tunnel (public HTTPS link) is possible but needs installing `cloudflared` and internet; only
  as a last resort.

---

## 1. Morning setup (20 minutes, on Aryan's laptop)

1. Plug in the charger; turn off sleep. Connect both laptops to the same hotspot.
2. Start everything:
   ```bash
   cd ~/Projects/LegalAgent/LegalAgent
   bash scripts/start_demo.sh            # Kev on :8008 (GPU) + dashboard on :8080 (+ Workbench window)
   hostname -I                           # first address = <aryan-ip> to type on the other laptop
   ```
   Expect: `Kev judge: up` and a status line with `"kev_server":true, "statute_sections":4408`.
3. If the other laptop cannot connect: `sudo ufw allow 8080/tcp` (only if ufw is enabled).
4. On the frontend laptop open `http://<aryan-ip>:8080/app`. Click **every contract once** in the dropdown and
   open `/scores` → *Clause-pair scores* once per contract you will show (the first score computation per contract
   takes 10–30 s on CPU; afterwards it is instant).
5. Prepare the terminal on Aryan's laptop (font size up, dark theme, full screen):
   ```bash
   venv/bin/python scripts/show_steps.py data/demo/generated/supreme_court_casebook.md --rows 12 --pairs 8
   ```
   Run it once to warm up, then clear the screen. A second terminal tab: `watch -n 1 nvidia-smi`.
6. Keep `docs/final_viva_docs/LEARNING.md` (answers + glossary) and `results/REPORT_TABLES.md` open on a phone/tablet.

If something breaks: `bash scripts/start_demo.sh stop` then `bash scripts/start_demo.sh` again. The database is
already filled, so the dashboard works even if Kev is down (new uploads then fall back to the rules judge, and the
status says so).

---

## 2. The 12-minute walk-through

### ① Problem (1 min) — no screen
"Contracts fail not only because of one bad clause but because clauses interact, and because some clauses are
void under Indian law. Reviewing a 300-page concession by hand takes days. LegalAgent does two checks:
**clause ↔ clause** inside the contract and **clause ↔ Indian law**, entirely on a laptop GPU."

### ② The product: a real Indian concession (3 min) — frontend laptop, `/app`
1. Dropdown → **Pune Metro Line-3 Concession — 15 planted irregularities**. Point at the metrics bar:
   clauses, Clause ↔ Clause issues, Clause ↔ Indian law issues, high severity, and the run line
   (`judge=local, classifier=inlegalbert …`) — "this came from the pipeline, nothing is typed in".
2. Graph: "only clauses involved in a finding are drawn; red lines are clause-pair issues judged by Kev, dashed blue
   are cross-references our extractor resolved; purple borders are clauses with an Indian-law issue."
3. Click **Clause ↔ Law** → first card **Clause 91.3 (36-month post-termination non-compete)** → *Details*:
   the clause text, the retrieved **Indian Contract Act s.27** text with a confidence chip, and the Supreme Court
   precedent (Percept D'Mark v. Zaheer Khan). "The law shown is retrieved from India Code text, and every cited
   section is checked to exist."
4. Click **Clause ↔ Clause** → a pair card (e.g. 91.1 ↔ 91.2 liability cap vs indemnity) → *Details*.
5. Mention the grey **Low-confidence signals** group: "we never hide a weak signal; it is shown, labelled low."

### ③ Real ground truth: the Supreme Court casebook (2 min)
Dropdown → **Supreme Court casebook — 18 real clauses**. Each ARTICLE heading carries what the court held
(VOID / UPHELD). Show one VOID case (Superintendence v. Krishan Murgai, non-compete) flagged with
**ICA s.27**, then one UPHELD case (Niranjan Shankar Golikari) and say honestly:
"Kev catches 6 of 9 clauses the court struck down — regex rules caught 0 — but it also flags upheld clauses.
That is why every law finding carries a confidence label and the system is a reviewer's assistant, not a judge."

### ④ Live: upload a contract (2 min)
**Upload & analyse** → drop `data/demo/generated/04_executive_employment_agreement_clean.md` (or any PDF) → watch the
live progress (ingest → extract → classify → shortlist → judge → law → grounding) → it opens automatically.
For a scanned PDF say: "pages without a text layer go through Tesseract OCR in parallel and are cached."

### ⑤ The engine: every stage as tables (3 min) — Aryan's laptop terminal
```bash
venv/bin/python scripts/show_steps.py data/demo/generated/supreme_court_casebook.md --rows 12 --pairs 8
```
Press **Enter** per stage and say one line each:

| Stage | Say |
|---|---|
| 1 Ingestion | "PyMuPDF/pymupdf4llm for digital pages, Tesseract for scans; cached." |
| 2 Extraction | "Numbered clauses, parts, parent links, cross-references resolved to clause ids." |
| 3 Classification | "Our fine-tuned InLegalBERT on 22 clause types: 0.93 F1 in-domain, 0.75 out-of-domain." |
| 4 Shortlisting | "253 possible pairs → 60 by cross-refs, the clash matrix and hybrid BM25+dense retrieval." |
| 5 Kev judge | "Each pair: probabilities for every relation, a severity and a statute choice, ~0.3–0.5 s on our GPU." Point at `nvidia-smi`. |
| 6 Clause vs law | "Regex column vs Kev's probability per legal risk → Act and section, with confidence." |
| 7 Statute RAG | "Top India Code sections: BM25 + our fine-tuned InLegal-SBERT, fused, with an Act prior." |
| 8 Result | "This is what is stored in SQLite and shown in the dashboard." |

The same output is saved as `logs/steps_supreme_court_casebook.html` (open it if the terminal is hard to read).

### ⑥ All comparisons on one page (1 min) — frontend laptop, `/report`
`http://<aryan-ip>:8080/report` (static file `results/REPORT.html`, rebuild with
`venv/bin/python scripts/build_report.py`). Every table says what it tests; green = best. Scroll to:
3 (judge: Kev 71 % vs rules 46 %), 4 (law: Kev 6/9 vs regex 0/9), 5 (statute RAG), **9 (Kev speed: decisions/s,
tokens read/s, latency)** and **10 (end-to-end time per contract, per stage)**. Say: "Kev reads ~300 tokens and
points at an answer; it doesn't generate text, so we measure tokens read per second and decisions per second."

### ⑥b Under the hood (optional) — frontend laptop, `/scores`
- **Document → clauses**: pick the 305-page scanned Pune Metro PDF; show a page image next to its OCR'd clauses.
- **Clause-pair scores**: BM25 / dense / GNN / type-matrix scores behind the shortlist for one clause.
- **Finding explained**: every number behind one finding (Kev probabilities, retrieval scores).
- **Results**: the evaluation charts. Close with the summary table below.

---

## 3. Numbers to say (from `results/REPORT_TABLES.md`)

| What | Number |
|---|---|
| Clause classifier (InLegalBERT, CLAUSE-22) | micro-F1 0.931 test, 0.750 out-of-domain (MiniLM baseline 0.828 / 0.590) |
| Pair judge on our bad/fixed checklist | Kev 71 % vs rules 46 % |
| Pair judge recall on lawyer-annotated CUAD pairs | Kev 75 % vs rules 7.5 % |
| Clause vs law on Supreme Court struck-down clauses | Kev 6/9 vs regex 0/9 |
| Statute retrieval, exact section in top 5 | 0.32 (BM25 0.11) |
| Statute library | 4,408 sections from 37 Acts |
| Teacher (Gemini 4) checked against independent truth | 92.9 % checklist, 85.7 % real citations |
| Cost / privacy | ₹0 per contract, nothing leaves the laptop |

## 4. If asked "is it finished?"
Yes — it is a working end-to-end system: any PDF/DOCX/TXT goes in, findings come out, stored and browsable, with
every stage measured. What is *not* done is lawyer-verified training data for Indian clause pairs; that is the
honest limitation and the first item of future work (see `docs/final_viva_docs/FINAL_REPORT.md` §6).

## 5. Fallbacks
| Problem | Do |
|---|---|
| Frontend laptop can't reach Aryan's IP | Show everything on Aryan's laptop |
| Kev down / GPU error | `bash scripts/start_demo.sh stop && bash scripts/start_demo.sh`; the stored results still show |
| Upload slow (big scanned PDF) | Use the employment agreement sample; say the 305-page scan is already analysed (contract in the list) |
| `/scores` first load slow | It is computing on CPU; switch to another tab and come back |
| Projector only takes one laptop | Project the frontend laptop; turn Aryan's laptop to the panel for stage ⑤ |
