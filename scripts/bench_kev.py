#!/bin/sh
"exec" "$(dirname "$0")/../venv/bin/python" "$0" "$@"
"""
Kev throughput on our laptop GPU (RTX 4050, 6 GB).

Kev is a decision model: it READS the state (clauses + question) and points at one of the given options;
it does not write text. So the speed that matters is input tokens read per second and decisions per second.

    venv/bin/python scripts/bench_kev.py            # needs the Kev server on :8008
    -> results/kev_throughput.json
"""
import json
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from legalagent.core import local_judge as lj
from legalagent.core import statutory_kev as sk


def requests_from_checklist(n=24):
    rows = [json.loads(l) for l in (ROOT / "research/teacher_labels/checklist_pairs.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    from legalagent.core.types import Clause
    out = []
    for r in rows[:n]:
        a = Clause(id="a", contract_id="b", number="A", text=r["a_text"])
        b = Clause(id="b", contract_id="b", number="B", text=r["b_text"])
        out.append(("pair", lj.pair_request(a, b, ["bench"], [])))
        out.append(("clause_vs_law", sk.request(r["a_text"])))
    return out


def run(reqs, workers):
    lat, tok, state = [], 0, 0

    def one(x):
        t = time.perf_counter()
        r = lj._post(x[1])
        return (time.perf_counter() - t) * 1000, r.get("usage", {})

    t0 = time.perf_counter()
    with ThreadPoolExecutor(workers) as pool:
        for ms, u in pool.map(one, reqs):
            lat.append(ms)
            tok += int(u.get("input_tokens", 0))
            state += int(u.get("state_tokens", 0))
    wall = time.perf_counter() - t0
    lat.sort()
    return {"workers": workers, "requests": len(reqs), "wall_s": round(wall, 2),
            "decisions_per_s": round(len(reqs) / wall, 2),
            "input_tokens_per_s": round(tok / wall), "avg_input_tokens": round(tok / len(reqs)),
            "latency_ms_p50": round(statistics.median(lat), 1), "latency_ms_p95": round(lat[int(0.95 * (len(lat) - 1))], 1)}


def main():
    if not lj.available():
        sys.exit("Kev server not running on :8008 (bash scripts/start_demo.sh)")
    reqs = requests_from_checklist()
    lj._post(reqs[0][1])  # warm-up
    out = {"gpu": "RTX 4050 Laptop 6 GB", "model": "Kev-0.8B (Qwen3.5-0.8B + pointer head), bf16",
           "note": "Kev outputs a probability over the given options (no generated text); "
                   "speed = input tokens read per second and decisions per second",
           "runs": [run(reqs, 1), run(reqs, 2)]}
    try:
        import subprocess
        out["gpu_memory_mib"] = int(subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"]).decode().split()[0])
    except Exception:
        pass
    p = ROOT / "results" / "kev_throughput.json"
    p.write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
