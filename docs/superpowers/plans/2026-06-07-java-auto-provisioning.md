# Java Auto-Provisioning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `phantasos build` run on any mainstream platform without the user pre-installing a JRE — phantasos provisions its own pinned Temurin JRE 17 on first use, with a `PHANTASOS_JAVA` override.

**Architecture:** A new `provision.py` module owns toolchain provisioning: it resolves a `java` binary by checking the `PHANTASOS_JAVA` override, then a local cache, then downloading a pinned, checksum-verified Temurin JRE 17 for the detected `(os, arch)` and extracting it (path-traversal-safe) into `~/.cache/phantasos`. A shared `_download_verified()` helper does streamed-download + SHA256 verification for **both** the JRE and the existing OpenAPI Generator jar. `generate.py` slims down to "build the command and run it," invoking the resolved java path instead of the literal `"java"`. Pure standard library — no new runtime dependencies.

**Tech Stack:** Python 3.11+ (stdlib: `urllib.request`, `hashlib`, `tarfile`, `zipfile`, `platform`, `tempfile`, `shutil`, `pathlib`), pytest, nox, ruff, mypy. Eclipse Temurin JRE 17 (GPLv2+CE, downloaded at runtime — not redistributed).

---

## Design decisions (from the grill — the contract this plan implements)

1. **Keep OpenAPI Generator (Java); provision Java for the user.** Not replacing the engine.
2. **Provision by runtime download** (consistent with the jar, which is already fetched on first run). Not a bundled JRE wheel.
3. **Eclipse Temurin JRE 17**, pinned to an exact build.
4. **Managed-by-default + `PHANTASOS_JAVA` override.** Default uses the managed Temurin; if `PHANTASOS_JAVA` is set, use that java and skip all download logic.
5. **5 mainstream platforms:** `linux-x64`, `linux-aarch64`, `mac-x64`, `mac-aarch64`, `windows-x64`. Anything else (incl. Windows-arm64, Alpine/musl) → a precise error pointing at `PHANTASOS_JAVA`.
6. **SHA256 verification on both the JRE and the jar; pin the exact Temurin build.** Refinement (for your review): we pin a hardcoded release + per-platform SHA256 **table** of constructed Adoptium GitHub-release URLs, rather than querying `api.adoptium.net` at runtime. More deterministic, no runtime API dependency, checksums reviewable in source. Checksums are fetched from the authoritative Adoptium source during implementation (Task 4), never hand-written.
7. **CI smoke exercises the real auto-provision** (remove `setup-java`; extend the existing cache to cover the JRE). The override path is covered by a hermetic unit test.
8. **Tests are hermetic** (mock only the network; real checksum + real extraction on tiny fixtures). The single real-download integration path is the CI smoke job.
9. **Docs:** README/docs gain a "Requirements" note that Java is auto-provisioned, documenting `PHANTASOS_JAVA`.

## File structure

| File | Responsibility | Change |
|---|---|---|
| `src/phantasos/provision.py` | Toolchain provisioning: `resolve_java()`, platform detection, pinned JRE table, shared `_download_verified()`, safe extraction, `cache_dir()`, `ProvisionError` | **Create** |
| `src/phantasos/generate.py` | Build the OAG command and run it; `ensure_jar()` now checksum-verified via the shared helper; uses resolved java | Modify |
| `tests/test_provision.py` | Unit tests for provisioning (all branches + error paths) | **Create** |
| `tests/test_generate.py` | Unit tests for `ensure_jar` verification + `generate` using resolved java | **Create** |
| `.github/workflows/ci.yml` | Smoke job: drop `setup-java`, extend cache key to include the JRE | Modify (lines 69–92) |
| `noxfile.py` | `smoke` session docstring no longer claims "requires JDK 17" | Modify (lines 104–112) |
| `pyproject.toml` | Add `provision.py` to ruff `per-file-ignores` (S310 urlopen) | Modify |
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
import tempfile
import urllib.request
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
import tarfile
import io


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

- [ ] **Step 3: Implement `_safe_extract`**

Add the imports `import tarfile` and `import zipfile` to the top of `provision.py`, then add:

```python
def _safe_extract(archive: Path, dest: Path) -> None:
    """Extract a .tar.gz or .zip into `dest`, rejecting path-traversal members."""
    dest = dest.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    if archive.name.endswith(".zip"):
        with zipfile.ZipFile(archive) as zf:
            names = zf.namelist()
            for name in names:
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
Expected: FAIL — `AttributeError: module 'phantasos.provision' has no attribute '_platform_key'` (and `provision.platform` not imported).

- [ ] **Step 3: Implement detection**

Add `import platform` to the top of `provision.py`, then add (note: `_JRE` is defined in Task 4; until then `_platform_key` references the module-level name, so place this function *below* where `_JRE` will live, or define `_JRE: dict[str, _Jre] = {}` now and fill it in Task 4 — this plan defines the empty dict here and fills it in Task 4):

```python
# Set of supported platform keys. The pinned download table (_JRE) is filled in
# the next task; keep the key set here so detection is testable independently.
_SUPPORTED = {"linux-x64", "linux-aarch64", "mac-x64", "mac-aarch64", "windows-x64"}

_ARCH = {"x86_64": "x64", "amd64": "x64", "arm64": "aarch64", "aarch64": "aarch64"}
_OS = {"Linux": "linux", "Darwin": "mac", "Windows": "windows"}


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

**Files:**
- Modify: `src/phantasos/provision.py`
- Test: `tests/test_provision.py`

- [ ] **Step 1: Fetch the REAL pinned release + per-platform SHA256 values**

The JRE table must contain authentic checksums — never hand-write them. Run this to print the pinned Temurin 17 JRE URLs and SHA256s for all 5 platforms, then paste the values into `_JRE` in Step 3:

```bash
REL="jdk-17.0.13+11"; TAG="${REL/+/%2B}"; V="17.0.13_11"
for pf in "linux x64 tar.gz" "linux aarch64 tar.gz" "mac x64 tar.gz" "mac aarch64 tar.gz" "windows x64 zip"; do
  set -- $pf; os=$1; arch=$2; ext=$3
  base="https://github.com/adoptium/temurin17-binaries/releases/download/${TAG}/OpenJDK17U-jre_${arch}_${os}_hotspot_${V}.${ext}"
  sha=$(curl -fsSL "${base}.sha256.txt" | awk '{print $1}')
  echo "$os-$arch  url=$base  sha256=$sha"
done
```
Expected: 5 lines, each with a real 64-hex `sha256`. (If a `.sha256.txt` 404s, the release tag/filename drifted — verify against https://adoptium.net/temurin/releases/?version=17 and update `REL`/`V`.)

- [ ] **Step 2: Write the failing tests** (override, missing override, cache hit, download+extract)

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
    # _download_verified must NOT be called on a cache hit:
    monkeypatch.setattr(provision, "_download_verified", lambda *a: pytest.fail("downloaded"))
    assert provision.resolve_java() == java


def test_resolve_java_downloads_and_extracts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PHANTASOS_JAVA", raising=False)
    monkeypatch.setenv("PHANTASOS_CACHE", str(tmp_path))
    monkeypatch.setattr(provision, "_platform_key", lambda: "linux-x64")
    # Fake the network: write a tar.gz whose single top dir holds bin/java.
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

- [ ] **Step 3: Run to verify they fail**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest pytest tests/test_provision.py -k resolve_java -q`
Expected: FAIL — `AttributeError: ... has no attribute 'resolve_java'` / `_JRE` / `_JRE_RELEASE`.

- [ ] **Step 4: Implement the table + `resolve_java()`**

Add `import shutil` to the top of `provision.py`, add `from dataclasses import dataclass`, then add (replacing the empty `_JRE = {}` placeholder from Task 3 if you used one). Paste the real URLs/SHA256s from Step 1 into the table. `java_subpath` differs by OS — macOS archives nest the runtime under `Contents/Home`:

```python
@dataclass(frozen=True)
class _Jre:
    url: str
    sha256: str
    java_subpath: str  # path to the java binary, relative to the extracted home dir


_JRE_RELEASE = "jdk-17.0.13+11"  # pinned Temurin build

# Values from Task 4 Step 1 (real Adoptium checksums — do not invent).
_JRE: dict[str, _Jre] = {
    "linux-x64": _Jre(
        url="https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.13%2B11/OpenJDK17U-jre_x64_linux_hotspot_17.0.13_11.tar.gz",
        sha256="<paste linux-x64 sha256>",
        java_subpath="bin/java",
    ),
    "linux-aarch64": _Jre(
        url="https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.13%2B11/OpenJDK17U-jre_aarch64_linux_hotspot_17.0.13_11.tar.gz",
        sha256="<paste linux-aarch64 sha256>",
        java_subpath="bin/java",
    ),
    "mac-x64": _Jre(
        url="https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.13%2B11/OpenJDK17U-jre_x64_mac_hotspot_17.0.13_11.tar.gz",
        sha256="<paste mac-x64 sha256>",
        java_subpath="Contents/Home/bin/java",
    ),
    "mac-aarch64": _Jre(
        url="https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.13%2B11/OpenJDK17U-jre_aarch64_mac_hotspot_17.0.13_11.tar.gz",
        sha256="<paste mac-aarch64 sha256>",
        java_subpath="Contents/Home/bin/java",
    ),
    "windows-x64": _Jre(
        url="https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.13%2B11/OpenJDK17U-jre_x64_windows_hotspot_17.0.13_11.zip",
        sha256="<paste windows-x64 sha256>",
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

Now remove the temporary `_SUPPORTED` set from Task 3 and update `_platform_key` to validate against the real table instead:

```python
    if key not in _JRE:
        raise ProvisionError(
            f"no managed Temurin JRE for this platform ({system} {machine}).\n"
            f"Install a JRE 11+ and set PHANTASOS_JAVA=/path/to/java to use it."
        )
    return key
```
(Delete the now-unused `_SUPPORTED` constant.)

- [ ] **Step 5: Run to verify they pass**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest pytest tests/test_provision.py -q`
Expected: PASS (all provision tests green, incl. the 4 resolve_java tests).

- [ ] **Step 6: Commit**

```bash
git add src/phantasos/provision.py tests/test_provision.py
git commit -m "feat(provision): pinned Temurin JRE 17 table + resolve_java()"
```

---

### Task 5: Verify the OAG jar download (DRY via the shared helper)

**Files:**
- Modify: `src/phantasos/generate.py`
- Test: `tests/test_generate.py`

- [ ] **Step 1: Fetch the real OAG jar SHA256**

```bash
curl -fsSL https://repo1.maven.org/maven2/org/openapitools/openapi-generator-cli/7.7.0/openapi-generator-cli-7.7.0.jar.sha256
```
Expected: a 64-hex string. (Maven Central publishes the `.sha256` sidecar next to the jar.)

- [ ] **Step 2: Write the failing test**

```python
# tests/test_generate.py
"""Unit tests for jar provisioning and the OAG invocation (network mocked)."""

from pathlib import Path

import pytest

from phantasos import generate, provision


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
    # Cache hit: second call must not re-download.
    monkeypatch.setattr(generate.provision, "_download_verified", lambda *a: pytest.fail("re-downloaded"))
    assert generate.ensure_jar() == jar
```

- [ ] **Step 3: Run to verify it fails**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest pytest tests/test_generate.py -k ensure_jar -q`
Expected: FAIL — `AttributeError: module 'phantasos.generate' has no attribute 'JAR_SHA256'`.

- [ ] **Step 4: Update `ensure_jar` to verify via the shared helper**

Edit `src/phantasos/generate.py`: replace the top of the file (imports + `_cache_dir`/`ensure_jar`/`check_java`) so it delegates to `provision`. Paste the real jar SHA256 from Step 1 into `JAR_SHA256`:

```python
"""Run OpenAPI Generator (python) — jar fetch/verify + invocation."""

from __future__ import annotations

import subprocess
from pathlib import Path

from . import provision

OAG_VERSION = "7.7.0"
_JAR_URL = (
    "https://repo1.maven.org/maven2/org/openapitools/openapi-generator-cli/"
    f"{OAG_VERSION}/openapi-generator-cli-{OAG_VERSION}.jar"
)
JAR_SHA256 = "<paste OAG jar sha256 from Step 1>"


def ensure_jar() -> Path:
    jar = provision.cache_dir() / f"openapi-generator-cli-{OAG_VERSION}.jar"
    if not jar.exists():
        print(f"  fetching openapi-generator-cli {OAG_VERSION} -> {jar}")
        provision._download_verified(_JAR_URL, JAR_SHA256, jar)
    return jar
```

(`check_java()` and the old `_cache_dir()`/`urllib`/`shutil`/`os` imports are removed — `generate()` will use `provision.resolve_java()` in Task 6.)

- [ ] **Step 5: Run to verify it passes**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest pytest tests/test_generate.py -k ensure_jar -q`
Expected: PASS (1 passed).

- [ ] **Step 6: Commit**

```bash
git add src/phantasos/generate.py tests/test_generate.py
git commit -m "feat(generate): checksum-verify the OAG jar via the shared helper"
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
Expected: FAIL — `AssertionError` on `captured["cmd"][0]` being the literal `"java"`, not `/fake/java`.

- [ ] **Step 3: Update `generate()` to use the resolved java**

In `src/phantasos/generate.py`, change `generate()` so it resolves java first and uses that path as `argv[0]`:

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

- [ ] **Step 4: Run to verify it passes (and the full unit suite)**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest pytest tests/ -q`
Expected: PASS — all existing tests plus the new `test_provision.py`/`test_generate.py`.

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

In `pyproject.toml`, the existing line is `"src/phantasos/generate.py" = ["S603", "S404", "S310"]`. `generate.py` no longer opens URLs (that moved to `provision.py`) but still runs a subprocess; `provision.py` opens URLs. Update to:

```toml
"src/phantasos/generate.py" = ["S603"]
"src/phantasos/provision.py" = ["S310"]
```

- [ ] **Step 2: Update the `smoke` session docstring in `noxfile.py`**

Replace the docstring of the `smoke` session (lines ~105–109) so it no longer claims a JDK must be installed:

```python
    """Build the example SDKs end-to-end.

    phantasos auto-provisions a pinned Temurin JRE 17 on first run (cached under
    ~/.cache/phantasos), so no system Java is required; set PHANTASOS_JAVA to use
    your own JVM. Needs network for the one-time JRE + OAG jar download. Not in
    the default session list. Each SDK is written to a sibling dir (see transformations/).
    """
```

- [ ] **Step 3: Run lint + type-check**

Run: `uv run nox -s lint type_check` (or, if the project venv won't build on your filesystem, `UV_PROJECT_ENVIRONMENT=$HOME/.venvs/phantasos uv run nox -s lint type_check`)
Expected: PASS — ruff and mypy clean. (If ruff flags an unused `# noqa`, remove it; if it flags S202 in `provision.py`, confirm the `# noqa: S202` comments from Task 2 are present.)

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

Replace the whole `smoke:` job so it (a) removes the `setup-java` step — proving the auto-provision works with **no system Java** — and (b) extends the cache key to cover the JRE (so the ~40 MB download happens once, then is reused):

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
          key: phantasos-toolchain-oag7.7.0-jre17.0.13
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

- [ ] **Step 1: Add a Requirements note**

Add a short section to `README.md` near the install/usage instructions (place it after the install section; match the surrounding heading style):

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

### Task 10: Full verification (the real proof)

**Files:** none (verification only).

- [ ] **Step 1: Full unit suite + lint + type-check**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.venvs/phantasos uv run nox -s lint type_check tests-3.12`
Expected: all green. (`tests-3.12` runs pytest with coverage; the new tests are hermetic and must not hit the network.)

- [ ] **Step 2: Real end-to-end auto-provision (the actual feature)**

In an environment with **no `java` on PATH** and a clean cache:
```bash
rm -rf ~/.cache/phantasos
PHANTASOS_JAVA= UV_PROJECT_ENVIRONMENT=$HOME/.venvs/phantasos uv run phantasos build transformations/prisma-browser.py
```
Expected: prints `provisioning Temurin JRE 17.0.13+11 (...one-time)`, then `fetching openapi-generator-cli 7.7.0`, then the normal build summary — **with no pre-installed Java**. Confirms detect → download → checksum → extract → run.

- [ ] **Step 3: Override path**

```bash
PHANTASOS_JAVA=$(command -v java || echo "$HOME/.cache/phantasos/temurin-jdk-17.0.13+11-linux-x64/bin/java") \
  UV_PROJECT_ENVIRONMENT=$HOME/.venvs/phantasos uv run phantasos build transformations/adem.py
```
Expected: builds without any new download (uses the provided java).

- [ ] **Step 4: Confirm no new runtime dependency crept in**

Run: `grep -nE 'dependencies *=' -A6 pyproject.toml | head -20`
Expected: the `[project].dependencies` list is unchanged (still just `ruamel.yaml`, `jinja2`) — provisioning is stdlib-only.

- [ ] **Step 5: Final review against the design decisions**

Re-read the "Design decisions" section above and confirm each of the 9 points is satisfied by the merged changes. If all green, the feature is complete.

---

## Notes for the executor

- **Never fabricate checksums.** The `<paste …>` markers in Tasks 4 and 5 are filled *only* from the fetch commands in those tasks' Step 1. A wrong checksum is a security regression, not a typo.
- **macOS layout gotcha:** macOS Temurin archives nest the runtime under `Contents/Home`, hence `java_subpath="Contents/Home/bin/java"` for the two `mac-*` keys. Linux/Windows are flat (`bin/java`, `bin/java.exe`).
- **Why pinned table over live API:** deterministic builds, no dependency on `api.adoptium.net` uptime at build time, and the security-critical checksums live in version control where they're reviewed. Bumping the JRE = re-run Task 4 Step 1 with a new `REL`/`V` and update the table.
- **Filesystem note (this sandbox only):** the repo lives on a symlink-less FUSE mount, so use `UV_PROJECT_ENVIRONMENT=$HOME/.venvs/phantasos` for any `uv run`. On normal filesystems this isn't needed.
