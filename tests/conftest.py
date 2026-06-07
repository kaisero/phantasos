"""Pytest config for the phantasos framework engine tests.

Ensures the `phantasos` package (under src/) is importable even without an editable
install. SDK-specific tests live with each generated SDK, not here.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
