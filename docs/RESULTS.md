# Baseline Results — Llama 3.1 8B Instruct, zero-shot text-to-SQL

**Status: FIRST REAL NUMBER CAPTURED.** This is the X in the claim
"improved execution accuracy from **X%** to **Y%**" — nothing fine-tuned yet,
but the measurement foundation is done and reproducible.

## What the baseline model does

The **base, non-fine-tuned** `meta-llama/Llama-3.1-8B-Instruct` is asked to
write SQL directly from the prompt — no training, no examples (zero-shot):

- **System:** "You are a text-to-SQL assistant…" + the target database's
  schema (tables, columns, types) + primary/foreign keys
- **User:** the natural-language question
- **Model:** generates the SQL (greedy decoding, temperature 0, ≤300 tokens)
- **Harness:** executes the generated SQL **and** the gold SQL against the
  real SQLite database, compares result sets (row-order-insensitive) →
  **execution accuracy**; normalized SQL string equality → **exact match**

**Why it exists:** without this number, "fine-tuning improved accuracy" is
meaningless. Every future result (few-shot, fine-tuned) is reported against
this baseline.

## Metrics (run: `baseline-zeroshot-200`)

| Metric | Value | Meaning |
|---|---|---|
| **Execution accuracy** | **60.5%** | generated SQL returned the same result set as gold on 121/200 |
| **Exact match** | 29.0% | normalized SQL strings identical on 58/200 (stricter) |
| Aggregation (GROUP BY/HAVING/count/sum/avg/min/max) | 68.97% | strongest category |
| Set-operation (UNION/INTERSECT/EXCEPT) | 53.33% | |
| Join | 45.83% | |
| Subquery (nested SELECT) | 37.14% | weakest category |

**By difficulty:** pending — the HF mirror's rows carry no difficulty labels;
supply the official Spider `dev.json` via `--difficulty-json` to stratify by
easy/medium/hard/extra-hard.

**Where the model already works:** straightforward aggregations
(`SELECT count(*) FROM singer`). **Where it struggles:** nested subqueries and
multi-table joins — exactly where fine-tuning (and more schema context) should
show the biggest delta.

## What we are achieving

1. **A defensible X%.** 60.5% execution accuracy (200-example sample, greedy)
   is the bar fine-tuning must clear — and the mechanism to prove it cleared
   it is in place and automatic.
2. **A reproducible measurement pipeline.** Same harness, same databases,
   same decode settings → anyone can rerun and get the same number.
3. **Granular signal.** The feature stratification tells us *where* to expect
   gains (subqueries, joins) before we spend GPU on training.

## Caveats (honest)

- **Sample:** 200 of 1,034 test examples (full-set run = `--max-examples 0` /
  omit the flag).
- **Difficulty stratification pending** official dev.json labels.
- **Zero-shot only** — the few-shot baseline (2 in-context examples) typically
  lands higher and should be captured next.
- Greedy decoding (temperature 0) — a deliberate choice for reproducibility.

## Reproduce

```sh
modal run modal_app.py::run_baseline \
    --model meta-llama/Llama-3.1-8B-Instruct --max-examples 200
# full test set:
modal run modal_app.py::run_baseline \
    --model meta-llama/Llama-3.1-8B-Instruct
```

Results land in `llama33-runs` volume (`baseline.json`) and print in the run.

## Next steps

- [ ] Few-shot baseline (2–3 shots) → compare against 60.5%
- [ ] Full 1,034-example zero-shot run
- [ ] Official difficulty labels → stratified table
- [ ] QLoRA fine-tuning → the Y% (target: clear the baseline per-category)
