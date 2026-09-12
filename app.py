"""Root entrypoint for WindTurbine-TSLM Streamlit demo."""

import sys
from pathlib import Path

# Add repo root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from demo.app import main

if __name__ == "__main__":
    main()
