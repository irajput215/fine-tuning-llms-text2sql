#!/usr/bin/env python3
"""
modal_app.py — run the baseline and QLoRA training on Modal.

Prereqs:
  modal secret create huggingface-secret HF_TOKEN="hf_..."  # once (already created)
  modal token new                                     # once (browser login)

Usage:
  modal run training/modal_app.py baseline \
      --model meta-llama/Llama-3.1-8B-Instruct --max-examples 200 --few-shot 2
  modal run training/modal_app.py baseline --model meta-llama/Llama-3.1-8B-Instruct
  modal run training/modal_app.py train \
      --model meta-llama/Llama-3.1-8B-Instruct --epochs 2 --rank 16

Outputs land on the `llama33-runs` volume (and the returned summary prints).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import modal

REPO = Path(__file__).resolve().parents[1]

IMAGE_DEPS = [
    "torch", "transformers>=4.46", "peft", "bitsandbytes", "trl", "accelerate",
    "datasets", "evaluate", "vllm", "huggingface_hub", "sentencepiece",
    "mlflow", "scikit-learn",
]

image = modal.Image.debian_slim(python_version="3.12").pip_install(IMAGE_DEPS)
app = modal.App("llama33-text2sql", image=image)
volume = modal.Volume.from_name("llama33-runs", create_if_missing=True)

# Mount the repo (data/spider databases included — the zip excluded to save
# upload). Read-only at runtime; outputs go to the volume.
def _mount_condition(path: Path) -> bool:
    return not (path.name == "spider_databases.zip" or ".git" in path.parts)

mount = modal.Mount.from_local_dir(REPO, remote_path="/repo", condition=_mount_condition)

COMMON = dict(
    image=image,
    mounts=[mount],
    volumes={"/runs": volume},
    secrets=[modal.Secret.from_name("huggingface-secret")],  # captain-created secret (HF_TOKEN key)
    retries=0,
)


@app.function(gpu="A10G", timeout=10800, **COMMON)
def run_baseline(model: str, max_examples: int | None, few_shot: int,
                 out_name: str) -> dict:
    os.chdir("/repo")
    sys.path.insert(0, "/repo")
    from training.run_baseline import run_baseline

    summary = run_baseline(
        model,
        Path("data/processed/test.jsonl"),
        Path("data/spider/spider_data/database"),
        Path("data/processed/train.jsonl"),
        max_examples, few_shot,
    )
    path = f"/runs/{out_name}"
    with open(path, "w") as fh:
        fh.write(json.dumps(summary, indent=1))
    volume.commit()
    return summary


@app.function(gpu="A10G", timeout=10800, **COMMON)
def run_train(model: str, epochs: int, rank: int, lr: float, batch_size: int,
              max_length: int, max_steps: int | None, out_name: str) -> dict:
    os.chdir("/repo")
    sys.path.insert(0, "/repo")
    from training.train_qlora import train_qlora

    save_dir = Path(f"/runs/checkpoints/{out_name}")
    train_qlora(
        model,
        Path("data/processed/train.jsonl"),
        Path("data/processed/val.jsonl"),
        Path("data/spider/spider_data/database"),
        epochs, rank, rank * 2, lr, batch_size, max_length, 0, save_dir,
        val_every_steps=500, max_steps=max_steps,
    )
    volume.commit()
    best = (save_dir / "best.txt").read_text() if (save_dir / "best.txt").exists() else "?"
    return {"best": best, "checkpoints": save_dir}


@app.local_entrypoint()
def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)

    b = sub.add_parser("baseline")
    b.add_argument("--model", required=True)
    b.add_argument("--max-examples", type=int, default=None)
    b.add_argument("--few-shot", type=int, default=0)
    b.add_argument("--out-name", default="baseline.json")

    t = sub.add_parser("train")
    t.add_argument("--model", required=True)
    t.add_argument("--epochs", type=int, default=2)
    t.add_argument("--rank", type=int, default=16)
    t.add_argument("--lr", type=float, default=2e-4)
    t.add_argument("--batch-size", type=int, default=2)
    t.add_argument("--max-length", type=int, default=2048)
    t.add_argument("--max-steps", type=int, default=None)
    t.add_argument("--out-name", default="run1")

    args = ap.parse_args()
    if args.mode == "baseline":
        print(run_baseline.remote(args.model, args.max_examples, args.few_shot,
                                  args.out_name))
    else:
        print(run_train.remote(args.model, args.epochs, args.rank, args.lr,
                               args.batch_size, args.max_length, args.max_steps,
                               args.out_name))
