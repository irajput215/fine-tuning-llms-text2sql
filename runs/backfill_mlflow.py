#!/usr/bin/env python3
"""
backfill_mlflow.py — import the existing run records into a local MLflow
store so `uv run mlflow ui` shows the full history today (before future runs
auto-log from the containers).

Usage:
    uv run python runs/backfill_mlflow.py
    uv run mlflow ui   # browse at http://localhost:5000
"""
from __future__ import annotations

import json
from pathlib import Path

import mlflow

RUNS = Path(__file__).resolve().parent
mlflow.set_tracking_uri(f"sqlite:///{(RUNS.parent / 'mlruns' / 'mlflow.db').resolve()}")
mlflow.set_experiment("llama33-text2sql")

RECORDS = {
    "baseline-zeroshot-200.json": ("baseline-zero-shot", "baseline"),
    "baseline-fewshot-200.json": ("baseline-few-shot", "baseline"),
    "eval-run1-val50.json": ("eval-run1-val50", "eval"),
    "eval-run1-test200.json": ("eval-run1-test200", "eval"),
    "eval-run1-test1034.json": ("eval-run1-test1034", "eval"),
}
# Manual metadata for the training run (no JSON summary was saved).
TRAIN_RUN = {
    "params": {"model": "meta-llama/Llama-3.1-8B-Instruct", "method": "QLoRA",
               "rank": 16, "alpha": 32, "lr": 2e-4, "epochs": 2,
               "batch_size": 2, "max_length": 2048,
               "target_modules": "q,k,v,o_proj", "steps": 1576},
    "metrics": {"train_loss": 0.0255, "train_runtime_s": 8421.0},
}


def main() -> None:
    logged = 0
    for fname, (run_name, _kind) in RECORDS.items():
        path = RUNS / fname
        if not path.exists():
            print(f"skip {fname} (missing)")
            continue
        data = json.loads(path.read_text())
        with mlflow.start_run(run_name=run_name):
            mlflow.log_params({"source": fname})
            for k, v in data.items():
                if isinstance(v, (int, float)):
                    mlflow.log_metric(k, float(v))
                else:
                    mlflow.log_param(k, str(v))
            logged += 1
        print(f"logged {fname}")
    with mlflow.start_run(run_name="train-run1"):
        mlflow.log_params(TRAIN_RUN["params"])
        mlflow.log_metrics(TRAIN_RUN["metrics"])
        logged += 1
    print(f"done — {logged} runs in {mlflow.get_tracking_uri()}\n"
          "browse with: uv run mlflow ui")


if __name__ == "__main__":
    main()
