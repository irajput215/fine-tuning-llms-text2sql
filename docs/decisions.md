# llama33-text2sql — Decision Records

ADR-style records of the choices made: **context → options → decision → why**.
Timeline in [development-log.md](development-log.md).

---

## D1 · Dataset sources: HF mirrors + official databases zip

- **Date:** 2026-08-30
- **Context:** Spider ships as an official zip (Google Drive) plus community
  mirrors. The HF example dataset (`xlangai/spider`) has no schema; the
  official Drive ID we first tried was stale (404).
- **Decision:** examples from `xlangai/spider`, schemas from
  `richardr1126/spider-schema`, SQLite databases from the official zip (ID
  extracted from the official Spider page).
- **Why:** HF mirrors are reliable and version-pinned; the schema dataset
  gives ready-made per-db schema + PK/FK; the official zip is the only source
  of the actual SQLite databases the eval harness must execute against.

## D2 · Split discipline: 80/10/10, dev held out as test

- **Date:** 2026-08-30
- **Context:** Hyperparameter and checkpoint selection need a val set; the
  claim needs an untouched test set.
- **Decision:** train → train/val (90/10 of Spider's train split); Spider's
  validation split (1,034) becomes the test set, never used for tuning.
- **Why:** test-touched-once is the only defensible way to report accuracy;
  keeping Spider's official dev split keeps numbers comparable to published
  results.

## D3 · Compute: Modal (over RunPod / Colab)

- **Date:** 2026-08-30
- **Context:** Three viable GPU paths for Llama 3.1 8B (24GB-class): RunPod
  (SSH pods, ~$0.30–1/hr), Modal (serverless, $30 credit, auto-stops), Colab/
  Kaggle (free, session limits).
- **Decision:** **Modal** — code-as-deployment, auto-stop (no cost leakage),
  free credit covers baseline + a few training runs, and the same code scales
  to an A100 for the 70B ambition later.
- **Why:** reproducibility and zero babysitting beat raw cheapness for a
  resume-grade project; RunPod's manual-pod workflow and Colab's session
  limits both add friction.

## D4 · Eval methodology: execution accuracy + exact-match, no LLM judge

- **Date:** 2026-08-30
- **Context:** Text-to-SQL can be scored by string match, LLM-as-judge, or by
  actually executing the SQL.
- **Decision:** primary = **execution accuracy** (result-set comparison on the
  real SQLite db, row-order-insensitive); secondary = **exact-match**
  (normalized SQL). No judge in the loop.
- **Why:** execution accuracy is the benchmark-standard, fully reproducible,
  and immune to judge variance; exact-match is a stricter secondary. The
  harness also stratifies by difficulty and SQL feature so "where it helped"
  is visible, not just "that it helped".

## D5 · Model: Llama 3.1 8B first, 70B later (same code)

- **Date:** 2026-08-30
- **Context:** The outline claimed "24GB is enough" — false for Llama 3.3
  (70B, ~45–50GB at 4-bit). A single 24GB card fits 8B-class only.
- **Decision:** start with **Llama 3.1 8B Instruct** on an A10G; keep the
  70B as the scale-up run on A100/H100 (Modal: one decorator change).
- **Why:** same methodology, same harness, 1/10th the cost; the resume claim
  ("8B baseline X% → fine-tuned Y%") is already meaningful, and the 70B run
  becomes a documented scaling experiment.

## D6 · Generation: vLLM, transformers fallback

- **Date:** 2026-08-30
- **Context:** The baseline needs ~1,034 generations; greedy decode in
  transformers is slow.
- **Decision:** use **vLLM** for batched generation in the Modal image, with a
  transformers fallback path for RunPod/Colab.
- **Why:** order-of-magnitude faster; the fallback keeps the script
  environment-agnostic.

## D7 · Training: SFTTrainer, completion-only supervision, best-val-exec checkpoint

- **Date:** 2026-08-30
- **Context:** QLoRA training needs a trainer; checkpoint selection should
  reflect the actual goal (execution accuracy), not just loss.
- **Decision:** TRL **SFTTrainer** + `DataCollatorForCompletionOnlyLM` (only
  the gold-SQL section is supervised), and the saved checkpoint is the one
  with the **best validation execution accuracy** (harness on a val sample),
  not the last step.
- **Why:** completion-only prevents the model from learning to emit prompts;
  val-exec selection ships the checkpoint that actually answers SQL best and
  guards against overfit checkpoints.
