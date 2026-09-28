#!/usr/bin/env python3
"""Run bp24tron from any working directory."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bp24tron.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
