# Prompt for the research session

Copy everything below the line into a new Claude Code session (working dir: this repo on the
laptop, or any folder with SSH access to `aryan@192.168.1.10`).

---

You are doing focused research for **LegalAgent**, a B.Tech major project (JIIT Noida) that
detects cross-clause risks in contracts (e.g. an indemnity that escapes a liability cap) with a
focus on **Indian** commercial contracts. The viva is in ~18 hours; I need your results in
**≤ 3 hours** so we can retrain the classifier (~45 min on an RTX 4050).

The repo is at `/home/aryan/Projects/LegalAgent/LegalAgent` on `aryan@192.168.1.10`
(SSH works without a password; branch `final`; Python venv at `venv/`). **Do not modify code,
data, or git state** — another session is actively training models and editing code. Only write
files inside `research/clause_taxonomy/`.

1. Read `research/clause_taxonomy/01_REQUIREMENTS.md` (the brief: constraints, questions,
   deliverables) and `02_EXISTING_STATE.md` (what exists today, with numbers). Then read
   `clause20/labels.yaml`, `clause20/label_map.yaml`, `clause20/build.py` (skim),
   `legalagent/core/classification.py`, `legalagent/core/analysis.py`,
   `legalagent/core/candidate_selection.py`, and `docs/CUAD.md`.
2. Research on the web: legal clause taxonomies and datasets (CUAD, LEDGAR full & LexGLUE,
   ContractNLI, MAUD, ACORD, CLAUDETTE/unfair-ToS, LegalBench clause tasks, any Indian contract
   or clause datasets, Indian PPP model concession agreements), and what Indian contract
   review practice checks (ICA 1872 ss.23/27/73/74/124-125, SRA 1963, A&C Act 1996, Stamp Act,
   DPDP 2023, force majeure / change in law in Indian PPP contracts). Verify every dataset
   claim (HF id/URL, licence, gated or not, size). Prefer primary sources; cite URLs.
3. You may run **read-only** analysis on the laptop to measure things (e.g. count how many CUAD
   highlights or LEDGAR rows would fall into a proposed new label, by reading
   `clause20/data/interim/*.csv` or `clause20/data/CLAUSE20.csv` with pandas in `venv/`).
   Do not run training, do not touch the GPU (it is busy), do not write outside
   `research/clause_taxonomy/`.
4. Produce the five deliverables listed in `01_REQUIREMENTS.md` (`04_FINDINGS.md`,
   `05_PROPOSED_labels.yaml`, `06_PROPOSED_label_map.yaml`, `07_DATASETS.md`,
   `08_MIGRATION.md`). The two yaml files must be drop-in valid: same schema as the current
   files; every CUAD and LEDGAR source label still mapped; every non-`other` label appears in
   at least one `conflict_pairs` entry; each label you keep must have ≥ 300 rows after the
   build's dedup **or** be explicitly marked rule-based/silver in `known_gaps` with how it is
   detected. Validate the yaml by loading it with `venv/bin/python -c "import yaml; ..."` and
   by running the counting check from step 3 against your proposed mapping.
5. Be decisive: give one recommended taxonomy (not a menu), rank changes by value/effort, and
   state plainly what cannot be done before the deadline. End `04_FINDINGS.md` with a
   one-paragraph "what to tell the viva panel about our label design" summary.
