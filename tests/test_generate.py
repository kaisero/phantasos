"""Unit tests for jar provisioning and the OAG invocation (network mocked)."""

from pathlib import Path

import pytest

from phantasos.generator.sdk import generate
from phantasos.generator.sdk import generate as _gen
from phantasos.generator.sdk.generate import _oag_cmd


def test_ensure_jar_uses_verified_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PHANTASOS_CACHE", str(tmp_path))
    called: dict[str, object] = {}

    def fake_dl(url: str, sha: str, dest: Path) -> None:
        called["url"], called["sha"] = url, sha
        dest.write_bytes(b"jar")

    monkeypatch.setattr("phantasos.generator.sdk.provision._download_verified", fake_dl)
    jar = generate.ensure_jar()
    assert jar.exists()
    assert called["url"] == generate._JAR_URL
    assert called["sha"] == generate.JAR_SHA256
    assert "7.22.0" in str(jar)

    def _boom(*a: object) -> None:
        pytest.fail("re-downloaded")

    monkeypatch.setattr("phantasos.generator.sdk.provision._download_verified", _boom)
    assert generate.ensure_jar() == jar


def test_generate_invokes_resolved_java(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "phantasos.generator.sdk.provision.resolve_java", lambda: Path("/fake/java")
    )
    monkeypatch.setattr(generate, "ensure_jar", lambda: tmp_path / "oag.jar")
    captured: dict[str, list[str]] = {}

    def fake_run(cmd: list[str], **kw: object) -> object:
        captured["cmd"] = cmd
        return None

    monkeypatch.setattr("phantasos.generator.sdk.generate.subprocess.run", fake_run)
    generate.generate("spec.yaml", str(tmp_path), "pkg", library="urllib3")
    assert captured["cmd"][0] == "/fake/java"
    assert "-jar" in captured["cmd"]
    assert str(tmp_path / "oag.jar") in captured["cmd"]


def test_generate_passes_discriminator_lookup_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "phantasos.generator.sdk.provision.resolve_java", lambda: Path("/fake/java")
    )
    monkeypatch.setattr(generate, "ensure_jar", lambda: tmp_path / "oag.jar")
    captured: dict[str, list[str]] = {}

    def fake_run(cmd: list[str], **kw: object) -> object:
        captured["cmd"] = cmd
        return None

    monkeypatch.setattr("phantasos.generator.sdk.generate.subprocess.run", fake_run)

    generate.generate("spec.yaml", str(tmp_path), "pkg")
    props = captured["cmd"][captured["cmd"].index("--additional-properties") + 1]
    assert "useOneOfDiscriminatorLookup=true" in props

    generate.generate(
        "spec.yaml", str(tmp_path), "pkg", oneof_discriminator_lookup=False
    )
    props = captured["cmd"][captured["cmd"].index("--additional-properties") + 1]
    assert "useOneOfDiscriminatorLookup=false" in props


def test_write_ignore_lists_suppressed_files(tmp_path: Path) -> None:
    from phantasos.generator.sdk import generate

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


def test_generate_cmd_uses_template_dir() -> None:
    from phantasos.generator.sdk import generate

    cmd = generate._oag_cmd(
        "spec.yaml", "/out", "pkg", "urllib3", oneof_discriminator_lookup=True
    )
    assert "-t" in cmd
    i = cmd.index("-t")
    assert cmd[i + 1].endswith("oag_templates/python")


def test_prune_removes_suppressed_files(tmp_path: Path) -> None:
    from phantasos.generator.sdk import generate

    # simulate stale OAG files + a real package + a scaffold file that must survive
    (tmp_path / "setup.py").write_text("old", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("old", encoding="utf-8")
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "python.yml").write_text(
        "old", encoding="utf-8"
    )
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text("keep", encoding="utf-8")
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("", encoding="utf-8")

    generate.prune_suppressed_files(tmp_path)

    assert not (tmp_path / "setup.py").exists()
    assert not (tmp_path / "requirements.txt").exists()
    assert not (tmp_path / ".github" / "workflows" / "python.yml").exists()
    # non-suppressed files survive
    assert (tmp_path / ".github" / "workflows" / "ci.yml").exists()
    assert (tmp_path / "pkg" / "__init__.py").exists()


def test_skip_validate_spec_flag_present_when_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "phantasos.generator.sdk.provision.resolve_java", lambda: "java"
    )
    monkeypatch.setattr(_gen, "ensure_jar", lambda: "oag.jar")
    cmd = _oag_cmd("spec.yaml", "/out", "pkg", "urllib3", True, skip_validate_spec=True)
    assert "--skip-validate-spec" in cmd


def test_skip_validate_spec_absent_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "phantasos.generator.sdk.provision.resolve_java", lambda: "java"
    )
    monkeypatch.setattr(_gen, "ensure_jar", lambda: "oag.jar")
    cmd = _oag_cmd(
        "spec.yaml", "/out", "pkg", "urllib3", True, skip_validate_spec=False
    )
    assert "--skip-validate-spec" not in cmd
