"""Readers for the Greenbyte SCADA exports (Cubico wind farms on Zenodo).

Each turbine-year comes as two CSVs inside a yearly zip: ``Turbine_Data_<farm>_<n>_<range>.csv`` (10-minute
telemetry, 9 comment lines then a header starting with ``# Date and time``) and ``Status_<farm>_<n>_<range>.csv``
(the event log, header starting with ``Timestamp start``; ``Timestamp end`` is ``-`` for open events).

Adapted from M. Kalk's ``mk/src/data/preprocessor.py`` (header detection, duration parsing); reads straight from
the zips so nothing has to be extracted.
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import pandas as pd

_HEADER_STARTS = ("Date and time", "Timestamp")


def _read_greenbyte_csv(raw: bytes) -> pd.DataFrame:
    """Parse one export: skip the ``#`` comment block, keep the header row, strip a leading ``# ``."""
    lines = raw.decode("utf-8", errors="replace").splitlines()
    header_idx = next(
        (i for i, line in enumerate(lines) if line.lstrip("#").strip().startswith(_HEADER_STARTS)),
        None,
    )
    if header_idx is None:
        raise ValueError("no Greenbyte header row found")
    lines[header_idx] = lines[header_idx].lstrip("#").strip()
    df = pd.read_csv(io.StringIO("\n".join(lines[header_idx:])), low_memory=False)
    df.columns = [c.lstrip("#").strip() for c in df.columns]
    return df


def read_scada(raw: bytes) -> pd.DataFrame:
    """Telemetry export -> DataFrame indexed by UTC timestamp, sorted, duplicates dropped."""
    df = _read_greenbyte_csv(raw)
    index = pd.to_datetime(df.pop("Date and time"), utc=True).rename("t")
    df = df.set_index(index).sort_index()
    return df[~df.index.duplicated(keep="first")]


def _duration_seconds(val) -> float | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip()
    if not s or s == "-":
        return None
    parts = s.split(":")
    try:
        if len(parts) == 3:  # HH:MM:SS, hours may exceed 24
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        if len(parts) == 4:  # DD:HH:MM:SS
            return int(parts[0]) * 86400 + int(parts[1]) * 3600 + int(parts[2]) * 60 + float(parts[3])
        return float(s)
    except ValueError:
        return None


def read_status(raw: bytes) -> pd.DataFrame:
    """Status export -> DataFrame with ``start`` / ``end`` (UTC, end NaT when open), ``duration_s`` and the text columns."""
    df = _read_greenbyte_csv(raw)
    out = pd.DataFrame(
        {
            "start": pd.to_datetime(df["Timestamp start"], utc=True),
            "end": pd.to_datetime(df["Timestamp end"].replace("-", None), utc=True, errors="coerce"),
            "duration_s": df["Duration"].map(_duration_seconds),
            "status": df["Status"].astype(str).str.strip(),
            "code": df["Code"].astype(str).str.strip(),
            "message": df["Message"].astype(str).str.strip(),
            "service_category": df.get("Service contract category", pd.Series(dtype=str)).fillna("").astype(str).str.strip(),
            "iec_category": df.get("IEC category", pd.Series(dtype=str)).fillna("").astype(str).str.strip(),
        }
    )
    return out.dropna(subset=["start"]).sort_values("start").reset_index(drop=True)


@dataclass(frozen=True)
class TurbineYear:
    farm: str  # "penmanshiel" | "kelmarsh"
    turbine: int
    year: int
    zip_path: Path
    scada_member: str
    status_member: str

    @property
    def turbine_id(self) -> str:
        return f"{self.farm}-{self.turbine:02d}"

    def load(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        with zipfile.ZipFile(self.zip_path) as z:
            return read_scada(z.read(self.scada_member)), read_status(z.read(self.status_member))


_MEMBER_RE = re.compile(r"(Turbine_Data|Status)_(?:Penmanshiel|Kelmarsh)_(\d+)_(\d{4})-\d\d-\d\d_-_", re.I)


def iter_turbine_years(raw_dir: Path, farm: str) -> Iterator[TurbineYear]:
    """Yield one :class:`TurbineYear` per (turbine, year) found in ``raw_dir/<farm>/*.zip``."""
    for zip_path in sorted((raw_dir / farm).glob("*.zip")):
        with zipfile.ZipFile(zip_path) as z:
            members = z.namelist()
        found: dict[tuple[int, int], dict[str, str]] = {}
        for name in members:
            m = _MEMBER_RE.search(name)
            if not m:
                continue
            kind, turbine, year = m.group(1), int(m.group(2)), int(m.group(3))
            found.setdefault((turbine, year), {})[kind] = name
        for (turbine, year), parts in sorted(found.items()):
            if "Turbine_Data" in parts and "Status" in parts:
                yield TurbineYear(farm, turbine, year, zip_path, parts["Turbine_Data"], parts["Status"])
