"""Smoke check: import every generated module (in isolation) and count operations."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import venv
from pathlib import Path
from typing import Any

from . import provision

_SKIP_ENV = "PHANTASOS_SKIP_SMOKE"
# Vars that would leak the *parent* environment into the isolated subprocess and
# defeat the isolation (parent packages shadowing the venv, interpreter breakage).
_STRIP = ("VIRTUAL_ENV", "PYTHONHOME", "PYTHONPATH", "PYTHONSTARTUP")


class SmokeError(RuntimeError):
    """Raised when the isolated smoke environment cannot be provisioned."""


def _sanitized_env() -> dict[str, str]:
    """A copy of os.environ with venv/python path vars stripped."""
    return {k: v for k, v in os.environ.items() if k not in _STRIP}


def _count_operations(project_dir: str, package: str) -> int:
    """Count public API operations by scanning api/*_api.py text (no imports needed)."""
    ops = 0
    api_dir = Path(project_dir) / package / "api"
    for f in sorted(api_dir.glob("*_api.py")):
        for m in re.finditer(r"^    def ([a-z][a-zA-Z0-9_]*)\(", f.read_text(), re.M):
            if not m.group(1).endswith(
                ("_with_http_info", "_without_preload_content")
            ):
                ops += 1
    return ops


def _venv_python(venv_dir: Path) -> Path:
    """Path to the interpreter inside a created venv (cross-platform)."""
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _ensure_smoke_venv(project_dir: Path) -> Path:
    """Create (or reuse) a cached venv holding the SDK's declared deps; return its python."""
    reqs = project_dir / "requirements.txt"
    if not reqs.exists():
        raise SmokeError(
            f"no requirements.txt in {project_dir}; cannot isolate the smoke check. "
            f"Pass --no-smoke to skip, or build a spec that emits one."
        )
    key = hashlib.sha256(reqs.read_bytes()).hexdigest()[:16]
    venv_dir = provision.cache_dir() / "smoke-envs" / key
    py = _venv_python(venv_dir)
    ready = venv_dir / ".ready"
    if ready.exists() and py.exists():
        return py
    shutil.rmtree(venv_dir, ignore_errors=True)
    venv.EnvBuilder(with_pip=True).create(venv_dir)
    subprocess.run(  # noqa: S603
        [str(py), "-m", "pip", "install", "-q", "-r", str(reqs)],
        check=True,
        env=_sanitized_env(),
    )
    ready.write_text("")  # mark complete only after a successful install
    return py
