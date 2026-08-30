#!/usr/bin/env python3
"""
stage_spider.py — Spider -> chat-template JSONL (train/val/test), optional S3.

Pipeline:
  1. Load Spider examples from Hugging Face (`xlangai/spider`) — train +
     validation (the held-out dev set). Schemas come from
     `richardr1126/spider-schema` (per-database formatted schema + keys).
  2. Split train -> train/val (90/10); Spider validation -> test (held out).
  3. Format each example with Llama 3.3's chat template
     (system = task + schema + keys, user = question, assistant = gold SQL),
     optionally with lightweight token-overlap schema linking.
  4. Write `<out>/train.jsonl`, `val.jsonl`, `test.jsonl`.
  5. With --upload-s3, mirror the JSONLs to s3://<bucket>/text2sql/.
  6. With --fetch-databases, also fetch the official Spider sqlite databases
     (needed by the eval harness later).

Usage:
  uv run python data_prep/stage_spider.py --out data/processed \
      --max-examples 200          # small run to validate formatting
  uv run python data_prep/stage_spider.py --out data/processed \
      --schema-linking            # filter schema to question-overlapping names
  uv run python data_prep/stage_spider.py --upload-s3 your-bucket
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
import zipfile
from pathlib import Path

# ------------------------------------------------------------------ template
BOS = "<|begin_of_text|>"
CHAT_TEMPLATE = (
    "{bos}<|start_header_id|>system<|end_header_id|>\n\n"
    "{system}<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n"
    "{question}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
    "{query}<|eot_id|>"
)
SYSTEM_TEMPLATE = (
    "You are a text-to-SQL assistant. Given the database schema below, write a "
    "SQLite SQL query that answers the question.\n\nSchema:\n{schema}"
)

# Official Spider databases (Google Drive ID — best-effort; see --fetch-databases)
SPIDER_DB_ZIP_URL = (
    "https://drive.google.com/uc?export=download&id=1i4xw2Gsr5o8BTORcNw5lvNir7clvMBoi"
)

EXAMPLES_DATASET = "xlangai/spider"          # question/query pairs (train+validation)
SCHEMA_DATASET = "richardr1126/spider-schema"  # per-db schema + PK/FK


# ------------------------------------------------------------------ schema
def load_schema_map() -> dict[str, dict]:
    """db_id -> {schema, pk, fk} from the schema HF dataset (small: 166 dbs)."""
    from datasets import load_dataset  # imported lazily

    ds = load_dataset(SCHEMA_DATASET, split="train")
    return {
        r["db_id"]: {
            "schema": r["Schema (values (type))"],
            "pk": r["Primary Keys"],
            "fk": r["Foreign Keys"],
        }
        for r in ds
    }


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in re.findall(r"[a-z_]+", text.lower())}


def format_schema(meta: dict, question: str, use_linking: bool) -> str:
    """Schema block (+ optional token-overlap linking), PK/FK always kept."""
    parts = [meta["schema"]]
    if use_linking:
        qtokens = _tokens(question)
        parts = [
            line for line in meta["schema"].splitlines()
            if _tokens(line) & qtokens
        ] or [meta["schema"]]  # never produce an empty schema
    out = "\n".join(parts)
    if meta.get("pk") and meta["pk"].strip():
        out += f"\nPrimary Keys: {meta['pk']}"
    if meta.get("fk") and meta["fk"].strip():
        out += f"\nForeign Keys: {meta['fk']}"
    return out


def format_example(row: dict, schema_map: dict, use_linking: bool) -> dict:
    meta = schema_map.get(row["db_id"], {"schema": "(schema unavailable)", "pk": "", "fk": ""})
    schema = format_schema(meta, row["question"], use_linking)
    system = SYSTEM_TEMPLATE.format(schema=schema)
    text = CHAT_TEMPLATE.format(
        bos=BOS, system=system, question=row["question"], query=row["query"])
    return {
        "db_id": row["db_id"],
        "question": row["question"],
        "query": row["query"],
        "difficulty": row.get("difficulty", None),
        "text": text,
    }


# ------------------------------------------------------------------ load
def load_examples(max_examples: int | None) -> tuple[list[dict], list[dict]]:
    from datasets import load_dataset  # imported lazily

    def _split(name: str) -> list[dict]:
        ds = load_dataset(EXAMPLES_DATASET, split=name)
        rows = [dict(r) for r in ds]
        if max_examples:
            rows = rows[:max_examples]
        return rows

    return _split("train"), _split("validation")  # validation = Spider dev (held out)


# ------------------------------------------------------------------ output
def write_jsonl(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    print(f"wrote {len(rows):5d} rows -> {path}")


def upload_s3(paths: dict[str, Path], bucket: str) -> None:
    import boto3

    s3 = boto3.client("s3")
    for name, path in paths.items():
        key = f"text2sql/{path.name}"
        s3.upload_file(str(path), bucket, key)
        print(f"uploaded s3://{bucket}/{key}")


def fetch_databases(out: Path) -> None:
    """Best-effort download of the official Spider databases zip (for eval)."""
    out.mkdir(parents=True, exist_ok=True)
    dest = out / "spider_databases.zip"
    print(f"downloading Spider databases -> {dest} ...")
    try:
        with urllib.request.urlopen(SPIDER_DB_ZIP_URL, timeout=120) as resp, \
                dest.open("wb") as fh:
            fh.write(resp.read())
        with zipfile.ZipFile(dest) as zf:
            zf.extractall(out)
        print(f"databases extracted to {out}")
    except Exception as exc:  # noqa: BLE001
        print(f"WARNING: database fetch failed ({exc}) — "
              "download the Spider databases manually for eval.", file=sys.stderr)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("data/processed"),
                    help="output directory for JSONL splits")
    ap.add_argument("--max-examples", type=int, default=None,
                    help="limit rows per split (for validation runs)")
    ap.add_argument("--schema-linking", action="store_true",
                    help="filter schema to question-overlapping names")
    ap.add_argument("--upload-s3", metavar="BUCKET", default=None,
                    help="mirror JSONLs to s3://<bucket>/text2sql/")
    ap.add_argument("--fetch-databases", action="store_true",
                    help="also fetch the official Spider sqlite databases")
    args = ap.parse_args()

    train_raw, dev_raw = load_examples(args.max_examples)
    schema_map = load_schema_map()
    missing = sorted({r["db_id"] for r in train_raw} - set(schema_map))
    if missing:
        print(f"WARNING: {len(missing)} db_ids missing from schema map "
              f"(e.g. {missing[:3]}) — those rows get '(schema unavailable)'",
              file=sys.stderr)

    # split: train -> train/val (90/10); dev -> test (untouched)
    n_val = int(len(train_raw) * 0.1)
    splits = {
        "train": train_raw[: len(train_raw) - n_val],
        "val": train_raw[len(train_raw) - n_val:],
        "test": dev_raw,
    }

    out = args.out
    paths = {}
    for name, rows in splits.items():
        formatted = [
            format_example(r, schema_map, args.schema_linking) for r in rows
        ]
        path = out / f"{name}.jsonl"
        write_jsonl(formatted, path)
        paths[name] = path

    if args.upload_s3:
        upload_s3(paths, args.upload_s3)
    if args.fetch_databases:
        fetch_databases(out)


if __name__ == "__main__":
    main()
