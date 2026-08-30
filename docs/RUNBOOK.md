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

## 3. Validate the harness locally (no model, no GPU)

```sh
uv run python eval/run_eval.py \
    --test-jsonl data/processed/test.jsonl \
    --db-dir data/spider/spider_data/database \
    --gold-mode --max-examples 60
# Expect: execution accuracy 100% (gold vs gold) — proves the plumbing
```

## 4. Baseline — zero-shot

```sh
modal run training/modal_app.py baseline \
    --model meta-llama/Llama-3.1-8B-Instruct --max-examples 200
# small first: validates image build, model download, generation, harness
```

Then the full test set:

```sh
modal run training/modal_app.py baseline \
    --model meta-llama/Llama-3.1-8B-Instruct
```

## 5. Baseline — few-shot (stronger X%)

```sh
modal run training/modal_app.py baseline \
    --model meta-llama/Llama-3.1-8B-Instruct --few-shot 2 --max-examples 200
modal run training/modal_app.py baseline \
    --model meta-llama/Llama-3.1-8B-Instruct --few-shot 2
```

## 6. QLoRA fine-tuning

```sh
modal run training/modal_app.py train \
    --model meta-llama/Llama-3.1-8B-Instruct --epochs 2 --rank 16

# ablation: rank 32, or 3 epochs
modal run training/modal_app.py train \
    --model meta-llama/Llama-3.1-8B-Instruct --epochs 2 --rank 32
```

## 7. Where the outputs are

- **Baseline summaries** — `llama33-runs` Modal volume (`baseline.json`), plus
  printed on the run.
- **Checkpoints** — `llama33-runs/checkpoints/<run>/`, with `best.txt` naming
  the best-by-validation-exec checkpoint.
- **Local copies** — `modal volume ls llama33-runs` and
  `modal volume get llama33-runs <path>` to pull them down.

## 8. Next after training

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
