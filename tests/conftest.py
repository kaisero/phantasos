"""Pytest config: put the generated OAG SDK on sys.path."""
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "oag-sdk"))
warnings.simplefilter("ignore")  # lenient-enum warnings are expected in tests
