# Java Auto-Provisioning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `phantasos build` run on any mainstream platform without the user pre-installing a JRE — phantasos provisions its own pinned Temurin JRE 17 on first use, with a `PHANTASOS_JAVA` override. Also bump the pinned OpenAPI Generator to the latest release.

**Architecture:** A new `provision.py` module owns toolchain provisioning: it resolves a `java` binary by checking the `PHANTASOS_JAVA` override, then a local cache, then downloading a pinned, checksum-verified Temurin JRE 17 for the detected `(os, arch)` and extracting it (path-traversal-safe) into `~/.cache/phantasos`. A shared `_download_verified()` helper does streamed-download + SHA256 verification for **both** the JRE and the OpenAPI Generator jar. `generate.py` slims down to "build the command and run it," invoking the resolved java path instead of the literal `"java"`. Pure standard library — no new runtime dependencies.

**Tech Stack:** Python 3.11+ (stdlib: `urllib.request`, `hashlib`, `tarfile`, `zipfile`, `platform`, `tempfile`, `shutil`, `pathlib`), pytest, nox, ruff, mypy. Eclipse Temurin JRE 17 (`jdk-17.0.19+10`, GPLv2+CE, downloaded at runtime — not redistributed). OpenAPI Generator CLI `7.22.0`.

---

## python-pro validation (of "latest patch for both JRE and OAG")

- **JRE `17.0.13+11` → `17.0.19+10`: adopt.** Within-LTS patch bump; runtime security/bugfixes only. OAG output depends on the jar version, not the JRE patch level, so there is **no output-drift risk**. Cost: pinning "latest patch" means the table needs a manual refresh when a new 17.0.x ships (Dependabot doesn't cover a hardcoded table) — a one-command recipe is in "Notes for the executor."
- **OAG `7.7.0` → `7.22.0`: adopt, but treat as a guarded, reversible change — it is NOT a patch.** 15 minor generator releases; generated Python can change, and `patches.py` / vendored components / the two example SDKs assume 7.7.0 output. **Guardrail:** `build()` runs `smoke.smoke()` (imports every generated module + counts ops) on both example specs, in CI and locally — that is the gate. This bump is its own commit (Task 5) and is gated on a full smoke run of both specs in Task 10. If drift is material, fix patches/components or pin OAG back; the Java work does not depend on the OAG bump.

## Design decisions (the contract this plan implements)

1. **Keep OpenAPI Generator (Java); provision Java for the user.** Not replacing the engine.
2. **Provision by runtime download** (consistent with the jar, already fetched on first run). Not a bundled JRE wheel.
3. **Eclipse Temurin JRE 17, pinned to `jdk-17.0.19+10`** (latest 17 LTS patch).
4. **Managed-by-default + `PHANTASOS_JAVA` override.** If `PHANTASOS_JAVA` is set, use that java and skip all download logic.
5. **5 mainstream platforms:** `linux-x64`, `linux-aarch64`, `mac-x64`, `mac-aarch64`, `windows-x64`. Anything else → a precise error pointing at `PHANTASOS_JAVA`.
6. **SHA256 verification on both the JRE and the jar; pinned via a hardcoded table** of constructed Adoptium GitHub-release URLs + checksums (no runtime `api.adoptium.net` query). The Maven jar publishes only `.sha1`/`.md5`, so the jar's SHA256 is computed once from the authentic artifact (SHA1 cross-checked) and pinned.
7. **OAG bumped to `7.22.0`** (latest). Supersedes the earlier "OAG unchanged" note, per explicit user decision; guarded as above.
8. **CI smoke exercises the real auto-provision** (remove `setup-java`; extend the cache to cover the JRE). The override path is covered by a hermetic unit test.
9. **Tests are hermetic** (mock only the network; real checksum + real extraction on tiny fixtures). The single real-download integration path is the CI smoke job.
10. **Docs:** README gains a "Requirements" note that Java is auto-provisioned, documenting `PHANTASOS_JAVA`.

## File structure

| File | Responsibility | Change |
|---|---|---|
| `src/phantasos/provision.py` | Toolchain provisioning: `resolve_java()`, platform detection, pinned JRE table, shared `_download_verified()`, safe extraction, `cache_dir()`, `ProvisionError` | **Create** |
| `src/phantasos/generate.py` | Build the OAG command and run it; `ensure_jar()` checksum-verified via the shared helper; uses resolved java; OAG bumped to 7.22.0 | Modify |
| `tests/test_provision.py` | Unit tests for provisioning (all branches + error paths) | **Create** |
| `tests/test_generate.py` | Unit tests for `ensure_jar` verification + `generate` using resolved java | **Create** |
| `.github/workflows/ci.yml` | Smoke job: drop `setup-java`, extend cache key to include the JRE | Modify (lines 69–92) |
| `noxfile.py` | `smoke` session docstring no longer claims "requires JDK 17" | Modify (lines 104–112) |
| `pyproject.toml` | Adjust ruff `per-file-ignores` (S310 for provision.py; S603 for generate.py) | Modify |
| `README.md` | "Requirements" note: Java auto-provisioned + `PHANTASOS_JAVA` | Modify |

---

### Task 1: Shared verified-download helper + `ProvisionError` + `cache_dir`

**Files:**
- Create: `src/phantasos/provision.py`
- Test: `tests/test_provision.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_provision.py
"""Unit tests for the toolchain provisioner (hermetic — only the network is mocked)."""

import hashlib
import io
import tarfile
from pathlib import Path

import pytest

from phantasos import provision
from phantasos.provision import ProvisionError


class _FakeResp:
    """Minimal context-manager stand-in for urllib.request.urlopen()."""

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._read = False

    def __enter__(self) -> "_FakeResp":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def read(self, n: int = -1) -> bytes:
        if self._read:
            return b""
        self._read = True
        return self._data


def test_download_verified_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = b"hello-jre-bytes"
    monkeypatch.setattr(provision.urllib.request, "urlopen", lambda url: _FakeResp(payload))
    dest = tmp_path / "out.bin"
    provision._download_verified("https://x/y", hashlib.sha256(payload).hexdigest(), dest)
    assert dest.read_bytes() == payload


def test_download_verified_checksum_mismatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(provision.urllib.request, "urlopen", lambda url: _FakeResp(b"corrupt"))
    dest = tmp_path / "out.bin"
    with pytest.raises(ProvisionError, match="checksum mismatch"):
        provision._download_verified("https://x/y", "0" * 64, dest)
    assert not dest.exists()  # atomic: no partial file left behind
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest pytest tests/test_provision.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'phantasos.provision'`.

- [ ] **Step 3: Create `provision.py` with the helper, exception, and cache dir**

```python
# src/phantasos/provision.py
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
```

(The `tarfile`/`zipfile`/`platform`/`shutil`/`dataclass` imports are added now so later tasks don't re-touch the import block.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest pytest tests/test_provision.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/provision.py tests/test_provision.py
git commit -m "feat(provision): add verified-download helper, ProvisionError, cache_dir"
```

---

### Task 2: Path-traversal-safe archive extraction

**Files:**
- Modify: `src/phantasos/provision.py`
- Test: `tests/test_provision.py`

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_provision.py
def _make_tar(tmp_path: Path, members: dict[str, bytes]) -> Path:
    archive = tmp_path / "a.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return archive


def test_safe_extract_normal(tmp_path: Path) -> None:
    archive = _make_tar(tmp_path, {"top/bin/java": b"#!/bin/echo java"})
    dest = tmp_path / "out"
    provision._safe_extract(archive, dest)
    assert (dest / "top" / "bin" / "java").read_bytes() == b"#!/bin/echo java"


def test_safe_extract_rejects_traversal(tmp_path: Path) -> None:
    archive = _make_tar(tmp_path, {"../evil": b"x"})
    with pytest.raises(ProvisionError, match="unsafe path"):
        provision._safe_extract(archive, tmp_path / "out")
```

- [ ] **Step 2: Run to verify they fail**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest pytest tests/test_provision.py -k safe_extract -q`
Expected: FAIL — `AttributeError: module 'phantasos.provision' has no attribute '_safe_extract'`.

- [ ] **Step 3: Implement `_safe_extract`** (imports already present from Task 1)

```python
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
            tf.extractall(dest)  # noqa: S202 — members validated above
```

- [ ] **Step 4: Run to verify they pass**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest pytest tests/test_provision.py -k safe_extract -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/provision.py tests/test_provision.py
git commit -m "feat(provision): add path-traversal-safe archive extraction"
```

---

### Task 3: Platform detection

**Files:**
- Modify: `src/phantasos/provision.py`
- Test: `tests/test_provision.py`

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_provision.py
@pytest.mark.parametrize(
    ("system", "machine", "expected"),
    [
        ("Linux", "x86_64", "linux-x64"),
        ("Linux", "aarch64", "linux-aarch64"),
        ("Darwin", "x86_64", "mac-x64"),
        ("Darwin", "arm64", "mac-aarch64"),
        ("Windows", "AMD64", "windows-x64"),
    ],
)
def test_platform_key(monkeypatch: pytest.MonkeyPatch, system: str, machine: str, expected: str) -> None:
    monkeypatch.setattr(provision.platform, "system", lambda: system)
    monkeypatch.setattr(provision.platform, "machine", lambda: machine)
    assert provision._platform_key() == expected


def test_platform_key_unsupported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(provision.platform, "system", lambda: "Windows")
    monkeypatch.setattr(provision.platform, "machine", lambda: "ARM64")
    with pytest.raises(ProvisionError, match="PHANTASOS_JAVA"):
        provision._platform_key()
```

- [ ] **Step 2: Run to verify they fail**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest pytest tests/test_provision.py -k platform_key -q`
Expected: FAIL — `AttributeError: module 'phantasos.provision' has no attribute '_platform_key'`.

- [ ] **Step 3: Implement detection.** The validity check is against `_JRE` (defined in Task 4). To keep this task independently green, add a temporary empty table now and fill it in Task 4:

```python
_ARCH = {"x86_64": "x64", "amd64": "x64", "arm64": "aarch64", "aarch64": "aarch64"}
_OS = {"Linux": "linux", "Darwin": "mac", "Windows": "windows"}

# Temporary placeholder for Task 3's tests; REPLACED by the real table in Task 4.
_SUPPORTED = {"linux-x64", "linux-aarch64", "mac-x64", "mac-aarch64", "windows-x64"}


def _platform_key() -> str:
    system = platform.system()
    machine = platform.machine()
    osname = _OS.get(system)
    arch = _ARCH.get(machine.lower())
    key = f"{osname}-{arch}" if osname and arch else None
    if key not in _SUPPORTED:
        raise ProvisionError(
            f"no managed Temurin JRE for this platform ({system} {machine}).\n"
            f"Install a JRE 11+ and set PHANTASOS_JAVA=/path/to/java to use it."
        )
    return key
```

- [ ] **Step 4: Run to verify they pass**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest pytest tests/test_provision.py -k platform_key -q`
Expected: PASS (6 passed — 5 parametrized + 1 unsupported).

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/provision.py tests/test_provision.py
git commit -m "feat(provision): detect (os, arch) -> supported platform key"
```

---

### Task 4: Pinned JRE table + `resolve_java()`

The real pinned values below were fetched from Adoptium for `jdk-17.0.19+10` (latest Temurin 17 LTS patch). To re-verify or refresh them, see "Notes for the executor."

**Files:**
- Modify: `src/phantasos/provision.py`
- Test: `tests/test_provision.py`

- [ ] **Step 1: Write the failing tests** (override, missing override, cache hit, download+extract)

```python
# append to tests/test_provision.py
def test_resolve_java_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = tmp_path / "java"
    fake.write_text("")
    monkeypatch.setenv("PHANTASOS_JAVA", str(fake))
    assert provision.resolve_java() == fake


def test_resolve_java_override_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PHANTASOS_JAVA", "/no/such/java")
    with pytest.raises(ProvisionError, match="PHANTASOS_JAVA points to a missing path"):
        provision.resolve_java()


def test_resolve_java_cache_hit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PHANTASOS_JAVA", raising=False)
    monkeypatch.setenv("PHANTASOS_CACHE", str(tmp_path))
    monkeypatch.setattr(provision, "_platform_key", lambda: "linux-x64")
    home = tmp_path / f"temurin-{provision._JRE_RELEASE}-linux-x64"
    java = home / provision._JRE["linux-x64"].java_subpath
    java.parent.mkdir(parents=True)
    java.write_text("")
    monkeypatch.setattr(provision, "_download_verified", lambda *a: pytest.fail("downloaded"))
    assert provision.resolve_java() == java


def test_resolve_java_downloads_and_extracts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PHANTASOS_JAVA", raising=False)
    monkeypatch.setenv("PHANTASOS_CACHE", str(tmp_path))
    monkeypatch.setattr(provision, "_platform_key", lambda: "linux-x64")

    def fake_dl(url: str, sha: str, dest: Path) -> None:
        with tarfile.open(dest, "w:gz") as tf:
            info = tarfile.TarInfo(f"temurin-{provision._JRE_RELEASE}-linux-x64/bin/java")
            data = b"#!/bin/echo java"
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))

    monkeypatch.setattr(provision, "_download_verified", fake_dl)
    java = provision.resolve_java()
    assert java.name == "java" and java.exists()
```

- [ ] **Step 2: Run to verify they fail**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest pytest tests/test_provision.py -k resolve_java -q`
Expected: FAIL — `AttributeError: ... has no attribute 'resolve_java'` / `_JRE` / `_JRE_RELEASE`.

- [ ] **Step 3: Implement the table + `resolve_java()`.** Delete the temporary `_SUPPORTED` set from Task 3 and change `_platform_key`'s check from `key not in _SUPPORTED` to `key not in _JRE`. Then add:

```python
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
```

- [ ] **Step 4: Run to verify they pass (full provision suite)**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest pytest tests/test_provision.py -q`
Expected: PASS — all provision tests green (incl. platform_key now validating against `_JRE`).

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/provision.py tests/test_provision.py
git commit -m "feat(provision): pinned Temurin JRE 17.0.19+10 table + resolve_java()"
```

---

### Task 5: Verify the OAG jar + bump OAG to 7.22.0 (DRY via the shared helper)

> ⚠️ **Guarded change.** Bumping OAG from 7.7.0 to 7.22.0 can change generated output. This is its own commit; the smoke run in Task 10 is the gate. If smoke/patches break, fix them or revert this commit (the Java work does not depend on it).

**Files:**
- Modify: `src/phantasos/generate.py`
- Test: `tests/test_generate.py`

- [ ] **Step 1: (Re)confirm the OAG 7.22.0 jar SHA256**

Maven publishes only `.sha1`/`.md5` for the jar, so the SHA256 is computed from the artifact (SHA1 cross-checked). Already done; the pinned value is `3f1e6ce5c6ad4f15242c6170ab43aad4bad771622617eeece4a7d4f72ffaf329`. To re-verify:

```bash
base="https://repo1.maven.org/maven2/org/openapitools/openapi-generator-cli/7.22.0/openapi-generator-cli-7.22.0.jar"
curl -fsSL "$base" -o /tmp/oag.jar
test "$(sha1sum /tmp/oag.jar | awk '{print $1}')" = "$(curl -fsSL "$base.sha1")" && echo "sha1 cross-check OK"
sha256sum /tmp/oag.jar | awk '{print $1}'   # expect 3f1e6ce5...f329
```
Expected: `sha1 cross-check OK` and the SHA256 above.

- [ ] **Step 2: Write the failing test**

```python
# tests/test_generate.py
"""Unit tests for jar provisioning and the OAG invocation (network mocked)."""

from pathlib import Path

import pytest

from phantasos import generate


def test_ensure_jar_uses_verified_download(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PHANTASOS_CACHE", str(tmp_path))
    called: dict[str, object] = {}

    def fake_dl(url: str, sha: str, dest: Path) -> None:
        called["url"], called["sha"] = url, sha
        dest.write_bytes(b"jar")

    monkeypatch.setattr(generate.provision, "_download_verified", fake_dl)
    jar = generate.ensure_jar()
    assert jar.exists()
    assert called["url"] == generate._JAR_URL
    assert called["sha"] == generate.JAR_SHA256
    assert "7.22.0" in str(jar)
    monkeypatch.setattr(generate.provision, "_download_verified", lambda *a: pytest.fail("re-downloaded"))
    assert generate.ensure_jar() == jar
```

- [ ] **Step 3: Run to verify it fails**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest pytest tests/test_generate.py -k ensure_jar -q`
Expected: FAIL — `AttributeError: module 'phantasos.generate' has no attribute 'JAR_SHA256'`.

- [ ] **Step 4: Rewrite the top of `generate.py`** (bump OAG, verify jar via shared helper)

```python
"""Run OpenAPI Generator (python) — jar fetch/verify + invocation."""

from __future__ import annotations

import subprocess
from pathlib import Path

from . import provision

OAG_VERSION = "7.22.0"
_JAR_URL = (
    "https://repo1.maven.org/maven2/org/openapitools/openapi-generator-cli/"
    f"{OAG_VERSION}/openapi-generator-cli-{OAG_VERSION}.jar"
)
# Maven publishes only .sha1/.md5 for this jar; this SHA256 was computed from the
# authentic artifact (SHA1 cross-checked against Maven) and pinned. See Task 5 Step 1.
JAR_SHA256 = "3f1e6ce5c6ad4f15242c6170ab43aad4bad771622617eeece4a7d4f72ffaf329"


def ensure_jar() -> Path:
    jar = provision.cache_dir() / f"openapi-generator-cli-{OAG_VERSION}.jar"
    if not jar.exists():
        print(f"  fetching openapi-generator-cli {OAG_VERSION} -> {jar}")
        provision._download_verified(_JAR_URL, JAR_SHA256, jar)
    return jar
```

(The old `check_java()`, `_cache_dir()`, and the `urllib`/`shutil`/`os` imports are removed — `generate()` uses `provision.resolve_java()` in Task 6.)

- [ ] **Step 5: Run to verify it passes**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest pytest tests/test_generate.py -k ensure_jar -q`
Expected: PASS (1 passed).

- [ ] **Step 6: Commit**

```bash
git add src/phantasos/generate.py tests/test_generate.py
git commit -m "feat(generate): verify OAG jar via shared helper; bump OAG to 7.22.0"
```

---

### Task 6: `generate()` uses the resolved java path

**Files:**
- Modify: `src/phantasos/generate.py`
- Test: `tests/test_generate.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_generate.py
def test_generate_invokes_resolved_java(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(generate.provision, "resolve_java", lambda: Path("/fake/java"))
    monkeypatch.setattr(generate, "ensure_jar", lambda: tmp_path / "oag.jar")
    captured: dict[str, list[str]] = {}

    def fake_run(cmd: list[str], **kw: object) -> object:
        captured["cmd"] = cmd
        return None

    monkeypatch.setattr(generate.subprocess, "run", fake_run)
    generate.generate("spec.yaml", str(tmp_path), "pkg", library="urllib3")
    assert captured["cmd"][0] == "/fake/java"
    assert "-jar" in captured["cmd"]
    assert str(tmp_path / "oag.jar") in captured["cmd"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest pytest tests/test_generate.py -k resolved_java -q`
Expected: FAIL — `AssertionError` (cmd[0] is still the literal `"java"`).

- [ ] **Step 3: Update `generate()`**

```python
def generate(
    spec_path: str, out_dir: str, package: str, library: str = "urllib3"
) -> None:
    java = provision.resolve_java()
    jar = ensure_jar()
    cmd = [
        str(java),
        "-jar",
        str(jar),
        "generate",
        "-g",
        "python",
        "-i",
        spec_path,
        "-o",
        out_dir,
        "--package-name",
        package,
        "--additional-properties",
        f"library={library},disallowAdditionalPropertiesIfNotPresent=false",
        "--global-property",
        "modelDocs=false,apiDocs=false,modelTests=false,apiTests=false",
        "--inline-schema-options",
        "RESOLVE_INLINE_ENUMS=true",
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)  # noqa: S603
```

- [ ] **Step 4: Run to verify it passes (full unit suite)**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest pytest tests/ -q`
Expected: PASS — all existing tests plus the new `test_provision.py` / `test_generate.py`.

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generate.py tests/test_generate.py
git commit -m "feat(generate): invoke the resolved (auto-provisioned) java"
```

---

### Task 7: Lint/type config + nox docstring

**Files:**
- Modify: `pyproject.toml` (ruff per-file-ignores), `noxfile.py` (smoke docstring)

- [ ] **Step 1: Update ruff per-file-ignores**

In `pyproject.toml`, the existing line is `"src/phantasos/generate.py" = ["S603", "S404", "S310"]`. `generate.py` no longer opens URLs (moved to `provision.py`) but still runs a subprocess; `provision.py` opens URLs. Replace with:

```toml
"src/phantasos/generate.py" = ["S603"]
"src/phantasos/provision.py" = ["S310"]
```

- [ ] **Step 2: Update the `smoke` session docstring in `noxfile.py`**

```python
    """Build the example SDKs end-to-end.

    phantasos auto-provisions a pinned Temurin JRE 17 on first run (cached under
    ~/.cache/phantasos), so no system Java is required; set PHANTASOS_JAVA to use
    your own JVM. Needs network for the one-time JRE + OAG jar download. Not in
    the default session list. Each SDK is written to a sibling dir (see transformations/).
    """
```

- [ ] **Step 3: Run lint + type-check**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.venvs/phantasos uv run nox -s lint type_check`
Expected: PASS — ruff and mypy clean. (If ruff reports an unused `# noqa`, remove that specific code; if it flags S202 in `provision.py`, confirm the `# noqa: S202` comments from Task 2 are present.)

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml noxfile.py
git commit -m "chore: ruff ignores for provision.py; smoke docstring no longer requires a JDK"
```

---

### Task 8: CI smoke job — drop `setup-java`, cache the JRE

**Files:**
- Modify: `.github/workflows/ci.yml` (lines 69–92)

- [ ] **Step 1: Rewrite the `smoke` job**

```yaml
  smoke:
    name: Build smoke (auto-provisioned Java)
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@df4cb1c069e1874edd31b4311f1884172cec0e10 # v6.0.3
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@fac544c07dec837d0ccb6301d7b5580bf5edae39 # v8.2.0
        with:
          enable-cache: true
      # Caches both the OAG jar and the auto-provisioned Temurin JRE so the
      # one-time downloads are reused across runs. NO actions/setup-java — the
      # point of this job is to prove phantasos provisions Java itself.
      - name: Cache OAG jar + Temurin JRE
        uses: actions/cache@27d5ce7f107fe9357f9df03efb73ab90386fccae # v5.0.5
        with:
          path: ~/.cache/phantasos
          key: phantasos-toolchain-oag7.22.0-jre17.0.19
      - name: Build example SDKs (Java auto-provisioned)
        run: uv run nox -s smoke
```

- [ ] **Step 2: Validate the workflow YAML**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('valid')"`
Expected: `valid`.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: smoke job auto-provisions Java (drop setup-java; cache the JRE)"
```

---

### Task 9: Docs — Requirements note

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add a Requirements note** (place after the install section; match surrounding heading style)

```markdown
## Requirements

`phantasos build` runs OpenAPI Generator, which needs a Java runtime. **You do not
need to install Java** — on first build, phantasos downloads a pinned, checksum-verified
[Eclipse Temurin](https://adoptium.net/) JRE 17 for your platform into `~/.cache/phantasos`
(a one-time ~40 MB download; override the location with `PHANTASOS_CACHE`).

Supported platforms for auto-provisioning: Linux (x64/arm64), macOS (x64/arm64),
Windows (x64). On any other platform — or to use your own JVM — install a JRE 11+ and set
`PHANTASOS_JAVA=/path/to/java`.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: document Java auto-provisioning and the PHANTASOS_JAVA override"
```

---

### Task 10: Full verification (the real proof — incl. the OAG-bump gate)

**Files:** none (verification only).

- [ ] **Step 1: Full unit suite + lint + type-check**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.venvs/phantasos uv run nox -s lint type_check tests-3.12`
Expected: all green. The new tests are hermetic and must not hit the network.

- [ ] **Step 2: Real end-to-end auto-provision on BOTH specs (also the OAG-bump gate)**

In an environment with **no `java` on PATH** and a clean cache:
```bash
rm -rf ~/.cache/phantasos
UV_PROJECT_ENVIRONMENT=$HOME/.venvs/phantasos uv run phantasos build transformations/prisma-browser.py
UV_PROJECT_ENVIRONMENT=$HOME/.venvs/phantasos uv run phantasos build transformations/adem.py
```
Expected: each prints `provisioning Temurin JRE jdk-17.0.19+10 (...one-time)` (first build only), then `fetching openapi-generator-cli 7.22.0`, then a build summary with **0 smoke failures** — with no pre-installed Java.
**OAG-bump gate:** if either build reports smoke failures or `patches` counts drop to 0 unexpectedly (a sign 7.22.0's output shifted and patches no longer match), STOP — investigate the generated diff. Fix `patches.py`/components, or revert the Task 5 OAG bump and keep 7.7.0. The Java work stands on its own either way.

- [ ] **Step 3: Override path**

```bash
PHANTASOS_JAVA="$HOME/.cache/phantasos/temurin-jdk-17.0.19+10-linux-x64/bin/java" \
  UV_PROJECT_ENVIRONMENT=$HOME/.venvs/phantasos uv run phantasos build transformations/adem.py
```
Expected: builds without any new JRE download (uses the provided java).

- [ ] **Step 4: Confirm no new runtime dependency crept in**

Run: `grep -nE 'dependencies *=' -A6 pyproject.toml | head -20`
Expected: `[project].dependencies` unchanged (still just `ruamel.yaml`, `jinja2`) — provisioning is stdlib-only.

- [ ] **Step 5: Final review against the design decisions**

Re-read the "Design decisions" section and confirm each of the 10 points is satisfied. If all green, the feature is complete.

---

## Notes for the executor

- **Checksums are real and pre-fetched** (Adoptium for the JRE; computed-from-artifact for the jar with SHA1 cross-check). Do not alter them by hand. To **refresh the JRE** to a newer 17 patch:
  ```bash
  REL="jdk-17.0.<patch>+<build>"; TAG="${REL/+/%2B}"; V="17.0.<patch>_<build>"
  for pf in "linux x64 tar.gz" "linux aarch64 tar.gz" "mac x64 tar.gz" "mac aarch64 tar.gz" "windows x64 zip"; do
    set -- $pf; os=$1; arch=$2; ext=$3
    base="https://github.com/adoptium/temurin17-binaries/releases/download/${TAG}/OpenJDK17U-jre_${arch}_${os}_hotspot_${V}.${ext}"
    echo "$os-$arch  $base  $(curl -fsSL "${base}.sha256.txt" | awk '{print $1}')"
  done
  ```
  Then update `_JRE_RELEASE`, `_TEMURIN_BASE`, the per-platform URLs/sha256, and the CI cache key.
- **macOS layout gotcha:** macOS Temurin archives nest the runtime under `Contents/Home`, hence `java_subpath="Contents/Home/bin/java"` for the two `mac-*` keys. Linux/Windows are flat (`bin/java`, `bin/java.exe`).
- **Why pinned table over live API:** deterministic builds, no dependency on `api.adoptium.net` uptime at build time, and the security-critical checksums live in version control where they're reviewed.
- **OAG bump is reversible:** it's isolated to Task 5 (`OAG_VERSION` + `JAR_SHA256`). Reverting that one commit restores 7.7.0; nothing in the Java provisioning depends on the OAG version.
- **Filesystem note (this sandbox only):** the repo lives on a symlink-less FUSE mount, so use `UV_PROJECT_ENVIRONMENT=$HOME/.venvs/phantasos` for any `uv run`. On normal filesystems this isn't needed.
