"""Unit tests for jar provisioning and the OAG invocation (network mocked)."""

from pathlib import Path

import pytest

from phantasos import generate


def test_ensure_jar_uses_verified_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PHANTASOS_CACHE", str(tmp_path))
    called: dict[str, object] = {}

    def fake_dl(url: str, sha: str, dest: Path) -> None:
        called["url"], called["sha"] = url, sha
        dest.write_bytes(b"jar")

    monkeypatch.setattr("phantasos.provision._download_verified", fake_dl)
    jar = generate.ensure_jar()
    assert jar.exists()
    assert called["url"] == generate._JAR_URL
    assert called["sha"] == generate.JAR_SHA256
    assert "7.22.0" in str(jar)

    def _boom(*a: object) -> None:
        pytest.fail("re-downloaded")

    monkeypatch.setattr("phantasos.provision._download_verified", _boom)
    assert generate.ensure_jar() == jar


def test_generate_invokes_resolved_java(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("phantasos.provision.resolve_java", lambda: Path("/fake/java"))
    monkeypatch.setattr(generate, "ensure_jar", lambda: tmp_path / "oag.jar")
    captured: dict[str, list[str]] = {}

    def fake_run(cmd: list[str], **kw: object) -> object:
        captured["cmd"] = cmd
        return None

    monkeypatch.setattr("phantasos.generate.subprocess.run", fake_run)
    generate.generate("spec.yaml", str(tmp_path), "pkg", library="urllib3")
    assert captured["cmd"][0] == "/fake/java"
    assert "-jar" in captured["cmd"]
    assert str(tmp_path / "oag.jar") in captured["cmd"]


def test_write_ignore_lists_suppressed_files(tmp_path: Path) -> None:
    from phantasos import generate

    generate.write_openapi_generator_ignore(tmp_path)
    text = (tmp_path / ".openapi-generator-ignore").read_text(encoding="utf-8")
    for f in (
        "setup.py",
        "requirements.txt",
        "tox.ini",
        "git_push.sh",
        ".gitlab-ci.yml",
        ".travis.yml",
        ".github/workflows/python.yml",
        "README.md",
    ):
        assert f in text
