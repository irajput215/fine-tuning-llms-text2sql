#!/usr/bin/env python3
"""
run_baseline.py — baseline (zero-shot / few-shot) on the base model.

Environment-agnostic: runs on Modal (vLLM) or any GPU box (transformers
fallback). Generates SQL for each test example, then reuses the eval harness
primitives (execution accuracy + exact-match + stratification).

Usage (Modal):  modal run training/modal_app.py baseline --model ...
Usage (bare):   python training/run_baseline.py --model meta-llama/Llama-3.1-8B-Instruct
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eval.run_eval import (  # noqa: E402
    execute_sql, execution_accuracy, exact_match, classify_features,
    summarize, render_table,
)


def load_rows(path: Path, max_examples: int | None) -> list[dict]:
    rows = [json.loads(l) for l in open(path)]
    return rows[: max_examples] if max_examples else rows


def split_prompt(prompt: str) -> tuple[str, str]:
    """(system_block, final_question_block) from a staged prompt."""
    marker = "<|start_header_id|>user<|end_header_id|>\n\n"
    idx = prompt.rfind(marker)
    if idx == -1:
        return prompt, ""
    return prompt[:idx], prompt[idx + len(marker):]


def build_few_shot_prompt(row: dict, shots: list[dict], n: int) -> str:
    """Inject n gold Q/A examples before the final question (same chat format)."""
    system, final_q = split_prompt(row["prompt"])
    turns = []
    for s in shots[:n]:
        _, sq = split_prompt(s["prompt"])
        turns.append((sq, s["query"]))
    out = system
    for q, a in turns:
        out += "<|start_header_id|>user<|end_header_id|>\n\n" + q
        out += "<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n" + a + "<|eot_id|>"
    out += "<|start_header_id|>user<|end_header_id|>\n\n" + final_q
    out += "<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
    return out


def build_prompt(row: dict, few_shot: int, shot_rows: list[dict]) -> str:
    if few_shot > 0:
        return build_few_shot_prompt(row, shot_rows, few_shot)
    return row["prompt"]


def load_generator(model_id: str, quantize_4bit: bool):
    """vLLM first, transformers fallback."""
    os.environ.setdefault("HF_TOKEN", "")
    try:
        from vllm import LLM, SamplingParams
        # max_model_len must be capped: vLLM sizes the KV cache off the model's
        # 131k max and OOMs on 24GB with 15GB of weights (max len 32544 fits).
        # Our prompts are ~2-4k tokens; 8192 leaves headroom for schema + SQL.
        llm = LLM(model=model_id, tokenizer=model_id, dtype="bfloat16",
                  max_model_len=8192)
        sp = SamplingParams(temperature=0, max_tokens=300, stop=["<|eot_id|>"],
                            add_special_tokens=False)
        return ("vllm", llm, sp)
    except ImportError:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        tok = AutoTokenizer.from_pretrained(model_id, token=True)
        mkw = {"torch_dtype": torch.bfloat16, "device_map": "auto", "token": True}
        if quantize_4bit:
            from transformers import BitsAndBytesConfig
            mkw["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True, bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16)
        model = AutoModelForCausalLM.from_pretrained(model_id, **mkw)
        model.eval()
        return ("transformers", model, tok)


def generate(kind, gen, prompt: str) -> str:
    if kind == "vllm":
        _, llm, sp = gen
        out = llm.generate([prompt], sp)[0].outputs[0].text.strip()
        return out
    import torch

    _, model, tok = gen
    inputs = tok(prompt, return_tensors="pt").to(model.device)
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=300, do_sample=False,
                             pad_token_id=tok.pad_token_id)
    return tok.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()


def run_baseline(model_id: str, test_path: Path, db_dir: Path, train_path: Path,
                 max_examples: int | None, few_shot: int,
                 quantize_4bit: bool = False) -> dict:
    test_rows = load_rows(test_path, max_examples)
    shot_rows = load_rows(train_path, None) if few_shot else []
    gen = load_generator(model_id, quantize_4bit)
    results = []
    for i, row in enumerate(test_rows):
        prompt = build_prompt(row, few_shot, shot_rows)
        pred = generate(gen[0], gen, prompt)
        db_path = db_dir / row["db_id"] / f"{row['db_id']}.sqlite"
        gold_rows, gold_err = execute_sql(db_path, row["query"])
        pred_rows, pred_err = execute_sql(db_path, pred)
        exec_acc, _ = execution_accuracy(gold_rows, pred_rows)
        results.append({
            "db_id": row["db_id"], "difficulty": row.get("difficulty"),
            "features": classify_features(row["query"]),
            "gold": row["query"], "pred": pred,
            "gold_error": gold_err, "pred_error": pred_err,
            "exec": exec_acc, "exact": exact_match(row["query"], pred),
            "both_executed": gold_rows is not None and pred_rows is not None,
        })
        if (i + 1) % 25 == 0 or i == len(test_rows) - 1:
            acc = sum(r["exec"] for r in results) / len(results)
            print(f"  {i+1}/{len(test_rows)} exec={acc:.2%}", file=sys.stderr)
    label = f"baseline {model_id}" + (f" few-shot={few_shot}" if few_shot else " zero-shot")
    return summarize(results, label)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--test-jsonl", type=Path, default=Path("data/processed/test.jsonl"))
    ap.add_argument("--train-jsonl", type=Path, default=Path("data/processed/train.jsonl"))
    ap.add_argument("--db-dir", type=Path, default=Path("data/spider/spider_data/database"))
    ap.add_argument("--max-examples", type=int, default=None)
    ap.add_argument("--few-shot", type=int, default=0)
    ap.add_argument("--quantize-4bit", action="store_true")
    ap.add_argument("--out", type=Path, default=Path("data/baseline.json"))
    args = ap.parse_args()
    summary = run_baseline(args.model, args.test_jsonl, args.db_dir,
                           args.train_jsonl, args.max_examples, args.few_shot,
                           args.quantize_4bit)
    print(render_table(summary))
    args.out.write_text(json.dumps(summary, indent=1))
    print(f"\nresults -> {args.out}")


if __name__ == "__main__":
    main()
