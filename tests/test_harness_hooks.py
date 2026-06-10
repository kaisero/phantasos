"""Subprocess-level tests for the .claude/hooks quality-harness scripts."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent / ".claude" / "hooks"


def run_hook(
    script: str,
    payload: dict[str, object],
    config: Path,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PHANTASOS_HARNESS_CONFIG"] = str(config)
    env.update(extra_env or {})
    return subprocess.run(
        [sys.executable, str(HOOKS_DIR / script)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )


@pytest.fixture()
def config(tmp_path: Path) -> Path:
    cfg = tmp_path / "harness.toml"
    cfg.write_text(
        'protected_globs = ["products/*/overrides/tests/test_sdk_crud_live.py*",'
        ' "tests/acceptance/**"]\n'
        'fast_gate_command = ["python3", "-c", "raise SystemExit(0)"]\n'
        "fast_gate_enabled = true\n"
        "max_consecutive_blocks = 3\n"
    )
    return cfg


def _decision(proc: subprocess.CompletedProcess[str]) -> str | None:
    if not proc.stdout.strip():
        return None
    out = json.loads(proc.stdout)
    decision = out.get("hookSpecificOutput", {}).get("permissionDecision")
    return str(decision) if decision is not None else None


class TestFreezeOracle:
    def test_denies_write_to_protected_relative_path(self, config: Path) -> None:
        proc = run_hook(
            "freeze_oracle.py",
            {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": (
                        "products/x/overrides/tests/test_sdk_crud_live.py.jinja"
                    )
                },
                "cwd": "/repo",
            },
            config,
        )
        assert proc.returncode == 0
        assert _decision(proc) == "deny"

    def test_denies_edit_to_protected_absolute_path(
        self, config: Path, tmp_path: Path
    ) -> None:
        target = tmp_path / "repo" / "tests" / "acceptance" / "test_x.py"
        proc = run_hook(
            "freeze_oracle.py",
            {
                "tool_name": "Edit",
                "tool_input": {"file_path": str(target)},
                "cwd": str(tmp_path / "repo"),
            },
            config,
        )
        assert _decision(proc) == "deny"

    def test_allows_unprotected_path(self, config: Path) -> None:
        proc = run_hook(
            "freeze_oracle.py",
            {
                "tool_name": "Write",
                "tool_input": {"file_path": "src/phantasos/render.py"},
                "cwd": "/repo",
            },
            config,
        )
        assert proc.returncode == 0
        assert _decision(proc) is None

    def test_allows_payload_without_file_path(self, config: Path) -> None:
        proc = run_hook(
            "freeze_oracle.py",
            {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": "/repo"},
            config,
        )
        assert _decision(proc) is None

    def test_fails_closed_on_missing_config(self, tmp_path: Path) -> None:
        proc = run_hook(
            "freeze_oracle.py",
            {
                "tool_name": "Write",
                "tool_input": {"file_path": "anything.py"},
                "cwd": "/repo",
            },
            tmp_path / "does-not-exist.toml",
        )
        assert proc.returncode == 0
        assert _decision(proc) == "deny"


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@t", *args],
        check=True,
        capture_output=True,
    )


def _write_gate_config(root: Path, command: str, enabled: str = "true") -> Path:
    cfg_dir = root / ".claude"
    cfg_dir.mkdir(exist_ok=True)
    cfg = cfg_dir / "harness.toml"
    cfg.write_text(
        'protected_globs = ["products/*/overrides/tests/test_sdk_crud_live.py*"]\n'
        f"fast_gate_command = {command}\n"
        f"fast_gate_enabled = {enabled}\n"
        "max_consecutive_blocks = 3\n"
    )
    return cfg


PASS_CMD = '["python3", "-c", "raise SystemExit(0)"]'
FAIL_CMD = '["python3", "-c", "print(\'BOOM\'); raise SystemExit(1)"]'


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    protected = root / "products" / "p" / "overrides" / "tests"
    protected.mkdir(parents=True)
    (protected / "test_sdk_crud_live.py").write_text("# frozen\n")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "init")
    return root


def _stop_payload(session: str = "s1") -> dict[str, object]:
    return {"session_id": session, "stop_hook_active": False}


class TestFastGate:
    def test_clean_repo_passing_gate_allows(self, repo: Path) -> None:
        cfg = _write_gate_config(repo, PASS_CMD)
        proc = run_hook("fast_gate.py", _stop_payload(), cfg)
        assert proc.returncode == 0
        assert proc.stdout.strip() == ""

    def test_failing_gate_blocks_with_output(self, repo: Path) -> None:
        cfg = _write_gate_config(repo, FAIL_CMD)
        proc = run_hook("fast_gate.py", _stop_payload(), cfg)
        out = json.loads(proc.stdout)
        assert out["decision"] == "block"
        assert "BOOM" in out["reason"]

    def test_dirty_protected_path_blocks_even_when_gate_passes(
        self, repo: Path
    ) -> None:
        cfg = _write_gate_config(repo, PASS_CMD)
        frozen = (
            repo / "products" / "p" / "overrides" / "tests" / "test_sdk_crud_live.py"
        )
        frozen.write_text("# weakened!\n")
        proc = run_hook("fast_gate.py", _stop_payload(), cfg)
        out = json.loads(proc.stdout)
        assert out["decision"] == "block"
        assert "test_sdk_crud_live.py" in out["reason"]

    def test_untracked_file_in_protected_glob_blocks(self, repo: Path) -> None:
        cfg = _write_gate_config(repo, PASS_CMD)
        extra = repo / "products" / "q" / "overrides" / "tests"
        extra.mkdir(parents=True)
        (extra / "test_sdk_crud_live.py.jinja").write_text("# rogue copy\n")
        proc = run_hook("fast_gate.py", _stop_payload(), cfg)
        out = json.loads(proc.stdout)
        assert out["decision"] == "block"

    def test_loop_guard_allows_after_max_consecutive_blocks(self, repo: Path) -> None:
        cfg = _write_gate_config(repo, FAIL_CMD)
        for _ in range(3):  # max_consecutive_blocks = 3
            proc = run_hook("fast_gate.py", _stop_payload("loop-session"), cfg)
            assert json.loads(proc.stdout)["decision"] == "block"
        proc = run_hook("fast_gate.py", _stop_payload("loop-session"), cfg)
        assert proc.returncode == 0
        assert proc.stdout.strip() == ""  # allowed
        assert "WARNING" in proc.stderr

    def test_disabled_gate_allows_even_when_dirty(self, repo: Path) -> None:
        cfg = _write_gate_config(repo, FAIL_CMD, enabled="false")
        frozen = (
            repo / "products" / "p" / "overrides" / "tests" / "test_sdk_crud_live.py"
        )
        frozen.write_text("# weakened!\n")
        proc = run_hook("fast_gate.py", _stop_payload(), cfg)
        assert proc.returncode == 0
        assert proc.stdout.strip() == ""

    def test_fails_open_on_broken_config(self, tmp_path: Path) -> None:
        proc = run_hook(
            "fast_gate.py", _stop_payload(), tmp_path / "does-not-exist.toml"
        )
        assert proc.returncode == 0
        assert proc.stdout.strip() == ""
        assert "failing open" in proc.stderr
