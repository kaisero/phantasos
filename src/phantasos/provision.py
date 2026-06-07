"""Provision the Java toolchain for OpenAPI Generator.

Resolves a `java` binary without requiring the user to pre-install a JRE:
honors the PHANTASOS_JAVA override, else uses a pinned, checksum-verified
Temurin JRE 17 cached under ~/.cache/phantasos. Standard library only.
"""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
import tarfile
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path


class ProvisionError(RuntimeError):
    """Raised when the Java toolchain cannot be provisioned."""


def cache_dir() -> Path:
    """Shared on-disk cache for the OAG jar and the managed JRE."""
    base = Path(os.environ.get("PHANTASOS_CACHE", Path.home() / ".cache" / "phantasos"))
    base.mkdir(parents=True, exist_ok=True)
    return base


def _download_verified(url: str, sha256: str, dest: Path) -> None:
    """Stream `url` to `dest`, verifying SHA256. Atomic: `dest` appears only on success."""
    digest = hashlib.sha256()
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dest.parent, suffix=".part")
    try:
        with os.fdopen(fd, "wb") as out, urllib.request.urlopen(url) as resp:  # noqa: S310
            for chunk in iter(lambda: resp.read(1 << 20), b""):
                out.write(chunk)
                digest.update(chunk)
        actual = digest.hexdigest()
        if actual != sha256:
            raise ProvisionError(
                f"checksum mismatch for {url}\n"
                f"  expected {sha256}\n  got      {actual}"
            )
        os.replace(tmp, dest)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
