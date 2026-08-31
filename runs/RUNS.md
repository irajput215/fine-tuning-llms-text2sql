# RUNS — experiment ledger

Every training / evaluation run, durably recorded. JSON copies live next to
this file; MLflow (local) can be used for interactive views (`uv run mlflow ui`).

## Run table

| Run | Split | n | Execution acc. | Exact match | Notes |
|---|---|---|---|---|---|
| baseline-zeroshot-200 | test | 200 | 60.5% | 29.0% | base Llama 3.1 8B, greedy, zero-shot |
| **baseline-zeroshot-1034** | test | **1,034** | **67.89%** | 32.5% | full test set — the same-sample baseline |
| baseline-fewshot-200 | test | 200 | 60.0% | 34.5% | 2 in-context examples |
| train-run1 | train (6300) / val (700) | — | — | — | QLoRA r=16, 2 epochs, 1,576 steps |
| eval-run1-val50 | val | 50 | 72.0% | — | checkpoint-1576 |
| eval-run1-test200 | test | 200 | 68.0% | — | checkpoint-1576 |
| **eval-run1-test1034** | test | **1,034** | **73.89%** | — | **checkpoint-1576 — the final claim** |

## Claim

> Fine-tuned Llama 3.1 8B with QLoRA on Spider, improving execution accuracy
> from **67.89%** (zero-shot baseline) to **73.89%** (fine-tuned) on the
> identical 1,034-example test set (+6.0 points), via an automatic
> execution-based harness. (n=200: 60.5% → 68.0%.)

## train-run1 metadata

| Field | Value |
|---|---|
| Model | meta-llama/Llama-3.1-8B-Instruct |
| Method | QLoRA (4-bit NF4, double quant) |
| Target modules | q/k/v/o_proj |
| rank / alpha | 16 / 32 |
| lr / scheduler | 2e-4 / cosine (no warmup) |
| epochs / steps | 2 / 1,576 |
| Batch | 2 (grad accum 4 → effective 8) |
| Max length | 2,048 |
| Train loss (final) | 0.0255 |
| Runtime | 8,421 s (~2h20m) |
| GPU | Modal A10G |
| Est. cost | ~$1.40 |
| Modal app | `ap-yMFbGnoyfYD8W6sbDIRmxD` |
| Checkpoints | volume `llama33-runs/checkpoints/run1/` (500/1000/1500/1576) |
| Selection | pending best-by-val-exec re-run (loop fixed; final-step checkpoint scored here) |

## How to reproduce

```sh
modal run modal_app.py::run_train --model meta-llama/Llama-3.1-8B-Instruct --epochs 2 --rank 16
modal run modal_app.py::eval_checkpoint \
    --model meta-llama/Llama-3.1-8B-Instruct \
    --checkpoint-dir /runs/checkpoints/run1/checkpoint-1576 \
    --max-rows 200 --split test
```

## Ablation note (decision D9)

A rank-32 QLoRA run (run2) was launched but de-scoped by decision: the run1
claim (67.89% → 73.89%) stands as the project's result. run2's checkpoints
remain on the volume (`checkpoints/run2`) but are not part of the write-up.

## Storage tools

- **This ledger + JSON files** — durable, git-tracked, portable (interview-ready).
- **MLflow** — sqlite store (`mlruns/mlflow.db`, gitignored); browse with
  `uv run mlflow ui --backend-store-uri sqlite:///mlruns/mlflow.db`. Container
  runs log to the Modal volume (`sqlite:////runs/mlflow.db`) — pull with
  `modal volume get llama33-runs mlflow.db ./mlruns/mlflow.db` **after the next
  run creates it**.
- **Modal volume** — raw artifacts (checkpoints, eval JSONs) live on
  `llama33-runs`; `modal volume get` to pull.
