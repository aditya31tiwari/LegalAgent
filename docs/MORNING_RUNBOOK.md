# Morning runbook (you alone, 1–2 hours, no Claude)

Everything runs on the laptop in `~/Projects/LegalAgent/LegalAgent`. Copy-paste one block at a
time. If something looks wrong, the "If it went wrong" section has the exact undo.

## 0. Before you start (2 min)
```bash
cd ~/Projects/LegalAgent/LegalAgent
git status --short | head        # a few lines is normal
nvidia-smi                       # GPU visible?
```

## 1. Did the overnight run work? (5 min)
```bash
tail -n 25 logs/overnight.log
```
Look for, in order:
- `train exit=0` → Kev v3 trained. (`exit=1/2` = failed; go to step 4B.)
- `selected: <judge>` → which judge won on the independent tests.
- `committed …` and `== overnight done` → results are saved in git.

Then see the comparison that decided it:
```bash
venv/bin/python scripts/select_judge.py
```
It prints every judge with **checklist accuracy** (bad pairs caught + fixed pairs cleared) and
**CUAD lawyer-pair recall**. The top line is what the demo now serves.

## 2. Start the demo (3 min)
```bash
bash scripts/start_demo.sh
```
It prints the selected judge, starts Kev on :8008, the dashboard on :8080 and opens the Workbench
window. Then in the browser on the laptop:
- `http://localhost:8080/app` — dashboard
- `http://localhost:8080/scores` — under the hood

5-minute click-through (all must work):
1. `/app` → pick *Pune Metro — 15 planted irregularities* → findings list + graph render.
2. *Run Live Analysis* → upload `data/demo/india/adversarial/pune_metro_adversarial_15_changes.pdf`,
   judge = *Local Kev* → stages stream → findings appear (OCR is cached, ~1 min total).
3. `/scores` → **Document → clauses**: page image + highlighted clauses + tree.
4. `/scores` → **Clause-pair scores**: pick a contract and clause → bar chart.
5. `/scores` → **Finding explained**: Kev's probability bars + statute table.
6. `/scores` → **Results**: charts appear.
7. Workbench window → Playground → *Run every method* (example "cap").

Terminal playground (good fallback to show the panel):
```bash
venv/bin/python scripts/playground.py --example cap
venv/bin/python scripts/playground.py --example clean
```

## 3. Update the numbers in the report (30–45 min)
```bash
less results/REPORT_TABLES.md      # every table, regenerated from results/*.json
less docs/REPORT_CHANGES.md        # what to change in the .docx, section by section
```
Copy numbers **only** from `results/REPORT_TABLES.md`. If overnight changed the judge, the
"Pair judges", "Checklist", "CUAD" and "Litigated" tables have a new row for v3.

## 4. Push (2 min)
```bash
git log --oneline -3               # top line should be the overnight commit
git push origin final
```

### 4B. If it went wrong
- **v3 failed / worse**: nothing to do — `select_judge.py` keeps the previous best (base Kev or v2).
  Just run `bash scripts/start_demo.sh`.
- **Demo shows nothing / errors**: `bash scripts/start_demo.sh stop; bash scripts/start_demo.sh`
  and look at `logs/web.log`.
- **Kev won't start**: the dashboard falls back to the rules judge automatically; in the upload
  dialog choose *Deterministic rules*. Say so honestly if asked.
- **Want last night's (23:00) state back exactly**:
  ```bash
  git log --oneline -6                      # find the commit before "overnight: …"
  git checkout <that-hash> -- results/judge_selection.json
  bash scripts/start_demo.sh stop; bash scripts/start_demo.sh
  ```

## 5. Rehearse (remaining time)
- `docs/DEMO_GUIDE.md` — the 8–10 minute script.
- `docs/VIVA_NOTES.md` — likely questions and answers.
- `docs/EVALUATION.md` — what each number means and its limits.

## Watching a long job (any time)
```bash
bash scripts/watch_kev.sh          # Kev training progress / ETA / GPU; beeps when done
tail -f logs/overnight.log
```
