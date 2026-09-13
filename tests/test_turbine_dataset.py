"""TurbineQADataset against the local TimeNet registry (skipped when cubico/* is not built)."""

import numpy as np
import pytest

from turbine_tslm.data.channels import CHANNEL_NAMES

pytest.importorskip("opentslm")
from turbine_tslm.training.turbine_dataset import (
    make_dataset_class,
    stratified_subsample,
    z_score,
)


def _registry_has_cubico() -> bool:
    from timenet.registry.factory import default_registry_path

    root = default_registry_path()
    return all((root / "cubico" / f).exists() for f in ("penmanshiel", "kelmarsh"))


def test_z_score_handles_constant_and_nan():
    z, m, s = z_score(np.array([1.0, 1.0, 1.0], dtype=np.float32))
    assert m == 1.0 and s == 0.0 and np.all(z == 0)
    z, m, s = z_score(np.array([0.0, np.nan, 2.0], dtype=np.float32))
    assert m == 1.0 and z[1] == 0.0 and abs(z[0] + 1) < 1e-6


def test_stratified_subsample_keeps_both_answers():
    rows = [{"label": "none"}] * 50 + [{"label": "pitch_system"}] * 5
    out = stratified_subsample(rows, 8, seed=1)
    assert len(out) == 8 and sum(r["label"] != "none" for r in out) == 4
    assert stratified_subsample(rows, None) is rows


@pytest.mark.skipif(
    not _registry_has_cubico(), reason="cubico registry not built locally"
)
def test_samples_follow_the_opentslm_contract():
    DS = make_dataset_class("test", max_samples=12, seed=0)
    train, val, test = (
        DS(s, EOS_TOKEN="<eos>") for s in ("train", "validation", "test")
    )
    assert len(train) == 12 and len(val) == 12 and len(test) == 12
    assert {s["split"] for s in train} == {"train"}
    assert {s["split"] for s in val} == {"val"}
    assert {s["split"] for s in test} <= {"test_a", "test_b"}
    ex = train[0]
    assert set(ex) >= {
        "answer",
        "pre_prompt",
        "post_prompt",
        "time_series",
        "time_series_text",
        "window_id",
        "label",
    }
    assert len(ex["time_series"]) == len(CHANNEL_NAMES) == len(ex["time_series_text"])
    z = np.asarray(ex["time_series"][0])
    assert z.shape == (144,) and abs(z.mean()) < 1e-3 and not np.isnan(z).any()
    assert (
        ex["time_series_text"][0].startswith("wind speed in m/s")
        and "mean" in ex["time_series_text"][0]
    )
    assert ex["answer"].startswith("Answer: ") and ex["answer"].endswith("<eos>")
    assert ex["post_prompt"] == "Assessment:"
    assert (
        "Answer:" not in ex["pre_prompt"].split("End with")[0]
    )  # label never in the prompt
    assert sum(s["label"] != "none" for s in train) == 6


def test_rich_series_text_quotes_window_statistics():
    from turbine_tslm.data.prompts import series_text

    t = series_text("gen_bearing_rear_temperature", 45.0, 3.6, 41.2, 43.0, 47.9)
    assert t.endswith(
        "mean 45.0 std 3.6, first 6 h 41.2, 6 h before the end 43.0, last hour 47.9:"
    )
    assert series_text("wind_speed", 7.8, 2.4).endswith("mean 7.8 std 2.4:")
