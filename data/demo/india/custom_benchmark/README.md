# Custom Indian-Law Benchmark

These are synthetic contracts created for the prototype, not real legal agreements. Each file contains planted irregularities documented in `MANIFEST.json`:

- `01_msa_cap_indemnity.txt`: aggregate liability cap versus uncapped indemnity.
- `02_employment_non_compete.txt`: post-termination non-compete and survival dependency.
- `03_clean_services_control.txt`: clean control with no planted risk.

Run the benchmark with:

```bash
venv/bin/python scripts/run_custom_benchmark.py
```