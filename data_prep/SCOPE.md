# Scope — Fine-Tuning Llama 3.3 with QLoRA for Text-to-SQL

## The scope (one paragraph)

We fine-tune Llama 3.3 (QLoRA, 4-bit) to translate a natural-language question
plus a database schema into a **SQLite** SQL query, evaluated on the **Spider**
benchmark with execution accuracy as the primary metric. The model must
generalize **across databases** (the schema is provided at inference time, not
memorized), supporting SELECT/WHERE, JOINs, aggregations (GROUP BY/HAVING),
nested subqueries, and set operations (UNION/INTERSECT), over the **full
difficulty distribution** (easy/medium/hard/extra-hard), with every result
stratified by difficulty and SQL feature. In scope: baseline (zero-shot and
few-shot) vs. fine-tuned comparison on a fully held-out test set (Spider's
original dev split, touched exactly once), validation-driven checkpoint
selection, and an automatic execution-accuracy harness (no LLM-as-judge). Out
of scope for v1: single-database specialization, training-time schema linking
(model-side), non-SQLite dialects, and agentic/self-correction loops.

## Explicit decisions

| Decision | Choice | Why |
|---|---|---|
| Generalization mode | Cross-database (schema in prompt) | Matches Spider's eval setup; comparable to published numbers |
| SQL dialect | SQLite | Spider databases ship as SQLite; execution harness is trivial and deterministic |
| Split discipline | train 80% / val 10% / test 10% (test = Spider dev, untouched) | Val picks checkpoints; test is touched once at the end |
| Difficulty | Full distribution, stratified | An aggregate hides where the model struggles |
| Metrics | Execution accuracy (primary) + exact-match (secondary) | Fully reproducible; no judge needed |
| Baselines | Zero-shot + few-shot on the base model | The claim is the delta |
| Checkpointing | Best validation execution accuracy, not last step | Prevents overfit checkpoints from shipping |

## Data staging contract

- Each example is formatted with Llama 3.3's chat template
  (system = task + schema DDL, user = question, assistant = gold SQL).
- JSONL per split: `train.jsonl`, `val.jsonl`, `test.jsonl` (optionally
  mirrored to `s3://<bucket>/text2sql/`).
- Every row keeps raw fields (`db_id`, `question`, `query`, `difficulty`) so
  the eval harness never depends on the formatted string.
