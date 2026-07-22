"""Unit tests for the per-build git snapshot of generated projects."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from phantasos.generator import gitrepo


def _git(args: list[str], cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True
    ).stdout.strip()


def test_snapshot_no_remote_is_noop(tmp_path: Path) -> None:
    (tmp_path / "f.txt").write_text("x", encoding="utf-8")
    result = gitrepo.snapshot(
        tmp_path, distribution="d", author="A", author_email="a@b.c", remote=None
    )
    assert "skipped" in result
    assert not (tmp_path / ".git").exists()


def test_snapshot_inits_branch_remote_and_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if shutil.which("git") is None:
        pytest.skip("git not on PATH")
    # conftest sets this suite-wide; the snapshot must actually run here.
    monkeypatch.delenv("PHANTASOS_SKIP_FINALIZE", raising=False)

    (tmp_path / "pyproject.toml").write_text("[project]\nname='d'\n", encoding="utf-8")
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("", encoding="utf-8")

    remote = "https://github.com/acme/thing.git"
    result = gitrepo.snapshot(
        tmp_path,
        distribution="thing-sdk",
        author="Ada Lovelace",
        author_email="ada@example.com",
        remote=remote,
    )

    assert (tmp_path / ".git").is_dir()
    assert result["remote"] == remote
    assert result["branch"].startswith("phantasos/")
    # branch checked out matches what we reported
    assert _git(["rev-parse", "--abbrev-ref", "HEAD"], tmp_path) == result["branch"]
    # origin points at the configured remote
    assert _git(["remote", "get-url", "origin"], tmp_path) == remote
    # exactly one commit, every file staged (clean tree)
    assert _git(["rev-list", "--count", "HEAD"], tmp_path) == "1"
    assert _git(["status", "--porcelain"], tmp_path) == ""
    # commit message records what/who/whence
    msg = _git(["log", "-1", "--pretty=%B"], tmp_path)
    assert "Generate thing-sdk from phantasos" in msg
    assert "By: Ada Lovelace <ada@example.com>" in msg
    assert "phantasos commit:" in msg
    assert "Generated:" in msg
    # author identity came from the args, not the machine's git config
    assert _git(["log", "-1", "--pretty=%an <%ae>"], tmp_path) == "Ada Lovelace <ada@example.com>"
