"""MK source package."""

import sys
from pathlib import Path

_SRC_DIR = Path(__file__).resolve().parent
_MK_DIR = _SRC_DIR.parent
_REPO_ROOT = _MK_DIR.parent

for _p in [_MK_DIR, _REPO_ROOT]:
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
