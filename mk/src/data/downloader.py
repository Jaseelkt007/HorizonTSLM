"""Downloader for Penmanshiel and Kelmarsh wind farm SCADA data from Zenodo."""

import io
import os
import shutil
import urllib.request
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import requests

from src.data.schemas import (
    KELMARSH_ZENODO_RECORD_ID,
    PENMANSHIEL_ZENODO_RECORD_ID,
)


class RemoteZipFile(io.RawIOBase):
    """Seekable stream that reads zip segments using HTTP Range requests without downloading whole file."""

    def __init__(self, url: str):
        self.url = url
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req) as resp:
            self.length = int(resp.headers["Content-Length"])
        self.pos = 0

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        if whence == io.SEEK_SET:
            self.pos = offset
        elif whence == io.SEEK_CUR:
            self.pos += offset
        elif whence == io.SEEK_END:
            self.pos = self.length + offset
        return self.pos

    def tell(self) -> int:
        return self.pos

    def readinto(self, b: bytearray) -> int:
        if self.pos >= self.length:
            return 0
        end = min(self.pos + len(b) - 1, self.length - 1)
        req = urllib.request.Request(self.url, headers={"Range": f"bytes={self.pos}-{end}"})
        with urllib.request.urlopen(req) as resp:
            data = resp.read()
        b[: len(data)] = data
        self.pos += len(data)
        return len(data)


def fetch_zenodo_file_catalog(record_id: str = PENMANSHIEL_ZENODO_RECORD_ID) -> Dict[str, str]:
    """Returns mapping of filename -> download_url for the given Zenodo record."""
    url = f"https://zenodo.org/api/records/{record_id}"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    catalog = {}
    for f in data.get("files", []):
        filename = f.get("key")
        download_url = f.get("links", {}).get("self")
        if filename and download_url:
            catalog[filename] = download_url
    return catalog


def download_static_metadata(target_dir: Path, farm: str = "penmanshiel") -> Tuple[Path, Optional[Path]]:
    """Download static turbine info and signal mapping files for the specified farm."""
    target_dir.mkdir(parents=True, exist_ok=True)
    if farm.lower() == "penmanshiel":
        static_file = target_dir / "Penmanshiel_WT_static.csv"
        mapping_file = target_dir / "Penmanshiel_WT_dataSignalMapping.xlsx"
        record_id = PENMANSHIEL_ZENODO_RECORD_ID
        static_key = "Penmanshiel_WT_static.csv"
        mapping_key = "Penmanshiel_WT_dataSignalMapping.xlsx"
    else:
        static_file = target_dir / "Kelmarsh_WT_static.csv"
        mapping_file = target_dir / "Kelmarsh_WT_dataSignalMapping.csv"
        record_id = KELMARSH_ZENODO_RECORD_ID
        static_key = "Kelmarsh_WT_static.csv"
        mapping_key = "Kelmarsh_WT_dataSignalMapping.csv"

    catalog = fetch_zenodo_file_catalog(record_id=record_id)
    if not static_file.exists() and static_key in catalog:
        resp = requests.get(catalog[static_key], timeout=30)
        static_file.write_bytes(resp.content)

    if not mapping_file.exists() and mapping_key in catalog:
        resp = requests.get(catalog[mapping_key], timeout=30)
        mapping_file.write_bytes(resp.content)

    return static_file, mapping_file


def extract_turbine_year_from_zenodo(
    zip_filename: str,
    turbine_id: int,
    target_dir: Path,
    record_id: str = PENMANSHIEL_ZENODO_RECORD_ID,
    farm: str = "penmanshiel",
    catalog: Optional[Dict[str, str]] = None,
) -> Tuple[Optional[Path], Optional[Path]]:
    """Extract SCADA data and Status log for a specific turbine from a Zenodo zip archive."""
    target_dir.mkdir(parents=True, exist_ok=True)
    if catalog is None:
        catalog = fetch_zenodo_file_catalog(record_id=record_id)

    if zip_filename not in catalog:
        raise ValueError(f"Zip archive {zip_filename} not in Zenodo catalog")

    zip_url = catalog[zip_filename]
    remote = RemoteZipFile(zip_url)
    zf = zipfile.ZipFile(remote)

    data_file_out = None
    status_file_out = None

    farm_prefix = "Penmanshiel" if farm.lower() == "penmanshiel" else "Kelmarsh"
    turb_patterns = [
        f"Turbine_Data_{farm_prefix}_{turbine_id}_",
        f"Turbine_Data_{farm_prefix}_WT{turbine_id:02d}_",
        f"Turbine_Data_{farm_prefix}_{turbine_id:02d}_",
    ]
    status_patterns = [
        f"Status_{farm_prefix}_{turbine_id}_",
        f"Status_{farm_prefix}_WT{turbine_id:02d}_",
        f"Status_{farm_prefix}_{turbine_id:02d}_",
    ]

    for member in zf.namelist():
        if any(p in member for p in turb_patterns) and member.endswith(".csv"):
            dest = target_dir / member
            if not dest.exists():
                with zf.open(member) as src, open(dest, "wb") as dst:
                    shutil.copyfileobj(src, dst)
            data_file_out = dest
        elif any(p in member for p in status_patterns) and member.endswith(".csv"):
            dest = target_dir / member
            if not dest.exists():
                with zf.open(member) as src, open(dest, "wb") as dst:
                    shutil.copyfileobj(src, dst)
            status_file_out = dest

    return data_file_out, status_file_out
