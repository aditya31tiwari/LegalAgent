"""
Label exported clause pairs with the Antigravity CLI (agy) as the teacher model.

    venv/bin/python scripts/label_with_agy.py --model "<name from `agy models`>" --workers 3
    venv/bin/python scripts/build_judge_set.py import-labels --teacher antigravity-<model>

Reads   research/teacher_labels/pairs_to_label.jsonl     (scripts/build_judge_set.py pairs --export)
Writes  research/teacher_labels/labels/agy_<model>.jsonl (append-only; resumable)

Each call: `agy -p` (non-interactive print mode) with --json-schema enforcing the output,
--mode plan and an empty working directory, so the agent has nothing to edit and needs no
tools: the clause text is inside the prompt. Labelling rules are the same text the human-
facing PROMPT.md gives (relation / severity / risk / rationale / Indian citation).
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "research" / "teacher_labels"
AGY = shutil.which("agy") or str(Path.home() / ".local" / "bin" / "agy")

SCHEMA = {
    "type": "object",
    "properties": {
        "labels": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "pair_id": {"type": "string"},
                    "relation": {"type": "string", "enum": ["conflict", "dependency", "overlap", "ambiguity", "no_issue"]},
                    "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                    "risk": {"type": "number"},
                    "rationale": {"type": "string"},
                    "citation": {"type": "string"},
                    "a_types": {"type": "array", "items": {"type": "string"}},
                    "b_types": {"type": "array", "items": {"type": "string"}},
                    "fix_clause": {"type": "string", "enum": ["a", "b", "both", "none"]},
                    "suggested_fix": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
                },
                "required": ["pair_id", "relation", "severity", "risk", "rationale", "citation",
                             "a_types", "b_types", "fix_clause", "suggested_fix", "confidence"],
            },
        }
    },
    "required": ["labels"],
}


def rules_text() -> str:
    """The labelling rules section of PROMPT.md (single source of truth)."""
    text = (SRC / "PROMPT.md").read_text(encoding="utf-8")
    start = text.index("3. For each pair")
    end = text.index("4. Append one JSON")
    quality = text[text.index("## Quality bar"):]
    return text[start:end] + "\n" + quality


def build_prompt(batch: list[dict], rules: str) -> str:
    items = "\n\n".join(
        f"### {p['pair_id']}\nWhy shortlisted: {', '.join(p['surfaced_by'])}\n"
        f"Clause A (predicted types: {', '.join(p['a_labels']) or 'none'}):\n{p['a_text']}\n\n"
        f"Clause B (predicted types: {', '.join(p['b_labels']) or 'none'}):\n{p['b_text']}"
        for p in batch)
    return (
        "You are labelling clause pairs from commercial contracts as a teacher for a small "
        "on-device model (Indian contract review). Do not use any tools; answer from the text below.\n\n"
        f"{rules}\n\n"
        "Also, for every pair:\n"
        f"- a_types / b_types: the clause types of A and of B from this list (1-3 each, 'other' if none fits): {', '.join(clause_types())}\n"
        "- fix_clause: which clause a reviewer should amend to resolve the issue ('a', 'b' or 'both'; 'none' for no_issue)\n"
        "- suggested_fix: one sentence of replacement or added wording ('' for no_issue)\n"
        "- confidence: how sure you are of the relation label (low | medium | high)\n\n"
        f"Label every one of these {len(batch)} pairs and return JSON "
        '{"labels": [{"pair_id", "relation", "severity", "risk", "rationale", "citation", "a_types", "b_types", '
        '"fix_clause", "suggested_fix", "confidence"}, ...]} with exactly one entry per pair_id.\n\n' + items)


def clause_types() -> list[str]:
    import yaml
    spec = yaml.safe_load((ROOT / "clause20" / "labels.yaml").read_text(encoding="utf-8"))
    return [*spec["labels"], *spec.get("known_gaps", [])]


TYPES_SCHEMA = {
    "type": "object",
    "properties": {"items": {"type": "array", "items": {"type": "object", "properties": {
        "clause_id": {"type": "string"}, "types": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]}},
        "required": ["clause_id", "types", "confidence"]}}},
    "required": ["items"],
}


def types_prompt(batch: list[dict]) -> str:
    items = "\n\n".join(f"### {c['clause_id']}\n{c['text'][:1500]}" for c in batch)
    return ("You label clauses from contracts (many are Indian government concession / PPP agreements, some OCR'd) "
            "with clause types. Do not use tools. Allowed types: " + ", ".join(clause_types()) + ".\n"
            "Give every type that applies (usually 1, at most 3); 'other' only if none fits. Definitions-only or "
            "unreadable clauses: ['other'].\nReturn JSON {\"items\": [{\"clause_id\", \"types\", \"confidence\"}]} "
            f"with exactly one item per clause_id ({len(batch)} clauses).\n\n" + items)


def indian_clauses() -> list[dict]:
    """Every distinct Indian clause we evaluate on: the india_clause_eval set + both sides of Indian pairs."""
    seen, out = set(), []
    p = ROOT / "data" / "derived" / "india_clause_eval.jsonl"
    rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.exists() else []
    for r in rows:
        if r["id"] not in seen:
            seen.add(r["id"]); out.append({"clause_id": r["id"], "text": r["text"]})
    for l in (SRC / "pairs_to_label.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(l)
        if not r["contract"].startswith("india:"):
            continue
        for cid, txt in ((r["a_id"], r["a_text"]), (r["b_id"], r["b_text"])):
            if cid not in seen:
                seen.add(cid); out.append({"clause_id": cid, "text": txt})
    return out


HEARTBEAT_S = 15
VERBOSE = False
# Errors that will not fix themselves by retrying the next batch.
QUOTA_RE = re.compile(r"quota|rate.?limit|resource.?exhausted|\b429\b|too many requests|usage limit|exceeded|limit reached", re.I)


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def call_agy(prompt: str, model: str | None, schema_path: str, workdir: str, timeout: int, effort: str | None = None,
             tag: str = "") -> dict:
    cmd = [AGY, "-p", prompt, "--output-format", "json", "--json-schema", schema_path, "--mode", "plan",
           "--print-timeout", f"{timeout}s"]
    if model:
        cmd += ["--model", model]
    if effort:
        cmd += ["--effort", effort]
    proc = subprocess.Popen(cmd, cwd=workdir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    t0 = time.time()
    while True:  # heartbeat while the model thinks
        try:
            stdout, stderr = proc.communicate(timeout=HEARTBEAT_S)
            break
        except subprocess.TimeoutExpired:
            if time.time() - t0 > timeout + 60:
                proc.kill()
                raise RuntimeError(f"agy timed out after {timeout + 60}s")
            log(f"  … {tag} still running ({time.time() - t0:.0f}s)")
    out = json.loads(stdout.strip().splitlines()[-1]) if stdout.strip() else {}
    if VERBOSE:
        u = out.get("usage", {})
        log(f"  {tag}: agy status={out.get('status')} in {time.time() - t0:.0f}s, "
            f"tokens in={u.get('input_tokens')} out={u.get('output_tokens')} thinking={u.get('thinking_tokens')}")
    if out.get("status") == "ERROR" or not out.get("response"):
        raise RuntimeError(out.get("error") or stderr[-300:] or "empty response")
    resp = out["response"]
    if isinstance(resp, str):
        m = re.search(r"\{.*\}", resp, re.S)
        resp = json.loads(m.group(0)) if m else {}
    resp["_provenance"] = {"conversation_id": out.get("conversation_id"), "usage": out.get("usage"),
                           "duration_s": out.get("duration_seconds")}
    return resp


def label_types(args):
    """Clause-type labels for every Indian clause (resumable, same safety as pair labelling)."""
    clauses = indian_clauses()
    tag_m = re.sub(r"[^A-Za-z0-9._-]+", "_", args.model or "default")
    out_path = SRC / "labels" / f"types_agy_{tag_m}.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    done = {json.loads(l)["clause_id"] for l in out_path.read_text(encoding="utf-8").splitlines()} if out_path.exists() else set()
    todo = [c for c in clauses if c["clause_id"] not in done]
    batches = [todo[i:i + 25] for i in range(0, len(todo), 25)]
    log(f"types: {len(clauses)} Indian clauses, {len(done)} done, {len(todo)} to do in {len(batches)} batches")
    workdir = tempfile.mkdtemp(prefix="agy_types_")
    schema_path = os.path.join(workdir, "schema.json")
    Path(schema_path).write_text(json.dumps(TYPES_SCHEMA))
    allowed = set(clause_types())
    stop, lock = threading.Event(), threading.Lock()

    def run(batch):
        if stop.is_set():
            return
        ids = {c["clause_id"] for c in batch}
        tag = f"types {batch[0]['clause_id'][:30]}"
        for attempt in range(3):
            try:
                log(f"→ {tag} ({len(batch)} clauses)")
                resp = call_agy(types_prompt(batch), args.model, schema_path, workdir, args.timeout, None, tag)
                got = [x for x in resp.get("items", []) if x.get("clause_id") in ids]
                if len(got) < 0.8 * len(batch):
                    raise RuntimeError(f"only {len(got)}/{len(batch)} returned")
                prov = {"teacher_model": args.model, "labelled_at": time.strftime("%Y-%m-%dT%H:%M:%S"), **resp.get("_provenance", {})}
                with lock, out_path.open("a", encoding="utf-8") as f:
                    for x in got:
                        x["types"] = [t for t in x.get("types", []) if t in allowed] or ["other"]
                        f.write(json.dumps({**x, "_provenance": prov}, ensure_ascii=False) + "\n")
                log(f"✓ {tag}: {len(got)}")
                return
            except Exception as exc:
                log(f"✗ {tag} attempt {attempt + 1}: {str(exc)[:200]}")
                if QUOTA_RE.search(str(exc)):
                    stop.set()
                    log("!! quota reached — stopping cleanly; saved work is kept")
                    return
                time.sleep(5)

    with ThreadPoolExecutor(args.workers) as pool:
        list(pool.map(run, batches))
    n = sum(1 for _ in out_path.open(encoding="utf-8")) if out_path.exists() else 0
    log(f"types done: {n}/{len(clauses)} saved in {out_path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default=None, help="agy model name (see `agy models`); default = CLI default")
    ap.add_argument("--effort", choices=["low", "medium", "high"], default=None, help="agy reasoning effort")
    ap.add_argument("--batch", type=int, default=20)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--limit", type=int, default=0, help="only the first N pairs (smoke test)")
    ap.add_argument("--verbose", "-v", action="store_true", help="print every label as it arrives")
    ap.add_argument("--priority", action="store_true", help="Indian pairs, then xref/type-matrix pairs, then the rest")
    ap.add_argument("--max-total", type=int, default=0, help="stop once this many pairs are labelled in total")
    ap.add_argument("--types", action="store_true", help="label CLAUSE-22 types of all Indian clauses instead of pairs")
    ap.add_argument("--pairs", default="", help="alternative pairs file (e.g. checklist_pairs.jsonl)")
    ap.add_argument("--out-prefix", default="", help="output file prefix, e.g. 'checklist_'")
    args = ap.parse_args()
    global VERBOSE
    VERBOSE = args.verbose
    if args.types:
        return label_types(args)

    pairs_file = Path(args.pairs) if args.pairs else SRC / "pairs_to_label.jsonl"
    pairs = [json.loads(l) for l in pairs_file.read_text(encoding="utf-8").splitlines() if l.strip()]
    if args.limit:
        pairs = pairs[: args.limit]
    tag = re.sub(r"[^A-Za-z0-9._-]+", "_", args.model or "default")
    out_path = SRC / "labels" / f"{args.out_prefix}agy_{tag}.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out_path.exists():
        for l in out_path.read_text(encoding="utf-8").splitlines():
            try:
                done.add(json.loads(l)["pair_id"])
            except Exception:
                pass
    todo = [p for p in pairs if p["pair_id"] not in done]
    if args.priority:
        # Indian contracts first, then structural pairs (xref / type matrix), then the rest
        # in a fixed random order, so a quota-limited run labels the most useful pairs.
        import random as _r
        rank = {p["pair_id"]: _r.Random(7).random() for p in todo}
        todo.sort(key=lambda p: (not p["contract"].startswith("india:"),
                                 not ({"xref", "type_matrix"} & set(p["surfaced_by"])), rank[p["pair_id"]]))
    if args.max_total:
        todo = todo[: max(0, args.max_total - len(done))]
    batches = [todo[i:i + args.batch] for i in range(0, len(todo), args.batch)]
    log(f"model={args.model or 'agy default'}  pairs={len(pairs)}  already labelled={len(done)}  "
        f"to do={len(todo)} in {len(batches)} batches of {args.batch}  workers={args.workers}  output={out_path}")
    started = time.time()
    rel_counts = Counter()

    rules = rules_text()
    workdir = tempfile.mkdtemp(prefix="agy_label_")
    schema_path = os.path.join(workdir, "schema.json")
    Path(schema_path).write_text(json.dumps(SCHEMA))
    lock = threading.Lock()
    stats = {"ok": 0, "failed_batches": 0}

    stop = threading.Event()

    def run(batch):
        if stop.is_set():
            return
        ids = {p["pair_id"] for p in batch}
        tag = f"batch {batch[0]['pair_id']}..{batch[-1]['pair_id']}"
        for attempt in range(3):
            if stop.is_set():
                return
            try:
                log(f"→ {tag} ({len(batch)} pairs) sent to {args.model or 'agy'}" + (f" [retry {attempt}]" if attempt else ""))
                resp = call_agy(build_prompt(batch, rules), args.model, schema_path, workdir, args.timeout, args.effort, tag)
                got = [x for x in resp.get("labels", []) if x.get("pair_id") in ids]
                if len(got) < 0.8 * len(batch):
                    raise RuntimeError(f"only {len(got)}/{len(batch)} labels returned")
                prov = {"teacher_model": args.model or "agy-default", "batch": tag,
                        "labelled_at": time.strftime("%Y-%m-%dT%H:%M:%S"), **resp.get("_provenance", {})}
                with lock, out_path.open("a", encoding="utf-8") as f:
                    for x in got:
                        f.write(json.dumps({**x, "_provenance": prov}, ensure_ascii=False) + "\n")
                        rel_counts[x.get("relation")] += 1
                        if VERBOSE:
                            log(f"    {x['pair_id']}: {x.get('relation'):10s} {x.get('severity'):6s} "
                                f"{(x.get('citation') or '-')[:45]:45s} | {(x.get('rationale') or '')[:90]}")
                    stats["ok"] += len(got)
                    total = stats["ok"] + len(done)
                    rate = stats["ok"] / max(1e-9, time.time() - started)
                    eta = (len(pairs) - total) / rate / 60 if rate else 0
                    log(f"✓ {tag}: {len(got)} labels | progress {total}/{len(pairs)} ({100 * total / len(pairs):.1f}%) "
                        f"| {rate * 60:.0f} pairs/min | ETA {eta:.0f} min | so far {dict(rel_counts)}")
                return
            except Exception as exc:
                msg = str(exc)
                log(f"✗ {tag} attempt {attempt + 1} failed: {msg[:200]}")
                if QUOTA_RE.search(msg):
                    if not stop.is_set():
                        log("!! quota / rate limit reached — stopping cleanly: no new batches will start; "
                            "everything already labelled is saved.")
                    stop.set()
                    return
                time.sleep(5 * (attempt + 1))
        stats["failed_batches"] += 1

    pool = ThreadPoolExecutor(args.workers)
    try:
        for f in [pool.submit(run, b) for b in batches]:
            f.result()
    except KeyboardInterrupt:
        stop.set()
        log("!! interrupted (Ctrl-C) — waiting for in-flight batches to save, then exiting…")
    finally:
        pool.shutdown(wait=True, cancel_futures=True)
        saved = sum(1 for _ in out_path.open(encoding="utf-8")) if out_path.exists() else 0
        state = "STOPPED EARLY" if stop.is_set() else "done"
        log(f"{state}: {saved}/{len(pairs)} pairs labelled and saved in {out_path} "
            f"({stats['ok']} this run, {stats['failed_batches']} batches failed) in {(time.time() - started) / 60:.1f} min; "
            f"relation counts this run {dict(rel_counts)}")
        if saved < len(pairs):
            log("Resume later with the same command — finished pairs are skipped automatically.")


if __name__ == "__main__":
    main()
