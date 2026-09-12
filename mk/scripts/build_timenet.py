"""Script to build and publish Penmanshiel and Kelmarsh datasets into the local TimeNet registry."""

import argparse
import sys
from pathlib import Path

# Add repo root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.connectors.kelmarsh.connector import KelmarshConnector
from src.connectors.penmanshiel.connector import PenmanshielConnector
from timenet.client import TimeNet
from timenet.engine import run_pipeline
from timenet.registry.factory import default_registry_path


def build_connector(connector, registry_path: Path, force: bool = False):
    meta = connector.metadata()
    print(f"\n[*] --------------------------------------------------")
    print(f"[*] Building {meta.name} ({meta.dataset_id} v{meta.dataset_version})")
    print(f"[*] Registry destination: {registry_path}")

    version_dir = run_pipeline(
        connector=connector,
        root=registry_path,
        force=force,
        keep_cache=True,
    )
    print(f"[+] Successfully built and committed dataset to: {version_dir}")

    # Verify loading via TimeNet client
    print(f"[*] Verifying dataset via TimeNet client...")
    client = TimeNet(registry=registry_path)
    dataset = client.load(meta.dataset_id)
    print(f"[+] Loaded successfully! Records count: {len(dataset.records)}, Tasks count: {len(dataset.tasks)}")
    dataset.describe()


def main():
    parser = argparse.ArgumentParser(description="Build and register wind farm datasets in TimeNet.")
    parser.add_argument(
        "--dataset",
        type=str,
        choices=["penmanshiel", "kelmarsh", "all"],
        default="all",
        help="Which dataset to build into TimeNet (default: all)",
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=default_registry_path(),
        help="Path to TimeNet local registry directory",
    )
    parser.add_argument("--force", action="store_true", help="Force rebuild even if committed")
    args = parser.parse_args()

    if args.dataset in ["penmanshiel", "all"]:
        build_connector(PenmanshielConnector(), args.registry, force=args.force)

    if args.dataset in ["kelmarsh", "all"]:
        build_connector(KelmarshConnector(), args.registry, force=args.force)


if __name__ == "__main__":
    main()
