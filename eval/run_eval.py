#!/usr/bin/env python3
"""
run_eval.py — the execution-accuracy eval harness.

For each test example:
  1. (model mode) generate SQL from the prompt via a HF model (4-bit optional);
     (gold mode) use the gold SQL itself — validates the harness plumbing.
  2. Execute the generated AND gold SQL against the real SQLite database.
  3. Compare result sets (row-order insensitive) -> execution accuracy.
  4. Compare normalized SQL strings -> exact-match (secondary).
  5. Stratify by difficulty (if provided) and SQL feature (join/agg/subquery/set-op).

Usage:
  # harness validation (no model): gold-vs-gold must be 100% execution
  uv run python eval/run_eval.py --test-jsonl data/processed/test.jsonl \
      --db-dir data/spider/spider_data/database --gold-mode --max-examples 50

  # real run (needs GPU + HF license for the model)
  uv run python eval/run_eval.py --test-jsonl data/processed/test.jsonl \
      --db-dir data/spider/spider_data/database \
      --model meta-llama/Llama-3.1-8B-Instruct --max-examples 200

  # with official difficulties (from Spider dev.json): --difficulty-json dev.json
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

EXEC_TIMEOUT_S = 5  # per-query safety bound


# ------------------------------------------------------------------ sqlite
def execute_sql(db_path: Path, sql: str) -> tuple[list | None, str | None]:
    """Return (rows, error). rows is None when execution failed."""
    if not db_path.exists():
        return None, f"db missing: {db_path.name}"
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=EXEC_TIMEOUT_S)
        conn.execute("PRAGMA query_only = ON")
        cur = conn.execute(sql)
        rows = [tuple(r) for r in cur.fetchall()]
        conn.close()
        return rows, None
    except sqlite3.Error as exc:
        return None, str(exc)
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)


def normalize_rows(rows: list | None) -> list:
    """Row-order-insensitive comparison key: sorted, stringified tuples."""
    if rows is None:
        return []
    return sorted(tuple(str(c).strip() for c in r) for r in rows)


def execution_accuracy(gold_rows, pred_rows) -> tuple[float, bool]:
    """1.0 iff both executed and result sets match (multiset, order-insensitive)."""
    if gold_rows is None or pred_rows is None:
        return 0.0, False
    return (1.0 if normalize_rows(gold_rows) == normalize_rows(pred_rows) else 0.0), True


def normalize_sql(sql: str) -> str:
    s = re.sub(r"--[^\n]*", "", sql)
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.S)
    s = s.lower()
    s = re.sub(r"\s+", " ", s).strip().rstrip(";").strip()
    return s


def exact_match(gold: str, pred: str) -> int:
    return 1 if normalize_sql(gold) == normalize_sql(pred) else 0


# ------------------------------------------------------------------ stratification
FEATURE_RULES = [
    ("join", r"\bjoin\b"),
    ("aggregation", r"\b(group\s+by|having|count|sum|avg|min|max)\b"),
    ("subquery", r"\bselect\b.*\bselect\b"),
    ("set-operation", r"\b(union|intersect|except)\b"),
]


def classify_features(sql: str) -> list[str]:
    return [name for name, pat in FEATURE_RULES if re.search(pat, sql, re.I)]


# ------------------------------------------------------------------ generation
def load_model(model_id: str, quantize_4bit: bool):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_id, token=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    kwargs = {}
    if quantize_4bit:
        from transformers import BitsAndBytesConfig

        kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)
    model = AutoModelForCausalLM.from_pretrained(
        model_id, torch_dtype=torch.bfloat16, device_map="auto", token=True, **kwargs)
    model.eval()
    return model, tokenizer


def generate_sql(model, tokenizer, prompt: str, max_new_tokens: int = 300) -> str:
    import torch

    inputs = tokenizer(prompt, return_tensors="pt")
    inputs = {k: v.to(model.device) for k, v in inputs.items()}
    with torch.no_grad():
        out = model.generate(
            **inputs, max_new_tokens=max_new_tokens, do_sample=False,
            pad_token_id=tokenizer.pad_token_id)
    text = tokenizer.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
    # strip anything after the first SQL-looking end
    return text.strip()


# ------------------------------------------------------------------ evaluation
def evaluate_row(row: dict, db_dir: Path, gold_mode: bool,
                 model=None, tokenizer=None) -> dict:
    db_path = db_dir / row["db_id"] / f"{row['db_id']}.sqlite"
    gold = row["query"]

    if gold_mode:
        pred = gold
    else:
        pred = generate_sql(model, tokenizer, row["prompt"])

    gold_rows, gold_err = execute_sql(db_path, gold)
    pred_rows, pred_err = execute_sql(db_path, pred)

    exec_acc, both_ok = execution_accuracy(gold_rows, pred_rows)
    return {
        "db_id": row["db_id"],
        "difficulty": row.get("difficulty"),
        "features": classify_features(gold),
        "gold": gold,
        "pred": pred,
        "gold_error": gold_err,
        "pred_error": pred_err,
        "exec": exec_acc,
        "exact": exact_match(gold, pred),
        "both_executed": both_ok,
    }


def summarize(results: list[dict], label: str) -> dict:
    n = len(results)
    overall = sum(r["exec"] for r in results) / n if n else 0.0
    exact = sum(r["exact"] for r in results) / n if n else 0.0
    by_diff = defaultdict(list)
    by_feat = defaultdict(list)
    for r in results:
        by_diff[r["difficulty"] or "unknown"].append(r)
        for f in r["features"]:
            by_feat[f].append(r)
    return {
        "label": label,
        "n": n,
        "exec_accuracy": round(overall, 4),
        "exact_match": round(exact, 4),
        "by_difficulty": {
            k: round(sum(x["exec"] for x in v) / len(v), 4) for k, v in by_diff.items()
        },
        "by_feature": {
            k: round(sum(x["exec"] for x in v) / len(v), 4) for k, v in by_feat.items()
        },
    }


def render_table(s: dict) -> str:
    lines = [f"## {s['label']}  (n={s['n']})",
             f"- **execution accuracy:** {s['exec_accuracy']:.2%}",
             f"- **exact match:** {s['exact_match']:.2%}"]
    if s["by_difficulty"]:
        lines.append("- **by difficulty:** " + ", ".join(
            f"{k} {v:.2%}" for k, v in sorted(s["by_difficulty"].items())))
    if s["by_feature"]:
        lines.append("- **by feature:** " + ", ".join(
            f"{k} {v:.2%}" for k, v in sorted(s["by_feature"].items())))
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--test-jsonl", type=Path, required=True)
    ap.add_argument("--db-dir", type=Path, required=True)
    ap.add_argument("--max-examples", type=int, default=None)
    ap.add_argument("--gold-mode", action="store_true",
                    help="use gold SQL as prediction (validates the harness)")
    ap.add_argument("--model", default=None, help="HF model id for generation")
    ap.add_argument("--quantize-4bit", action="store_true")
    ap.add_argument("--difficulty-json", type=Path, default=None,
                    help="official Spider dev.json to overlay difficulties")
    ap.add_argument("--out", type=Path, default=Path("data/results.json"))
    args = ap.parse_args()

    rows = [json.loads(l) for l in open(args.test_jsonl)]
    if args.max_examples:
        rows = rows[: args.max_examples]

    if args.difficulty_json:
        diff_map = {r["question"]: r["difficulty"]
                    for r in json.loads(args.difficulty_json.read_text())}
        for r in rows:
            r["difficulty"] = diff_map.get(r["question"], r.get("difficulty"))

    model = tokenizer = None
    if not args.gold_mode:
        if not args.model:
            raise SystemExit("need --model (or --gold-mode to validate the harness)")
        print(f"loading {args.model} ...", file=sys.stderr)
        model, tokenizer = load_model(args.model, args.quantize_4bit)

    results = []
    for i, row in enumerate(rows):
        r = evaluate_row(row, args.db_dir, args.gold_mode, model, tokenizer)
        results.append(r)
        if (i + 1) % 50 == 0 or i == len(rows) - 1:
            print(f"  {i + 1}/{len(rows)} (exec so far "
                  f"{sum(x['exec'] for x in results) / len(results):.2%})", file=sys.stderr)

    summary = summarize(results, "gold-mode (harness check)" if args.gold_mode
                        else f"model: {args.model}")
    print(render_table(summary))
    payload = {"summary": summary, "rows": results}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=1))
    print(f"\nresults -> {args.out}")


if __name__ == "__main__":
    main()
