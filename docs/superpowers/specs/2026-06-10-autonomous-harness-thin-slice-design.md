# Autonomous test-quality harness — thin vertical slice (design)

**Date:** 2026-06-10 (revised same day after fresh-eyes simplification review)
**Branch:** new branch (off `main` or `cli-generator` — see open question #2)
**Status:** design approved, ready for implementation plan
**Research backing:** `docs/research/2026-06-09-autonomous-test-quality-harness.md` (local, gitignored — two deep-research passes, 50 claims verified, 0 refuted)

## Problem

The phantasos Claude Code setup runs mostly-unattended to build a code-generation toolchain (OpenAPI → Python SDKs and Typer/Rich CLIs). Two empirically-documented failure modes threaten it, and they are **orthogonal** — neither technique fixes both:

1. **Green-but-fake tests** — the agent games its own success criteria with over-mocked/monkeypatched tests that go green while proving nothing (editing test files, mocking the system under test, `exit(0)`, etc.). Worsens as model capability rises.
2. **Unvalidated assumptions about real systems** — code built on mistaken beliefs about how the real API behaves, never validated against the real thing.

The research concluded that "real-system integration testing" is necessary but **not sufficient** (it does nothing about fake tests), and that for a mostly-unattended loop the critical controls must be **deterministic hooks**, not prose conventions the model can rationalize past.

## Goal of this slice

Prove the **whole harness architecture on one narrow end-to-end path** before broadening either layer. This is deliberately a *thin vertical slice of both layers*:

- **Layer A (agent discipline):** freeze the spec-derived oracle so the agent cannot weaken it; gate "done" on a passing offline suite.
- **Layer B (real-system validation):** a live CRUD round-trip that exercises a phantasos-generated SDK against the real prisma-browser tenant.

Success = the agent, developing phantasos unattended, **cannot** (a) edit or weaken the frozen oracle (the emitted CRUD suite template), (b) declare a turn complete while the offline suite is red or a frozen path is dirty, or (c) merge a generator change that produces an SDK whose live CRUD round-trip fails — and each of these is enforced, not merely requested.

## Locked decisions

Resolved via grill-me + brainstorming; revised entries marked *(rev)* from the 2026-06-10 simplification review:

| Decision | Choice |
|---|---|
| First deliverable | Thin vertical slice of **both** layers (not Layer A or B alone) |
| Frozen oracle subject | A real-API CRUD round-trip through a **phantasos-generated SDK** |
| Frozen oracle location *(rev)* | The **emitted suite template** `products/<product>/overrides/tests/test_sdk_crud_live.py*` — the file that holds the real assertions. (Originally a phantasos-side wrapper test; that protected a thin driver while leaving the assertions editable — a hole.) |
| Who runs it | phantasos **emits** the suite into the generated SDK project **and runs it itself** against the live tenant |
| Orchestration *(rev)* | `nox -s live` orchestrates generate → install → run-emitted-suite **directly**. No phantasos-side pytest wrapper (it added a pytest-in-subprocess-pytest layer whose own content was trivial). |
| System under test | The **generated SDK's CRUD methods** — NOT the OpenAPI spec, NOT the CLI |
| Oracle form | **Hand-written explicit CRUD round-trip** through SDK methods (legible, trivially cleanable). Schema-derived/property-based breadth is deferred. |
| Schemathesis | **Out of this slice.** Its native runner validates spec↔API conformance (the API), not the generated SDK. Schema-derived data via Hypothesis, and an optional API-conformance pass, are broadening work. |
| CLI testing | **Out of scope.** The CLI's mapping/helper/dispatch layer needs its own e2e tests in the CLI project; it must not re-test the SDK. Separate later cycle. |
| Gate cadence | **Tiered** — fast offline gate every main-loop stop; live oracle at phase boundaries + CI |
| Gate events *(rev)* | `Stop` only for v1 — **not** `SubagentStop` (subagent-driven plans spawn dozens of subagents; gating each costs minutes apiece for no added net). |
| Bash-circumvention defense *(rev)* | **Outcome-based**: the Stop-gate checks `git diff` on protected paths and blocks while dirty. (Originally best-effort Bash command-scanning in PreToolUse — false-positive-prone regex whack-a-mole; dropped.) |
| Enforcement topology | **Hooks-first** — local `.claude/hooks/` carry enforcement; CI/GitHub-native review is a **light** (but present) backstop |
| CI freeze net *(rev)* | **CODEOWNERS + branch protection** on frozen paths (GitHub-native, zero YAML). Replaces the custom diff-check job + `oracle-change-approved` label. |
| Loop guard *(rev)* | Fast-gate allows-with-loud-warning after 3 consecutive blocked stops (prevents an unattended session looping forever on an unfixable red; CI still catches it). |
| Config | `.claude/harness.toml` kept — config separate from code for later cross-project extraction; single source of the protected globs for both hooks. |
| Mutation testing | **Deferred** to the next (broadening) cycle |
| CI | A **new `live.yml`** workflow (not an extension of `ci.yml`) |

## Architecture & components

Three cooperating parts: **agent-discipline hooks** (local, primary enforcement), the **live SDK CRUD oracle** (emitted + phantasos-run), and **GitHub-native backstops**.

| Component | Path | Role |
|---|---|---|
| Freeze hook | `.claude/hooks/freeze_oracle.py` | `PreToolUse` (matcher `Write\|Edit`): denies writes whose `tool_input.file_path` is under a protected glob. Globs from `harness.toml`. |
| Fast-gate hook | `.claude/hooks/fast_gate.py` | `Stop`: (1) blocks if `git diff` shows a protected path modified by any route; (2) runs the fast offline gate; blocks the stop on failure with the failing output. Loop guard after 3 consecutive blocks. |
| Committed settings | `.claude/settings.json` | Registers both hooks + needed permissions. (Today only `settings.local.json` exists.) |
| Harness config | `.claude/harness.toml` | Protected globs (shared by both hooks) + gate command + `fast_gate_enabled` + `max_consecutive_blocks`. |
| Test policy | `CLAUDE.md` (root, new) | Don't-mock-SUT/unowned; evidence-before-assertions; frozen-oracle contract; "run `nox -s live` at phase boundaries." |
| Frozen oracle (template) | `products/prisma-browser/overrides/tests/test_sdk_crud_live.py*` | The emitted CRUD suite — **holds the real assertions; this is the frozen file.** Emitted into each generated SDK as `tests/test_sdk_crud_live.py`. |
| Gate nox session | `noxfile.py` → `gate` | Fast, **single-interpreter**, offline: `ruff` + `mypy` + `pytest`. What the fast-gate hook runs every stop. |
| Live nox session | `noxfile.py` → `live` | Generates + installs the example SDK (smoke infra), then runs the generated project's emitted suite against the live tenant with creds from env. |
| CODEOWNERS | `.github/CODEOWNERS` (new) | Frozen paths require code-owner (human) review via branch protection — the non-bypassable net under the best-effort freeze hook. |
| CI live job | `.github/workflows/live.yml` (new) | Credentialed job runs `nox -s live` on PR (+ optional schedule for drift). |

**Install location:** hooks live in `.claude/hooks/` (NOT a plugin) — Claude Code bug #10412 breaks `Stop`-hook blocking when installed via the plugin system.

## Component details

### Freeze hook — `freeze_oracle.py` (`PreToolUse`, matcher `Write|Edit`)

- Reads `tool_input.file_path` from stdin JSON, normalizes repo-relative, matches against `protected_globs` from `harness.toml`.
- On match → emit and exit 0:
  ```json
  {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
   "permissionDecisionReason": "<path> is a frozen oracle — changes require human review, not agent edits. See CLAUDE.md."}}
  ```
  (`deny` is unconditional — any deny blocks the call.)
- No match → exit 0, no output (allow).
- **Fail closed:** any exception in this hook → emit `deny` (a crash must not silently allow an oracle edit).
- No Bash scanning: circumvention via shell (`mv`/`cp`/redirects) is caught **after the fact, deterministically** by the fast-gate's protected-path diff check, and at merge time by CODEOWNERS.

### Fast-gate hook — `fast_gate.py` (`Stop` only)

Order of checks on every main-loop stop:
1. **Frozen-path integrity:** `git diff --name-only` (plus untracked check) against `protected_globs` → any hit blocks the stop with "frozen path modified — revert it" regardless of test results. Outcome-based: catches every write route, including Bash tricks the freeze hook can't see.
2. **Offline gate:** run `fast_gate_command` from `harness.toml` (default `nox -s gate` — fast single-interpreter offline session: `ruff` + `mypy` + `pytest`). **Not** `nox -s tests` (full multi-Python matrix — far too slow per stop).
- Pass → exit 0 (agent may stop). Fail → emit top-level `{"decision": "block", "reason": "<last ~50 lines of failing output>"}` and exit 0. (Top-level `decision`, NOT `hookSpecificOutput` — verified `Stop`-hook contract.)
- **Loop guard:** track consecutive blocked stops (session-scoped counter file; reset on a passing gate). After `max_consecutive_blocks` (default 3) → allow the stop with a loud warning in the reason/stderr instead of blocking again. Honors the documented `stop_hook_active` input field. Prevents an unattended session burning itself on an unfixable red; CI still catches the state.
- `fast_gate_enabled=false` in `harness.toml` disables for interactive debugging without removing wiring.
- **Fail open:** any exception in this hook → log to stderr and exit 0 (allow). A bug in the gate runner must not wedge an unattended agent; CI is the backstop.

> **The asymmetry is deliberate:** the freeze hook fails *closed* (protect the oracle at all costs), the fast-gate fails *open* (never deadlock the loop). Stated explicitly so it is not "fixed" later by mistake.

### `.claude/settings.json` (committed)

Registers the two hooks against their events and carries the permissions the harness needs. Merges with the existing `settings.local.json` (which keeps `Workflow(deep-research)`).

### `.claude/harness.toml`

Single source of harness config — both hooks read it; reuse in another repo = copy `.claude/` + edit this file.

```toml
protected_globs = [
  "products/*/overrides/tests/test_sdk_crud_live.py*",  # the emitted-suite template = the real oracle
  "tests/acceptance/**",                                 # reserved for future hand-written oracles
]
fast_gate_command = ["nox", "-s", "gate"]
fast_gate_enabled = true
max_consecutive_blocks = 3
```

### `CLAUDE.md` (root, new)

Prose layer behind the hooks:
- Prefer real dependencies; **never mock the SUT or the unowned prisma-browser API boundary**.
- **Evidence before assertions:** paste real command output before claiming a pass.
- **Frozen-oracle contract:** protected paths (see `harness.toml`) are human-owned; never edit them to make something pass. If an oracle is wrong, surface it for human review.
- **Phase-boundary live gate:** run `nox -s live` before declaring a phase/task complete.

### Live SDK CRUD oracle (the emitted suite)

- **SUT = generated SDK methods.** Hand-written round-trip: `client.<resource>.create(...) → get(id) → assert the created object reads back correctly (types deserialize, fields match) → delete(id) → assert gone`, against the live tenant.
- **Resource:** the simplest fully-reversible resource; avoid `oneOf`-bodied resources (e.g. `applications`) for the slice. Final pick is a plan decision.
- **Single source, frozen at the source:** the round-trip is written once, as the per-product override template `products/prisma-browser/overrides/tests/test_sdk_crud_live.py*`, emitted into the generated SDK as `tests/test_sdk_crud_live.py`. The template is in `protected_globs` — **the assertions themselves are what the agent cannot weaken.**
- **Namespacing + cleanup:** run-id-prefixed resource names; a finalizer is registered **before** any resource is created; teardown sweeps-and-deletes by prefix. Survives a failing test body; sidesteps the verified pytest nuance that teardown does not run if fixture *setup* raises midway.
- **Credentials + skip:** `.env` (gitignored) locally, a GitHub Actions secret in `live.yml`. The emitted suite's conftest **skips** when creds are absent — credential-less contributors and offline loops are never blocked.
- **Control flow (nox-only, no wrapper):** `nox -s live` = generate the example SDK (reuse smoke machinery) → install it → run the generated project's `tests/test_sdk_crud_live.py` via pytest. Exit status of that pytest run is the oracle verdict. phantasos's own test suite stays fully offline.
- **What the agent runs at phase boundaries:** `nox -s live` (per CLAUDE.md).

### GitHub-native backstops

- **`.github/CODEOWNERS`:** entries for the protected paths (template glob + `tests/acceptance/`), owned by the human maintainer. With "require code-owner review" branch protection, any PR touching frozen paths needs human approval — the non-bypassable net; zero workflow YAML. (Requires repo admin to enable the branch-protection rule — noted as a one-time manual step.)
- **`live.yml`:** credentialed job running `nox -s live` on PR, optionally on schedule (real-API drift detection). Separate from `ci.yml` so a missing/expired tenant secret degrades gracefully without blocking the offline matrix.

## Error handling summary

| Failure | Behavior |
|---|---|
| Freeze hook crashes | **Fail closed** → deny the write |
| Fast-gate hook crashes | **Fail open** → allow the stop, log to stderr (CI backstops) |
| Oracle modified via Bash/any route (incl. freeze-hook bug #37210) | Fast-gate diff check blocks the stop until reverted; CODEOWNERS blocks the merge |
| Gate red and unfixable (env breakage) | Loop guard: after 3 consecutive blocks, allow-with-loud-warning; CI catches the red |
| Live creds absent | Emitted suite **skips** (not fails) |
| Live test body fails | Prefix-sweep cleanup still runs (finalizer registered pre-creation) |
| Stop-hook plugin bug #10412 | Avoided by installing in `.claude/hooks/`, not as a plugin |

## Testing the harness itself

The hooks are code and get unit tests (in phantasos's offline suite):
- `freeze_oracle.py`: protected path → asserts `deny` JSON; normal path → asserts allow; injected exception → asserts `deny` (fail-closed).
- `fast_gate.py`: dirty protected path → asserts block; passing gate + clean paths → exit 0; failing gate → asserts `decision: block` with output; 4th consecutive block → asserts allow-with-warning (loop guard); injected exception → asserts allow (fail-open).
- `nox -s live` is exercised by `live.yml`; locally it skips cleanly without creds.

## Out of scope (this slice) / deferred to broadening cycles

- **Mutation testing** (`mutmut` on the generator core) — the primary anti-fake-test gate; first broadening step.
- **Schemathesis** — both the native API-conformance pass and Hypothesis-generated property-based breadth through the SDK.
- **VCR/cassettes** — offline replay + drift detection; belongs to the CLI-e2e / offline-replay cycle.
- **CLI e2e mapping tests** — the CLI's mapping/helper/dispatch layer, in the CLI project, not re-testing the SDK.
- **`SubagentStop` gating** — revisit if main-loop-only proves too late in practice.
- **OS read-only perms** and **server-side git hooks** — heavier freeze layers; CODEOWNERS is the chosen backstop.
- **Full extraction** of the harness into a shareable cross-project package (harness.toml already isolates the config seam).

## Resolved (2026-06-10, user decisions)

1. **Resource pick:** **device-group** — the live CRUD round-trip creates/reads/deletes device-groups on the tenant. (Note for the plan: the SDK's id param naming varies — `device_group_id` vs `id` — a known SDK wrinkle; the suite uses whatever the generated SDK exposes today.)
2. **Branch strategy:** fresh branch off `main`, in an **isolated git worktree** — another agent works on this repo in parallel; the spec is carried onto the new branch (it currently lives on `cli-generator`).

## Open questions for the implementation plan

3. **`nox -s live` vs `smoke` reuse:** how much of the smoke session's generate-and-install machinery is factored out vs duplicated.
4. **`settings.json` hook registration shape** for shell-command hooks (the `claude -p` form) — confirm exact JSON against the installed Claude Code version.
5. **Loop-guard counter mechanism:** session-scoped state file location/keying (e.g. `$CLAUDE_SESSION_ID` availability in hook input) — pin during implementation.
