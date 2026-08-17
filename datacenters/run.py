#!/usr/bin/env python3
"""Compatibility wrapper for the top-level Code Collective runner."""

from __future__ import annotations

import runpy
from pathlib import Path


if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).resolve().parents[1] / "run.py"), run_name="__main__")
