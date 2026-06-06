"""Pytest config: put a generated SDK on sys.path.

Targets prisma-browser-sdk/ by default; override with SDK_UNDER_TEST=<project_dir>
to run the same suite against a freshly sdkgen-built SDK (parity testing).
"""
import os
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SDK = os.environ.get("SDK_UNDER_TEST", str(ROOT / "prisma-browser-sdk"))
sys.path.insert(0, SDK)
warnings.simplefilter("ignore")  # lenient-enum warnings are expected in tests
