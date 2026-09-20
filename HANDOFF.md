# LegalAgent — Developer & Agent Handoff Guide

## 1. Project Status Summary

- **Web Frontend**: Fully redesigned, committed, and pushed to `origin/aryan-sethi` ([`fb231cf`](https://github.com/aditya31tiwari/LegalAgent/commit/fb231cf2c1aa05b4e7a9ecc325e7d5739e6a0efe)).
  - [`web/landing.html`](file:///home/aryan/Projects/LegalAgent/LegalAgent/web/landing.html): Editorial-style legaltech landing page introducing platform features, Indian statutory compliance focus, 4-step pipeline, and tech stack.
  - [`web/index.html`](file:///home/aryan/Projects/LegalAgent/LegalAgent/web/index.html): Classy 3-panel contract intelligence dashboard (resizable panels, expandable clause cards, complete contract reading modal, edge-click to finding highlight, optimized Vis.js graph physics).
- **Backend & Database**: Fully working and tested locally, uncommitted as requested (`web/backend.py`, `web/server.py`, `legalagent/db.py`, `contracts.db`).
- **Research & Model Architecture**: Complete documentation in `research/`, including [`research/06_FINE_TUNING_AND_TEMPORAL_MODEL_PLAN.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/research/06_FINE_TUNING_AND_TEMPORAL_MODEL_PLAN.md) detailing the LoRA/QLoRA multi-adapter strategy for Indian legal datasets (open-india-law, KanoonGPT, etc.) and temporal era conflict detection (BNS 2023, DPDPA, IBC).

---

## 2. Git & Repository Status

- **Current Branch**: `aryan-sethi` (up to date with `origin/aryan-sethi`).
- **Main Branch**: `main` (clean and in sync with `origin/main`).
- **Configured Git Identity**:
  - Name: `Aryan Sethi`
  - Email: `aryan1024sethi@gmail.com`
  - GitHub Username: `PoopApple`
- **Remote**: `https://github.com/aditya31tiwari/LegalAgent.git`
- **Push Status**: Successfully pushed commit `fb231cf` to `origin/aryan-sethi`.
- **Pull Request**: Ready to open a PR on GitHub from `aryan-sethi` into `main`:
  [Compare & Pull Request on GitHub](https://github.com/aditya31tiwari/LegalAgent/compare/main...aryan-sethi)

---

## 3. Working Directory File Status

| File | Status | Description |
|:-----|:------:|:------------|
| `web/index.html` | Pushed (`fb231cf`) | Redesigned legal dashboard (664 lines) |
| `web/landing.html` | Pushed (`fb231cf`) | Editorial landing page |
| `web/backend.py` | Untracked | FastAPI REST backend with endpoints for analysis, export, and contract graphs |
| `web/server.py` | Untracked | Uvicorn entry point (port 8080) |
| `legalagent/db.py` | Untracked | SQLite schema, seed data, queries |
| `contracts.db` | Untracked | Seeded SQLite database (4 contracts) |
| `scripts/download_models.py` | Untracked | Model verification script |
| `research/` | Untracked | 8 Markdown research & specification documents |
| `CONTEXT.md` | Untracked | Architecture and system context document |
| `HANDOFF.md` | Untracked | This handoff guide |
| `.gitignore` | Modified | Added `.agents/` and `graphify-out/` exclusions |

---

## 4. How to Run & Verify

### Starting the Server
```bash
/home/aryan/Projects/LegalAgent/LegalAgent/venv/bin/python web/server.py
```

### Available URLs
- **Landing Page**: [http://localhost:8080/](http://localhost:8080/)
- **Dashboard Workspace**: [http://localhost:8080/app](http://localhost:8080/app)
- **Interactive REST Docs**: [http://localhost:8080/docs](http://localhost:8080/docs)

### Testing API Endpoints
```bash
/home/aryan/Projects/LegalAgent/LegalAgent/venv/bin/python -c "
import urllib.request, json
res = urllib.request.urlopen('http://localhost:8080/api/contracts/tech_msa')
data = json.loads(res.read())
print('Clauses:', len(data['clauses']), '| Edges:', len(data['edges']), '| Findings:', len(data['findings']))
"
```

---

## 5. Next Planned Steps

1. **Backend Integration & Commit**:
   - Review and commit the backend modules (`web/backend.py`, `web/server.py`, `legalagent/db.py`, `contracts.db`).
2. **Implement Temporal Legal Engine** (per `06_FINE_TUNING_AND_TEMPORAL_MODEL_PLAN.md`):
   - Build the IPC → BNS statutory mapping table (e.g. IPC Section 420 $\rightarrow$ BNS Section 318; IPC 406 $\rightarrow$ BNS 316).
   - Add era classification and automated detection of repealed statute references in contracts uploaded post-1 July 2024.
3. **Training & Fine-Tuning Pipeline**:
   - Implement `scripts/prepare_training_data.py` to curate `(anchor, positive)` and `(clause_A, clause_B, conflict_label)` pairs from CUAD and open Indian legal text datasets.
   - Configure QLoRA training loop on the local RTX 4050 6GB (`r=16`, `alpha=32`, batch size 2, gradient accumulation 16) using `sentence-transformers` v3+ and `peft`.
4. **Assessment Panel Demo Preparation**:
   - Rehearse live demo walkthrough showing:
     1. Portfolio contract selection (Tech MSA liability clash, NDA Section 27 void non-compete).
     2. Graph interaction (clicking edges to highlight right-panel statutory findings).
     3. "View Full" contract sequential view.
     4. Custom contract text paste & live graph extraction.
     5. Exporting executive audit memorandum.

---

## 6. Critical Rules & Environment Constraints

- **Python Environment**: The system Python 3.14 lacks pip/venv. ALWAYS use `/home/aryan/Projects/LegalAgent/LegalAgent/venv/bin/python`.
- **Network Restrictions**: Sandbox has restricted external network access. Package installations or model downloads require approved commands.
- **Graphify Knowledge Graph**: Per `.agents/rules/graphify.md`, whenever code files are modified, run `graphify update .` to keep AST-based graph current.
- **Design Constraints**:
  - No neon or glowing colors.
  - No `§` symbol (use "Section" or "Clause").
  - Maintain the classy, muted editorial legal palette (Navy `#1a2332`, Ivory `#f5f3ef`, Off-white `#fafaf8`, Copper `#9a7b4f`).
