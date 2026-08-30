# llama33-text2sql — Development Log

A running journal of every step, in order, with what it produced. Decision
rationale lives in [decisions.md](decisions.md); this file is the timeline.

**Convention:** every development step adds a dated entry here
(`YYYY-MM-DD · NN`).

---

## 2026-08-30

### 01 · Project inception
Captain asked for a resume-grade end-to-end project: fine-tune **Llama 3.3
(QLoRA)** on the **Spider** text-to-SQL benchmark with an automatic eval
harness that proves fine-tuning helped. Created `~/llama33-text2sql`, git
initialized, uv project (Python 3.12). ML deps declared via `uv add --no-sync`
(torch, transformers, peft, bitsandbytes, datasets, accelerate, evaluate,
mlflow) — no heavy install yet. Wrote the full plan README from the captain's
outline (claim statement, pipeline diagram, scope, steps 1–8).

### 02 · Data-prep stage
`data_prep/SCOPE.md` (one-paragraph scope + explicit decisions) and
`data_prep/stage_spider.py`:
- Examples from HF `xlangai/spider` (train + validation = held-out dev)
- Schemas from `richardr1126/spider-schema` (per-db schema + PK/FK)
- Llama 3.3 chat template (system = task + schema + keys, user = question,
  assistant = gold SQL); `prompt` (system+user only) stored separately for
  inference
- Split train → train/val (90/10); validation → test, untouched
- Optional `--schema-linking` (token overlap, safe fallback), `--upload-s3`
Debugging notes: HF split name is `validation` (not `dev`); the HF example
dataset carries no schema — the schema dataset was the fix; the schema map must
load in full (a test flag initially sliced it, breaking coverage).

### 03 · Full staging + databases
Full run: **6,300 train / 700 val / 1,034 test** JSONL. Fetched the official
Spider **SQLite databases** (206MB zip, verified working — layout
`spider_data/database/<db_id>/<db_id>.sqlite`). The remembered Google Drive ID
was wrong (404) — the correct one was extracted from the official Spider page
and wired into the script.

### 04 · Eval harness
`eval/run_eval.py`: execution accuracy (sqlite result-set comparison,
row-order-insensitive) + exact-match (normalized SQL), stratified by
difficulty (official `dev.json` via `--difficulty-json`) and SQL feature
(join/aggregation/subquery/set-op). Validated: gold-mode 100% exec + exact;
negative tests confirm wrong SQL → 0.0 and syntax errors are captured.

### 05 · Compute decision + Modal setup
Captain chose **Modal** for compute. Installed the Modal SDK; wrote
`training/run_baseline.py` (env-agnostic baseline: vLLM generation, few-shot
support, harness reuse), `training/train_qlora.py` (SFTTrainer QLoRA,
completion-only supervision, best-checkpoint by **validation execution
accuracy**), and `training/modal_app.py` (Modal entrypoint: A10G, hf-token
secret, repo mount, `llama33-runs` volume). Captain's HF token is stored in a
Modal secret (`hf-token`) — never in git.

### 06 · Documentation
Created `docs/development-log.md` (this file), `docs/decisions.md`, and
`docs/RUNBOOK.md`; README now points to them.
