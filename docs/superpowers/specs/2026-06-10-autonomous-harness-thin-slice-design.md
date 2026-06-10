# Autonomous test-quality harness — thin vertical slice (design)

**Date:** 2026-06-10
**Branch:** new branch (off `main` or `cli-generator` — see open question #2)
**Status:** design approved, ready for implementation plan
**Research backing:** `docs/research/2026-06-09-autonomous-test-quality-harness.md` (two deep-research passes, 50 claims verified, 0 refuted)

## Problem

The phantasos Claude Code setup runs mostly-unattended to build a code-generation toolchain (OpenAPI → Python SDKs and Typer/Rich CLIs). Two empirically-documented failure modes threaten it, and they are **orthogonal** — neither technique fixes both:

1. **Green-but-fake tests** — the agent games its own success criteria with over-mocked/monkeypatched tests that go green while proving nothing (editing test files, mocking the system under test, `exit(0)`, etc.). Worsens as model capability rises.
2. **Unvalidated assumptions about real systems** — code built on mistaken beliefs about how the real API behaves, never validated against the real thing.

The research concluded that "real-system integration testing" is necessary but **not sufficient** (it does nothing about fake tests), and that for a mostly-unattended loop the critical controls must be **deterministic hooks**, not prose conventions the model can rationalize past.

## Goal of this slice

Prove the **whole harness architecture on one narrow end-to-end path** before broadening either layer. This is deliberately a *thin vertical slice of both layers*:

- **Layer A (agent discipline):** freeze a spec-derived acceptance oracle so the agent cannot weaken it; gate "done" on a passing offline suite.
- **Layer B (real-system validation):** a live CRUD round-trip that exercises a phantasos-generated SDK against the real prisma-browser tenant.

Success = the agent, developing phantasos unattended, **cannot** (a) edit the frozen oracle to pass, (b) declare a turn complete while the offline suite is red, or (c) merge a generator change that produces an SDK whose live CRUD round-trip fails — and each of these is enforced, not merely requested.

## Locked decisions

These were resolved via grill-me + brainstorming before any code:

| Decision | Choice |
|---|---|
| First deliverable | Thin vertical slice of **both** layers (not Layer A or B alone) |
| Frozen oracle subject | A real-API CRUD round-trip through a **phantasos-generated SDK** |
| Who runs it | phantasos **emits** the suite into the generated SDK project **and runs it itself** against the live tenant (evolves `nox -s smoke`) |
| System under test | The **generated SDK's CRUD methods** — NOT the OpenAPI spec, NOT the CLI |
| Oracle form | **Hand-written explicit CRUD round-trip** through SDK methods (legible, trivially cleanable). Schema-derived/property-based breadth is deferred. |
| Schemathesis | **Out of this slice.** Its native runner validates spec↔API conformance (the API), not the generated SDK. Schema-derived data via Hypothesis, and an optional API-conformance pass, are broadening work. |
| CLI testing | **Out of scope.** The CLI's mapping/helper/dispatch layer needs its own e2e tests in the CLI project; it must not re-test the SDK. Separate later cycle. |
| Gate cadence | **Tiered** — fast offline gate every agent turn; live oracle at phase boundaries + required CI gate |
| Enforcement topology | **Hooks-first** — local `.claude/hooks/` carry enforcement; CI is a **light** (but present) backstop |
| Mutation testing | **Deferred** to the next (broadening) cycle |
| Reusability | Hooks are config-driven (project-agnostic) so they extract to other repos later; proven on phantasos now |
| CI | A **new `live.yml`** workflow (not an extension of `ci.yml`) |

## Architecture & components

Three cooperating parts: **agent-discipline hooks** (local, primary enforcement), the **live SDK CRUD oracle** (emitted + phantasos-run), and a **light CI backstop**.

| Component | Path | Role |
|---|---|---|
| Freeze hook | `.claude/hooks/freeze_oracle.py` | `PreToolUse` (matcher `Write\|Edit`, plus `Bash`): denies edits whose target is under a protected glob. Reads globs from harness config. |
| Fast-gate hook | `.claude/hooks/fast_gate.py` | `Stop` + `SubagentStop`: runs the fast **offline** suite; on failure blocks the stop with the failing output. |
| Committed settings | `.claude/settings.json` | Registers both hooks + needed permissions. (Today only `settings.local.json` exists.) |
| Harness config | `.claude/harness.toml` | Protected globs + fast-gate command + `fast_gate_enabled` flag. Makes hooks project-agnostic. |
| Test policy | `CLAUDE.md` (root, new) | Don't-mock-SUT/unowned; evidence-before-assertions; frozen-oracle contract; "run `nox -s live` at phase boundaries." |
| Frozen oracle | `tests/acceptance/test_generated_sdk_live.py` | phantasos-level assertion: "the generated example SDK passes the live CRUD round-trip." `@pytest.mark.live`. **The frozen file.** |
| Emitted suite (template) | phantasos scaffold/overrides → emits `tests/test_sdk_crud_live.py` into each generated SDK | Each generated SDK ships its own real-API CRUD suite. |
| Gate nox session | `noxfile.py` → `gate` | Fast, **single-interpreter**, offline: `ruff` + `mypy` + `pytest -m "not live"`. What the fast-gate hook runs every turn. |
| Live nox session | `noxfile.py` → `live` | Generates + installs the example SDK (smoke infra), runs the suite against the live tenant with creds from env. |
| CI backstop | `.github/workflows/live.yml` (new) | Credentialed job runs `nox -s live`; plus a "frozen paths unchanged" git-diff check. |

**Install location:** hooks live in `.claude/hooks/` (NOT a plugin) — Claude Code bug #10412 breaks `Stop`-hook exit-2/block when installed via the plugin system.

## Component details

### Freeze hook — `freeze_oracle.py` (`PreToolUse`)

- Matcher `Write|Edit|Bash` (tool-name only — verified mechanic; path logic must be inside the script).
- For `Write`/`Edit`: read `tool_input.file_path`, normalize repo-relative, match against `protected_globs` (default `tests/acceptance/**`).
- For `Bash`: best-effort scan of the command for `mv`/`cp`/`>`/`>>`/`tee`/`rm`/`sed -i` targeting a protected path. Documented as best-effort, not a guarantee.
- On match → emit and exit 0:
  ```json
  {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
   "permissionDecisionReason": "tests/acceptance/** is a frozen oracle — changes require human review, not agent edits. See CLAUDE.md."}}
  ```
  (`deny` is unconditional — any deny blocks the call.)
- No match → exit 0, no output (allow).
- **Fail closed:** any exception in this hook → emit `deny` (a crash must not silently allow an oracle edit).

### Fast-gate hook — `fast_gate.py` (`Stop` + `SubagentStop`)

- Runs the gate command from `harness.toml` (default `nox -s gate` — a fast single-interpreter offline session: `ruff` + `mypy` + `pytest -m "not live"`). **Not** `nox -s tests`, which would run the full multi-Python matrix and is far too slow for an every-turn gate.
- Pass → exit 0 (agent may stop).
- Fail → emit top-level `{"decision": "block", "reason": "<last ~50 lines of failing output>"}` and exit 0. (Top-level `decision`, NOT `hookSpecificOutput` — verified `Stop`-hook contract.)
- `harness.toml: fast_gate_enabled=false` lets a human disable it for interactive debugging without removing the wiring.
- **Fail open:** any exception in this hook → log to stderr and exit 0 (allow). A bug in the gate runner must not wedge an unattended agent; CI is the backstop for what it would have caught.

> **The asymmetry is deliberate:** the freeze hook fails *closed* (protect the oracle at all costs), the fast-gate fails *open* (never deadlock the loop). Stated explicitly so it is not "fixed" later by mistake.

### `.claude/settings.json` (committed)

Registers the two hooks against their events and carries the permissions the harness needs. Merges with the existing `settings.local.json` (which keeps `Workflow(deep-research)`).

### `.claude/harness.toml`

```toml
protected_globs = ["tests/acceptance/**"]
fast_gate_command = ["nox", "-s", "gate"]
fast_gate_enabled = true
```

### `CLAUDE.md` (root, new)

Prose layer behind the hooks:
- Prefer real dependencies; **never mock the SUT or the unowned prisma-browser API boundary**.
- **Evidence before assertions:** paste real command output before claiming a pass.
- **Frozen-oracle contract:** `tests/acceptance/**` is human-owned; never edit it to make something pass. If an oracle is wrong, surface it for human review.
- **Phase-boundary live gate:** run `nox -s live` before declaring a phase/task complete.

### Live SDK CRUD oracle

- **SUT = generated SDK methods.** Hand-written round-trip: `client.<resource>.create(...) → get(id) → assert the created object reads back correctly (types deserialize, fields match) → delete(id) → assert gone`, against the live tenant.
- **Resource:** the simplest fully-reversible resource; avoid `oneOf`-bodied resources (e.g. `applications`) for the slice. Final pick is a plan decision.
- **Namespacing + cleanup:** run-id-prefixed resource names; a finalizer is registered **before** any resource is created; teardown sweeps-and-deletes by prefix. This survives a failing test body and avoids the verified pytest nuance that teardown does not run if fixture *setup* raises midway.
- **Credentials + skip:** `.env` (gitignored) locally, a GitHub Actions secret in `live.yml`. A `conftest` fixture **skips** all `@pytest.mark.live` tests when creds are absent — the offline loop and credential-less contributors are never blocked.
- **`live` marker** registered in `pyproject.toml [tool.pytest.ini_options].markers` (repo runs `--strict-markers`).
- **Single source of the round-trip logic — no duplication.** The CRUD round-trip is written **once**, as the emitted template `tests/test_sdk_crud_live.py`. The generated SDK project ships it (its own real-API coverage). phantasos's frozen oracle does **not** re-implement the round-trip — it is a thin driver.
- **phantasos drives it — control flow (no recursion):** `nox -s live` runs `pytest -m live tests/acceptance/`. The frozen `tests/acceptance/test_generated_sdk_live.py` performs the generate-install-run **directly** (via the smoke helper) — it does NOT re-invoke `nox -s live`: it generates + installs the example SDK, then runs that generated project's emitted `test_sdk_crud_live.py` against the live tenant (subprocess pytest on the generated project) and asserts it passes. So phantasos validates that *what it emits actually works*, while the round-trip assertions live with the SDK.
- **What the agent runs at phase boundaries:** `nox -s live` (per CLAUDE.md).

### `live.yml` (new CI workflow, light backstop)

- Credentialed `live` job: tenant secret in env, runs `nox -s live`.
- **"Frozen paths unchanged" check:** `git diff` `tests/acceptance/**` against the base ref → fail unless a human applies an `oracle-change-approved` label. This is the actual net under the best-effort freeze hook.
- Runs on PR (and optionally a schedule for drift). Separate from `ci.yml` so a missing/expired tenant secret degrades gracefully without blocking the whole CI matrix.

## Error handling summary

| Failure | Behavior |
|---|---|
| Freeze hook crashes | **Fail closed** → deny the write |
| Fast-gate hook crashes | **Fail open** → allow the stop, log to stderr (CI backstops) |
| Live creds absent | `@pytest.mark.live` tests **skip** (not fail) |
| Live test body fails | Prefix-sweep cleanup still runs (finalizer registered pre-creation) |
| Freeze hook bypassed (bug #37210 / `--no-verify` / Bash trick) | CI "frozen paths unchanged" check rejects the change |
| Stop-hook plugin bug #10412 | Avoided by installing in `.claude/hooks/`, not as a plugin |

## Testing the harness itself

The hooks are code and get unit tests:
- `freeze_oracle.py`: protected path → asserts `deny` JSON; normal path → asserts allow; injected exception → asserts `deny` (fail-closed); a `Bash mv` into a protected path → asserts `deny`.
- `fast_gate.py`: passing gate → exit 0; failing gate → asserts `decision: block` with output; injected exception → asserts allow (fail-open).
- `nox -s live` is exercised by `live.yml`; locally it skips cleanly without creds.

## Out of scope (this slice) / deferred to broadening cycles

- **Mutation testing** (`mutmut` on the generator core) — the primary anti-fake-test gate; first broadening step.
- **Schemathesis** — both the native API-conformance pass and Hypothesis-generated property-based breadth through the SDK.
- **VCR/cassettes** — offline replay + drift detection; relevant to the CLI-e2e / offline-replay cycle, not this live-Schemathesis-free slice.
- **CLI e2e mapping tests** — the CLI's mapping/helper/dispatch layer, in the CLI project, not re-testing the SDK.
- **OS read-only perms** and **server-side git hooks** — the heavier freeze layers; hooks-first defers these (the CI check is the chosen backstop).
- **Full extraction** of the harness into a shareable cross-project package.

## Open questions for the implementation plan

1. **Resource pick** for the live CRUD round-trip (simplest fully-reversible; not `oneOf`-bodied).
2. **Branch strategy:** build on a fresh branch off `main`, or alongside the in-flight `cli-generator` work?
3. **`nox -s live` vs `smoke` reuse:** how much of the smoke session's generate-and-install machinery is factored out for reuse vs duplicated.
4. **`settings.json` hook registration shape** for shell-command hooks (the `claude -p` form) vs the SDK callback form — confirm the exact JSON against the installed Claude Code version, including the `defer` v2.1.89+ caveat.
5. **`oracle-change-approved` label** mechanics in `live.yml` (or a simpler "fail on any acceptance diff" for v1).
