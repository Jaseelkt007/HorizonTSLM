"""Build the window table for one farm without TimeNet (fast iteration / inspection).

    DATA_DIR=~/data uv run python scripts/build_windows.py penmanshiel --years 2018 --out /tmp/pen2018.parquet
"""

import argparse
from pathlib import Path

from turbine_tslm.connectors.cubico.base import build_window_table, data_dir

p = argparse.ArgumentParser()
p.add_argument("farm", choices=["penmanshiel", "kelmarsh"])
p.add_argument("--years", type=int, nargs="*")
p.add_argument("--out", type=Path)
a = p.parse_args()
df = build_window_table(a.farm, data_dir() / "raw", tuple(a.years) if a.years else None)
print(df.groupby(["split", "is_positive"]).size().unstack(fill_value=0))
print(df[df.is_positive].groupby(["horizon_h", "label"]).size().unstack(fill_value=0))
if a.out:
    df.to_parquet(a.out, index=False)
    print("wrote", a.out, df.shape)
