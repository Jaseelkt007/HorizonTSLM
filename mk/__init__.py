"""MK workspace package."""

import sys
from pathlib import Path

_MK_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _MK_DIR.parent

for _p in [_MK_DIR, _REPO_ROOT]:
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
