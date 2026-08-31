#!/usr/bin/env python3
"""
error_analysis.py — bucket failures from a per-row results JSON.

First-pass heuristics (syntax vs executed-but-wrong vs gold-error), failure
feature strata, and a markdown dump of failed examples for the manual
bucketing pass (the interview story: "I understand where and why it fails").

Usage:
    uv run python analysis/error_analysis.py \
        --rows runs/eval-run1-test1034.rows.json \
        --dump analysis/failures.md --max-dump 50
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rows", required=True, help="per-row results JSON")
    ap.add_argument("--dump", default="analysis/failures.md")
    ap.add_argument("--max-dump", type=int, default=50)
    args = ap.parse_args()

    rows = json.loads(Path(args.rows).read_text())
    n = len(rows)
    fails = [r for r in rows if r.get("exec") != 1.0]
    ok = n - len(fails)
    print(f"rows={n} correct={ok} failed={len(fails)} ({len(fails)/n:.1%})")

    # First-pass heuristic buckets — the manual pass refines these.
    buckets = Counter()
    for r in fails:
        if r.get("gold_error"):
            buckets["gold-query-error"] += 1
        elif r.get("pred_error"):
            buckets["syntax-or-exec-error"] += 1
        else:
            buckets["wrong-result"] += 1
    print("first-pass buckets:", dict(buckets))

    # Failure strata by SQL feature (which feature kinds fail most).
    feat = Counter()
    for r in fails:
        for f in r.get("features", []):
            feat[f] += 1
    print("failure features:", dict(feat))

    # Markdown dump for the manual bucketing pass.
    md = [
        "# Failure dump — manual bucketing",
        "",
        f"total rows: {n} | correct: {ok} | failed: {len(fails)} ({len(fails)/n:.1%})",
        "",
        "Bucket labels: wrong-table/column | wrong-join | wrong-aggregation | "
        "syntax-error | right-logic-wrong-shape | other",
        "",
    ]
    for i, r in enumerate(fails[: args.max_dump], 1):
        md.append(f"## {i}. `{r['db_id']}` ({', '.join(r.get('features', []))})")
        md.append(f"**Q:** {r['question']}")
        md.append(f"**gold:**\n```sql\n{r['gold']}\n```")
        md.append(f"**pred:**\n```sql\n{r['pred']}\n```")
        if r.get("pred_error"):
            md.append(f"**pred error:** `{r['pred_error']}`")
        md.append("")
    Path(args.dump).write_text("\n".join(md))
    print(f"dump -> {args.dump}")


if __name__ == "__main__":
    main()
