#!/usr/bin/env python3
"""
train_qlora.py — QLoRA fine-tuning with TRL SFTTrainer + val checkpointing.

Environment-agnostic (Modal / RunPod / Colab). Trains on the staged train
split, saves the checkpoint with the BEST validation execution accuracy
(reusing the eval harness on a val sample), and logs everything to MLflow.

Usage (Modal):  modal run training/modal_app.py train --model ...
Usage (bare):   python training/train_qlora.py --model meta-llama/Llama-3.1-8B-Instruct
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eval.run_eval import (  # noqa: E402
    execute_sql, execution_accuracy, render_table,
)
from training.run_baseline import load_rows, build_prompt, generate, load_generator  # noqa: E402

DEFAULT_TARGET_MODULES = ["q_proj", "k_proj", "v_proj", "o_proj"]


def evaluate_checkpoint(model, tokenizer, val_rows, db_dir, few_shot,
                        max_rows: int = 100) -> float:
    """Execution accuracy on a val sample (prompts built from staged rows)."""
    sample = val_rows[:max_rows]
    correct = 0
    for row in sample:
        prompt = build_prompt(row, few_shot, [])
        pred = generate("transformers", (model, tokenizer), prompt)
        db = db_dir / row["db_id"] / f"{row['db_id']}.sqlite"
        gold_rows, _ = execute_sql(db, row["query"])
        pred_rows, _ = execute_sql(db, pred)
        acc, ok = execution_accuracy(gold_rows, pred_rows)
        correct += int(acc == 1.0 and ok)
    return correct / len(sample)


def train_qlora(model_id: str, train_path: Path, val_path: Path, db_dir: Path,
                epochs: int, rank: int, alpha: int, lr: float, batch_size: int,
                max_length: int, few_shot: int, save_dir: Path,
                val_every_steps: int, max_steps: int | None) -> None:
    import torch
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model
    from transformers import (
        AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig,
        TrainingArguments, Trainer, DataCollatorForLanguageModeling,
    )
    from trl import SFTTrainer, DataCollatorForCompletionOnlyLM

    os.environ.setdefault("HF_TOKEN", "")

    tokenizer = AutoTokenizer.from_pretrained(model_id, token=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    bnb = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)
    model = AutoModelForCausalLM.from_pretrained(
        model_id, quantization_config=bnb,
        torch_dtype=torch.bfloat16, device_map="auto", token=True)

    lora = LoraConfig(
        r=rank, lora_alpha=alpha, target_modules=DEFAULT_TARGET_MODULES,
        lora_dropout=0.05, bias="none", task_type="CAUSAL_LM")
    model = get_peft_model(model, lora)
    model.print_trainable_parameters()

    rows = load_rows(train_path, max_steps)  # NOTE: max_steps used as row cap here
    ds = Dataset.from_list([{"text": r["text"]} for r in rows])
    val_rows = load_rows(val_path, None)

    # Only supervise the assistant (gold SQL) section of each chat example.
    response_template = "<|start_header_id|>assistant<|end_header_id|>\n\n"
    collator = DataCollatorForCompletionOnlyLM(
        response_template=response_template, tokenizer=tokenizer)

    args = TrainingArguments(
        output_dir=str(save_dir), num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=4,
        learning_rate=lr, lr_scheduler_type="cosine",
        warmup_ratio=0.05, logging_steps=10, save_strategy="steps",
        save_steps=val_every_steps, evaluation_strategy="no",
        bf16=True, report_to="mlflow", remove_unused_columns=False,
    )

    trainer = SFTTrainer(
        model=model, args=args, train_dataset=ds,
        tokenizer=tokenizer, data_collator=collator,
        max_seq_length=max_length,
    )
    trainer.train()

    # Best-checkpoint selection: eval each saved checkpoint on the val sample.
    best_acc, best_dir = -1.0, None
    for ckpt in sorted((save_dir).glob("checkpoint-*")):
        acc = evaluate_checkpoint(model, tokenizer, val_rows, db_dir, few_shot)
        print(f"checkpoint {ckpt.name}: val exec={acc:.2%}")
        if acc > best_acc:
            best_acc, best_dir = acc, ckpt
    print(f"BEST checkpoint: {best_dir} ({best_acc:.2%})")
    (save_dir / "best.txt").write_text(f"{best_dir}\n{best_acc:.4f}\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--train-jsonl", type=Path, default=Path("data/processed/train.jsonl"))
    ap.add_argument("--val-jsonl", type=Path, default=Path("data/processed/val.jsonl"))
    ap.add_argument("--db-dir", type=Path, default=Path("data/spider/spider_data/database"))
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--rank", type=int, default=16)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--batch-size", type=int, default=2)
    ap.add_argument("--max-length", type=int, default=2048)
    ap.add_argument("--few-shot", type=int, default=0)
    ap.add_argument("--val-every-steps", type=int, default=500)
    ap.add_argument("--max-steps", type=int, default=None,
                    help="cap training rows (dev) or steps")
    ap.add_argument("--save-dir", type=Path, default=Path("/runs/checkpoints"))
    args = ap.parse_args()
    train_qlora(
        args.model, args.train_jsonl, args.val_jsonl, args.db_dir,
        args.epochs, args.rank, args.rank * 2, args.lr, args.batch_size,
        args.max_length, args.few_shot, args.save_dir,
        args.val_every_steps, args.max_steps)


if __name__ == "__main__":
    main()
