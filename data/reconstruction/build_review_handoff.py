"""Backward-compatible entry point for the SCIPRA reviewer handoff.

The preliminary candidate-review handoff is obsolete because corpus membership
is now frozen. Execute the frozen audit handoff builder instead.
"""
from __future__ import annotations

import runpy
from pathlib import Path

HERE = Path(__file__).resolve().parent
runpy.run_path(str(HERE / "build_frozen_review_handoff.py"), run_name="__main__")
