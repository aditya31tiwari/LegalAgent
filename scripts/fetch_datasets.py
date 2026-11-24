"""
Fetch the public training data into dataset/ in the layout clause20/build.py reads.

    python scripts/fetch_datasets.py            # CUAD + LEDGAR
    python scripts/fetch_datasets.py --only cuad

  dataset/data.zip                 CUAD v1 (github.com/TheAtticusProject/cuad, CC BY 4.0)
  dataset/ledgar_{split}.csv.zip   LEDGAR from LexGLUE (HF coastalcph/lex_glue, CC BY-SA 4.0)
                                   columns: text,label (label = integer index into
                                   clause20/ledgar_labels.json, same as the Kaggle mirror)
"""
import argparse
import csv
import io
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "dataset"
CUAD_URL = "https://github.com/TheAtticusProject/cuad/raw/main/data.zip"


def fetch_cuad():
    out = RAW / "data.zip"
    if out.exists():
        print("cuad: already present", out)
        return
    print("cuad: downloading", CUAD_URL)
    urllib.request.urlretrieve(CUAD_URL, out)
    names = zipfile.ZipFile(out).namelist()
    assert "CUADv1.json" in names, names
    print("cuad: ok", out, f"{out.stat().st_size/1e6:.1f} MB")


def fetch_ledgar():
    from datasets import load_dataset
    names = json.loads((ROOT / "clause20" / "ledgar_labels.json").read_text())["names"]
    ds = load_dataset("coastalcph/lex_glue", "ledgar")
    hf_names = ds["train"].features["label"].names
    if hf_names != names:
        sys.exit("LEDGAR label order differs from clause20/ledgar_labels.json")
    for split in ("train", "validation", "test"):
        out = RAW / f"ledgar_{split}.csv.zip"
        if out.exists():
            print("ledgar:", split, "already present")
            continue
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["text", "label"])
        for row in ds[split]:
            w.writerow([row["text"], row["label"]])
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr(f"ledgar_{split}.csv", buf.getvalue())
        print("ledgar:", split, len(ds[split]), "rows ->", out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["cuad", "ledgar"])
    args = ap.parse_args()
    RAW.mkdir(exist_ok=True)
    if args.only in (None, "cuad"):
        fetch_cuad()
    if args.only in (None, "ledgar"):
        fetch_ledgar()


if __name__ == "__main__":
    main()
