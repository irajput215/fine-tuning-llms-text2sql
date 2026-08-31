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

### 07 · Modal integration debugging saga
Integrated Modal (SDK 1.5.5) and hit a chain of doc/release mismatches,
each diagnosed from the installed package: Mount moved/removed (P5a–c),
local_entrypoint CLI flags rejected (P5d), include_source mounts only the app
file (P5e), plus the secret-name mismatch (P6) and the vLLM KV-cache OOM
(P7). All documented in `docs/PROBLEMS.md` with fixes + evidence. State: the
baseline run reaches generation after the max_model_len cap; volume-based
repo mount works end to end.

### 08 · First baseline captured — the X%
Modal run `baseline-zeroshot-200` succeeded end to end (after the P7/P9 fixes):
**zero-shot Llama 3.1 8B → 60.5% execution accuracy** (n=200, greedy),
29.0% exact match. Feature stratification: aggregation 68.97%, set-op 53.33%,
join 45.83%, subquery 37.14%. Difficulty labels pending (HF rows carry none;
official dev.json via --difficulty-json). Summary saved to the volume and
copied to `analysis/baseline-zeroshot-200.json`. Documented in
`docs/RESULTS.md`.

### 09 · Few-shot baseline — flat exec, better exact-match
Ran `baseline-fewshot-200` (2 in-context examples): **execution accuracy
60.0%** (vs 60.5% zero-shot — noise), **exact match 34.5%** (vs 29.0% — up
5.5). Per-feature: subquery +2.9, join −6.3, aggregation −4.3, set-op flat.
Interpretation: 2 shots change SQL *style* (better string match) but not
*correctness*; fine-tuning, not prompting, is the expected lever. Summaries
saved to the volume + `analysis/`. RESULTS.md updated with the comparison.

### 10 · Fine-tuning SUCCESS — the claim
QLoRA run1 (r=16, 2 epochs, 1576 steps, 2h23m, A10G) converged (train loss
0.0255) and saved checkpoints 500/1000/1500/1576 to the volume. The
checkpoint-selection eval crashed ("expected 3, got 2" — generate() needs the
3-tuple, evaluate_checkpoint passed a 2-tuple; fixed + full tracebacks in the
catch). Added `eval_checkpoint` modal fn (4-bit base + PeftModel, split option).
Results: **fine-tuned test exec 68.0% (n=200) vs zero-shot baseline 60.5% —
+7.5 pts on the same test set.** Val n=50: 72.0%.


### 11 · FULL test set — the final claim
eval-checkpoint-1576 on the complete 1,034-example test set:
**execution accuracy 73.89%** (34 min, ~$0.35). Container MLflow auto-logging
created the volume's mlflow.db + experiment (verified — now pullable for local
UI browsing). Ledger + RESULTS.md updated. Remaining for a same-sample delta:
full-set zero-shot baseline run (vLLM).


### 12 · Full-set zero-shot baseline — the airtight delta
Zero-shot baseline on the full 1,034 test set (vLLM): **67.89%** exec (exact
32.5%). Same-sample full-set claim: **67.89% → 73.89% (+6.0 points)**.
By-feature: aggregation 69.4%, join 59.1%, set-op 43.8%, subquery 43.4%.
Saved to runs/baseline-zeroshot-1034.json; ledger + RESULTS.md updated.

### 13 · Error analysis first pass + ablation decision
Rows-enabled eval (n=1,034) produced per-row results. First-pass analysis:
**270 failures (26.1%)** — 83% executed-but-wrong-result, 16% syntax/exec
errors, ~1% gold-query errors; failure features dominated by join (154) and
aggregation (139). 50-example dump in `analysis/failures.md` for the manual
bucketing pass. Decision D9: claim fixed on run1 (67.89 → 73.89); rank-32
ablation (run2) de-scoped (checkpoints saved, out of the write-up).
