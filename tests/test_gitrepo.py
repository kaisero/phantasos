"""Unit tests for the per-build git snapshot of generated projects."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from phantasos.generator import gitrepo

_GIT = shutil.which("git")


def _git(args: list[str], cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True).stdout.strip()


def _make_upstream(path: Path) -> str:
    """A local upstream repo with one commit; returns its path as a fetchable remote."""
    path.mkdir()
    _git(["init", "-q", "-b", "main"], path)
    (path / "README.md").write_text("upstream\n", encoding="utf-8")
    (path / "old_only.py").write_text("x = 1\n", encoding="utf-8")
    _git(["add", "-A"], path)
    _git(["-c", "user.name=U", "-c", "user.email=u@x.y", "commit", "-q", "-m", "init"], path)
    return str(path)


def _make_project(path: Path) -> None:
    path.mkdir()
    (path / "pyproject.toml").write_text("[project]\nname='d'\n", encoding="utf-8")
    (path / "pkg").mkdir()
    (path / "pkg" / "__init__.py").write_text("", encoding="utf-8")


def test_snapshot_no_remote_is_noop(tmp_path: Path) -> None:
    (tmp_path / "f.txt").write_text("x", encoding="utf-8")
    result = gitrepo.snapshot(tmp_path, distribution="d", author="A", author_email="a@b.c", remote=None)
    assert "skipped" in result
    assert not (tmp_path / ".git").exists()


@pytest.mark.skipif(_GIT is None, reason="git not on PATH")
def test_snapshot_bases_on_upstream_and_commits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # conftest sets this suite-wide; the snapshot must actually run here.
    monkeypatch.delenv("PHANTASOS_SKIP_FINALIZE", raising=False)
    upstream = _make_upstream(tmp_path / "upstream")
    upstream_tip = _git(["rev-parse", "HEAD"], tmp_path / "upstream")
    project = tmp_path / "proj"
    _make_project(project)

    result = gitrepo.snapshot(
        project,
        distribution="thing-sdk",
        author="Ada Lovelace",
        author_email="ada@example.com",
        remote=upstream,
    )

    assert result["based_on"] == "upstream"
    assert result["branch"].startswith("phantasos/")
    assert _git(["rev-parse", "--abbrev-ref", "HEAD"], project) == result["branch"]
    assert _git(["remote", "get-url", "origin"], project) == upstream
    # the commit sits ON TOP of the fetched upstream tip -> clean one-commit diff
    assert _git(["rev-list", "--count", "HEAD"], project) == "2"
    assert _git(["rev-parse", "HEAD~1"], project) == upstream_tip
    # working tree fully committed; the generated tree replaced the upstream files
    assert _git(["status", "--porcelain"], project) == ""
    files = set(_git(["ls-files"], project).splitlines())
    assert "pyproject.toml" in files and "pkg/__init__.py" in files
    assert "old_only.py" not in files  # upstream-only file dropped in the diff
    # message + author identity
    msg = _git(["log", "-1", "--pretty=%B"], project)
    assert "Generate thing-sdk from phantasos" in msg
    assert "By: Ada Lovelace <ada@example.com>" in msg
    assert "phantasos commit:" in msg and "Generated:" in msg
    assert _git(["log", "-1", "--pretty=%an <%ae>"], project) == "Ada Lovelace <ada@example.com>"


@pytest.mark.skipif(_GIT is None, reason="git not on PATH")
def test_snapshot_falls_back_to_fresh_when_remote_unreachable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PHANTASOS_SKIP_FINALIZE", raising=False)
    project = tmp_path / "proj"
    _make_project(project)

    # a local path that isn't a repo -> fetch fails offline, no network, no prompt
    result = gitrepo.snapshot(
        project,
        distribution="thing-sdk",
        author="A",
        author_email="a@b.c",
        remote=str(tmp_path / "does-not-exist.git"),
    )

    assert result["based_on"] == "fresh"
    assert _git(["rev-list", "--count", "HEAD"], project) == "1"  # root commit
    assert _git(["status", "--porcelain"], project) == ""
