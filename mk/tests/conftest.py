import sys
from pathlib import Path

# Ensure mk/ and repo root are in sys.path
MK_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = MK_DIR.parent

for p in [MK_DIR, REPO_ROOT]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
