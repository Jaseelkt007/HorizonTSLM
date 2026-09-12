"""Native TimeNet connector for Kelmarsh Wind Farm SCADA & Status data."""

import datetime
from fractions import Fraction
from pathlib import Path
from typing import Callable, List

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from src.data.preprocessor import (
    TelemetryWindow,
    generate_synthetic_scada_windows,
)
from src.data.schemas import SELECTED_SIGNALS, WINDOW_STEPS
from timenet.connectors.base import BaseConnector
from timenet.dataset import TimeFDataset, TimeSeries
from timenet.dataset.axis import RegularAxis
from timenet.types import (
    Annotation,
    AnswerTask,
    ClassificationTask,
    DataSource,
    TimeSeriesSpec,
    ureg,
)


def _make_lazy_loader(values: np.ndarray) -> Callable[[], pa.Array]:
    """Return a zero-argument callable that returns a float32 PyArrow Array."""
    val_copy = values.astype(np.float32)

    def loader() -> pa.Array:
        return pa.array(val_copy, type=pa.float32())

    return loader


def _get_signal_unit(canonical_name: str):
    unit_map = {
        "wind_speed": ureg.meter / ureg.second,
        "power": ureg.kilowatt,
        "rotor_speed": ureg.rpm,
        "generator_rpm": ureg.rpm,
        "gear_oil_temp": ureg.degC,
        "gen_bearing_temp": ureg.degC,
        "pitch_angle": ureg.degree,
        "drivetrain_accel": ureg.dimensionless,  # mm/s^2 handled dimensionlessly in Pint
    }
    return unit_map.get(canonical_name, ureg.dimensionless)


class KelmarshConnector(BaseConnector[Path]):
    """TimeNet BaseConnector implementation for Kelmarsh wind farm SCADA & Status logs."""

    CARD = Path(__file__).with_name("dataset.yaml")
    values_backend = "parquet"

    def download(self, cache_dir: Path) -> List[Path]:
        """Prepare or discover telemetry window data.

        Writes/caches intermediate windows into cache_dir and returns the path reference.
        """
        cache_dir.mkdir(parents=True, exist_ok=True)
        window_parquet_path = cache_dir / "kelmarsh_windows.parquet"

        if window_parquet_path.exists():
            return [window_parquet_path]

        # Generate or load windows
        windows = generate_synthetic_scada_windows(num_turbines=6, windows_per_turbine=30, seed=42)

        # Convert windows to tabular parquet format for fast lazy retrieval
        rows = []
        for w_idx, w in enumerate(windows):
            row = {
                "window_id": f"w-{w_idx:05d}",
                "turbine_id": w.turbine_id,
                "start_time": w.start_time,
                "end_time": w.end_time,
                "label_idx": w.label_idx,
                "label_name": w.label_name,
                "prompt": w.prompt,
                "rationale": w.rationale,
                "action": w.action,
            }
            # Flatten signals (72, 8) into individual channel lists
            for col_idx, sig in enumerate(SELECTED_SIGNALS):
                row[sig.canonical_name] = w.signals[:, col_idx].tolist()
            rows.append(row)

        df = pd.DataFrame(rows)
        df.to_parquet(window_parquet_path, index=False)
        return [window_parquet_path]

    def convert(self, raw_refs: List[Path]) -> TimeFDataset:
        """Parse raw parquet references and populate a TimeFDataset."""
        parquet_path = raw_refs[0]
        df = pd.read_parquet(parquet_path)

        metadata = self.metadata()
        dataset = TimeFDataset(metadata=metadata)

        # Shared data source definition
        data_source = DataSource(
            data_source_type="sensor",
            name="Kelmarsh MM92 SCADA System",
            provider="Cubico Sustainable Investments",
        )

        # Build specs for each of the 8 channels
        specs = {}
        for sig in SELECTED_SIGNALS:
            specs[sig.canonical_name] = TimeSeriesSpec(
                spec_type=sig.canonical_name,
                name=sig.description,
                unit_value=_get_signal_unit(sig.canonical_name),
                data_source=data_source,
            )

        # Regular 10-minute sampling axis (10 min = 600,000,000 microseconds)
        time_axis = RegularAxis(period_us=Fraction(600_000_000, 1), start_index=0)

        # Iterate over records
        for _, row in df.iterrows():
            rec_id = str(row["window_id"])
            turbine_id = str(row["turbine_id"])
            start_dt = pd.to_datetime(row["start_time"])
            start_us = int(start_dt.timestamp() * 1_000_000)

            series_list = []
            for sig in SELECTED_SIGNALS:
                sig_values = np.array(row[sig.canonical_name], dtype=np.float32)
                loader = _make_lazy_loader(sig_values)
                ts = TimeSeries(
                    spec=specs[sig.canonical_name],
                    signal=sig.canonical_name,
                    time_axis=time_axis,
                    loader=loader,
                    source_id=turbine_id,
                    time_series_id=f"{rec_id}_{sig.canonical_name}",
                    n_values=WINDOW_STEPS,
                )
                series_list.append(ts)

            # Add record to dataset
            record = dataset.add_record(
                time_series=tuple(series_list),
                subject_ids=(turbine_id,),
                record_id=rec_id,
                start_time=start_us,
            )

            # Add annotations
            farm_anno = Annotation(key="wind_farm", value="Kelmarsh", id=f"farm-{rec_id}")
            turb_anno = Annotation(key="turbine_id", value=turbine_id, id=f"turb-{rec_id}")
            fault_anno = Annotation(key="fault_class", value=str(row["label_name"]), id=f"fault-{rec_id}")
            record.add_annotations([farm_anno, turb_anno, fault_anno])

            # Add tasks: Classification and Chain-of-Thought Answer
            cls_task = ClassificationTask(
                target=str(row["label_name"]),
                id=f"task-cls-{rec_id}",
            )
            ans_task = AnswerTask(
                prompt=str(row["prompt"]),
                target=str(row["action"]),
                rationale=str(row["rationale"]),
                input_annotation_ids=(fault_anno.id,),
                from_tasks=(cls_task,),
                id=f"task-ans-{rec_id}",
            )
            dataset.add_tasks(record, [cls_task, ans_task])

        return dataset
