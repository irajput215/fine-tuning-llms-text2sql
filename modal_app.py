#!/usr/bin/env python3
"""
modal_app.py — run the baseline and QLoRA training on Modal.

Prereqs (once):
  modal token new
  modal secret create huggingface-secret HF_TOKEN="hf_..."   # captain-created

Usage (Modal SDK 1.5.5 — call functions directly; options are generated from
the function signatures):

  modal run modal_app.py::run_baseline \
      --model meta-llama/Llama-3.1-8B-Instruct --max-examples 200
  modal run modal_app.py::run_baseline \
      --model meta-llama/Llama-3.1-8B-Instruct --few-shot 2
  modal run modal_app.py::run_train \
      --model meta-llama/Llama-3.1-8B-Instruct --epochs 2 --rank 16

Outputs land on the `llama33-runs` volume (and the returned summary prints).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import modal

# NOTE (Modal SDK 1.5.5): local-dir Mount() is removed — the repo is carried
# by include_source (App default True), which mounts THIS directory (the repo
# root) at /root/ inside the container.
IMAGE_DEPS = [
    "torch", "transformers>=4.46", "peft", "bitsandbytes", "trl", "accelerate",
    "datasets", "evaluate", "vllm", "huggingface_hub", "sentencepiece",
    "mlflow", "scikit-learn",
]

image = (
    modal.Image.from_registry(
        "nvidia/cuda:12.4.0-devel-ubuntu22.04", add_python="3.12"
    )
    .pip_install(IMAGE_DEPS)
)
app = modal.App("llama33-text2sql", image=image)
volume = modal.Volume.from_name("llama33-runs", create_if_missing=True)
repo_volume = modal.Volume.from_name("llama33-repo", create_if_missing=True)
SECRET = modal.Secret.from_name("huggingface-secret")  # HF_TOKEN key

COMMON = dict(
    image=image,
    volumes={"/runs": volume, "/repo": repo_volume},
    secrets=[SECRET],
    retries=0,
)


def _repo_setup() -> None:
    # The repo rides on the llama33-repo volume (include_source only mounts
    # this app file in 1.5.5):
    #   modal volume put llama33-repo training /repo/training
    #   modal volume put llama33-repo eval     /repo/eval
    #   modal volume put llama33-repo data_prep /repo/data_prep
    #   modal volume put llama33-repo data     /repo/data
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
    """QLoRA fine-tune with SFTTrainer; best checkpoint by val exec accuracy."""
    _repo_setup()
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
