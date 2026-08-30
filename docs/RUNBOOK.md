# RUNBOOK — from checkout to results

Everything you need to reproduce the project on Modal. Assumes:
`~/llama33-text2sql`, Modal CLI installed (`uv add modal` done), and the
**Meta Llama license accepted** on Hugging Face with a read token.

## 1. One-time setup

```sh
cd ~/llama33-text2sql

# Modal login (browser)
modal token new

# Store the HF token as a Modal secret (never in git)
modal secret create huggingface-secret HF_TOKEN="hf_..."   # already done by the captain

# (Optional, local) install the full ML stack
uv sync
```

## 2. Stage the data (already done — re-run only if data changes)

```sh
uv run python data_prep/stage_spider.py --out data/processed
# -> data/processed/{train,val,test}.jsonl  (6300 / 700 / 1034)

# Fetch the SQLite databases (already downloaded; script does it via gdown)
uv run python data_prep/stage_spider.py --out data/processed --fetch-databases
```

## 3. Push the repo to a Modal volume (once + after each code change)

Modal 1.5.5 no longer accepts `mounts=` on functions, so the repo (code +
data) rides on a volume:

```sh
modal volume create llama33-repo      # once (errors if it already exists — fine)
modal volume put llama33-repo training   /repo/training
modal volume put llama33-repo eval       /repo/eval
modal volume put llama33-repo data_prep  /repo/data_prep
modal volume put llama33-repo data       /repo/data
```

## 4. Validate the harness locally (no model, no GPU)

```sh
uv run python eval/run_eval.py \
    --test-jsonl data/processed/test.jsonl \
    --db-dir data/spider/spider_data/database \
    --gold-mode --max-examples 60
# Expect: execution accuracy 100% (gold vs gold) — proves the plumbing
```

## 5. Baseline — zero-shot

```sh
modal run modal_app.py::run_baseline \
    --model meta-llama/Llama-3.1-8B-Instruct --max-examples 200
# small first: validates image build, model download, generation, harness
```

Then the full test set:

```sh
modal run modal_app.py::run_baseline \
    --model meta-llama/Llama-3.1-8B-Instruct
```

## 6. Baseline — few-shot (stronger X%)

```sh
modal run modal_app.py::run_baseline \
    --model meta-llama/Llama-3.1-8B-Instruct --few-shot 2 --max-examples 200
modal run modal_app.py::run_baseline \
    --model meta-llama/Llama-3.1-8B-Instruct --few-shot 2
```

## 7. QLoRA fine-tuning

```sh
modal run modal_app.py::run_train \
    --model meta-llama/Llama-3.1-8B-Instruct --epochs 2 --rank 16

# ablation: rank 32, or 3 epochs
modal run modal_app.py::run_train \
    --model meta-llama/Llama-3.1-8B-Instruct --epochs 2 --rank 32
```

## 8. Where the outputs are

- **Baseline summaries** — `llama33-runs` Modal volume (`baseline.json`), plus
  printed on the run.
- **Checkpoints** — `llama33-runs/checkpoints/<run>/`, with `best.txt` naming
  the best-by-validation-exec checkpoint.
- **Local copies** — `modal volume ls llama33-runs` and
  `modal volume get llama33-runs <path>` to pull them down.

## 9. Next after training

1. **Test the best checkpoint** (touch test exactly once): run the eval
   harness with the fine-tuned adapter (post-merge: the train script's
   `evaluate_checkpoint` is the pattern; a `--checkpoint` eval path lands in
   `eval/`).
2. **Ablations + error analysis** (`analysis/`): rank 16 vs 32, failure
   bucketing from `data/results.json` rows.
3. **Results table** into `README.md` — baseline vs fine-tuned, stratified by
   difficulty and SQL feature.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `modal run` fails at model load | Accept the Meta license on HF for that model id; check the secret exists (`modal secret list`) |
| First run very slow | Image build (~5–10 min) + ~16GB model download — once, then cached |
| `400` on image build deps | Free-tier GPU/image limits; check `modal profile` plan |
| Harness gold-mode < 100% | Database mismatch — verify `--db-dir` points at `spider_data/database` |
| OOM on A10G | Lower `--batch-size`, or drop `--max-length` to 1536 |
| vLLM KV-cache OOM (`max seq len 131072`) | Already fixed: `max_model_len=8192` in `run_baseline.py` — cap it, never let vLLM size KV off the model's full 131k |
| FlashInfer `Could not find nvcc` | Already fixed: `VLLM_USE_FLASHINFER_SAMPLER=0` in `run_baseline.py` — native sampler, no CUDA toolkit needed |
