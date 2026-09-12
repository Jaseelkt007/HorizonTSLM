"""OpenTSLM ``QADataset`` over the Cubico TimeNet registry (docs/problem-statement.md §6-7).

One sample per window record: the connector's pre-prompt (``AnswerTask.prompt``), 19 channel prompts (per-channel
z-score inside the window, raw mean/std written into the channel text via ``prompts.series_text``), the fixed
post-prompt and the answer (``AnswerTask.target``, e.g. ``Answer: yes, generator_cooling``). Splits come from the
``split`` annotation the connector wrote — nothing is re-split here, and nothing here reads CSVs or parquet.

OpenTSLM caches the formatted splits on the *class*, so every run configuration gets its own subclass via
``make_dataset_class``.

    uv run python -m turbine_tslm.training.turbine_dataset          # prints sizes and one sample
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from typing import Any, Literal

import numpy as np
from opentslm.prompt.text_time_series_prompt import TextTimeSeriesPrompt
from opentslm.time_series_datasets.QADataset import QADataset
from timenet.client import TimeNet
from timenet.registry.factory import default_registry_path
from timenet.types import AnswerTask

from turbine_tslm.data.channels import CHANNEL_NAMES
from turbine_tslm.data.prompts import POST_PROMPT, series_text

DATASET_IDS: tuple[str, ...] = ("cubico/penmanshiel", "cubico/kelmarsh")
SPLIT_MAP: dict[str, tuple[str, ...]] = {
    "train": ("train",),
    "validation": ("val",),
    "test": ("test_a", "test_b"),
}
MIN_STD = 1e-6


def load_rows(
    dataset_ids: Sequence[str] = DATASET_IDS, registry=None
) -> list[dict[str, Any]]:
    """All window records of the given TimeNet datasets as plain dicts (series as float32 arrays, by channel)."""
    tn = TimeNet(registry=registry or default_registry_path())
    rows: list[dict[str, Any]] = []
    for did in dataset_ids:
        ds = tn.load(did)
        for rec in ds.records:
            ann = {a.key: a.value for a in rec.annotations}
            qa = ds.tasks_for(rec, AnswerTask)
            if len(qa) != 1:
                raise ValueError(
                    f"{rec.record_id}: expected one AnswerTask, found {len(qa)}"
                )
            series = {
                ts.signal: np.asarray(ts.to_numpy(), dtype=np.float32)
                for ts in rec.time_series
            }
            missing = [c for c in CHANNEL_NAMES if c not in series]
            if missing:
                raise ValueError(f"{rec.record_id}: missing channels {missing}")
            rows.append(
                {
                    "window_id": rec.record_id,
                    "split": ann["split"],
                    "farm": ann["farm"],
                    "horizon_h": int(ann["horizon_h"]),
                    "label": ann["label"],
                    "pre_prompt": qa[0].prompt,
                    "answer": qa[0].target,
                    "series": series,
                }
            )
    return rows


def stratified_subsample(
    rows: list[dict[str, Any]], n: int | None, seed: int = 0
) -> list[dict[str, Any]]:
    """At most ``n`` rows, half positives where available (so smoke runs see both answers)."""
    if n is None or len(rows) <= n:
        return rows
    rng = random.Random(seed)
    pos = [r for r in rows if r["label"] != "none"]
    neg = [r for r in rows if r["label"] == "none"]
    rng.shuffle(pos)
    rng.shuffle(neg)
    k_pos = min(len(pos), n // 2)
    out = pos[:k_pos] + neg[: n - k_pos]
    rng.shuffle(out)
    return out


def z_score(v: np.ndarray) -> tuple[np.ndarray, float, float]:
    mean = float(np.nanmean(v))
    std = float(np.nanstd(v))
    z = (v - mean) / max(std, MIN_STD)
    return (
        np.nan_to_num(z, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32),
        mean,
        std,
    )


class TurbineQADataset(QADataset):
    """Class attributes are the run configuration; subclass (``make_dataset_class``) rather than mutate."""

    dataset_ids: tuple[str, ...] = DATASET_IDS
    split_map: dict[str, tuple[str, ...]] = SPLIT_MAP
    max_samples: int | None = None  # per OpenTSLM split, stratified
    horizons: tuple[int, ...] | None = None  # e.g. (6,) to train on one question only
    seed: int = 0
    registry = None
    _rows: list[dict[str, Any]] | None = None

    def __init__(
        self, split: Literal["train", "test", "validation"], EOS_TOKEN: str, **kw
    ):
        super().__init__(split, EOS_TOKEN, **kw)

    @classmethod
    def rows(cls) -> list[dict[str, Any]]:
        if cls._rows is None:
            cls._rows = load_rows(cls.dataset_ids, cls.registry)
        return cls._rows

    def _load_splits(self):
        rows = self.rows()
        if self.horizons:
            rows = [r for r in rows if r["horizon_h"] in self.horizons]
        out = []
        for key in ("train", "validation", "test"):
            sel = [r for r in rows if r["split"] in self.split_map[key]]
            out.append(stratified_subsample(sel, self.max_samples, self.seed))
        return tuple(out)

    def _get_pre_prompt(self, row) -> str:
        return row["pre_prompt"]

    def _get_post_prompt(self, row) -> str:
        return POST_PROMPT

    def _get_answer(self, row) -> str:
        return row["answer"]

    def _get_text_time_series_prompt_list(self, row) -> list[TextTimeSeriesPrompt]:
        prompts = []
        for name in CHANNEL_NAMES:
            z, mean, std = z_score(row["series"][name])
            prompts.append(TextTimeSeriesPrompt(series_text(name, mean, std), z))
        return prompts

    def _format_sample(self, row):
        sample = super()._format_sample(row)
        for k in ("window_id", "split", "farm", "horizon_h", "label"):
            sample[k] = row[k]
        return sample


def make_dataset_class(name: str, **config) -> type[TurbineQADataset]:
    """A fresh subclass (own OpenTSLM cache) with the given attribute overrides."""
    bad = set(config) - {
        "dataset_ids",
        "split_map",
        "max_samples",
        "horizons",
        "seed",
        "registry",
    }
    if bad:
        raise TypeError(f"unknown dataset options {sorted(bad)}")
    if config.get("horizons"):
        config["horizons"] = tuple(int(h) for h in config["horizons"])
    return type(
        f"TurbineQADataset_{name}", (TurbineQADataset,), {**config, "_rows": None}
    )


if __name__ == "__main__":
    DS = make_dataset_class("main")
    parts = {s: DS(s, EOS_TOKEN="<eos>") for s in ("train", "validation", "test")}
    for s, d in parts.items():
        print(s, len(d))
    ex = parts["train"][0]
    print({k: v for k, v in ex.items() if k not in ("time_series", "time_series_text")})
    print(ex["time_series_text"][0], np.asarray(ex["time_series"][0])[:6])
