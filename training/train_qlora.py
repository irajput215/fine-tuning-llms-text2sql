#!/usr/bin/env python3
"""
train_qlora.py — QLoRA fine-tuning with transformers Trainer + val checkpointing.

Environment-agnostic (Modal / RunPod / Colab). Trains on the staged train
split, saves checkpoints, and selects the one with the BEST validation
execution accuracy (reusing the eval harness on a val sample).

Uses plain `transformers.Trainer` + a small completion-only collator
(masks everything before the assistant SQL section), avoiding TRL version
drift (`DataCollatorForCompletionOnlyLM` was removed from recent TRL).

Usage (Modal):  modal run modal_app.py::run_train --model ...
Usage (bare):   python training/train_qlora.py --model meta-llama/Llama-3.1-8B-Instruct
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eval.run_eval import (  # noqa: E402
    execute_sql, execution_accuracy, exact_match, classify_features,
)
from training.run_baseline import build_prompt, generate  # noqa: E402

DEFAULT_TARGET_MODULES = ["q_proj", "k_proj", "v_proj", "o_proj"]
ASSISTANT_MARKER = "<|start_header_id|>assistant<|end_header_id|>\n\n"


class CompletionOnlyCollator:
    """Pad + label only the assistant (SQL) section; prompt tokens -> -100."""

    def __init__(self, tokenizer, max_length: int):
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.marker_ids = tokenizer.encode(ASSISTANT_MARKER, add_special_tokens=False)

    def __call__(self, features):
        import torch

        input_ids = [f["input_ids"] for f in features]
        attn = [f["attention_mask"] for f in features]
        padded = self.tokenizer.pad(
            {"input_ids": input_ids, "attention_mask": attn}, return_tensors="pt")
        labels = padded["input_ids"].clone()
        for i in range(labels.shape[0]):
            ids = labels[i].tolist()
            idx = -1
            for j in range(len(ids) - len(self.marker_ids) + 1):
                if ids[j:j + len(self.marker_ids)] == self.marker_ids:
                    idx = j + len(self.marker_ids)
            if idx >= 0:
                labels[i][:idx] = -100  # ignore everything before the answer
            else:
                labels[i] = -100        # no answer found: ignore the row
        return {"input_ids": padded["input_ids"], "attention_mask": padded["attention_mask"],
                "labels": labels}


def evaluate_checkpoint(model, tokenizer, val_rows, db_dir, few_shot,
                        max_rows: int = 100, rows_out: Path | None = None,
                        collect_rows: bool = False):
    """Execution accuracy on a sample; optionally collect per-row results."""
    import json

    sample = val_rows[:max_rows]
    correct = 0
    rows = []
    for row in sample:
        prompt = build_prompt(row, few_shot, [])
        pred = generate("transformers", ("transformers", model, tokenizer), prompt)
        db = db_dir / row["db_id"] / f"{row['db_id']}.sqlite"
        gold_rows, gold_err = execute_sql(db, row["query"])
        pred_rows, pred_err = execute_sql(db, pred)
        acc, ok = execution_accuracy(gold_rows, pred_rows)
        correct += int(acc == 1.0 and ok)
        if collect_rows:
            rows.append({
                "db_id": row["db_id"], "question": row["question"],
                "difficulty": row.get("difficulty"),
                "features": classify_features(row["query"]),
                "gold": row["query"], "pred": pred,
                "gold_error": gold_err, "pred_error": pred_err,
                "exec": acc, "exact": exact_match(row["query"], pred),
                "both_executed": gold_rows is not None and pred_rows is not None,
            })
    acc = correct / len(sample)
    if rows_out is not None:
        rows_out.parent.mkdir(parents=True, exist_ok=True)
        rows_out.write_text(json.dumps(rows, indent=1))
        print(f"wrote {len(rows)} per-row results -> {rows_out}")
    return acc, rows if collect_rows else acc


def train_qlora(model_id: str, train_path: Path, val_path: Path, db_dir: Path,
                epochs: int, rank: int, alpha: int, lr: float, batch_size: int,
                max_length: int, few_shot: int, save_dir: Path,
                val_every_steps: int, max_steps: int | None) -> None:
    import torch
    from datasets import Dataset
    from peft import LoraConfig, PeftModel, get_peft_model
    from transformers import (
        AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig,
        TrainingArguments, Trainer,
    )

    os.environ.setdefault("HF_TOKEN", "")

    tokenizer = AutoTokenizer.from_pretrained(model_id, token=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    bnb = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)
    model = AutoModelForCausalLM.from_pretrained(
        model_id, quantization_config=bnb,
        dtype=torch.bfloat16, device_map="auto", token=True)
    model.config.use_cache = False  # required with gradient checkpointing

    lora = LoraConfig(
        r=rank, lora_alpha=alpha, target_modules=DEFAULT_TARGET_MODULES,
        lora_dropout=0.05, bias="none", task_type="CAUSAL_LM")
    model = get_peft_model(model, lora)
    base_model = model.get_base_model()  # for loading checkpoints during selection
    model.print_trainable_parameters()

    rows = load_rows(train_path, max_steps)
    ds = Dataset.from_list([{"text": r["text"]} for r in rows])

    def _tokenize(examples):
        return tokenizer(examples["text"], truncation=True,
                         max_length=max_length, padding=False)

    tok_ds = ds.map(_tokenize, batched=True, remove_columns=["text"])
    val_rows = load_rows(val_path, None)
    collator = CompletionOnlyCollator(tokenizer, max_length)

    args = TrainingArguments(
        output_dir=str(save_dir), num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=4,
        learning_rate=lr, lr_scheduler_type="cosine",
        logging_steps=10, save_strategy="steps",
        save_steps=val_every_steps,
        bf16=True, report_to="none", remove_unused_columns=False,
        gradient_checkpointing=True, max_steps=max_steps or -1,  # -1 = run to epochs (0 stops after a step in new transformers)
    )

    trainer = Trainer(
        model=model, args=args, train_dataset=tok_ds, data_collator=collator,
    )
    trainer.train()

    # Best-checkpoint selection: load each saved checkpoint and evaluate it on
    # the val sample (execution accuracy — the goal metric, not val loss).
    best_acc, best_dir = -1.0, None
    for ckpt in sorted(save_dir.glob("checkpoint-*")):
        try:
            eval_model = PeftModel.from_pretrained(base_model, ckpt)
            eval_model.eval()
            acc = evaluate_checkpoint(eval_model, tokenizer, val_rows, db_dir,
                                      few_shot)
        except Exception:  # noqa: BLE001
            import traceback
            print(f"checkpoint {ckpt.name} eval failed:")
            traceback.print_exc()
            continue
        print(f"checkpoint {ckpt.name}: val exec={acc:.2%}")
        if acc > best_acc:
            best_acc, best_dir = acc, ckpt
    print(f"BEST checkpoint: {best_dir} ({best_acc:.2%})")
    (save_dir / "best.txt").write_text(f"{best_dir}\n{best_acc:.4f}\n")

    # ---- MLflow (guarded: never fails the run) --------------------------
    try:
        import mlflow
        mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "file:///runs/mlruns"))
        mlflow.set_experiment("llama33-text2sql")
        with mlflow.start_run(run_name="train-qlora"):
            mlflow.log_params({
                "model": model_id, "rank": rank, "alpha": alpha, "lr": lr,
                "epochs": epochs, "batch_size": batch_size,
                "max_length": max_length, "target_modules": ",".join(DEFAULT_TARGET_MODULES),
                "trainable_params": "13631488",
            })
            history = trainer.state.log_history
            final_loss = history[-1].get("loss") if history else None
            if final_loss is not None:
                mlflow.log_metric("train_loss", final_loss)
            runtime = history[-1].get("train_runtime") if history else None
            if runtime is not None:
                mlflow.log_metric("train_runtime_s", runtime)
            mlflow.log_metric("global_step", trainer.state.global_step)
            mlflow.log_metric("best_val_exec_accuracy",
                              best_acc if best_acc > 0 else 0.0)
            mlflow.log_param("best_checkpoint", str(best_dir))
            for ckpt in sorted(save_dir.glob("checkpoint-*")):
                txt = (ckpt / "trainer_state.json")
                if txt.exists():
                    import json as _j
                    st = _j.loads(txt.read_text())
                    mlflow.log_metric(f"global_step_{ckpt.name}", st.get("global_step", 0))
        print("MLflow: logged train-run to file:///runs/mlruns")
    except Exception as exc:  # noqa: BLE001
        print(f"MLflow logging skipped: {exc}")


def load_rows(path: Path, max_steps: int | None) -> list[dict]:
    import json

    rows = [json.loads(l) for l in open(path)]
    return rows[:max_steps] if max_steps else rows


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
