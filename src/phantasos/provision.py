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


def _safe_extract(archive: Path, dest: Path) -> None:
    """Extract a .tar.gz or .zip into `dest`, rejecting path-traversal members."""
    dest = dest.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    if archive.name.endswith(".zip"):
        with zipfile.ZipFile(archive) as zf:
            for name in zf.namelist():
                if not (dest / name).resolve().is_relative_to(dest):
                    raise ProvisionError(f"unsafe path in archive: {name}")
            zf.extractall(dest)  # noqa: S202 — members validated above
    else:
        with tarfile.open(archive) as tf:
            for member in tf.getmembers():
                if not (dest / member.name).resolve().is_relative_to(dest):
                    raise ProvisionError(f"unsafe path in archive: {member.name}")
            tf.extractall(dest, filter="data")  # noqa: S202 — members validated + data filter


_ARCH = {"x86_64": "x64", "amd64": "x64", "arm64": "aarch64", "aarch64": "aarch64"}
_OS = {"Linux": "linux", "Darwin": "mac", "Windows": "windows"}


def _platform_key() -> str:
    system = platform.system()
    machine = platform.machine()
    osname = _OS.get(system)
    arch = _ARCH.get(machine.lower())
    key = f"{osname}-{arch}" if osname and arch else None
    if key not in _JRE:
        raise ProvisionError(
            f"no managed Temurin JRE for this platform ({system} {machine}).\n"
            f"Install a JRE 11+ and set PHANTASOS_JAVA=/path/to/java to use it."
        )
    return key


@dataclass(frozen=True)
class _Jre:
    url: str
    sha256: str
    java_subpath: str  # path to the java binary, relative to the extracted home dir


_JRE_RELEASE = "jdk-17.0.19+10"  # pinned latest Temurin 17 LTS patch
_TEMURIN_BASE = "https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.19%2B10"

_JRE: dict[str, _Jre] = {
    "linux-x64": _Jre(
        url=f"{_TEMURIN_BASE}/OpenJDK17U-jre_x64_linux_hotspot_17.0.19_10.tar.gz",
        sha256="adb5a2364baa51de1ef91bb9911f5a61d24b045fe1d6647cb8050272a3a8ee75",
        java_subpath="bin/java",
    ),
    "linux-aarch64": _Jre(
        url=f"{_TEMURIN_BASE}/OpenJDK17U-jre_aarch64_linux_hotspot_17.0.19_10.tar.gz",
        sha256="aae834297a87736869745be7c1fca3207ea9167c5824f41c88b0ebb2e3ccb9b1",
        java_subpath="bin/java",
    ),
    "mac-x64": _Jre(
        url=f"{_TEMURIN_BASE}/OpenJDK17U-jre_x64_mac_hotspot_17.0.19_10.tar.gz",
        sha256="91bbd07b9c65d9ecbe1fa0081b3c1ad549ed34ed21085a72fdb76598a740b54c",
        java_subpath="Contents/Home/bin/java",
    ),
    "mac-aarch64": _Jre(
        url=f"{_TEMURIN_BASE}/OpenJDK17U-jre_aarch64_mac_hotspot_17.0.19_10.tar.gz",
        sha256="cef790b404cf168fd1a8a7abc5054fbb442c7d4bfe390cceccfe3f64b9b776a9",
        java_subpath="Contents/Home/bin/java",
    ),
    "windows-x64": _Jre(
        url=f"{_TEMURIN_BASE}/OpenJDK17U-jre_x64_windows_hotspot_17.0.19_10.zip",
        sha256="79a598e1fbb4e16582d92c4ee22280a3c4d72fd52606e1e46b1223c0fe53b0da",
        java_subpath="bin/java.exe",
    ),
}


def resolve_java() -> Path:
    """Return a path to a usable `java`, provisioning a pinned Temurin JRE if needed."""
    override = os.environ.get("PHANTASOS_JAVA")
    if override:
        java = Path(override)
        if not java.exists():
            raise ProvisionError(f"PHANTASOS_JAVA points to a missing path: {java}")
        return java

    key = _platform_key()
    asset = _JRE[key]
    home = cache_dir() / f"temurin-{_JRE_RELEASE}-{key}"
    java = home / asset.java_subpath
    if java.exists():
        return java

    print(f"  provisioning Temurin JRE {_JRE_RELEASE} ({key}, ~40 MB, one-time) -> {home}")
    suffix = ".zip" if asset.url.endswith(".zip") else ".tar.gz"
    archive = cache_dir() / f"temurin-{_JRE_RELEASE}-{key}{suffix}"
    _download_verified(asset.url, asset.sha256, archive)

    staging = cache_dir() / f".extract-{key}"
    shutil.rmtree(staging, ignore_errors=True)
    _safe_extract(archive, staging)
    top = next(p for p in staging.iterdir() if p.is_dir())  # single top-level dir
    shutil.rmtree(home, ignore_errors=True)
    os.replace(top, home)
    shutil.rmtree(staging, ignore_errors=True)
    archive.unlink(missing_ok=True)

    if not java.exists():
        raise ProvisionError(f"java not found after extracting {asset.url} (looked for {java})")
    return java
