#!/usr/bin/env python3
"""Stop hook: block stopping while frozen paths are dirty or the gate is red.

Order: (1) honor fast_gate_enabled; (2) outcome check — any protected glob
modified/untracked in git blocks regardless of test results (catches every
write route, including Bash tricks PreToolUse cannot see); (3) run the
offline gate command, block on failure with the output tail; (4) loop guard.

Fail-OPEN: an internal error allows the stop (never deadlock an unattended
loop) — CI re-runs the same checks. Counterpart freeze_oracle.py fails CLOSED;
the asymmetry is deliberate (see the spec).
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path


def _config_path() -> Path:
    override = os.environ.get("PHANTASOS_HARNESS_CONFIG")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent.parent / "harness.toml"


def _git_lines(root: Path, *args: str) -> list[str]:
    proc = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True)
    return [line for line in proc.stdout.splitlines() if line.strip()]


def _dirty_protected(root: Path, globs: list[str]) -> list[str]:
    changed = _git_lines(root, "diff", "--name-only", "HEAD")
    untracked = _git_lines(root, "ls-files", "--others", "--exclude-standard")
    hits = {f for f in changed + untracked if any(fnmatch.fnmatch(f, g) for g in globs)}
    return sorted(hits)


def _root_key(root: Path) -> str:
    return hashlib.sha256(str(root).encode()).hexdigest()[:12]


def _state_path(root: Path) -> Path:
    return Path(tempfile.gettempdir()) / f"phantasos-fast-gate-{_root_key(root)}.json"


def _read_blocks(state_path: Path, session: str) -> int:
    try:
        state = json.loads(state_path.read_text())
    except (OSError, ValueError):
        return 0
    return int(state.get("blocks", 0)) if state.get("session_id") == session else 0


def _write_blocks(state_path: Path, session: str, blocks: int) -> None:
    state_path.write_text(json.dumps({"session_id": session, "blocks": blocks}))


def main() -> int:
    try:
        data = json.load(sys.stdin)
        cfg_path = _config_path()
        with cfg_path.open("rb") as f:
            cfg = tomllib.load(f)
        if not cfg.get("fast_gate_enabled", True):
            return 0

        root = cfg_path.resolve().parent.parent  # .claude/harness.toml -> repo root
        globs = [str(g) for g in cfg.get("protected_globs", [])]
        session = str(data.get("session_id", ""))
        state_path = _state_path(root)
        blocks = _read_blocks(state_path, session)
        max_blocks = int(cfg.get("max_consecutive_blocks", 3))

        failures: list[str] = []
        dirty = _dirty_protected(root, globs)
        if dirty:
            failures.append(
                "frozen paths modified — revert them before stopping "
                "(they are human-owned; see CLAUDE.md):\n  " + "\n  ".join(dirty)
            )
        else:
            cmd = [str(c) for c in cfg["fast_gate_command"]]
            env = os.environ.copy()
            env.setdefault(
                "UV_PROJECT_ENVIRONMENT",
                f"{tempfile.gettempdir()}/phantasos-gate-venv-{_root_key(root)}",
            )
            proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True, env=env)
            if proc.returncode != 0:
                tail = "\n".join((proc.stdout + "\n" + proc.stderr).splitlines()[-50:])
                failures.append(f"offline gate failed ({' '.join(cmd)}); fix before stopping:\n{tail}")

        if not failures:
            _write_blocks(state_path, session, 0)
            return 0

        if blocks >= max_blocks:
            print(
                f"WARNING: fast gate still failing after {max_blocks} consecutive "
                "blocked stops — allowing this stop so the session does not wedge. "
                "CI will catch the red state.\n" + "\n\n".join(failures),
                file=sys.stderr,
            )
            _write_blocks(state_path, session, 0)
            return 0

        _write_blocks(state_path, session, blocks + 1)
        print(json.dumps({"decision": "block", "reason": "\n\n".join(failures)}))
        return 0
    except Exception as exc:  # fail OPEN by design
        print(
            f"fast_gate hook error ({exc!r}) — failing open (allowing stop); CI is the backstop.",
            file=sys.stderr,
        )
        return 0


if __name__ == "__main__":
    sys.exit(main())
