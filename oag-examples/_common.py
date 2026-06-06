"""Shared helpers for the OAG-SDK example scripts."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "oag-sdk"))


def load_dotenv(path: Path = ROOT / ".env") -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def get_client():
    """Load ./.env and build a facade Client (OAuth2 from CLIENT_ID/SECRET/SCOPE)."""
    load_dotenv()
    from prisma_browser.extras import Client

    return Client.from_env()
