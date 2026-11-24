"""
Fully fine-tune a transformer encoder as a multi-label CLAUSE-20 clause classifier.

    python train/finetune_classifier.py                                  # law-ai/InLegalBERT
    python train/finetune_classifier.py --model nlpaueb/legal-bert-base-uncased --out models/clause20_legalbert
    python train/finetune_classifier.py --epochs 1 --limit 2000          # smoke test

Data: clause20/data/CLAUSE20.csv (clause20/build.py). Uses LexGLUE's official LEDGAR
split + contract-level CUAD splits; `test_ood` = clauses from CUAD contracts never
seen in training (closest to real use).

Writes the model + tokenizer to --out (default models/clause20_inlegalbert, which
legalagent.core.classification loads as backend "inlegalbert"), the validation-tuned
threshold to clause20_meta.json, and metrics to results/classifier_<name>.json.
"""
import argparse
import csv
import json
import math
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DATA = ROOT / "clause20" / "data" / "CLAUSE20.csv"


def load_rows(limit=None):
    csv.field_size_limit(10**9)
    with open(DATA, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    by = {}
    for r in rows:
        by.setdefault(r["split"], []).append(r)
    if limit:
        rnd = random.Random(0)
        by = {k: rnd.sample(v, min(limit, len(v))) for k, v in by.items()}
    return by


class ClauseSet(Dataset):
    def __init__(self, rows, label_index):
        self.texts = [r["text"] for r in rows]
        self.y = np.zeros((len(rows), len(label_index)), dtype=np.float32)
        for i, r in enumerate(rows):
            for lab in r["labels"].split("|"):
                if lab in label_index:
                    self.y[i, label_index[lab]] = 1.0

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, i):
        return self.texts[i], self.y[i]


def metrics(y, probs, thr, labels):
    """micro/macro F1 over the real labels (not 'other'), top-1 and exact-match accuracy."""
    from sklearn.metrics import f1_score, precision_score, recall_score
    real = [i for i, n in enumerate(labels) if n != "other"]
    pred = (probs >= thr).astype(int)
    # top-1: the argmax label is one of the gold labels
    top1 = float(np.mean([y[i, probs[i].argmax()] == 1 for i in range(len(y))]))
    # exact match over all labels; empty predictions fall back to argmax
    p2 = pred.copy()
    for i in range(len(p2)):
        if p2[i].sum() == 0:
            p2[i, probs[i].argmax()] = 1
    exact = float(np.mean((p2 == y).all(axis=1)))
    return {
        "micro_f1": float(f1_score(y[:, real], pred[:, real], average="micro", zero_division=0)),
        "macro_f1": float(f1_score(y[:, real], pred[:, real], average="macro", zero_division=0)),
        "micro_p": float(precision_score(y[:, real], pred[:, real], average="micro", zero_division=0)),
        "micro_r": float(recall_score(y[:, real], pred[:, real], average="micro", zero_division=0)),
        "top1_acc": top1,
        "exact_match": exact,
        "n": int(len(y)),
    }


def predict(model, tok, texts, device, max_len, bs=64):
    model.eval()
    out = []
    with torch.no_grad(), torch.autocast(device_type=device, dtype=torch.float16, enabled=device == "cuda"):
        for i in range(0, len(texts), bs):
            enc = tok(texts[i:i + bs], truncation=True, max_length=max_len, padding=True, return_tensors="pt").to(device)
            out.append(torch.sigmoid(model(**enc).logits.float()).cpu().numpy())
    return np.vstack(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="law-ai/InLegalBERT")
    ap.add_argument("--out", default=str(ROOT / "models" / "clause20_inlegalbert"))
    ap.add_argument("--epochs", type=float, default=3)
    ap.add_argument("--bs", type=int, default=16)
    ap.add_argument("--lr", type=float, default=3e-5)
    ap.add_argument("--max-len", type=int, default=256)
    ap.add_argument("--limit", type=int, default=None, help="rows per split (smoke test)")
    ap.add_argument("--seed", type=int, default=13)
    args = ap.parse_args()

    from transformers import AutoModelForSequenceClassification, AutoTokenizer, get_linear_schedule_with_warmup

    torch.manual_seed(args.seed)
    random.seed(args.seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    by = load_rows(args.limit)
    labels = sorted({l for r in by["train"] for l in r["labels"].split("|")})
    label_index = {l: i for i, l in enumerate(labels)}
    print(f"{args.model} on {device}: {len(by['train'])} train rows, {len(labels)} labels", flush=True)

    tok = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForSequenceClassification.from_pretrained(
        args.model, num_labels=len(labels), problem_type="multi_label_classification",
        id2label=dict(enumerate(labels)), label2id=label_index,
    ).to(device)

    train = ClauseSet(by["train"], label_index)

    def collate(batch):
        texts, ys = zip(*batch)
        enc = tok(list(texts), truncation=True, max_length=args.max_len, padding=True, return_tensors="pt")
        enc["labels"] = torch.tensor(np.stack(ys))
        return enc

    loader = DataLoader(train, batch_size=args.bs, shuffle=True, collate_fn=collate, num_workers=2)
    steps = math.ceil(len(loader) * args.epochs)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    sched = get_linear_schedule_with_warmup(opt, int(0.06 * steps), steps)
    scaler = torch.amp.GradScaler(enabled=device == "cuda")

    t0, step, losses = time.time(), 0, []
    model.train()
    while step < steps:
        for batch in loader:
            batch = {k: v.to(device) for k, v in batch.items()}
            with torch.autocast(device_type=device, dtype=torch.float16, enabled=device == "cuda"):
                loss = model(**batch).loss
            scaler.scale(loss).backward()
            scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(opt)
            scaler.update()
            opt.zero_grad(set_to_none=True)
            sched.step()
            losses.append(loss.item())
            step += 1
            if step % 200 == 0:
                print(f"step {step}/{steps} loss {np.mean(losses[-200:]):.4f} {time.time()-t0:.0f}s", flush=True)
            if step >= steps:
                break
        model.train()
    train_s = time.time() - t0

    # Threshold tuned on validation only.
    val = ClauseSet(by["validation"], label_index)
    vp = predict(model, tok, val.texts, device, args.max_len)
    best = max((metrics(val.y, vp, t, labels)["micro_f1"], t) for t in np.arange(0.1, 0.71, 0.05))
    thr = round(float(best[1]), 2)
    print(f"validation micro-F1 {best[0]:.3f} at threshold {thr}", flush=True)

    results = {"model": args.model, "threshold": thr, "train_seconds": round(train_s), "epochs": args.epochs,
               "lr": args.lr, "batch_size": args.bs, "max_len": args.max_len, "labels": labels, "splits": {}}
    results["splits"]["validation"] = metrics(val.y, vp, thr, labels)
    for split in ("test", "test_ood"):
        ds = ClauseSet(by[split], label_index)
        t = time.time()
        p = predict(model, tok, ds.texts, device, args.max_len)
        m = metrics(ds.y, p, thr, labels)
        m["ms_per_clause"] = round(1000 * (time.time() - t) / max(1, len(ds)), 2)
        results["splits"][split] = m
        print(split, json.dumps(m), flush=True)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(out)
    tok.save_pretrained(out)
    (out / "clause20_meta.json").write_text(json.dumps({"threshold": thr, "base_model": args.model, "labels": labels}, indent=2))
    res_dir = ROOT / "results"
    res_dir.mkdir(exist_ok=True)
    (res_dir / f"classifier_{out.name}.json").write_text(json.dumps(results, indent=2))
    print("saved", out, flush=True)


if __name__ == "__main__":
    main()
