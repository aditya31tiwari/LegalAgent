# Morning runbook (you alone, 1–2 hours, no Claude)

Everything runs on Aryan's laptop in `~/Projects/LegalAgent/LegalAgent`. The database is already filled with
real pipeline runs, results are committed and pushed (branch `final`). The morning is: **start → check → rehearse**.
How to present: [PANEL_DEMO.md](PANEL_DEMO.md).

## 0. Before you start (2 min)
```bash
cd ~/Projects/LegalAgent/LegalAgent
git log --oneline -1          # latest "final" commit
nvidia-smi                    # GPU visible (driver 595)?
```

## 1. Start (3 min)
```bash
bash scripts/start_demo.sh            # Kev on :8008 (GPU) + dashboard :8080 + Workbench window
hostname -I                           # first address = the IP for the other laptop
```
Expect `Kev judge: up` and `"kev_server":true … "statute_sections":4408`.

## 2. Ten-minute click-through (all must work)
On the frontend laptop (same hotspot): `http://<ip>:8080/…`

1. `/app` → contract list shows 10 contracts (Pune Metro excerpt, Supreme Court casebook, CUAD contract, 5 samples,
   2 full scanned PDFs). Pick each once (warms up). Filters *Clause ↔ Clause / Clause ↔ Law / Cross-refs* work,
   *Details* opens on a card.
2. `/app` → **Upload & analyse** → `data/demo/samples/04_executive_employment_agreement.md` → live stages → opens.
   **Do this once before the panel arrives**: the first upload after a restart loads the models (≈50 s);
   later uploads of a short contract take ≈15 s.
3. `/scores` → Document → clauses (pick the Pune PDF; page image shows) · Clause-pair scores (first time per
   contract 10–30 s) · Finding explained · Results.
4. `/report` → all tables visible (rebuild: `venv/bin/python scripts/build_report.py`).
5. Terminal on Aryan's laptop:
   ```bash
   venv/bin/python scripts/show_steps.py data/demo/generated/supreme_court_casebook.md --rows 12 --pairs 8
   ```
   press Enter through 8 stages.

## 3. Rehearse (rest of the time)
Nothing is changed in the morning — the project is shown exactly as committed (branch `final`).
- `PANEL_DEMO.md` walk-through twice, timed (≈12 min).
- `LEARNING.md` — likely questions + glossary + "what each table tests".
- `PROCESS.md` §4 — the failed attempts (panels like these).

## If something goes wrong
| Problem | Fix |
|---|---|
| Page doesn't load on other laptop | open everything on Aryan's laptop (`http://localhost:8080/app`) · or `sudo ufw allow 8080/tcp` |
| Kev down / "judge=rules" on uploads | `bash scripts/start_demo.sh stop; bash scripts/start_demo.sh` — stored results still show meanwhile |
| GPU out of memory in `/tmp/kev_demo_serve.log` | same restart; close anything else using the GPU (`nvidia-smi`) |
| Database looks wrong / empty | `git checkout origin/final -- contracts.db` then restart (the committed database has all 10 contracts) |
| Need exact pushed state back | `git fetch origin; git checkout origin/final -- .` then restart |

**Do not** run `scripts/overnight.sh`, `seed_demo.py` or any training: the demo is shown as committed.
