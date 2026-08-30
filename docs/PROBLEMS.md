# llama33-text2sql — Problems Solved (Troubleshooting Log)

Every real problem hit on this project, in order: **symptom → root cause →
fix → evidence**. This is the debugging saga — the strongest interview
material in the repo, because it shows diagnosis, not just "it worked".

---

## P1 · HF dataset split name mismatch

- **Symptom:** `load_dataset("xlangai/spider", split="dev")` →
  `Unknown split "dev". Should be one of ['train', 'validation']`.
- **Root cause:** the HF mirror names Spider's dev set `validation`.
- **Fix:** use `split="validation"` for the held-out dev set.
- **Evidence:** staging run produced the correct 1,034-row test split.

## P2 · HF example dataset carries no schema

- **Symptom:** `no schema tables found` — the `tables` column doesn't exist in
  `xlangai/spider` rows (columns: `db_id, query, question, *_toks`).
- **Root cause:** the example dataset ships questions/answers only; schema
  lives elsewhere.
- **Fix:** pull schemas (schema + PK/FK) from `richardr1126/spider-schema`.
- **Evidence:** prompts now render real schema + `Primary Keys:`/`Foreign Keys:`.

## P3 · Schema map sliced by the test flag

- **Symptom:** linking run produced `(schema unavailable)` for every row.
- **Root cause:** `--max-examples` was also slicing the schema dataset
  (first 20 dbs alphabetically), so example dbs had no schema entry.
- **Fix:** always load the full schema map (166 dbs, tiny); only slice examples.
- **Evidence:** `department_management` etc. now covered; the earlier
  "1 db missing" warning disappeared.

## P4 · Wrong Google Drive ID for the databases (404)

- **Symptom:** `Error 404` from Drive; gdown failed.
- **Root cause:** the remembered ID (`1i4xw2Gsr5o8BTORcNw5lvNir7clvMBoi`) was
  stale; Drive silently 404s bad file IDs.
- **Fix:** extracted the real ID (`1403EGqzIDoHMdQF4c9Bkyl7dZLZ5Wt6J`) from the
  official Spider page; gdown then downloaded the 206MB zip fine.
- **Evidence:** 2,625 entries extracted; `department_management.sqlite` loads.

## P5 · Modal SDK 1.5.5 API drift (the saga)

Modal moved fast between docs and release. Every failure below was a stale-API
error, each fixed by reading the installed package rather than the docs.

### P5a · `modal.Mount` doesn't exist
- **Symptom:** `AttributeError: module 'modal' has no attribute 'Mount'`.
- **Root cause:** `Mount` moved to `modal.mount.Mount`.
- **Fix:** import from the submodule.

### P5b · `Mount()` constructor prohibited
- **Symptom:** `Class _Mount has no constructor. Use class constructor
  methods instead.`
- **Root cause:** local-dir mount construction is now the private
  `_from_local_dir`; the public `from_local_dir` is gone in 1.5.5 (stale docs).

### P5c · `mounts=` removed from `@app.function`
- **Symptom:** `TypeError: _App.function() got an unexpected keyword argument
  'mounts'` (raised through a deprecation wrapper).
- **Root cause:** per-function mounts fully removed in 1.5.5; the shipped
  docstrings still show the old pattern.
- **Fix (architecture):** carry the repo on a **Modal Volume**
  (`llama33-repo`) mounted at `/repo`; `include_source` only auto-mounts the
  app file, not sibling directories.

### P5d · `local_entrypoint` + argparse flags rejected
- **Symptom:** `No such option '--model'` from Modal's CLI.
- **Root cause:** 1.5.5's `modal run` takes **function references**
  (`file::function`) and auto-generates CLI options from function signatures;
  the old local-entrypoint pattern doesn't pass flags through.
- **Fix:** drop the entrypoint; call `modal run modal_app.py::run_baseline
  --model ...` (verified: `--model` required, `--max-examples`, `--few-shot`
  generated correctly).

### P5e · `include_source` mounts only the app file
- **Symptom:** in the container, `from training.run_baseline import` →
  `ModuleNotFoundError: No module named 'training'` (the run had already
  started and paid ~3 minutes of GPU).
- **Root cause:** with a standalone `.py` entrypoint, include_source mounts
  the single file, not the directory.
- **Fix:** volume-mounted repo at `/repo` + `os.chdir("/repo")` before imports.

## P6 · Secret name mismatch

- **Symptom:** (prevented before running) app expected `hf-token`, captain
  created `huggingface-secret`.
- **Root cause:** the captain followed the Modal quickstart's secret name.
- **Fix:** aligned the app to the existing secret name.
- **Evidence:** `modal secret list` confirmed the name; `modal run` passed the
  secret into the container.

## P7 · vLLM KV-cache OOM on the A10G

- **Symptom:** `ValueError: To serve at least one request with the model's max
  seq len (131072), 16.0 GiB KV cache is needed, which is larger than the
  available KV cache memory (3.97 GiB).`
- **Root cause:** vLLM sizes the KV cache off the model's configured max
  sequence length (131k for Llama 3.1). With ~15GB of bfloat16 weights on a
  24GB A10G, only ~4GB remained — nowhere near the 16GB the full-length cache
  would need. (Our prompts are ~2–4k tokens.)
- **Fix:** `LLM(..., max_model_len=8192)` — cap the context window to what the
  task actually needs; vLLM then sizes the KV cache to fit.
- **Evidence:** engine initialized cleanly after the cap (container reached
  generation).

## P8 · Stale command path after moving the app

- **Symptom:** `FileNotFoundError: .../training/modal_app.py` on `modal run`.
- **Root cause:** the app was moved to the repo root (P5e fix); the old path
  lingered in muscle memory.
- **Fix:** documented `modal run modal_app.py::...` from the repo root.

---

## Recurring lesson

**When a tool's docs and its installed release disagree, read the installed
package** (`dir(module)`, `inspect.signature`, grep the source). Every P5
failure was a doc/release mismatch — the package source was the source of
truth, and each fix was found there in minutes.

## P9 · FlashInfer JIT needs nvcc (CUDA toolkit missing in the image)

- **Symptom:** after the KV-cache fix, the engine reaches warmup then dies:
  `RuntimeError: Could not find nvcc and default cuda_home='/usr/local/cuda'
  doesn't exist` (from `flashinfer/jit/core.py`).
- **Root cause:** vLLM 0.28 selected **FlashInfer** for top-p/top-k sampling
  ("Using FlashInfer for top-p & top-k sampling"). FlashInfer JIT-compiles a
  CUDA kernel at runtime, which requires the CUDA **toolkit** (`nvcc`); the
  Modal image ships only the CUDA **runtime** (via torch/vLLM wheels).
- **Fix:** `os.environ["VLLM_USE_FLASHINFER_SAMPLER"] = "0"` before loading
  vLLM — verified against the vLLM 0.28.0 source (`topk_topp_sampler.py`
  returns False and falls back to the native sampler when the var is 0).
- **Evidence:** the env var name confirmed in the installed release's source,
  not docs (the recurring lesson again).
