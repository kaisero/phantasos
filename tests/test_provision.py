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
