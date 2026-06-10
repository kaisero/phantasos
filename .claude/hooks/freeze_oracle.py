#!/usr/bin/env python3
"""PreToolUse hook: deny Write/Edit to frozen-oracle paths.

Fail-CLOSED: any internal error denies the call — a crash must never
silently allow an oracle edit. See CLAUDE.md "Frozen-oracle contract".
Config: ../harness.toml next to this script's parent dir, overridable via
the PHANTASOS_HARNESS_CONFIG env var (used by the unit tests).
"""

from __future__ import annotations

import fnmatch
import json
import os
import sys
import tomllib
from pathlib import Path


def _config_path() -> Path:
    override = os.environ.get("PHANTASOS_HARNESS_CONFIG")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent.parent / "harness.toml"


def _protected_globs() -> list[str]:
    with open(_config_path(), "rb") as f:
        return [str(g) for g in tomllib.load(f)["protected_globs"]]


def _deny(reason: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )


def _repo_relative(file_path: str, cwd: str) -> str:
    p = Path(file_path)
    if not p.is_absolute():
        return str(p)
    try:
        return str(p.resolve().relative_to(Path(cwd).resolve()))
    except ValueError:
        return str(p)


def main() -> int:
    try:
        data = json.load(sys.stdin)
        tool_input = data.get("tool_input") or {}
        file_path = str(tool_input.get("file_path") or "")
        if not file_path:
            return 0  # not a file-writing call we can judge
        rel = _repo_relative(file_path, str(data.get("cwd") or os.getcwd()))
        for glob in _protected_globs():
            if fnmatch.fnmatch(rel, glob):
                _deny(
                    f"{rel} is a frozen path ({glob}) — human-owned. Never edit "
                    "it to make work pass; if the oracle is wrong, stop and "
                    "surface it for human review. See CLAUDE.md."
                )
                return 0
        return 0
    except Exception as exc:  # fail CLOSED by design
        _deny(
            f"freeze_oracle hook error ({exc!r}) — failing closed: no writes "
            "allowed until the harness config is fixed."
        )
        return 0


if __name__ == "__main__":
    sys.exit(main())
