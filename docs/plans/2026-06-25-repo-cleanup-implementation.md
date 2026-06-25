# Repo Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute the surgical code-quality wins from `docs/plans/2026-06-25-repo-cleanup-findings.md` — remove proven dead code, eliminate one accidental duplication, decompose two over-complex functions, fix a layering inversion, and reorganize the test suite — without changing any user-observable behavior.

**Architecture:** Pure refactor. Because every change is behavior-preserving, **the existing 567-test suite is the primary safety net** (green before → green after each task), supplemented by new focused unit tests where a task creates a new seam or closes a coverage gap. Work proceeds in four batches (A–D) ordered low-risk → higher-risk; each task ends green and is committed independently.

**Tech Stack:** Python 3.11+, pydantic v2, typer, jinja2, ruamel.yaml, jmespath; pytest + nox; ruff + mypy (strict).

## Global Constraints

- **Python floor `>=3.11`** (ruff `target-version = py311`); use `X | None`, not `Optional[X]`.
- **No behavior change.** This is a refactor: the emitted SDK/CLI artifacts, the `ir.json` contract, and all CLI exit codes/output must be byte-for-byte unchanged unless a task explicitly says otherwise (none do).
- **Do NOT DRY across the `generator/sdk` ↔ `generator/cli` boundary.** That duplication is deliberate separation-of-duty. All extraction in this plan is within a single path or in the shared `opmodel` base.
- **Do NOT edit frozen oracles** — any path matching `protected_globs` in `.claude/harness.toml`, including `harness.toml` itself. If one looks wrong, stop and surface it.
- **No mocking of the system-under-test or the prisma-browser API boundary** (repo test policy). Mock only the network/OAG-jar boundary.
- **uv/nox env hygiene (this machine):** export `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup` for `uv run ...`; for venv-backed nox sessions (`tests`, `live`, `smoke`) also export `NOX_ENVDIR=$HOME/.tmp/cleanup-nox`. **Do NOT set `TMPDIR`** (breaks `test_config_init_and_show_commands`).
- **Phase gate:** run `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup uv run nox -s gate` (offline gate) after every task and `... uv run nox -s live` (skips without creds) before declaring a batch complete.
- **Branch/PR:** all work on `feature/repo-cleanup`; PR `--base develop`; **squash-merge**; **no version bump**. Record any user-observable change under `## [Unreleased]` in `CHANGELOG.md` (most tasks here are internal — add an entry only where a public symbol or behavior is touched).
- **Context docs:** after a batch that alters a subsystem, update its `.agents/context/*.md` deep-dive narrative and run `... uv run nox -s context` (`-- --check` must pass). Task 14 handles this.

---

## Review log (two python-pro plan reviews, 2026-06-25)

The plan was peer-reviewed against the real code on two axes. Both review sub-agents were
cut off by a session-limit reset before emitting reports, so the reviews were completed
inline using the already-read source. Corrections applied to this revision:

- **Test fixtures (Tasks 7–8):** dropped the fragile `tests/_emitted_support.py` import seam
  (no `tests/__init__.py`, no precedent for `from tests.<mod>` here). Shared fixtures move to
  `tests/conftest.py` (auto-discovered, the existing `emit_cli` pattern); cross-file helpers
  become conftest fixtures.
- **Task 1:** `import sys` must STAY in `modelschema.py` (uses `sys.modules` at lines 75/127)
  and `introspect.py`; only `classify.py` may drop it.
- **Task 11:** `cli/ir.py` line 8 must change `from typing import Any, Literal` → `from typing
  import Any` (verified: `Literal` is used only by the three moved defs).
- **Task 10:** `_render_docs` returns `list[str]` and the caller extends `written` (no
  `written.append` hand-off).
- **Task 12:** the re-raise test injects a fault into a collaborator (`load_product`), not into
  `app` itself, to respect the no-SUT-mock policy.
- **Task 9:** kept as plain module-level functions (NOT an `IrBuilder` class) — lower-risk for a
  behavior-preserving refactor; dropped the unused `models` param from `_resolve_columns`.

---

## File Structure

New files:
- `src/phantasos/generator/opmodel/_pathutil.py` — the `on_sys_path()` context manager (Task 1).
- `src/phantasos/generator/opmodel/vocab.py` — `FlagKind`, `Verb`, `SubVerb` literals, the new canonical home (Task 11).
- `tests/test_opmodel_pathutil.py` — unit test for the context manager (Task 1).
- `tests/test_sdk_preprocess.py` — direct unit tests for `sdk/preprocess.py` (Task 12).
- `tests/test_cli_emitted_{environments,config,runtime,history,logging,output}.py` — the split of `test_cli_emitted.py` (Task 7).

Modified (high-traffic):
- `src/phantasos/cli.py` — extract `_load_or_exit` / `_build_ir_or_exit` (Task 4); add error-funnel test coverage (Task 12).
- `src/phantasos/generator/cli/classify.py` — adopt `on_sys_path` (Task 1); decompose `build_cli_ir` (Task 9); import vocab from `opmodel` (Task 11).
- `src/phantasos/generator/cli/render_cli.py` — data-drive renders, extract `_enrich_ir`/`_render_docs` (Task 10).
- `src/phantasos/generator/cli/modelschema.py` — adopt `on_sys_path` (Task 1).
- `src/phantasos/generator/opmodel/{introspect,inventory,classify}.py` — adopt `on_sys_path` (Task 1); delete dead code (Tasks 2, 3); import vocab locally (Task 11).
- `src/phantasos/generator/cli/ir.py` — re-export vocab from `opmodel` for back-compat (Task 11).
- `tests/conftest.py` — home for the shared `emitted`/`emitted_auth`/`fake_client` fixtures (Task 7) and the `render_and_import` fixture (Task 8).

Renamed:
- `tests/test_cli_docs.py` → `tests/test_sdk_docs_context.py` (Task 5).

---

# Batch A — Tier 1: quick, safe, proven

## Task 1: `on_sys_path()` context manager (kills the 3× `sys.path` guard)

**Files:**
- Create: `src/phantasos/generator/opmodel/_pathutil.py`
- Create: `tests/test_opmodel_pathutil.py`
- Modify: `src/phantasos/generator/opmodel/introspect.py:196-206` (replace inline guard)
- Modify: `src/phantasos/generator/cli/classify.py:131-139` (replace inline guard)
- Modify: `src/phantasos/generator/cli/modelschema.py:169-176` (replace inline guard)

**Interfaces:**
- Produces: `on_sys_path(path: Path) -> ContextManager[None]` in `phantasos.generator.opmodel._pathutil`. Idempotent: inserts `str(path)` at `sys.path[0]` only if absent; removes on exit only if this call inserted it.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_opmodel_pathutil.py
"""Unit tests for the on_sys_path context manager."""

from __future__ import annotations

import sys
from pathlib import Path

from phantasos.generator.opmodel._pathutil import on_sys_path


def test_inserts_and_removes_when_absent(tmp_path: Path) -> None:
    p = str(tmp_path)
    assert p not in sys.path
    with on_sys_path(tmp_path):
        assert sys.path[0] == p
    assert p not in sys.path


def test_leaves_preexisting_entry_untouched(tmp_path: Path) -> None:
    p = str(tmp_path)
    sys.path.insert(0, p)
    try:
        with on_sys_path(tmp_path):
            assert p in sys.path
        assert p in sys.path  # we did not insert it, so we must not remove it
    finally:
        sys.path.remove(p)


def test_removes_even_on_exception(tmp_path: Path) -> None:
    p = str(tmp_path)
    try:
        with on_sys_path(tmp_path):
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert p not in sys.path
```

- [ ] **Step 2: Run test to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup uv run pytest tests/test_opmodel_pathutil.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'phantasos.generator.opmodel._pathutil'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/phantasos/generator/opmodel/_pathutil.py
"""Shared introspection primitive: temporarily put a built SDK on sys.path."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def on_sys_path(path: Path) -> Iterator[None]:
    """Insert ``str(path)`` at the front of ``sys.path`` for the block's duration.

    No-op if the entry is already present (and then it is NOT removed on exit),
    so nested/overlapping uses never strip an entry a caller put there.
    """
    entry = str(path)
    added = entry not in sys.path
    if added:
        sys.path.insert(0, entry)
    try:
        yield
    finally:
        if added and entry in sys.path:
            sys.path.remove(entry)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup uv run pytest tests/test_opmodel_pathutil.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Adopt it in `opmodel/introspect.py`**

Replace the body of `introspect` (lines 199-206) so it reads:

```python
def introspect(
    package: str, sdk_path: Path, *, registry_attr: str = "_RESOURCES"
) -> OperationInventory:
    with on_sys_path(sdk_path):
        return _introspect(package, registry_attr)
```

Add the import near the top (after the existing `from .inventory import ...`):

```python
from ._pathutil import on_sys_path
```

- [ ] **Step 6: Adopt it in `cli/classify.py`**

Replace lines 131-139 (the `added = ...` / `try` / `finally` guard inside `cli_operations`) with:

```python
    with on_sys_path(sdk_path):
        facade = importlib.import_module(f"{package}.extras.facade")
        wrappers: dict[str, tuple[type[Any], str]] = getattr(facade, registry_attr)
```

Add the import (with the other `..opmodel` imports near line 30):

```python
from ..opmodel._pathutil import on_sys_path
```

Then remove the now-unused `import sys` from `classify.py` **only if** no other `sys.` reference remains (grep first: `grep -n "sys\." src/phantasos/generator/cli/classify.py`).

- [ ] **Step 7: Adopt it in `cli/modelschema.py`**

Replace `build_model_registry`'s body (lines 169-176) with:

```python
def build_model_registry(
    package: str, sdk_path: Path, inv: OperationInventory
) -> dict[str, ModelSchema]:
    with on_sys_path(sdk_path):
        return registry_from_models(_root_models(package, inv))
```

Add `from ..opmodel._pathutil import on_sys_path`. **Keep `import sys`** here — `modelschema.py` still uses `sys.modules` at lines 75 and 127 (verified), so do NOT remove it. (Contrast `classify.py` in Step 6, where `sys` is used only by the guard and CAN be dropped.)

- [ ] **Step 8: Run the affected suites**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup uv run pytest tests/test_cli_introspect.py tests/test_cli_classify.py tests/test_cli_modelschema.py tests/test_opmodel_pathutil.py -q`
Expected: PASS, no regressions.

- [ ] **Step 9: Gate + commit**

```bash
UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup uv run nox -s gate
git add src/phantasos/generator/opmodel/_pathutil.py tests/test_opmodel_pathutil.py \
  src/phantasos/generator/opmodel/introspect.py \
  src/phantasos/generator/cli/classify.py src/phantasos/generator/cli/modelschema.py
git commit -m "refactor(opmodel): extract on_sys_path() context manager; dedup 3x sys.path guard"
```

> Note: `sdk/docs.py:173` has a 4th copy of this guard, but it is cross-path (`sdk`). Leave it for now — Task 11 may repoint it; do not collapse it solely to DRY.

---

## Task 2: Delete vestigial `OperationInfo.return_type`

**Files:**
- Modify: `src/phantasos/generator/opmodel/inventory.py:51` (delete the field)

**Interfaces:**
- Consumes: nothing. `return_type` is declared once and never set (all 8 construction sites omit it) or read.

- [ ] **Step 1: Prove it is dead**

Run: `grep -rn "return_type" src/ tests/ products/ | grep -v "return_type:" ` then `grep -rn "\.return_type" src/ tests/`
Expected: zero hits other than the declaration line `inventory.py:51`. (If any hit appears, STOP — it is not dead.)

- [ ] **Step 2: Delete the field**

In `src/phantasos/generator/opmodel/inventory.py`, remove line 51:

```python
    return_type: str = ""
```

- [ ] **Step 3: Run the inventory/introspect/classify suites**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup uv run pytest tests/test_cli_introspect.py tests/test_cli_classify.py tests/test_opmodel_classify.py -q`
Expected: PASS. (`extra="forbid"` on the model means a stray `return_type=` kwarg would now error — the green suite confirms none exists.)

- [ ] **Step 4: Typecheck + gate + commit**

```bash
UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup uv run nox -s gate
git add src/phantasos/generator/opmodel/inventory.py
git commit -m "refactor(opmodel): drop vestigial OperationInfo.return_type (superseded by return_model)"
```

---

## Task 3: Delete 3 unused back-compat aliases

**Files:**
- Modify: `src/phantasos/generator/opmodel/introspect.py:292-294`

**Interfaces:**
- Consumes: nothing. `_scalar_type`, `_field_kind`, `_union_members` have zero references; `_enum_values` / `_unwrap_optional` are kept (re-exported by the `cli/introspect.py` shim and used by `sdk/`).

- [ ] **Step 1: Prove the three are dead (and the two survivors are not)**

Run:
```bash
for s in _scalar_type _field_kind _union_members; do echo "== $s =="; grep -rn "$s" src/ tests/ | grep -v "introspect.py:29"; done
grep -rn "_enum_values\|_unwrap_optional" src/ tests/
```
Expected: the three loop targets show only their own definition lines; `_enum_values`/`_unwrap_optional` show real consumers (`cli/introspect.py`, `sdk/examples.py`, `sdk/wrapper.py`, tests). If a loop target has any other hit, STOP.

- [ ] **Step 2: Delete the three alias lines**

In `src/phantasos/generator/opmodel/introspect.py`, remove lines 292-294:

```python
_scalar_type = scalar_type
_field_kind = field_kind
_union_members = union_members
```

Keep lines 290-291 (`_enum_values` / `_unwrap_optional`). Update the comment on line 289 to read `# Backward-compatible private aliases (consumed by the cli.introspect shim + sdk).`

- [ ] **Step 3: Run the suite for affected modules**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup uv run pytest tests/test_cli_introspect.py tests/test_sdk_wrapper.py -q`
Expected: PASS.

- [ ] **Step 4: Gate + commit**

```bash
UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup uv run nox -s gate
git add src/phantasos/generator/opmodel/introspect.py
git commit -m "refactor(opmodel): drop 3 unused private aliases (_scalar_type/_field_kind/_union_members)"
```

---

## Task 4: Dedup host `cli.py` (`_load_or_exit` / `_build_ir_or_exit`)

**Files:**
- Modify: `src/phantasos/cli.py` (the 3× `load_product` guard + the 2× IR-build block)

**Interfaces:**
- Produces (module-private):
  - `_load_or_exit(product: str) -> LoadedProduct` — loads via `load_product`, converting `FileNotFoundError`/`ValueError` into `typer.Exit(2)` with the standardized message.
  - `_build_ir_or_exit(loaded: LoadedProduct) -> tuple[CliIR, CliConfig, list[str]]` — runs `load_cli_config` → `cli_operations` (ImportError→Exit(2)) → `build_model_registry` → `build_cli_ir`; returns `(ir, cfg, unmapped)`.

> Note: `sdk_build` also catches `pydantic.ValidationError` (cli_discover/cli_build do not). Keep `_load_or_exit` to the shared `(FileNotFoundError, ValueError)` contract and leave `sdk_build`'s extra `ValidationError` catch inline around the call, so no behavior changes.

- [ ] **Step 1: Run the host-CLI suite to establish a green baseline**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup uv run pytest tests/test_cli.py tests/test_cli_discover.py -q`
Expected: PASS (record the count).

- [ ] **Step 2: Add the two helpers**

In `src/phantasos/cli.py`, after the imports, add (the type imports go under `TYPE_CHECKING` to avoid import-time cost, matching the file's lazy-import style):

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .generator.cli.cliconfig import CliConfig
    from .generator.cli.ir import CliIR
    from .productconfig import LoadedProduct


def _load_or_exit(product: str) -> LoadedProduct:
    try:
        return load_product(product)
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(2) from exc


def _build_ir_or_exit(loaded: LoadedProduct) -> tuple[CliIR, CliConfig, list[str]]:
    from .generator.cli.classify import build_cli_ir, cli_operations
    from .generator.cli.cliconfig import load_cli_config
    from .generator.cli.modelschema import build_model_registry

    cfg = load_cli_config(Path(loaded.base_dir) / "cli.yml")
    try:
        # Wrapper-backed inventory: dispatch goes through the typed
        # client.<object>.<verb>(...) wrappers; the command tree is still
        # classified off the RAW operation names.
        inv = cli_operations(loaded.config.package, Path(loaded.output_dir))
    except ImportError as exc:
        typer.echo(f"ERROR: SDK not importable — build it first ({exc})", err=True)
        raise typer.Exit(2) from exc
    models = build_model_registry(loaded.config.package, Path(loaded.output_dir), inv)
    ir, unmapped = build_cli_ir(inv, cfg, models=models)
    return ir, cfg, unmapped
```

- [ ] **Step 3: Rewrite `cli_discover` to use the helpers**

Replace `cli_discover`'s body (current lines 71-100) with:

```python
    """print the classification table + cli.yml stub"""
    from .generator.cli.discover import render_stub, render_table

    loaded = _load_or_exit(product)
    ir, _cfg, unmapped = _build_ir_or_exit(loaded)
    typer.echo(render_table(ir, unmapped))
    if write_stub:
        stub_path = Path(loaded.base_dir) / "cli.yml.stub"
        stub_path.write_text(render_stub(ir, unmapped), encoding="utf-8")
        typer.echo(f"\nwrote {stub_path}", err=True)
```

- [ ] **Step 4: Rewrite `cli_build` to use the helpers**

Replace `cli_build`'s body up to the `scaffold_ctx` line (current lines 109-140) with:

```python
    """emit the CLI project from a built SDK"""
    from . import scaffold
    from .generator.cli.render_cli import cli_overrides_dir, render_cli
    from .generator.cli.scaffold_context import build_cli_scaffold_context

    loaded = _load_or_exit(product)
    ir, cfg, unmapped = _build_ir_or_exit(loaded)
    if loaded.config.project is None and cfg.project is None:
        typer.echo(
            "ERROR: cli build needs project metadata to scaffold the CLI — add a "
            "'project:' block to sdk.yml or cli.yml (see docs/authoring.md)",
            err=True,
        )
        raise typer.Exit(2)
    scaffold_ctx = build_cli_scaffold_context(loaded, ir, cfg)
```

Leave everything from `cli_pkg = ...` onward unchanged.

- [ ] **Step 5: Update `sdk_build` to use `_load_or_exit` (keeping its extra ValidationError catch)**

In `sdk_build`, replace the `try: loaded = load_product(...) except (FileNotFoundError, ValueError)... except ValidationError...` block (lines 34-41) with:

```python
    try:
        loaded = load_product(product)
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(2) from exc
    except ValidationError as exc:
        typer.echo(f"ERROR: invalid sdk.yml:\n{exc}", err=True)
        raise typer.Exit(2) from exc
```

(Leave `sdk_build` as-is — it has the extra `ValidationError` branch that the shared helper deliberately omits. Do NOT route it through `_load_or_exit`.)

- [ ] **Step 6: Run the host-CLI suite — must still be green**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup uv run pytest tests/test_cli.py tests/test_cli_discover.py -q`
Expected: PASS, same count as Step 1.

- [ ] **Step 7: Typecheck + gate + commit**

```bash
UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup uv run nox -s gate
git add src/phantasos/cli.py
git commit -m "refactor(cli): extract _load_or_exit/_build_ir_or_exit; dedup discover/build"
```

---

## Task 5: Rename misnamed `test_cli_docs.py` → `test_sdk_docs_context.py`

**Files:**
- Rename: `tests/test_cli_docs.py` → `tests/test_sdk_docs_context.py`

> Rationale: the file imports and tests `phantasos.generator.sdk.docs` (not CLI docs). The real CLI-docs tests live in `tests/cli/test_docs_context.py`. First confirm the file is not a frozen oracle.

- [ ] **Step 1: Confirm not protected**

Run: `grep -n "test_cli_docs" .claude/harness.toml`
Expected: no match (so the rename is allowed). If matched, STOP.

- [ ] **Step 2: Rename with git**

```bash
git mv tests/test_cli_docs.py tests/test_sdk_docs_context.py
```

- [ ] **Step 3: Fix the in-file path comment**

In `tests/test_sdk_docs_context.py`, change the first line `# tests/test_cli_docs.py` to `# tests/test_sdk_docs_context.py`.

- [ ] **Step 4: Run it under the new name**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup uv run pytest tests/test_sdk_docs_context.py -q`
Expected: PASS (same tests as before).

- [ ] **Step 5: Gate + commit**

```bash
UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup uv run nox -s gate
git add -A tests/test_sdk_docs_context.py
git commit -m "test: rename test_cli_docs.py -> test_sdk_docs_context.py (it tests sdk.docs)"
```

---

## Task 6: Mark the 17s OAG-jar build test as slow

**Files:**
- Modify: `tests/test_sdk_build.py` (the `test_build_emits_wrapper` test)
- Modify: `pyproject.toml` (`[tool.pytest.ini_options].markers` — register `slow`)

> `test_build_emits_wrapper` runs the full preprocess→OAG-jar→patches→vendor→smoke pipeline inside the unit run (17.2s, the slowest test). Marking it `slow` lets the default unit loop deselect it while the `smoke` nox session (which already builds SDKs end-to-end) keeps it.

- [ ] **Step 1: Register the marker (keeps `--strict-markers` happy)**

In `pyproject.toml` under `[tool.pytest.ini_options]`, add:

```toml
markers = ["slow: end-to-end builds (OAG jar / Java) — deselect with -m 'not slow'"]
```

- [ ] **Step 2: Mark the test**

In `tests/test_sdk_build.py`, add `@pytest.mark.slow` directly above `def test_build_emits_wrapper(...)` (import `pytest` if not already imported).

- [ ] **Step 3: Verify it is deselectable and still runnable**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup uv run pytest tests/test_sdk_build.py -m "not slow" -q` → the wrapper test is deselected.
Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup uv run pytest tests/test_sdk_build.py -q` → still collected and PASS (no `-m` filter).

- [ ] **Step 4: Confirm the `tests` nox session is unaffected**

Check `noxfile.py:133-151` (`tests` session). If it does NOT pass `-m "not slow"`, leave it — the marker is opt-out only; the default `nox -s tests` still runs everything. (Do not silently drop coverage; if you want the unit run faster, that is a separate, surfaced decision.)

- [ ] **Step 5: Gate + commit**

```bash
UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup uv run nox -s gate
git add tests/test_sdk_build.py pyproject.toml
git commit -m "test: mark test_build_emits_wrapper slow (17s OAG-jar build)"
```

- [ ] **Step 6: Close Batch A — run live**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup NOX_ENVDIR=$HOME/.tmp/cleanup-nox uv run nox -s live`
Expected: PASS or "skipped (no credentials)". Batch A complete.

---

# Batch B — test reorganization

## Task 7: Split `test_cli_emitted.py` (3,935 LOC) by behavioral seam

**Files:**
- Modify: `tests/test_cli_emitted.py` (becomes the `output`-rendering residue, or is fully drained — see Step 6)
- Create: `tests/test_cli_emitted_environments.py`, `tests/test_cli_emitted_config.py`, `tests/test_cli_emitted_runtime.py`, `tests/test_cli_emitted_history.py`, `tests/test_cli_emitted_logging.py`
- Modify: `tests/conftest.py` — the shared `emitted`/`emitted_auth`/`fake_client` fixtures move here so the split files get them auto-discovered with NO import (the established pattern; `emit_cli` already lives in conftest).

> This is a **mechanical move**, not a rewrite. No test body changes. The seams (from the prefix histogram): `env_*`/`auth_*`/`missing_*`/`no_auth_*` → environments; `config_*` → config; `runtime_*`/`cli_runner_*`/create/update/delete dispatch → runtime; `history` → history; `logging`/`diagnostics` → logging; everything output/table/columns/yaml/pager/autopager stays in the (renamed-in-place) base file. Confirm `tests/test_cli_emitted.py` is not in `protected_globs` first.

- [ ] **Step 1: Confirm not protected + green baseline + record the manifest**

```bash
grep -n "test_cli_emitted" .claude/harness.toml   # expect no match
UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup uv run pytest tests/test_cli_emitted.py -q   # record N passed
grep -nE "^def (test_|_)" tests/test_cli_emitted.py > /tmp/cleanup/emitted_manifest.txt
```
If protected, STOP.

- [ ] **Step 2: Move shared fixtures + cross-file helpers into `tests/conftest.py`**

There is no `tests/__init__.py` and no precedent for `from tests.<mod> import ...` in this repo, so a new importable `_emitted_support.py` seam is fragile. Use the established pattern instead: cut the `emitted` (34-53) and `emitted_auth` (96-142) fixtures into `tests/conftest.py` (where `emit_cli` already lives). pytest auto-discovers conftest fixtures for every test under `tests/`, so split files reference them **by name with no import**. For helper FUNCTIONS shared across more than one resulting file (notably `_fake_client`, used by the runtime seam and `test_cli_emitted_real.py`), move them to `conftest.py` and expose each as a fixture returning the callable:

```python
# tests/conftest.py
@pytest.fixture
def fake_client():
    return _fake_client   # _fake_client defined just above in conftest
```
Call sites change from `_fake_client(rec)` to requesting the `fake_client` fixture and calling `fake_client(rec)`. A helper used by only ONE seam moves WITH that seam's file (`_hist`→history, `_row`→output, `_read_environments_yml`→environments, `_read_config_yml`/`_write_user_config`/`_write_user_env_file`→config).

- [ ] **Step 3: Create the per-seam files by moving whole test functions**

For each seam, cut the matching `def test_*` blocks (and any seam-only helper) out of `test_cli_emitted.py` into the new file. No fixture imports are needed (conftest provides `emitted`/`emitted_auth`/`fake_client`); carry only the stdlib/pytest imports each file actually uses. Map:
- `tests/test_cli_emitted_environments.py` ← all `test_env_*`, `test_auth_*`, `test_missing_*`, `test_no_auth_*` (uses `emitted_auth`, `_read_environments_yml`).
- `tests/test_cli_emitted_config.py` ← all `test_config_*` (16) + `test_bool_*` (uses `_read_config_yml`, `_write_user_config`, `_write_user_env_file`).
- `tests/test_cli_emitted_runtime.py` ← `test_runtime_*`, `test_create_*`, `test_update_*`, `test_show_*` dispatch, `test_dry_*`, `test_injected_*` (uses `_fake_client`, `_oag_fake_client`, `_capture_facade_kwargs`).
- `tests/test_cli_emitted_history.py` ← all `test_history_*` (+ `_hist`).
- `tests/test_cli_emitted_logging.py` ← `test_logging_*`, `test_diagnostics_*`.
- residual `tests/test_cli_emitted.py` keeps output/render: `test_table_*`, `test_output_*`, `test_yaml_*`, `test_pager_*`, `test_autopager_*`, `test_columns_*`, `test_render_*`, `test_quiet_*`, `test_query_*`, `test_enum_*`, `test_scalar_*`, `test_version_*`, `test_meta_*`, etc. (+ `_row`, `_run_show_widget`).

- [ ] **Step 4: Verify zero tests lost (manifest diff)**

```bash
grep -hnE "^def test_" tests/test_cli_emitted*.py | sed -E 's/.*def (test_[a-z0-9_]+).*/\1/' | sort > /tmp/cleanup/after.txt
grep -E "def test_" /tmp/cleanup/emitted_manifest.txt | sed -E 's/.*def (test_[a-z0-9_]+).*/\1/' | sort > /tmp/cleanup/before.txt
diff /tmp/cleanup/before.txt /tmp/cleanup/after.txt && echo "NO TESTS LOST"
```
Expected: `NO TESTS LOST` (empty diff).

- [ ] **Step 5: Run the whole emitted family — count must match baseline**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup uv run pytest tests/test_cli_emitted*.py -q`
Expected: same total passed as Step 1's N (152), zero failures.

- [ ] **Step 6: Gate + commit**

```bash
UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup uv run nox -s gate
git add tests/test_cli_emitted*.py tests/conftest.py
git commit -m "test: split test_cli_emitted.py into per-seam files; shared fixtures to conftest"
```

---

## Task 8: Consolidate render/import/cleanup into one shared fixture

**Files:**
- Modify: `tests/conftest.py` (add `render_and_import`; route the `emitted`/`emitted_auth` fixtures through it)
- Modify: `tests/test_cli_emitted_real.py`, `tests/test_cli_dispatch_matrix.py`, `tests/test_cli_render.py` (replace the ~16+ inline `del sys.modules[... startswith(pkg)]` purges with the helper)

**Interfaces:**
- Produces: `render_and_import(out_dir: Path, package: str) -> ModuleType` context manager / helper in `tests/conftest.py` that (1) puts `out_dir` on `sys.path`, (2) purges any already-imported `package*` modules from `sys.modules`, (3) imports & returns the package, (4) on exit restores `sys.path` and re-purges. Always calls `load_config.cache_clear()` if the emitted package exposes it.

- [ ] **Step 1: Green baseline**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup uv run pytest tests/test_cli_emitted_real.py tests/test_cli_dispatch_matrix.py tests/test_cli_render.py -q` (record counts).

- [ ] **Step 2: Add the helper to `conftest.py`**

```python
# tests/conftest.py  (append)
import importlib
from contextlib import contextmanager
from types import ModuleType


@contextmanager
def _imported(out_dir: Path, package: str):
    """Import an emitted package from out_dir with a clean module namespace."""
    def _purge() -> None:
        for name in [m for m in sys.modules if m == package or m.startswith(package + ".")]:
            del sys.modules[name]
    entry = str(out_dir)
    added = entry not in sys.path
    if added:
        sys.path.insert(0, entry)
    _purge()
    try:
        yield importlib.import_module(package)
    finally:
        _purge()
        if added and entry in sys.path:
            sys.path.remove(entry)


@pytest.fixture
def render_and_import():
    """Yield the _imported(out_dir, package) context manager to tests."""
    return _imported
```

- [ ] **Step 3: Route `emitted` / `emitted_auth` through it**

In `tests/conftest.py`, rewrite the `emitted`/`emitted_auth` fixtures so their `sys.path`/`sys.modules` bookkeeping is replaced by `with _imported(out, "fakesdk_cli"): yield out` (keep yielding the same object — just drop the hand-rolled purge/restore).

- [ ] **Step 4: Replace inline purges in the three consumer files**

In `test_cli_emitted_real.py`, `test_cli_dispatch_matrix.py`, `test_cli_render.py`, replace each inline `del sys.modules[...]` purge + `sys.path` dance with the `render_and_import` fixture (or `_imported` import). Grep to confirm none remain: `grep -rn "del sys.modules" tests/` → only `conftest.py` should match.

- [ ] **Step 5: Full emitted + real + matrix + render run**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup uv run pytest tests/test_cli_emitted*.py tests/test_cli_dispatch_matrix.py tests/test_cli_render.py -q`
Expected: counts match Steps 1 and Task 7; zero failures; **run twice** to confirm no order-dependence (`-p no:randomly` not needed; just rerun).

- [ ] **Step 6: Gate + commit**

```bash
UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup uv run nox -s gate
git add tests/conftest.py tests/test_cli_emitted_real.py \
  tests/test_cli_dispatch_matrix.py tests/test_cli_render.py
git commit -m "test: consolidate render/import/cleanup into shared render_and_import fixture"
```

---

## Task 13: Trim `emitted_real` duplicates + parametrize copy-pasted families

**Files:**
- Modify: `tests/test_cli_emitted_real.py` (drop fakesdk-equivalent generator-only assertions)
- Modify: `tests/test_cli_emitted_config.py` / `tests/test_cli_emitted_environments.py` (parametrize near-twins)

> Keep every test that needs the REAL spec (real model construction via `model_construct`, classifier-against-real-spec, real enum/URL validation). Only drop assertions that prove generator-output properties independent of the spec and are already proven on fakesdk.

- [ ] **Step 1: Identify the spec-independent duplicates**

In `test_cli_emitted_real.py`, locate the lint-clean, `--version`, and `config init/show` tests (the report cites `:719`, `:729`, `:857`). Confirm each has a fakesdk twin in the split files (`grep -rn "lint\|--version\|config init" tests/test_cli_emitted*.py`).

- [ ] **Step 2: Delete the confirmed duplicates from `test_cli_emitted_real.py`**

Remove only those 3 generator-only tests. Leave a one-line module comment: `# generator-output invariants (lint-clean, --version, config init/show) are proven on fakesdk in test_cli_emitted*.py; this module covers real-spec behavior only.`

- [ ] **Step 3: Parametrize obvious near-twins**

Collapse copy-pasted families with `@pytest.mark.parametrize`, e.g. the `env_delete_*` cases and `test_diagnostics_plain`/`_styled`/`_min_level`. Keep one test function per family; assert the same things per param. Show the diff is behavior-identical by name-mapping in the commit message.

- [ ] **Step 4: Run + confirm net coverage unchanged**

```bash
UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup uv run pytest tests/test_cli_emitted*.py --cov=phantasos --cov-report=term-missing -q
```
Expected: PASS; total coverage ≥ the pre-task number (95.84%). If coverage drops, a deleted test was not actually a duplicate — restore it.

- [ ] **Step 5: Gate + commit + close Batch B with live**

```bash
UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup uv run nox -s gate
git add tests/test_cli_emitted_real.py tests/test_cli_emitted_config.py tests/test_cli_emitted_environments.py
git commit -m "test: drop fakesdk-equivalent real-SDK duplicates; parametrize near-twins"
UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup NOX_ENVDIR=$HOME/.tmp/cleanup-nox uv run nox -s live
```

---

# Batch C — source complexity

## Task 9: Decompose `build_cli_ir` (CC 53 → orchestrator + named stages)

**Files:**
- Modify: `src/phantasos/generator/cli/classify.py:395-611`

**Interfaces:**
- Produces (module-private, signatures the orchestrator calls):
  - `_validate_defaults(cfg: CliConfig, ops_index: dict[str, OperationInfo]) -> None`
  - `_emit_command(groups, op, *, verb, obj, variant, sub_verb, body_model, cfg, models, variant_param=None) -> None` (the promoted `_emit` closure)
  - `_relax_patch_body_requiredness(groups: dict[str, Command]) -> None`
  - `_flag_get_by_id_only(groups: dict[str, Command]) -> None`
  - `_resolve_columns(groups, cfg, dispatch_index) -> None` (the columns block reads `groups`/`cfg.columns`/`dispatch_index` only — it does NOT use `models`)
- `build_cli_ir` keeps its exact public signature and return type `tuple[CliIR, list[str]]`.

> Pure extraction: move each commented block (529-539, 547-555, 557-602) verbatim into a named function taking the locals it reads as params; promote the `_emit` closure (431-498) to module level, passing `cfg`/`models` explicitly. **No logic edits.** The existing `test_cli_classify.py` (560 LOC) + `test_cli_dispatch_matrix.py` are the oracle.
>
> Design note: keep these as plain module-level functions, NOT an `IrBuilder` class. For a behavior-preserving refactor, threading explicit params is lower-risk and easier to verify than introducing stateful object shape; a class is a larger redesign and out of scope here.

- [ ] **Step 1: Green baseline + record complexity**

```bash
UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup uv run pytest tests/test_cli_classify.py tests/test_cli_dispatch_matrix.py tests/test_cli_ir.py -q
uvx radon cc -s src/phantasos/generator/cli/classify.py | grep build_cli_ir   # F (53)
```

- [ ] **Step 2: Promote `_emit` to a module-level `_emit_command`**

Cut the nested `def _emit(...)` (431-498). Define it at module scope with the captured names (`groups`, `cfg`, `models`) added as explicit params. At the call sites (517-527), pass them through. Run the suite — must stay green.

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup uv run pytest tests/test_cli_classify.py -q` → PASS.

- [ ] **Step 3: Extract `_validate_defaults`**

Move the defaults-validation loop (418-429) into `_validate_defaults(cfg, ops_index)`; call it from `build_cli_ir`. Run the classify suite → PASS.

- [ ] **Step 4: Extract the three post-passes**

Move blocks 536-539 → `_relax_patch_body_requiredness(groups)`; 547-555 → `_flag_get_by_id_only(groups)`; 557-602 (incl. the `rank`/`_rep_op`/`obj_fields`/columns logic) → `_resolve_columns(groups, cfg, dispatch_index)`. Call them in the same order from the orchestrator. Run the classify + dispatch suites → PASS.

- [ ] **Step 5: Confirm complexity dropped + full CLI suite green**

```bash
uvx radon cc -s src/phantasos/generator/cli/classify.py | grep -E "build_cli_ir|_emit_command|_resolve_columns"  # build_cli_ir now <= C
UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup uv run pytest tests/test_cli_classify.py tests/test_cli_dispatch_matrix.py tests/test_cli_ir.py tests/test_cli_emitted*.py -q
```
Expected: all PASS; `build_cli_ir` no longer F-rank.

- [ ] **Step 6: Gate + commit**

```bash
UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup uv run nox -s gate
git add src/phantasos/generator/cli/classify.py
git commit -m "refactor(cli): decompose build_cli_ir into orchestrator + named stages"
```

---

## Task 10: Data-drive `render_cli` (CC 32 → table + extracted helpers)

**Files:**
- Modify: `src/phantasos/generator/cli/render_cli.py:295-464`

**Interfaces:**
- Produces (module-private):
  - `_GENERATED: tuple[tuple[str, str], ...]` — `(template, rel_dest)` pairs for the ~10 fixed `_generated/*` renders.
  - `_enrich_ir(ir: CliIR, auth: object | None, errors: object | None) -> CliIR` — the two `model_copy` enrichment blocks (334-341).
  - `_render_docs(env, ctx, ir, docs, *, distribution, docs_site_name, resolved_prefix, docs_repo_url, docs_description, render_doc_sink) -> None` — the whole `if docs is not None` block (420-458).
- `render_cli` keeps its exact public signature and return type `list[str]`.

> Behavior-preserving. The emitted file set, `ir.json`, and `spec.py` must be byte-identical. `test_cli_render.py` (219 LOC) + `test_cli_skeleton.py` + the emitted suites are the oracle.

- [ ] **Step 1: Green baseline + snapshot the emitted file list**

```bash
UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup uv run pytest tests/test_cli_render.py tests/test_cli_skeleton.py -q
```
Note: `test_cli_render.py` already asserts the written-file set — that is the byte-for-byte guard.

- [ ] **Step 2: Extract `_enrich_ir`**

Replace lines 334-341 with `ir = _enrich_ir(ir, auth, errors); ctx["ir"] = ir`. Define `_enrich_ir` to perform the same two `hasattr`-gated `model_copy` updates and return the (possibly new) ir. Run render suite → PASS.

- [ ] **Step 3: Data-drive the fixed `_generated/*` renders**

Replace the ~10 literal `render("_generated/x.jinja", gen / "x")` lines (349-358) with:

```python
_GENERATED = (
    ("_generated/__init__.py.jinja", "__init__.py"),
    ("_generated/config.py.jinja", "config.py"),
    ("_generated/default_config.yml.jinja", "default_config.yml"),
    ("_generated/config_commands.py.jinja", "config_commands.py"),
    ("_generated/history.py.jinja", "history.py"),
    ("_generated/cli_commands.py.jinja", "cli_commands.py"),
    ("_generated/diagnostics.py.jinja", "diagnostics.py"),
    ("_generated/logging_setup.py.jinja", "logging_setup.py"),
    ("_generated/output.py.jinja", "output.py"),
    ("_generated/runtime.py.jinja", "runtime.py"),
)
# ... inside render_cli:
for template, rel in _GENERATED:
    render(template, gen / rel)
```
Keep the `spec.py`, conditional `environment_commands.py`, and `ir.json` writes exactly as-is (they are not uniform renders). Run render suite → PASS.

- [ ] **Step 4: Extract `_render_docs`**

Move the entire `if docs is not None:` block (420-458), including the nested `render_doc` closure and the conditional `has_auth`/`show_pagination_guide` renders, into `_render_docs(...) -> list[str]` that returns the doc rel-paths it wrote. Call it as `if docs is not None: written.extend(_render_docs(...))`, so the returned `written` list (which `_format_generated` consumes) stays in the same order. Run render + emitted-docs suites → PASS.

- [ ] **Step 5: Confirm complexity dropped + byte-identical output**

```bash
uvx radon cc -s src/phantasos/generator/cli/render_cli.py | grep render_cli   # now <= C
UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup uv run pytest tests/test_cli_render.py tests/test_cli_skeleton.py tests/test_cli_emitted*.py tests/cli/ -q
```
Expected: all PASS.

- [ ] **Step 6: Gate + commit + close Batch C with live**

```bash
UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup uv run nox -s gate
git add src/phantasos/generator/cli/render_cli.py
git commit -m "refactor(cli): data-drive render_cli fixed renders; extract _enrich_ir/_render_docs"
UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup NOX_ENVDIR=$HOME/.tmp/cleanup-nox uv run nox -s live
```

---

# Batch D — layering + coverage

## Task 11: Fix the layering inversion (`opmodel/vocab.py`)

**Files:**
- Create: `src/phantasos/generator/opmodel/vocab.py`
- Modify: `src/phantasos/generator/opmodel/inventory.py:9`, `introspect.py:17`, `classify.py:12` (import from `.vocab`, not `..cli.ir`)
- Modify: `src/phantasos/generator/cli/ir.py` (define vocab by importing from `..opmodel.vocab`, re-export for back-compat)

**Interfaces:**
- Produces: `FlagKind`, `Verb`, `SubVerb` Literal aliases in `phantasos.generator.opmodel.vocab` (values identical to today's `cli/ir.py` definitions).
- `cli.ir.FlagKind/Verb/SubVerb` continue to exist (re-exported), so every existing import site keeps working.

> Root cause: the base layer `opmodel` imports UP into `cli.ir` for these three Literals. Moving them down to `opmodel/vocab.py` restores an acyclic `opmodel → {sdk, cli}`. The values are unchanged, so the serialized `ir.json`/`spec.py` contract is untouched.

- [ ] **Step 1: Green baseline**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup uv run pytest tests/test_cli_ir.py tests/test_cli_classify.py tests/test_cli_introspect.py tests/test_opmodel_classify.py -q`

- [ ] **Step 2: Create `opmodel/vocab.py`**

```python
# src/phantasos/generator/opmodel/vocab.py
"""Classification vocabulary shared by opmodel, sdk, and cli (the base layer).

Lives here (not cli.ir) so the base opmodel layer never imports up into cli.
cli.ir re-exports these names for backward compatibility.
"""

from __future__ import annotations

from typing import Literal

FlagKind = Literal["scalar", "enum", "json", "file", "id"]
Verb = Literal["create", "update", "delete", "show", "request", "load", "backup"]
SubVerb = Literal[
    "create",
    "patch",
    "put",
    "update",
    "get",
    "list",
    "delete",
    "bulk_create",
    "bulk_delete",
    "action",
]
```

- [ ] **Step 3: Repoint the opmodel imports**

- `opmodel/inventory.py:9`: `from ..cli.ir import FlagKind` → `from .vocab import FlagKind`
- `opmodel/introspect.py:17`: `from ..cli.ir import FlagKind` → `from .vocab import FlagKind`
- `opmodel/classify.py:12`: `from ..cli.ir import SubVerb, Verb` → `from .vocab import SubVerb, Verb`

- [ ] **Step 4: Make `cli/ir.py` re-export from vocab**

In `cli/ir.py`, replace the local `FlagKind = Literal[...]` (line 12) and the `Verb`/`SubVerb` definitions (77-89) with a single re-export near the top:

```python
from ..opmodel.vocab import FlagKind, SubVerb, Verb  # re-exported for back-compat
```

Keep `FlagKind`/`Verb`/`SubVerb` in `cli/ir.py`'s `__all__` if it has one (add one if needed) so `from .ir import Verb` keeps resolving. **Then fix the now-unused import**: `Literal` in `cli/ir.py` is used ONLY by the three moved definitions (verified — lines 12/77/78), so change line 8 `from typing import Any, Literal` → `from typing import Any` (else ruff F401 fails the gate). `Any` stays — it is used elsewhere in `ir.py`.

- [ ] **Step 5: Confirm the cycle is gone**

```bash
uvx pydeps --version >/dev/null 2>&1 && uvx pydeps src/phantasos/generator/opmodel --only phantasos.generator --no-show 2>/dev/null || true
# Manual check: opmodel must no longer import cli
grep -rn "from ..cli\|from \.\.cli\|import.*cli\.ir" src/phantasos/generator/opmodel/*.py
```
Expected: the grep returns **nothing** (opmodel no longer reaches into cli).

- [ ] **Step 6: Full suite + typecheck**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup uv run pytest tests/test_cli_ir.py tests/test_cli_classify.py tests/test_cli_introspect.py tests/test_opmodel_classify.py tests/test_sdk_wrapper.py tests/test_cli_emitted*.py -q`
Then: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup uv run nox -s gate` (runs mypy strict).
Expected: PASS — including the emitted suites (proves `spec.py`/`ir.json` unchanged).

- [ ] **Step 7: Commit**

```bash
git add src/phantasos/generator/opmodel/vocab.py src/phantasos/generator/opmodel/inventory.py \
  src/phantasos/generator/opmodel/introspect.py src/phantasos/generator/opmodel/classify.py \
  src/phantasos/generator/cli/ir.py
git commit -m "refactor(opmodel): move Verb/SubVerb/FlagKind down to opmodel.vocab (fix layering inversion)"
```

> Optional follow-on (only if green stays trivially): repoint `sdk/examples.py:21` and `sdk/wrapper.py:30` from the `cli.introspect` shim to `..opmodel.introspect` directly, removing the last sideways `sdk → cli` edge. Keep `cli/introspect.py` as a shim for tests. If it adds any churn or risk, defer it.

---

## Task 12: Close the two real coverage gaps

**Files:**
- Create: `tests/test_sdk_preprocess.py`
- Modify: `tests/test_cli.py` (add the error-funnel test for `main()`)

> `sdk/preprocess.py` is the lowest-covered module (84%) with no direct unit test; `cli.py` is 80% with the `except Exception` exit-code path in `main()` untested. Both are easy, valuable additions. No mocking of the SUT — call the real functions.

- [ ] **Step 1: Read the uncovered lines to target them precisely**

```bash
UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup uv run pytest tests/test_sdk_patches.py --cov=phantasos.generator.sdk.preprocess --cov-report=term-missing -q
```
Read `src/phantasos/generator/sdk/preprocess.py` around the missing lines (66,70,75-82,119-123,177,180,199): `_resolve_type` allOf/cycle branches, the latin-1→utf-8 mojibake repair, `hoist_items` skip paths.

- [ ] **Step 2: Write `test_sdk_preprocess.py` (real inputs, no mocks)**

Cover, with real minimal OpenAPI dict fragments fed to the real functions:
- `_resolve_type` on a `$ref` cycle (recursion guard) and on an `allOf` node.
- `collapse_allof` merging a 2-member `allOf`.
- `fix_strings_and_enums` repairing a mojibake string (a byte sequence that round-trips latin-1→utf-8).
- `hoist_items` on a node it should skip.

(Write the test names first, run to fail with `assert`/import errors, then fill bodies until each targeted line is hit.)

- [ ] **Step 3: Add the `main()` error-funnel test to `test_cli.py`**

```python
def test_main_returns_exit_code_from_click_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    # An unknown subcommand makes typer/click raise an exception carrying exit_code=2;
    # main() must capture it and return the code (not raise).
    from phantasos import cli

    assert cli.main(["definitely-not-a-command"]) == 2


def test_main_reraises_plain_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    # Inject a fault into a COLLABORATOR (load_product), not into main() or `app`.
    # A RuntimeError is not one of the exit_code-bearing click errors, so it must
    # propagate through main()'s funnel (the bare `raise` on the no-exit_code path).
    from phantasos import cli

    def _boom(_product: str) -> object:
        raise RuntimeError("no exit_code here")

    monkeypatch.setattr(cli, "load_product", _boom)
    with pytest.raises(RuntimeError):
        cli.main(["sdk", "build", "anything"])
```

> Note: `sdk_build` only catches `FileNotFoundError`/`ValueError`/`ValidationError` around `load_product`, so a `RuntimeError` bubbles through `app()` to `main()`'s `except Exception` with no `.exit_code` → the bare `raise` (line 190). This exercises the real funnel without mocking the system under test (`main`) or the `app` object.

- [ ] **Step 4: Run with coverage — confirm both modules climb**

```bash
UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup uv run pytest tests/test_sdk_preprocess.py tests/test_cli.py \
  --cov=phantasos.generator.sdk.preprocess --cov=phantasos.cli --cov-report=term-missing -q
```
Expected: PASS; `preprocess.py` and `cli.py` coverage both increase (targeted lines now hit).

- [ ] **Step 5: Gate + commit**

```bash
UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup uv run nox -s gate
git add tests/test_sdk_preprocess.py tests/test_cli.py
git commit -m "test: add direct sdk/preprocess unit tests + cli.main error-funnel coverage"
```

---

## Task 14: Refresh agent-context docs + final full-suite verification

**Files:**
- Modify: relevant `.agents/context/*.md` deep-dives (start at `.agents/context/index.md`; likely the CLI-generator and SDK-generator docs touched by Tasks 1, 9, 10, 11)

- [ ] **Step 1: Read the index and identify affected deep-dives**

Read `.agents/context/index.md`; for each subsystem changed (opmodel layering, cli classify/render, the new `vocab`/`_pathutil` modules), update the narrative to match (e.g. "Verb/SubVerb/FlagKind now live in `opmodel/vocab.py`"; "`build_cli_ir` is an orchestrator over named stages").

- [ ] **Step 2: Refresh generated blocks**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup uv run nox -s context`
Then verify: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup uv run nox -s context -- --check`
Expected: `--check` passes.

- [ ] **Step 3: Full suite, gate, live, audit**

```bash
UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup NOX_ENVDIR=$HOME/.tmp/cleanup-nox uv run nox -s tests
UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup uv run nox -s gate
UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup NOX_ENVDIR=$HOME/.tmp/cleanup-nox uv run nox -s live
UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cleanup uv run nox -s audit
```
Expected: 567 passing (or more, with new tests), coverage ≥ 95.84%, gate green, live green-or-skipped, audit clean.

- [ ] **Step 4: Commit context refresh**

```bash
git add .agents/context/
git commit -m "docs(context): refresh deep-dives after repo-cleanup refactor"
```

- [ ] **Step 5: Open the PR**

```bash
git push "https://x-access-token:$(gh auth token)@github.com/kaisero/phantasos.git" feature/repo-cleanup
gh pr create --base develop --title "refactor: repo cleanup (dead code, dedup, complexity, layering, tests)" \
  --body "Implements docs/plans/2026-06-25-repo-cleanup-implementation.md. Pure refactor — no behavior change; no version bump. See docs/plans/2026-06-25-repo-cleanup-findings.md for the audit."
```

---

# Deferred (Tier 3 — NOT in this plan)

Explicitly out of scope here; surfaced in the findings report. Revisit deliberately, not as drive-bys:
- **`LoadedProduct` Protocol typing** (`productconfig.py`) — touches the load path; do as its own change with care.
- **Error-template Jinja base block** (`sdk/components/errors/*.jinja`) — emitted/template scope; changes generated output; maintainability-only.
- **`tests/cli/` split-axis decision** + `modelschema` test de-dup — needs a one-axis decision (CLI-docs-only vs all-`test_cli_*`).
- **`StrEnum` for Verb/SubVerb/FlagKind** — crosses the frozen `ir.json`/`spec.py` contract; belongs in the in-flight CLI IR-deepening work, not here.
- **`emitted` fixture session-scoping**, **`pydantic>=2.11` floor bump**, **`select_method_for_verb` fate** — minor; maintainer's call.

---

# Self-review

- **Spec coverage:** Findings Tier 1 → Tasks 1–6; Tier 2 → Tasks 7–13; layering/coverage → Tasks 11–12; context refresh → Task 14. Tier 3 explicitly deferred. ✓
- **Placeholder scan:** every code step shows real code; refactor tasks name exact functions/lines and use the existing suite as the oracle. ✓
- **Type consistency:** new symbols (`on_sys_path`, `_load_or_exit`, `_build_ir_or_exit`, `_emit_command`, `_enrich_ir`, `_render_docs`, `opmodel.vocab.{FlagKind,Verb,SubVerb}`, `render_and_import`) are defined once and referenced with matching names/signatures across tasks. ✓
- **Ordering:** Task 7 (split) establishes the shared `conftest.py` fixtures; Task 8 (consolidate `render_and_import`) builds on them; Tasks 9/10 are independent; Task 11 must precede Task 14's context note about vocab. Batches run A→D. ✓
