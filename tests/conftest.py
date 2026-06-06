"""Pytest config for the sdkgen framework engine tests.

Ensures the `sdkgen` package (at the repo root) is importable regardless of how
pytest is invoked. SDK-specific tests live with the generated SDK, not here.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
