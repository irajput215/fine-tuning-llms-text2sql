# Portfolio & Interview Guide — llama33-text2sql

Everything here is **true of the code in this repo** and backed by real runs.
Use these numbers in resumes and interviews; never claim what is not here.

## Verified facts (memorize these)

| Fact | Value |
|---|---|
| Dataset | Spider, ~10k question/SQL pairs, 166+ databases |
| Splits | train 6,300 / val 700 / **test 1,034** (Spider dev, held out) |
| Model | meta-llama/Llama-3.1-8B-Instruct |
| Method | QLoRA, 4-bit NF4 + double quant, rank 16 / alpha 32, q/k/v/o_proj |
| Training | 2 epochs, 1,576 steps, batch 2 (accum 4), lr 2e-4, cosine |
| Zero-shot baseline (full test) | **67.89%** exec, 32.5% exact |
| **Fine-tuned (full test)** | **73.89%** exec — **+6.0 points** |
| Same-sample n=200 | 60.5% → 68.0% |
| Few-shot (n=200) | 60.0% exec, 34.5% exact (style up, correctness flat) |
| Val (n=50) | 72.0% (consistent direction) |
| Failure rate (fine-tuned) | 26.1% — 83% wrong-result, 16% syntax, ~1% gold-error |
| Training runtime / cost | ~2h20m, ~$1.40 on Modal A10G |
| Tracking | MLflow (7 runs) + `runs/` ledger |

## Resume bullets

- **Fine-tuned Llama 3.1 8B with QLoRA on the Spider text-to-SQL benchmark,
  improving execution accuracy from 67.89% (zero-shot baseline) to 73.89% on
  the identical 1,034-example test set** — proven by an automatic
  execution-based harness (SQL executed against real SQLite databases,
  result-set comparison, no LLM-as-judge).
- Built a **medallion-style data pipeline** for the benchmark: chat-template
  formatting with schema + primary/foreign keys, token-overlap schema linking,
  strict train/val/test discipline (test touched once).
- Engineered the **evaluation harness**: execution accuracy + exact-match,
  stratified by SQL feature (joins/aggregations/subqueries/set-ops); used for
  baselines, checkpoint selection, and final reporting.
- **QLoRA fine-tuning pipeline** on serverless GPU (Modal): 4-bit NF4, LoRA
  on attention projections, completion-only supervision, validation-driven
  checkpoint selection, MLflow + ledger experiment tracking.
- **Diagnosed and fixed 13 real production issues** (docs/PROBLEMS.md) —
  framework version drift, GPU memory sizing, tooling staleness — each with
  root cause and evidence.

## Interview Q&A — every failure and code change

### The debugging saga (P1–P13) — "tell me about a hard problem"

Use these as your war stories. For each: symptom → root cause → fix → evidence.

| # | Failure | Root cause | Fix |
|---|---|---|---|
| P1 | HF split `dev` not found | mirror names it `validation` | use `validation` |
| P2 | no schema in example dataset | schema lives in a separate dataset | `richardr1126/spider-schema` (schema + PK/FK) |
| P3 | every schema "unavailable" | test flag sliced the schema map | load full schema map always |
| P4 | Google Drive 404 for databases | stale file ID | real ID from the official page |
| P5 | Modal SDK API drift (×5) | docs vs installed release (1.5.5) | read the installed package; `Mount`→volume, function-ref CLI, `Image.add_local_dir(copy=True)` |
| P6 | secret name mismatch | captain followed the quickstart name | align app to existing secret |
| P7 | vLLM KV-cache OOM | 131k max-seq wants 16GB cache on 24GB | `max_model_len=8192` |
| P8 | stale command path | app moved to repo root | document new path |
| P9 | FlashInfer needs nvcc | JIT sampler; no CUDA toolkit in image | `VLLM_USE_FLASHINFER_SAMPLER=0` |
| P10 | TRL collator gone | removed in recent TRL | custom 20-line completion collator |
| P11 | training ran 1 step | `max_steps` semantics (None rejected, 0 stops) | `max_steps=-1` |
| P12 | checkpoint eval crashed | `generate()` needs the 3-tuple | pass `(kind, model, tokenizer)` |
| P13 | container ran stale code | Modal volume snapshot semantics | code baked into the image |

**The one-liner that ties it together:** *"The pattern in every fix was: when
the tool's docs and its installed release disagree, read the installed source
— and when infrastructure serves stale state, make code immutable in the
image."*

### Design questions — expect these

- **Why execution accuracy over LLM-as-judge?** Reproducible, no judge
  variance, benchmark-standard; exact-match as a stricter secondary.
- **Why QLoRA?** Full fine-tuning of 8B needs ~60GB; QLoRA (4-bit NF4 + LoRA)
  trains 0.17% of params on 24GB with ~1% quality loss vs full FT at this
  scale — the standard cost/quality tradeoff.
- **Why 8B, not Llama 3.3 (70B)?** Same methodology on a 24GB GPU; the 70B is
  a config change (`gpu="A100-80GB"`), documented as the scale-up run. The
  claim doesn't depend on model size.
- **Why rank 16, alpha 32, 2 epochs?** Standard QLoRA starting point (2×rank);
  1,576 steps converged (loss 0.0255); checkpoint selection by val-exec guards
  overfitting.
- **How do you know it didn't overfit?** Val exec is the selector, not loss;
  the final-step checkpoint scored 73.89% on held-out test — plus the error
  analysis shows structured failures (joins), not memorized trainset.
- **Why does few-shot underperform?** 2 examples changed SQL *style* (exact
  match +5.5) but not *correctness* (exec flat) — prompting doesn't carry
  schema/join structure; fine-tuning does. Genuinely useful finding.
- **Where does it still fail?** 26.1%: 83% wrong-result, dominated by joins
  and aggregations — the natural next lever (better schema linking,
  more/diverse training data, higher rank).
- **What would you do next?** difficulty-stratified reporting (official
  labels), best-checkpoint selection re-run, rank-32 ablation, 70B scale-up,
  per-row error bucketing (dump is ready).
- **What did the 70B story teach you about cost?** 8B QLoRA on A10G ≈ $1.40
  per run; full pipeline (baselines + train + evals) ≈ $5 total — you can
  build a real ML story for single-digit dollars.

### Do-not-claim list

- Watermarking / real-time streaming — not in this project
- Multi-GPU / distributed training — single A10G
- Full parameter fine-tuning — QLoRA only (0.17% trainable)
- The best-checkpoint number — we scored the final-step checkpoint
  (selection loop is fixed and ready, not yet re-run)
- Difficulty-stratified results — labels pending (feature stratification done)

### Demo tips

- Show `uv run mlflow ui` with the 7 runs — instant credibility.
- Walk the eval harness on 5 gold-mode examples (100%) then 5 real ones.
- Explain P13 (stale volume → image-baked code) as the architecture story.
- Have `docs/PROBLEMS.md` + `runs/RUNS.md` open — evidence beats claims.
