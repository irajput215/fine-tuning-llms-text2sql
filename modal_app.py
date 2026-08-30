#!/usr/bin/env python3
"""
modal_app.py — run the baseline and QLoRA training on Modal.

Code and data are baked into the IMAGE (immutable per deploy — no stale
volume snapshots); outputs/checkpoints land on the llama33-runs volume.

Prereqs (once):
  modal token new
  modal secret create huggingface-secret HF_TOKEN="hf_..."   # captain-created

Usage (Modal SDK 1.5.5 — function refs, options from signatures):
  modal run modal_app.py::run_baseline \
      --model meta-llama/Llama-3.1-8B-Instruct --max-examples 200
  modal run modal_app.py::run_baseline \
      --model meta-llama/Llama-3.1-8B-Instruct --few-shot 2
  modal run modal_app.py::run_train \
      --model meta-llama/Llama-3.1-8B-Instruct --epochs 2 --rank 16
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import modal

REPO = Path(__file__).resolve().parent

IMAGE_DEPS = [
    "torch", "transformers>=4.46", "peft", "bitsandbytes", "trl", "accelerate",
    "datasets", "evaluate", "vllm", "huggingface_hub", "sentencepiece",
    "mlflow", "scikit-learn",
]

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(IMAGE_DEPS)
    # Code is baked into the IMAGE (immutable per deploy) — the volume's
    # snapshot semantics served stale code on fresh runs. Data rides along;
    # outputs/checkpoints still go to the volume.
    .copy_local_dir(str(REPO / "training"), "/repo/training")
    .copy_local_dir(str(REPO / "eval"), "/repo/eval")
    .copy_local_dir(str(REPO / "data_prep"), "/repo/data_prep")
    .copy_local_dir(str(REPO / "data"), "/repo/data")
)
app = modal.App("llama33-text2sql", image=image)
volume = modal.Volume.from_name("llama33-runs", create_if_missing=True)
SECRET = modal.Secret.from_name("huggingface-secret")  # HF_TOKEN key

COMMON = dict(
    image=image,
    volumes={"/runs": volume},
    secrets=[SECRET],
    retries=0,
)


def _repo_setup() -> None:
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    os.chdir("/repo")
    sys.path.insert(0, "/repo")


@app.function(gpu="A10G", timeout=10800, **COMMON)
def run_baseline(model: str, max_examples: int = 0, few_shot: int = 0,
                 out_name: str = "baseline.json") -> dict:
    """Zero/few-shot baseline on the base model, evaluated by the harness."""
    _repo_setup()
    from training.run_baseline import run_baseline as _run

    max_examples = max_examples or None
    summary = _run(
        model,
        Path("data/processed/test.jsonl"),
        Path("data/spider/spider_data/database"),
        Path("data/processed/train.jsonl"),
        max_examples, few_shot,
    )
    with open(f"/runs/{out_name}", "w") as fh:
        fh.write(json.dumps(summary, indent=1))
    volume.commit()
    return summary


@app.function(gpu="A10G", timeout=10800, **COMMON)
def run_train(model: str, epochs: int = 2, rank: int = 16, lr: float = 2e-4,
              batch_size: int = 2, max_length: int = 2048,
              max_steps: int = 0, out_name: str = "run1") -> dict:
    """QLoRA fine-tune; best checkpoint by val exec accuracy."""
    _repo_setup()
    import hashlib

    tq = Path("/repo/training/train_qlora.py")
    print("FINGERPRINT sha256:", hashlib.sha256(tq.read_bytes()).hexdigest()[:12])
    print("FINGERPRINT line56:", tq.read_text().splitlines()[55][:60])

    from training.train_qlora import train_qlora

    save_dir = Path(f"/runs/checkpoints/{out_name}")
    train_qlora(
        model,
        Path("data/processed/train.jsonl"),
        Path("data/processed/val.jsonl"),
        Path("data/spider/spider_data/database"),
        epochs, rank, rank * 2, lr, batch_size, max_length, 0, save_dir,
        val_every_steps=500, max_steps=max_steps or None,
    )
    volume.commit()
    best = (save_dir / "best.txt").read_text() if (save_dir / "best.txt").exists() else "?"
    return {"best": best, "checkpoints": str(save_dir)}
