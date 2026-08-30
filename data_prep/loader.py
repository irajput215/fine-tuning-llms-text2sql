#!/usr/bin/env python3
"""
loader.py — load the staged Spider splits as HF datasets.

Usage:
    from data_prep.loader import load_splits
    train, val, test = load_splits("data/processed")
"""
from __future__ import annotations

from pathlib import Path

from datasets import Dataset


def load_split(path: str | Path) -> Dataset:
    return Dataset.from_json(str(path))


def load_splits(root: str | Path):
    root = Path(root)
    return (
        load_split(root / "train.jsonl"),
        load_split(root / "val.jsonl"),
        load_split(root / "test.jsonl"),
    )


def load_local_spider(data_root: str | Path):
    """Convenience: read raw Spider json from an extracted official zip."""
    import json

    root = Path(data_root)
    return (
        json.loads((root / "train.json").read_text()),
        json.loads((root / "dev.json").read_text()),
        json.loads((root / "tables.json").read_text()),
    )
