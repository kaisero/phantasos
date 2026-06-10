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
    payload: dict,
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
                    "file_path": "products/x/overrides/tests/test_sdk_crud_live.py.jinja"
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
