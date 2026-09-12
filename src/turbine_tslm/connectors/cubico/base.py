"""Shared TimeNet connector for the Cubico wind farms (early-warning windows, docs/problem-statement.md).

``download()`` builds the window table from the raw Zenodo zips under ``$DATA_DIR/raw/<farm>/`` (run
``scripts/download_data.sh`` first) and caches it as one parquet file. ``convert()`` turns that table into a
``TimeFDataset``: one record per window with 19 series, the labels as annotations, a ``ClassificationTask`` on
the horizon label and an ``AnswerTask`` carrying the MVP prompt/answer. The alarm text is stored only in
annotations that are never referenced as task inputs.

Connector skeleton adapted from M. Kalk's ``mk/src/connectors``.
"""

from __future__ import annotations

import os
from fractions import Fraction
from pathlib import Path
from typing import ClassVar

import numpy as np
import pandas as pd
import pyarrow as pa
from timenet.connectors.base import BaseConnector
from timenet.dataset import TimeFDataset, TimeSeries
from timenet.dataset.axis import RegularAxis
from timenet.types import Annotation, AnswerTask, ClassificationTask, DataSource, TimeSeriesSpec, ureg

from turbine_tslm.data.channels import CHANNEL_NAMES, CHANNELS, STEP_MINUTES
from turbine_tslm.data.greenbyte import iter_turbine_years
from turbine_tslm.data.prompts import answer_label, pre_prompt
from turbine_tslm.data.windows import WINDOW_STEPS, build_windows, records_to_frame


def _text(v) -> str | None:
    return None if v is None or (isinstance(v, float) and np.isnan(v)) else str(v)


def _num(v) -> float | None:
    return None if v is None or pd.isna(v) else float(v)


def data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", "data")).expanduser()


def build_window_table(farm: str, raw_dir: Path, years: tuple[int, ...] | None = None) -> pd.DataFrame:
    frames = []
    for ty in iter_turbine_years(raw_dir, farm):
        if years and ty.year not in years:
            continue
        scada, status = ty.load()
        recs = build_windows(scada, status, farm=farm, turbine=ty.turbine)
        print(f"[windows] {ty.turbine_id} {ty.year}: {sum(r.is_positive for r in recs)} pos / {sum(not r.is_positive for r in recs)} neg")
        if recs:
            frames.append(records_to_frame(recs, ty.year))
    if not frames:
        raise FileNotFoundError(f"no turbine-year files found under {raw_dir / farm}")
    return pd.concat(frames, ignore_index=True)


class CubicoConnector(BaseConnector[Path]):
    FARM: ClassVar[str]
    PROVIDER_NAME: ClassVar[str]

    def download(self, cache_dir: Path) -> list[Path]:
        cache_dir.mkdir(parents=True, exist_ok=True)
        out = cache_dir / f"{self.FARM}_windows.parquet"
        if not out.exists():
            prebuilt = data_dir() / "interim" / f"{self.FARM}_windows.parquet"  # scripts/build_windows.py output
            if prebuilt.exists():
                out.write_bytes(prebuilt.read_bytes())
            else:
                build_window_table(self.FARM, data_dir() / "raw").to_parquet(out, index=False)
        return [out]

    def convert(self, raw_refs: list[Path]) -> TimeFDataset:
        df = pd.read_parquet(raw_refs[0])
        dataset = TimeFDataset(metadata=self.metadata())
        source = DataSource(data_source_type="sensor", name=self.PROVIDER_NAME, provider="Cubico Sustainable Investments")
        specs = {
            ch.name: TimeSeriesSpec(spec_type=ch.name, name=ch.description, unit_value=ureg.Unit(ch.unit), data_source=source)
            for ch in CHANNELS
        }
        axis = RegularAxis(period_us=Fraction(STEP_MINUTES * 60 * 1_000_000, 1), start_index=0)

        for row in df.itertuples(index=False):
            rid = row.window_id
            anchor = pd.Timestamp(row.anchor)
            start = anchor - pd.Timedelta(minutes=(WINDOW_STEPS - 1) * STEP_MINUTES)
            series = []
            for name in CHANNEL_NAMES:
                values = np.asarray(getattr(row, name), dtype=np.float32)
                series.append(
                    TimeSeries(
                        spec=specs[name], signal=name, time_axis=axis,
                        loader=(lambda v=values: pa.array(v, type=pa.float32())),
                        source_id=row.turbine_id, time_series_id=f"{rid}:{name}", n_values=WINDOW_STEPS,
                    )
                )
            record = dataset.add_record(
                time_series=tuple(series), subject_ids=(row.turbine_id,), record_id=rid,
                start_time=int(start.timestamp() * 1_000_000),
            )
            ann = {
                "split": _text(row.split), "farm": _text(row.farm), "turbine_id": _text(row.turbine_id), "year": int(row.year),
                "anchor": anchor.isoformat(), "horizon_h": int(row.horizon_h), "state_at_anchor": _text(row.state_at_anchor),
                "label": _text(row.label), "is_positive": bool(row.is_positive),
                "fault_within_1h": _text(row.fault_within_1h), "fault_within_3h": _text(row.fault_within_3h),
                "fault_within_6h": _text(row.fault_within_6h),
                "lead_time_min": _num(row.lead_time_min),
                "next_event_message": _text(row.next_event_message),
                "next_event_iec": _text(row.next_event_iec),
                "next_event_duration_h": _num(row.next_event_duration_h),
            }
            # TimeNet rejects a value-less annotation and needs one value type per key, so negatives omit the
            # next-event fields (parquet stores their missing strings as NaN floats).
            record.add_annotations([Annotation(key=k, value=v, id=f"{rid}:{k}") for k, v in ann.items() if v is not None])
            prompt = pre_prompt(row.farm, row.turbine_id, anchor.strftime("%B"), row.state_at_anchor, int(row.horizon_h))
            dataset.add_tasks(
                record,
                [
                    ClassificationTask(target=row.label, id=f"{rid}:cls"),
                    AnswerTask(prompt=prompt, target=answer_label(row.label), id=f"{rid}:qa"),
                ],
            )
        return dataset
