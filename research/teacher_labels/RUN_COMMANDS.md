# Teacher labelling — commands to run

Run these in **your own laptop terminal** (the one where `agy` is signed in). Copy-paste one at a time.

## 1. Smoke test (20 pairs, 1–3 min)

```bash
cd ~/Projects/LegalAgent/LegalAgent && bash research/teacher_labels/run_teacher.sh smoke
```

Wait for the line starting with `done:`, then tell Claude. Claude checks the 20 labels before the full run.

## 2. Full run (2,522 pairs, ~30–60 min, keep the terminal open)

```bash
cd ~/Projects/LegalAgent/LegalAgent && bash research/teacher_labels/run_teacher.sh full
```

If it stops for any reason, run the same command again; it resumes where it left off.

## 3. Optional: second teacher for agreement (300 pairs, another model family)

Can run at the same time as step 2, in a second terminal tab:

```bash
cd ~/Projects/LegalAgent/LegalAgent && bash research/teacher_labels/run_teacher.sh second
```

## Models

- Primary teacher: `gemini-4-hydrogen-high` (Gemini 4 Hydrogen, high effort)
- Second opinion: `claude-sonnet-5-5-medium` (different model family, used only for inter-annotator agreement)
- Full list: `/tmp/agymodel` (output of `agy models`)

Output files: `research/teacher_labels/labels/agy_<model>.jsonl`
