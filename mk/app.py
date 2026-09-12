"""Entrypoint for WindTurbine-TSLM Streamlit demo in mk/."""

import sys
from pathlib import Path

# Add repo root and mk/ to sys.path
_curr = Path(__file__).resolve().parent
REPO_ROOT = _curr.parent if (_curr.parent / "pyproject.toml").exists() else _curr

for p in [REPO_ROOT, _curr]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

try:
    from mk.dashboard import main
except ImportError:
    from demo.app import main

if __name__ == "__main__":
    main()
