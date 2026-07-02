# harness-and-testing

Validated against 7881143 on 2026-06-14 · Purpose: mechanism and rationale of the autonomous quality harness — the enforcement layer that makes the agent's test quality guarantees real.

The **binding rules** (no mocking the SUT, evidence before assertions, frozen-oracle contract, phase-boundary live gate) live in `CLAUDE.md` "Test policy". This document explains why the harness is built the way it is and how the pieces fit together. Do not restate the rules here.

---

## What it defends against

Two orthogonal failure modes (documented in `docs/specs/2026-06-10-autonomous-harness-thin-slice-design.md` §Problem) threaten an unattended agent loop:

1. **Green-but-fake tests.** The agent games its own success criteria — over-mocking, monkeypatching, editing test assertions, or inserting `exit(0)` — so tests go green while proving nothing. Mocking the system under test or the prisma-browser API boundary is the canonical form. Worsens as model capability rises.

2. **Unvalidated assumptions about the real API.** Code built on mistaken beliefs about the live tenant, never exercised against it. Real-system integration tests are necessary but do nothing about fake tests; the two defenses are complementary, not redundant.

The harness addresses both: the freeze hook prevents oracle weakening (failure mode 1); the live gate catches mismatched assumptions (failure mode 2). Hooks enforce both — prose conventions that the model can rationalize past do not.

---

## The two hooks

Both hooks are registered in `.claude/settings.json`. The freeze hook fires on `Write|Edit`; the fast-gate fires on `Stop`. Their config (protected globs, gate command, loop-guard threshold) lives in `.claude/harness.toml` — a single shared source read by both scripts.

The harness protects its own files (`.claude/harness.toml`, `.claude/hooks/**`, `.claude/settings.json`) so the agent cannot disable its own guardrails.

### freeze_oracle.py — PreToolUse, fail-CLOSED

`.claude/hooks/freeze_oracle.py` intercepts every `Write` or `Edit` call before it executes. It reads `tool_input.file_path` from the hook's stdin JSON, normalizes it to a repo-relative path, and matches against the `protected_globs` list from `harness.toml`. On a match it emits a `permissionDecision: deny` JSON block — Claude Code's PreToolUse contract; `deny` is unconditional and blocks the tool call.

**Fail-closed by design:** any exception inside the hook emits `deny` rather than allowing the call. A crash in the freeze hook must never silently permit an oracle edit. This is the safe-fail direction for the write gate.

The hook does not attempt to scan Bash commands for shell tricks (`mv`, `cp`, redirects). Circumvention via Bash is caught after the fact by the fast-gate's outcome-based dirty check.

### fast_gate.py — Stop, fail-OPEN

`.claude/hooks/fast_gate.py` runs on every main-loop `Stop`. It checks in order:

1. **Frozen-path integrity check.** Runs `git diff --name-only HEAD` plus `git ls-files --others` and matches results against `protected_globs`. Any hit blocks the stop — regardless of test results — with a message naming the dirty paths. This is the outcome-based backstop that catches every write route the freeze hook cannot see (Bash, tool bugs, etc.).

2. **Offline gate.** Runs `fast_gate_command` from `harness.toml` (`uv run nox -s gate` — ruff + mypy + pytest, single interpreter, no coverage matrix). Failure blocks the stop and includes up to the last 50 lines of output in the block reason.

3. **Loop guard.** A session-scoped counter file (in `$TMPDIR`) tracks consecutive blocked stops. After `max_consecutive_blocks` (default 3) consecutive blocks, the hook allows the stop with a loud warning to stderr instead of blocking again. This prevents an unattended session from looping forever on an unfixable red state; CI still catches it.

**Fail-open by design:** any exception in the hook logs to stderr and exits 0 (allow). A bug in the gate runner must not wedge an unattended agent; CI is the backstop for that failure case.

### The deliberate asymmetry

The freeze hook fails *closed*; the fast-gate fails *open*. The asymmetry is intentional and stated explicitly in the design spec so it is not "corrected" later by mistake:

- **Freeze hook (write gate):** if in doubt, deny. A spurious denial is annoying but recoverable; a spurious allow corrupts the oracle.
- **Fast-gate (stop gate):** if in doubt, allow. A spurious allow means one unchecked stop; CI catches the red state. A spurious block wedges the session permanently.

---

## The gates

### nox -s gate — fast offline (every stop)

`gate` in `noxfile.py` runs `ruff check`, `ruff format --check`, `mypy`, and `pytest -q -m "not slow"` in `venv_backend="none"` mode (the invoking `uv run` environment; no new venv creation). It is the command the Stop hook runs on every agent turn. It must stay fast: no multi-Python matrix, no coverage instrumentation, no network. The `-m "not slow"` filter deselects the two `@pytest.mark.slow` end-to-end OAG/Java builds (`test_sdk_build.py`) — on a provisioned machine those otherwise fire multi-minute Java builds on every stop; their coverage lives in the `smoke`/`cli-docs` CI jobs.

The fast_gate hook defaults `UV_PROJECT_ENVIRONMENT` to a stable per-checkout path under `$TMPDIR` so the gate runs against a persistent venv rather than re-creating it each stop.

### Product enrollment — nox.toml

Product enrollment for the product-parametrized sessions (`smoke`, `live`, `sdk-docs`) lives in the root `nox.toml`, not in `noxfile.py`: each stage lists its `products`, and `sdk-docs` carries optional per-product `[[sdk-docs.assert]]` content checks (`file` relative to the built `site/`, plus `contains`/`not_contains`). The noxfile reads it via stdlib `tomllib` and runs each stage generically over its products; an unknown product name fails fast. Add a product to a stage there once it is ready to be gated. (phantasos's own `docs` site is separate and not governed by `nox.toml`.)

### nox -s smoke — real-artifact builds + ring-3 tests (CI)

`smoke` in `noxfile.py` builds every `nox.toml [smoke]` SDK end-to-end (auto-provisioned Java), then runs `pytest -m real_sdk` against the freshly-built artifacts. This is the **only** CI place the ring-3 tests execute — the tests that reflect over the *real* OAG-built SDK (typed wrappers, oneOf dispatch, docs fidelity, CLI dispatch), gated by the `real_sdk` fixture (`tests/conftest.py`). The matrix `tests` job builds no SDK, so those tests skip there; without this step the failure class an OAG upgrade introduces (emitted-shape drift) would be invisible in CI, since the fakesdk-fixture tests re-encode the assumed shape. The `real_sdk` marker is auto-applied to any test requesting the fixture, so the ring is selectable as one set. The SDK is built at the sibling path the tests expect but is *not* editable-installed (the tests add it to `sys.path` themselves), so it stays invisible to mypy and the gate. Each built SDK carries a `.build-stamp` (generator SHA); the fixture skip-loudly when a local artifact was built from a different generator commit.

### nox -s live — real-tenant CRUD (advisory / local phase boundary)

`live` in `noxfile.py` runs the full live validation: build the prisma-browser SDK (`phantasos sdk build prisma-browser --no-smoke`), install the generated project, then run `pytest` against the generated project's `tests/test_sdk_crud_live.py`. Exit status of that pytest run is the oracle verdict. It is **advisory / local-only** — there is no `live.yml` (running mutating CRUD against a real tenant on every push is a deliberate non-goal); run it manually before declaring a phase or task done.

The session reads a local `.env` file if present (convenience for local runs). When `CLIENT_ID`, `CLIENT_SECRET`, or `SCOPE` are absent, the emitted suite's `pytestmark` causes all tests to skip — not fail — so offline runs and credential-less contributors are never blocked.

`CLAUDE.md` requires running `nox -s live` before declaring a phase or task complete.

### The frozen oracle

The emitted live CRUD suite originates as a Jinja template: `products/prisma-browser/overrides/tests/test_sdk_crud_live.py.jinja`. This is the file that holds the real assertions — a hand-written device-group CRUD round-trip (`create → read → assert fields → delete → assert gone`). It is what the agent must never weaken.

The template is in `protected_globs`, so:

- The freeze hook denies any `Write` or `Edit` call targeting it.
- The fast-gate blocks any stop where it appears dirty in git.
- (Planned — see *Backstops* below:) CODEOWNERS + branch protection would add human code-owner review on any PR that touches it.

The emitted file (`tests/test_sdk_crud_live.py` in the generated SDK output directory) is a build artifact, not a protected path — but the template that generated it is.

---

## Backstops

> **Status: partially decided.** The backstops were specified in the harness
> design (`docs/specs/2026-06-10-autonomous-harness-thin-slice-design.md`). Today:
> `.github/CODEOWNERS` still does **not** exist (planned — the intended
> non-bypassable human net below the best-effort freeze hook), while
> `.github/workflows/live.yml` is now a **deliberate non-goal** (see below) —
> automated real-artifact coverage is the offline `smoke` ring-3 path instead.

### CODEOWNERS (planned)

A `.github/CODEOWNERS` covering the frozen paths, with "require code-owner review"
branch protection, would make any PR that modifies a protected path need human
approval before merge — the non-bypassable net below the best-effort freeze hook.

### CI — live.yml (deliberate non-goal)

There is **no** `.github/workflows/live.yml`, by decision: running mutating CRUD
against a real tenant on every push (or a schedule) is not a goal — `nox -s live`
stays an advisory, local phase-boundary gate the author runs with local creds. The
CI real-artifact coverage that *is* automated is the offline path: the `smoke` job
builds every enrolled SDK and runs the ring-3 `pytest -m real_sdk` tests, and the
`sdk-docs`/`cli-docs` jobs build the docs sites under `mkdocs --strict`.

---

## Build / run pointers

- **Offline gate (every stop, also run manually):** `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-ctx uv run nox -s gate`
- **Live gate (phase boundaries):** `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-ctx NOX_ENVDIR=/tmp/phantasos-nox uv run nox -s live`
- **Hook unit tests:** `tests/test_harness_hooks.py` — exercises freeze (deny on match, allow on miss, deny on crash) and fast-gate (block on dirty path, block on red gate, loop-guard allow-with-warning, allow on exception).
- **Context freshness check:** `uv run nox -s context -- --check` (verifies generated blocks in other context docs; no generated blocks in this file).

---

## Gotchas

- **Fail-closed vs fail-open asymmetry** is intentional. Do not "fix" the fast-gate to fail-closed — that wedges unattended sessions.
- **Loop guard (`max_consecutive_blocks = 3`) allows with a warning**, not silently. The session can exit a stuck red state, but the loud warning in stderr makes the escape visible. CI catches the underlying failure.
- **sshfs environment:** `.venv` cannot hold symlinks on sshfs-mounted checkouts. Always set `UV_PROJECT_ENVIRONMENT=/tmp/<name>` when running `uv run nox`. For venv-backed sessions (`live`, `smoke`) also set `NOX_ENVDIR=/tmp/phantasos-nox` to keep session venvs off sshfs. The Stop hook sets a per-checkout default automatically.
- **`gate` uses `venv_backend="none"`** — it runs in the invoking environment, not a session venv. `live` and `smoke` create their own venvs and need `NOX_ENVDIR` on sshfs.
- **`fast_gate_enabled = false` in `harness.toml`** disables the Stop gate for interactive debugging without removing the wiring. The freeze hook is always active regardless.
- **The hook is installed in `.claude/hooks/`, not as a plugin.** Claude Code bug #10412 breaks `Stop`-hook blocking when installed via the plugin system.

---

## See also

- `CLAUDE.md` — the binding rules (test policy, evidence-before-assertions, frozen-oracle contract, phase-boundary live gate).
- `docs/specs/2026-06-10-autonomous-harness-thin-slice-design.md` — the full design: locked decisions, architecture table, error-handling summary, out-of-scope deferred work.
- `.agents/context/index.md` — system overview and links to other deep-dives.
