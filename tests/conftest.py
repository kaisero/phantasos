"""Pytest config for the phantasos framework engine tests.

Ensures the `phantasos` package (under src/) is importable even without an editable
install. SDK-specific tests live with each generated SDK, not here.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# CI (e.g. GitHub Actions) exports FORCE_COLOR, which makes the emitted CLI's Rich
# console emit ANSI escapes even without a TTY — breaking help-output text/panel
# assertions that pass locally (where FORCE_COLOR is unset). Neutralize it so
# rendered CLI output is deterministic across local and CI runs.
os.environ.pop("FORCE_COLOR", None)
