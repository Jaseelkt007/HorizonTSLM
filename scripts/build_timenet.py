"""Build cubico/penmanshiel and cubico/kelmarsh into the local TimeNet registry and verify they load.

    DATA_DIR=~/data uv run python scripts/build_timenet.py [--only penmanshiel|kelmarsh] [--force]

Uses timenet.engine.run_pipeline directly because the connectors live outside the timenet_connectors package.
"""

import argparse

from timenet.client import TimeNet
from timenet.engine import run_pipeline
from timenet.registry.factory import default_registry_path

from turbine_tslm.connectors.cubico.kelmarsh import KelmarshConnector
from turbine_tslm.connectors.cubico.penmanshiel import PenmanshielConnector

p = argparse.ArgumentParser()
p.add_argument("--only", choices=["penmanshiel", "kelmarsh"])
p.add_argument("--force", action="store_true")
a = p.parse_args()
registry = default_registry_path()
for name, cls in (("penmanshiel", PenmanshielConnector), ("kelmarsh", KelmarshConnector)):
    if a.only and a.only != name:
        continue
    conn = cls()
    version_dir = run_pipeline(connector=conn, root=registry, force=a.force, keep_cache=True)
    print(f"[timenet] built {conn.metadata().dataset_id} -> {version_dir}")
    ds = TimeNet(registry=registry).load(conn.metadata().dataset_id)
    ds.describe()
