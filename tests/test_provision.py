"""Unit tests for the toolchain provisioner (hermetic — only the network is mocked)."""

import hashlib
import io
import tarfile
from pathlib import Path

import pytest

from phantasos.generator.sdk import provision
from phantasos.generator.sdk.provision import ProvisionError


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


def test_download_verified_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = b"hello-jre-bytes"
    monkeypatch.setattr("urllib.request.urlopen", lambda url: _FakeResp(payload))
    dest = tmp_path / "out.bin"
    sha = hashlib.sha256(payload).hexdigest()
    provision._download_verified("https://x/y", sha, dest)
    assert dest.read_bytes() == payload


def test_download_verified_checksum_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("urllib.request.urlopen", lambda url: _FakeResp(b"corrupt"))
    dest = tmp_path / "out.bin"
    with pytest.raises(ProvisionError, match="checksum mismatch"):
        provision._download_verified("https://x/y", "0" * 64, dest)
    assert not dest.exists()  # atomic: no partial file left behind


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
def test_platform_key(
    monkeypatch: pytest.MonkeyPatch, system: str, machine: str, expected: str
) -> None:
    monkeypatch.setattr("platform.system", lambda: system)
    monkeypatch.setattr("platform.machine", lambda: machine)
    assert provision._platform_key() == expected


def test_platform_key_unsupported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("platform.system", lambda: "Windows")
    monkeypatch.setattr("platform.machine", lambda: "ARM64")
    with pytest.raises(ProvisionError, match="PHANTASOS_JAVA"):
        provision._platform_key()


def test_resolve_java_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = tmp_path / "java"
    fake.write_text("")
    monkeypatch.setenv("PHANTASOS_JAVA", str(fake))
    assert provision.resolve_java() == fake


def test_resolve_java_override_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PHANTASOS_JAVA", "/no/such/java")
    with pytest.raises(ProvisionError, match="PHANTASOS_JAVA points to a missing path"):
        provision.resolve_java()


def test_resolve_java_cache_hit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("PHANTASOS_JAVA", raising=False)
    monkeypatch.setenv("PHANTASOS_CACHE", str(tmp_path))
    monkeypatch.setattr(provision, "_platform_key", lambda: "linux-x64")
    home = tmp_path / f"temurin-{provision._JRE_RELEASE}-linux-x64"
    java = home / provision._JRE["linux-x64"].java_subpath
    java.parent.mkdir(parents=True)
    java.write_text("")
    monkeypatch.setattr(
        provision, "_download_verified", lambda *a: pytest.fail("downloaded")
    )
    assert provision.resolve_java() == java


def test_resolve_java_downloads_and_extracts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("PHANTASOS_JAVA", raising=False)
    monkeypatch.setenv("PHANTASOS_CACHE", str(tmp_path))
    monkeypatch.setattr(provision, "_platform_key", lambda: "linux-x64")

    def fake_dl(url: str, sha: str, dest: Path) -> None:
        member = f"temurin-{provision._JRE_RELEASE}-linux-x64/bin/java"
        with tarfile.open(dest, "w:gz") as tf:
            info = tarfile.TarInfo(member)
            data = b"#!/bin/echo java"
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))

    monkeypatch.setattr(provision, "_download_verified", fake_dl)
    java = provision.resolve_java()
    assert java.name == "java" and java.exists()
