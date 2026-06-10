# Autonomous Test-Quality Harness — Thin Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove the autonomous quality-harness architecture end-to-end: a freeze hook that denies agent edits to frozen oracles, a Stop-gate that blocks "done" on a red offline suite or dirty frozen paths, and a live device-group CRUD round-trip through the generated prisma-browser SDK against the real tenant.

**Architecture:** Two small Python hook scripts in `.claude/hooks/` (config from `.claude/harness.toml`, registered in `.claude/settings.json`) enforce discipline locally; a Jinja template emitted into the generated SDK holds the real CRUD assertions (the frozen oracle); `nox -s gate` (fast, offline, every stop) and `nox -s live` (generate → install → run emitted suite, phase boundaries + CI) tier the gating; CODEOWNERS + a new `live.yml` workflow are the GitHub-side net.

**Tech Stack:** Python 3.11+ stdlib only for hooks (`tomllib`, `json`, `fnmatch`, `subprocess`), nox + uv (existing patterns), pytest, Jinja2 (existing scaffold), GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-06-10-autonomous-harness-thin-slice-design.md` (committed on this branch, e0c3322).

---

## Context for a zero-context engineer

- **Repo layout:** `src/phantasos/` is the generator; `products/prisma-browser/` holds `sdk.yml` (with `output: ../../../prisma-browser-sdk`), `openapi.yml`, and `overrides/` (scaffold overrides; `.jinja` files are rendered with a context that includes `package`, non-`.jinja` copied verbatim — see `src/phantasos/scaffold.py`). `phantasos build prisma-browser` generates the SDK into the resolved `output` dir (`load_product("prisma-browser").output_dir`).
- **Generated SDK facts (verified against the built SDK):** package `prisma_browser`; `Client.from_env()` lives in `prisma_browser.extras.facade` and reads env `CLIENT_ID`, `CLIENT_SECRET`, `SCOPE` (+ optional `PRISMA_SASE_BASE_URL`). Device-group API on `client.device_groups`: `create_device_group(device_group_request: DeviceGroupRequest) -> CreateDeviceGroup201Response` (field `device_group_id`), `get_device_group_by_id(device_group_id) -> DeviceGroup` (fields `id`, `name`, `platform`), `list_device_groups(limit=..., device_group_name=...) -> ListDeviceGroups200Response` (field `data`), `delete_device_group(device_group_id) -> None`. `DeviceGroupRequest(name, platform)` — both required; `DeviceGroupPlatform.DESKTOP_BROWSER == 'Desktop Browser'`. Not-found raises `prisma_browser.exceptions.NotFoundException`.
- **Environment quirk:** this machine's repo is on sshfs — `.venv` cannot hold symlinks. Always run uv with an explicit env dir, e.g. `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-harness-venv uv run ...`. The fast-gate hook sets a per-checkout default automatically.
- **Run all commands from the worktree root** (`.claude/worktrees/harness-thin-slice/`); the branch is `worktree-harness-thin-slice` off `main`.
- **Verified hook contracts (from the research):** PreToolUse blocks via stdout JSON `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "..."}}` with exit 0; Stop blocks via **top-level** `{"decision": "block", "reason": "..."}` with exit 0. Matchers filter by tool NAME only; path logic lives inside the script. JSON on stdout is only honored on exit 0.

---

### Task 1: Harness config + repo hygiene

**Files:**
- Create: `.claude/harness.toml`
- Modify: `.gitignore` (only if `.env` is not already ignored)

- [ ] **Step 1: Write the config**

Create `.claude/harness.toml`:

```toml
# Quality-harness config — single source for the .claude/hooks/ scripts.
# Reuse in another repo = copy .claude/hooks + this file, adjust values.

# Paths the agent must never write (the freeze hook denies Write/Edit;
# the Stop gate blocks while any of these is dirty in git).
# Includes the harness itself so the agent cannot disable its own guardrails.
protected_globs = [
    "products/*/overrides/tests/test_sdk_crud_live.py*", # emitted-suite template = the frozen oracle
    "tests/acceptance/**",                               # reserved for future hand-written oracles
    ".claude/harness.toml",
    ".claude/hooks/**",
    ".claude/settings.json",
]

# Offline gate the Stop hook runs on every main-loop stop.
fast_gate_command = ["uv", "run", "nox", "-s", "gate"]
fast_gate_enabled = true

# Loop guard: after this many consecutive blocked stops, allow with a loud
# warning instead of blocking forever (CI still catches the red state).
max_consecutive_blocks = 3
```

- [ ] **Step 2: Ensure `.env` is gitignored**

Run: `grep -n "^\.env$" .gitignore || echo MISSING`
If MISSING, append a line `.env` to `.gitignore`.

- [ ] **Step 3: Commit**

```bash
git add .claude/harness.toml .gitignore
git commit -m "feat(harness): add .claude/harness.toml (protected globs + gate config)"
```

---

### Task 2: Freeze hook (`freeze_oracle.py`) — TDD

**Files:**
- Create: `.claude/hooks/freeze_oracle.py`
- Test: `tests/test_harness_hooks.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_harness_hooks.py`:

```python
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
    return out.get("hookSpecificOutput", {}).get("permissionDecision")


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-harness-venv uv run pytest tests/test_harness_hooks.py -v`
Expected: FAIL — `FileNotFoundError` / non-zero from missing `.claude/hooks/freeze_oracle.py`.

- [ ] **Step 3: Implement the hook**

Create `.claude/hooks/freeze_oracle.py`:

```python
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
    except Exception as exc:  # noqa: BLE001 — fail CLOSED by design
        _deny(
            f"freeze_oracle hook error ({exc!r}) — failing closed: no writes "
            "allowed until the harness config is fixed."
        )
        return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-harness-venv uv run pytest tests/test_harness_hooks.py -v`
Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add .claude/hooks/freeze_oracle.py tests/test_harness_hooks.py
git commit -m "feat(harness): freeze_oracle PreToolUse hook (fail-closed deny on frozen paths)"
```

---

### Task 3: Stop-gate hook (`fast_gate.py`) — TDD

**Files:**
- Create: `.claude/hooks/fast_gate.py`
- Test: `tests/test_harness_hooks.py` (append)

The hook does, in order: (1) skip if disabled; (2) block if any protected glob is dirty in git (modified vs HEAD or untracked) — this is the outcome-based net that catches Bash-route circumvention; (3) run the offline gate command, block on failure with the output tail; (4) loop-guard: after `max_consecutive_blocks` consecutive blocks for the same session, allow with a loud stderr warning. Fail-OPEN on internal errors.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_harness_hooks.py`:

```python
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


def _stop_payload(session: str = "s1") -> dict:
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
        frozen = repo / "products" / "p" / "overrides" / "tests" / "test_sdk_crud_live.py"
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
        frozen = repo / "products" / "p" / "overrides" / "tests" / "test_sdk_crud_live.py"
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-harness-venv uv run pytest tests/test_harness_hooks.py::TestFastGate -v`
Expected: FAIL — missing `.claude/hooks/fast_gate.py`.

- [ ] **Step 3: Implement the hook**

Create `.claude/hooks/fast_gate.py`:

```python
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
    proc = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=True
    )
    return [line for line in proc.stdout.splitlines() if line.strip()]


def _dirty_protected(root: Path, globs: list[str]) -> list[str]:
    changed = _git_lines(root, "diff", "--name-only", "HEAD")
    untracked = _git_lines(root, "ls-files", "--others", "--exclude-standard")
    hits = {
        f
        for f in changed + untracked
        if any(fnmatch.fnmatch(f, g) for g in globs)
    }
    return sorted(hits)


def _state_path(root: Path) -> Path:
    key = hashlib.sha256(str(root).encode()).hexdigest()[:12]
    return Path(tempfile.gettempdir()) / f"phantasos-fast-gate-{key}.json"


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
        with open(cfg_path, "rb") as f:
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
            key = hashlib.sha256(str(root).encode()).hexdigest()[:12]
            env.setdefault(
                "UV_PROJECT_ENVIRONMENT", f"{tempfile.gettempdir()}/phantasos-gate-venv-{key}"
            )
            proc = subprocess.run(
                cmd, cwd=root, capture_output=True, text=True, env=env
            )
            if proc.returncode != 0:
                tail = "\n".join(
                    (proc.stdout + "\n" + proc.stderr).splitlines()[-50:]
                )
                failures.append(
                    f"offline gate failed ({' '.join(cmd)}); fix before stopping:\n{tail}"
                )

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
    except Exception as exc:  # noqa: BLE001 — fail OPEN by design
        print(
            f"fast_gate hook error ({exc!r}) — failing open (allowing stop); "
            "CI is the backstop.",
            file=sys.stderr,
        )
        return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-harness-venv uv run pytest tests/test_harness_hooks.py -v`
Expected: 12 PASS (5 freeze + 7 fast-gate).

- [ ] **Step 5: Commit**

```bash
git add .claude/hooks/fast_gate.py tests/test_harness_hooks.py
git commit -m "feat(harness): fast_gate Stop hook (dirty-oracle check, offline gate, loop guard; fail-open)"
```

---

### Task 4: `nox -s gate` session

**Files:**
- Modify: `noxfile.py` (append after the `tests` session)

- [ ] **Step 1: Add the session**

Append to `noxfile.py` (after `tests`, before `audit`):

```python
@nox.session(venv_backend="none")
def gate(session: nox.Session) -> None:
    """Fast offline quality gate — single environment, no venv creation.

    Run by the Stop hook on every agent turn (see .claude/harness.toml), so it
    must stay fast: ruff + mypy + the offline pytest suite, no coverage, no
    multi-Python matrix. Runs in the invoking environment (``uv run nox``).
    """
    session.run("ruff", "check", ".")
    session.run("ruff", "format", "--check", ".")
    session.run("mypy")
    session.run("pytest", "-q")
```

- [ ] **Step 2: Run it**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-harness-venv uv run nox -s gate`
Expected: all four commands pass (ruff, ruff format, mypy, pytest with the new hook tests). If ruff/mypy flag the new hook scripts, fix the scripts — they are part of the linted codebase.

- [ ] **Step 3: Commit**

```bash
git add noxfile.py
git commit -m "feat(harness): nox -s gate (fast single-env offline gate for the Stop hook)"
```

---

### Task 5: `settings.json` registration + `CLAUDE.md` policy

**Files:**
- Create: `.claude/settings.json`
- Create: `CLAUDE.md` (repo root)

- [ ] **Step 1: Write settings.json**

Create `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$CLAUDE_PROJECT_DIR/.claude/hooks/freeze_oracle.py\""
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$CLAUDE_PROJECT_DIR/.claude/hooks/fast_gate.py\""
          }
        ]
      }
    ]
  }
}
```

(Note: `settings.local.json` keeps the user-local `Workflow(deep-research)` permission; do not move it here.)

- [ ] **Step 2: Write CLAUDE.md**

Create `CLAUDE.md` at the repo root:

```markdown
# phantasos — agent working agreement

## Test policy (enforced by hooks — see .claude/harness.toml)

- Prefer real dependencies. NEVER mock the system under test, and never mock
  the prisma-browser API boundary in tests that claim to validate behavior
  against it.
- Evidence before assertions: run the command and show its real output before
  claiming anything passes.
- Frozen oracles: every path matching `protected_globs` in
  `.claude/harness.toml` is human-owned. Never edit one to make work pass.
  If an oracle looks wrong, STOP and surface it for human review.
- Phase boundaries: run `uv run nox -s live` (live CRUD validation against the
  real tenant; skips without credentials) before declaring a phase or task
  complete. The offline gate (`uv run nox -s gate`) runs automatically on stop.

## Environment notes

- This repo may sit on sshfs where `.venv` cannot hold symlinks. Run uv with
  an explicit env dir: `UV_PROJECT_ENVIRONMENT=/tmp/<name> uv run ...`
  (the Stop hook sets a per-checkout default automatically).
```

- [ ] **Step 3: Manually verify the freeze hook end-to-end**

The hooks activate for NEW Claude Code sessions (hook registrations are read at session start). Verify the script contract directly now:

Run:
```bash
echo '{"tool_name":"Write","tool_input":{"file_path":"products/prisma-browser/overrides/tests/test_sdk_crud_live.py.jinja"},"cwd":"'$PWD'"}' | python3 .claude/hooks/freeze_oracle.py
```
Expected: one JSON line containing `"permissionDecision": "deny"`.

Run:
```bash
echo '{"session_id":"manual","stop_hook_active":false}' | python3 .claude/hooks/fast_gate.py; echo "exit=$?"
```
Expected: `exit=0` and empty stdout if the worktree is clean and the gate passes (takes ~30–60s, it runs the real gate); a `{"decision": "block", ...}` line if anything is red.

- [ ] **Step 4: Commit**

```bash
git add .claude/settings.json CLAUDE.md
git commit -m "feat(harness): register hooks in settings.json + CLAUDE.md test policy"
```

---

### Task 6: The frozen oracle — emitted CRUD suite template

**Files:**
- Create: `products/prisma-browser/overrides/tests/test_sdk_crud_live.py.jinja`
- Test: `tests/test_crud_live_template.py`

- [ ] **Step 1: Write the failing test (template renders + compiles)**

Create `tests/test_crud_live_template.py`:

```python
"""The emitted live-CRUD suite template must render to valid Python."""

from pathlib import Path

from jinja2 import Environment

TEMPLATE = Path("products/prisma-browser/overrides/tests/test_sdk_crud_live.py.jinja")


def test_template_renders_and_compiles() -> None:
    rendered = Environment().from_string(TEMPLATE.read_text()).render(
        package="prisma_browser"
    )
    compile(rendered, "test_sdk_crud_live.py", "exec")  # SyntaxError = fail
    assert "from prisma_browser.extras.facade import Client" in rendered
    assert "device_group" in rendered
    assert "skipif" in rendered  # must skip, not fail, without credentials
```

- [ ] **Step 2: Run test to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-harness-venv uv run pytest tests/test_crud_live_template.py -v`
Expected: FAIL — `FileNotFoundError` for the template.

- [ ] **Step 3: Write the template**

Create `products/prisma-browser/overrides/tests/test_sdk_crud_live.py.jinja`:

```python
"""Live CRUD round-trip for {{ package }} device groups — FROZEN ORACLE.

Part of the phantasos quality harness: proves the generated SDK performs a
real create -> read -> delete cycle against a live tenant. Do NOT weaken,
mock, or skip-hack this suite — the template it is generated from is a
protected path (see the phantasos repo's CLAUDE.md and .claude/harness.toml);
changes require human review.

Skips (never fails) when live credentials are absent, so offline runs and
credential-less contributors are unaffected.
"""

import os
import uuid

import pytest

from {{ package }}.exceptions import NotFoundException
from {{ package }}.extras.facade import Client
from {{ package }}.models.device_group_platform import DeviceGroupPlatform
from {{ package }}.models.device_group_request import DeviceGroupRequest

_REQUIRED_ENV = ("CLIENT_ID", "CLIENT_SECRET", "SCOPE")
_PREFIX = "phx-harness-"

pytestmark = pytest.mark.skipif(
    any(not os.environ.get(var) for var in _REQUIRED_ENV),
    reason="live tenant credentials not set: " + ", ".join(_REQUIRED_ENV),
)


@pytest.fixture()
def client():
    c = Client.from_env()
    yield c
    c.close()


@pytest.fixture()
def created_ids(client):
    """Cleanup net, registered BEFORE any resource is created.

    Teardown runs even when the test body fails: it deletes every tracked id,
    then sweeps the tenant for leftovers carrying our prefix (leaks from
    crashed earlier runs).
    """
    ids = []
    yield ids
    for dg_id in ids:
        try:
            client.device_groups.delete_device_group(dg_id)
        except NotFoundException:
            pass  # already deleted by the test body — the happy path
    page = client.device_groups.list_device_groups(limit=100)
    for dg in page.data or []:
        if dg.name.startswith(_PREFIX):
            try:
                client.device_groups.delete_device_group(dg.id)
            except NotFoundException:
                pass


def test_device_group_crud_round_trip(client, created_ids):
    name = _PREFIX + uuid.uuid4().hex[:12]

    created = client.device_groups.create_device_group(
        DeviceGroupRequest(name=name, platform=DeviceGroupPlatform.DESKTOP_BROWSER)
    )
    assert created.device_group_id, "create returned no deviceGroupId"
    created_ids.append(created.device_group_id)

    got = client.device_groups.get_device_group_by_id(created.device_group_id)
    assert got.id == created.device_group_id
    assert got.name == name
    assert got.platform == DeviceGroupPlatform.DESKTOP_BROWSER

    client.device_groups.delete_device_group(created.device_group_id)
    with pytest.raises(NotFoundException):
        client.device_groups.get_device_group_by_id(created.device_group_id)
```

(Known risk, accepted for v1: the final get-after-delete assumes read-after-delete consistency; if the live run shows eventual-consistency flakes there, replace it with a short retry loop — flag it to the human rather than weakening the assertion.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-harness-venv uv run pytest tests/test_crud_live_template.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add products/prisma-browser/overrides/tests/test_sdk_crud_live.py.jinja tests/test_crud_live_template.py
git commit -m "feat(harness): frozen oracle — live device-group CRUD suite emitted into the SDK"
```

---

### Task 7: `nox -s live` session

**Files:**
- Modify: `noxfile.py` (imports + new session after `smoke`)

- [ ] **Step 1: Add the session**

Add `from pathlib import Path` to the imports at the top of `noxfile.py` (next to `import os`), then append after the `smoke` session:

```python
@nox.session
def live(session: nox.Session) -> None:
    """Generate the prisma-browser SDK and run its live CRUD suite (real tenant).

    Phase-boundary + CI gate (live.yml). Needs CLIENT_ID/CLIENT_SECRET/SCOPE
    in the environment (a local ``.env`` is read as a convenience); the suite
    SKIPS without them, so running this credential-less is safe and green.
    Needs network + Java (auto-provisioned, like ``smoke``).
    """
    _sync(session, "test")
    env_file = Path(".env")
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key, _, value = stripped.partition("=")
                session.env.setdefault(key.strip(), value.strip().strip('"'))
    session.run("phantasos", "build", "prisma-browser", "--no-smoke")
    from phantasos.productconfig import load_product

    out_dir = load_product("prisma-browser").output_dir
    session.install(str(out_dir))
    session.run("pytest", "-v", str(out_dir / "tests" / "test_sdk_crud_live.py"))
```

- [ ] **Step 2: Verify the credential-less path (skip, not fail)**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-harness-venv env -u CLIENT_ID -u CLIENT_SECRET -u SCOPE uv run nox -s live`
Expected: the SDK builds (first run downloads the OAG jar + JRE into `~/.cache/phantasos` — can take minutes), the generated suite is collected, and the CRUD test reports `SKIPPED ... live tenant credentials not set`. Session exits 0.
Note: in this worktree the SDK output resolves to `.claude/worktrees/prisma-browser-sdk` (sibling of the worktree, per `sdk.yml`'s relative `output`) — it does NOT touch the real `~/git/prisma-browser-sdk`.

- [ ] **Step 3: Run the offline gate (the noxfile changed)**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-harness-venv uv run nox -s gate`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add noxfile.py
git commit -m "feat(harness): nox -s live (generate SDK, run emitted live CRUD suite)"
```

---

### Task 8: GitHub backstops — CODEOWNERS + `live.yml`

**Files:**
- Create: `.github/CODEOWNERS`
- Create: `.github/workflows/live.yml`

- [ ] **Step 1: Write CODEOWNERS**

Create `.github/CODEOWNERS`:

```
# Frozen-oracle + harness paths: changes require human review.
# Mirrors protected_globs in .claude/harness.toml — keep the two in sync.
/products/*/overrides/tests/test_sdk_crud_live.py* @kaisero
/tests/acceptance/ @kaisero
/.claude/ @kaisero
/CLAUDE.md @kaisero
```

- [ ] **Step 2: Write live.yml**

Create `.github/workflows/live.yml` (mirrors `ci.yml`'s pinned actions + smoke's toolchain cache):

```yaml
name: Live

on:
  pull_request:
  workflow_dispatch:
  schedule:
    - cron: '0 5 * * 1' # weekly drift check against the real tenant

concurrency:
  group: live-${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: read

jobs:
  live:
    name: Live SDK CRUD validation
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@df4cb1c069e1874edd31b4311f1884172cec0e10 # v6.0.3
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@fac544c07dec837d0ccb6301d7b5580bf5edae39 # v8.2.0
        with:
          enable-cache: true
      - name: Cache OAG jar + Temurin JRE
        uses: actions/cache@27d5ce7f107fe9357f9df03efb73ab90386fccae # v5.0.5
        with:
          path: ~/.cache/phantasos
          key: phantasos-toolchain-oag7.22.0-jre17.0.19-smokeenv1
      # Without repo secrets (e.g. forks) the suite SKIPS — the job stays green
      # and proves only generate+collect; with secrets it is a real CRUD gate.
      - name: Generate SDK + run live CRUD suite
        env:
          CLIENT_ID: ${{ secrets.CLIENT_ID }}
          CLIENT_SECRET: ${{ secrets.CLIENT_SECRET }}
          SCOPE: ${{ secrets.SCOPE }}
        run: uv run nox -s live
```

- [ ] **Step 3: Commit**

```bash
git add .github/CODEOWNERS .github/workflows/live.yml
git commit -m "feat(harness): CODEOWNERS freeze net + live.yml CRUD validation workflow"
```

- [ ] **Step 4: Note the two one-time manual GitHub steps (for the human)**

Report at the end of the task — these cannot be done from the repo:
1. Branch protection on `main`: enable "Require review from Code Owners".
2. Add repo secrets `CLIENT_ID`, `CLIENT_SECRET`, `SCOPE` (test-tenant credentials).

---

### Task 9: Live end-to-end proof + docs/memory sync

**Files:**
- Modify: `docs/superpowers/specs/2026-06-10-autonomous-harness-thin-slice-design.md` (config/glob sync note)

- [ ] **Step 1: Run the full live oracle with credentials**

Requires the test-tenant `.env` (CLIENT_ID/CLIENT_SECRET/SCOPE) at the worktree root — **ask the human for it if absent; do not invent credentials.**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-harness-venv uv run nox -s live`
Expected: `test_device_group_crud_round_trip PASSED` — a real device group named `phx-harness-<hex>` was created, read back, and deleted on the tenant. If it FAILS at the get-after-delete with a non-404, see the eventual-consistency note in the template (Task 6) and surface to the human before changing anything.

- [ ] **Step 2: Verify cleanup left nothing behind**

Run (from the worktree root, with `.env` loaded into the shell):
```bash
set -a; . ./.env; set +a
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-harness-venv uv run python - <<'EOF'
import sys

from phantasos.productconfig import load_product

sys.path.insert(0, str(load_product("prisma-browser").output_dir))
from prisma_browser.extras.facade import Client

c = Client.from_env()
page = c.device_groups.list_device_groups(limit=100)
leftovers = [d.name for d in (page.data or []) if d.name.startswith("phx-harness-")]
print("leftovers:", leftovers)
assert not leftovers, "cleanup failed — delete these on the tenant and fix the sweep"
c.close()
EOF
```
Expected: `leftovers: []`.

- [ ] **Step 3: Sync the spec's example config with reality**

In the spec's `harness.toml` example, the implemented file added three self-protection entries (`.claude/harness.toml`, `.claude/hooks/**`, `.claude/settings.json`) and `fast_gate_command = ["uv", "run", "nox", "-s", "gate"]`. Update the spec's example block to match the committed `.claude/harness.toml` verbatim, and add one sentence under "Component details → `.claude/harness.toml`": "The harness protects its own config, hooks, and settings so the agent cannot disable its guardrails."

- [ ] **Step 4: Run the offline gate one last time**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-harness-venv uv run nox -s gate`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/specs/2026-06-10-autonomous-harness-thin-slice-design.md
git commit -m "docs(spec): sync harness.toml example with implementation (self-protection globs)"
```

---

## Verification checklist (whole slice)

- [ ] `uv run nox -s gate` green (ruff + mypy + offline pytest incl. 13 new harness tests)
- [ ] `freeze_oracle.py` denies a Write to the template path (manual echo test, Task 5 Step 3)
- [ ] `fast_gate.py` blocks on a dirtied template, allows after revert
- [ ] `nox -s live` without creds: builds SDK, suite SKIPS, exit 0
- [ ] `nox -s live` with creds: real CRUD round-trip PASSES, zero leftovers
- [ ] New Claude Code session in this checkout: agent attempt to edit the template is denied by the hook (the registrations load at session start)
- [ ] Human one-timers noted: branch protection (code-owner review) + repo secrets

## Known follow-ups (broadening cycles — out of scope here)

- Mutation testing (`mutmut`) gate on the generator core.
- Hypothesis/schema-derived input breadth through the SDK; optional Schemathesis API-conformance pass.
- CLI e2e mapping tests (CLI project).
- `SubagentStop` gating if main-loop-only proves too late.
- Extracting `.claude/hooks/` + `harness.toml` into a shareable cross-project package.
