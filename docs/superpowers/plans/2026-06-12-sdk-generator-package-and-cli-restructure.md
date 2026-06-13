# SDK Generator Package + Host-CLI Restructure — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Relocate SDK-generation logic into `src/phantasos/generator/sdk/` (sibling to `generator/cli/`) and move the command to `phantasos sdk build` (host CLI migrated argparse→Typer), with zero SDK-build behavior change.

**Architecture:** A structural refactor. The SDK-gen pipeline modules (`generate/preprocess/patches/render/smoke/provision` + `components/`) and the `build()` orchestrator move under `generator/sdk/`; shared infra (`scaffold*`, `productconfig`, `config`) stays top-level; `cli.py` becomes a Typer app. Each task leaves the full test suite green (the refactor analog of red→green: do the move, watch imports break, fix them, watch green).

**Tech Stack:** Python 3.11+, Typer/click, pytest, git mv, ruff, mypy.

**Design doc:** `docs/superpowers/specs/2026-06-12-sdk-generator-package-and-cli-restructure-design.md`

**Test runner note:** `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-repro uv run python -m pytest …` (the `.nox` venv path fails on this sshfs checkout). `ruff check`/`mypy` likewise via `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-repro uv run …`. NOTE: `ruff format --check` has KNOWN pre-existing repo-wide drift (ruff 0.15.16 bump); ignore format-only diffs, only act on `ruff check` lint failures.

**Pre-flight facts (verified):**
- `src/phantasos/__init__.py` is 149 lines: `_ABOUT` (27-32), `build()` (35-135), `_load_hooks()` (138-149). `build()` does local imports `from . import generate, preprocess, render, smoke` (line 36), `from . import patches` (86), `from . import scaffold` (108); type hint `LoadedProduct` from `from .productconfig import LoadedProduct` (line 17).
- `render.py:9` `from .productconfig import LoadedProduct` — the ONLY non-sibling internal import in the moving set. `generate.py:8`/`smoke.py:16` `from . import provision` (siblings — stay relative).
- `scaffold.py`, `scaffold/`, `productconfig.py`, `config.py` STAY top-level (shared, imported by host + cli generator).
- Test importers: `test_generate.py:7,77,95`; `test_render.py:5`; `test_smoke.py:7,8`; `test_provision.py:10,11`; `test_framework.py:6`; `test_cli.py` (monkeypatch strings `phantasos.generate.*`/`render.vendor`/`patches.apply_generic_patches`/`smoke.smoke`/`preprocess.tag_operations`, `phantasos.build`, and `cli.main([...])`); `test_scaffold.py:6` STAYS unchanged.
- `noxfile.py:113-114` `session.run("phantasos","build", …)`.

---

## Task 1: Move the SDK-gen pipeline modules into `generator/sdk/` (build() stays put for now)

**Files:**
- Create: `src/phantasos/generator/sdk/__init__.py`
- Move: `git mv` of `generate.py`, `preprocess.py`, `patches.py`, `render.py`, `smoke.py`, `provision.py`, `components/` → `src/phantasos/generator/sdk/`
- Modify: `src/phantasos/generator/sdk/render.py` (one import), `src/phantasos/__init__.py` (build()'s local imports), tests: `test_generate.py`, `test_render.py`, `test_smoke.py`, `test_provision.py`, `test_framework.py`, and the monkeypatch paths in `test_cli.py`

- [ ] **Step 1: Establish the green baseline**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-repro uv run python -m pytest tests/test_generate.py tests/test_render.py tests/test_smoke.py tests/test_provision.py tests/test_framework.py tests/test_cli.py -q`
Expected: PASS (baseline before the move).

- [ ] **Step 2: Create the package and move the modules**

```bash
cd /home/ubuntu/git/phantasos
mkdir -p src/phantasos/generator/sdk
printf '"""SDK generation: preprocess -> generate (OAG) -> patch -> vendor -> scaffold -> smoke."""\n' > src/phantasos/generator/sdk/__init__.py
git add src/phantasos/generator/sdk/__init__.py
for m in generate preprocess patches render smoke provision; do
  git mv src/phantasos/$m.py src/phantasos/generator/sdk/$m.py
done
git mv src/phantasos/components src/phantasos/generator/sdk/components
```

- [ ] **Step 3: Verify the move broke imports (red)**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-repro uv run python -m pytest tests/test_generate.py -q`
Expected: FAIL/ERROR — `ModuleNotFoundError: No module named 'phantasos.generate'` (and `render.py` may fail to import `productconfig`).

- [ ] **Step 4: Fix the one non-sibling internal import in render.py**

In `src/phantasos/generator/sdk/render.py`, change line 9:
```python
from .productconfig import LoadedProduct
```
to:
```python
from ...productconfig import LoadedProduct
```
(`generate.py`/`smoke.py` keep `from . import provision` — provision is now a sibling. `preprocess.py`/`patches.py` had no internal phantasos imports.)

- [ ] **Step 5: Update `build()`'s local imports in `phantasos/__init__.py`**

Line 36: `from . import generate, preprocess, render, smoke` → `from .generator.sdk import generate, preprocess, render, smoke`
Line 86: `from . import patches` → `from .generator.sdk import patches`
(Leave line 108 `from . import scaffold` unchanged — scaffold stays top-level.)

- [ ] **Step 6: Update test imports**

- `tests/test_generate.py`: `from phantasos import generate` (lines 7, 77, 95) → `from phantasos.generator.sdk import generate`. Monkeypatch strings: `"phantasos.provision._download_verified"`/`"phantasos.provision.resolve_java"` → `"phantasos.generator.sdk.provision.…"`; `"phantasos.generate.subprocess.run"` → `"phantasos.generator.sdk.generate.subprocess.run"`.
- `tests/test_render.py:5`: `from phantasos import render` → `from phantasos.generator.sdk import render`. (Leave the `from phantasos.productconfig import …` line on :6 untouched.)
- `tests/test_smoke.py:7,8`: `from phantasos import smoke` → `from phantasos.generator.sdk import smoke`; `from phantasos.smoke import SmokeError` → `from phantasos.generator.sdk.smoke import SmokeError`.
- `tests/test_provision.py:10,11`: `from phantasos import provision` → `from phantasos.generator.sdk import provision`; `from phantasos.provision import ProvisionError` → `from phantasos.generator.sdk.provision import ProvisionError`.
- `tests/test_framework.py:6`: `from phantasos import patches, preprocess, render` → `from phantasos.generator.sdk import patches, preprocess, render`.
- `tests/test_cli.py` (monkeypatch STRINGS only in THIS task — leave `cli.main(["build",…])` invocation lists and the `phantasos.build(loaded)` calls for Task 2/3): update **every** `monkeypatch.setattr("phantasos.<mod>.…")` string across ALL test functions (not just the ones inside `cli.main(...)` tests) — verified occurrences at lines ~92, 93, 94, 96, 100, 159, 161, 188, 206. Map: `"phantasos.generate.…"`→`"phantasos.generator.sdk.generate.…"`, `"phantasos.render.vendor"`→`"phantasos.generator.sdk.render.vendor"`, `"phantasos.patches.apply_generic_patches"`→`"phantasos.generator.sdk.patches.apply_generic_patches"`, `"phantasos.smoke.smoke"`→`"phantasos.generator.sdk.smoke.smoke"`, `"phantasos.preprocess.tag_operations"`→`"phantasos.generator.sdk.preprocess.tag_operations"`, and `"phantasos.provision.…"`→`"phantasos.generator.sdk.provision.…"`. Leave `"phantasos.scaffold.render_scaffold"` (≈line 164) UNCHANGED (scaffold stays top-level). After this task `grep -n "phantasos\.\(generate\|render\|patches\|smoke\|preprocess\|provision\)\." tests/test_cli.py` must return ZERO non-`generator.sdk` hits.

- [ ] **Step 7: Verify green**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-repro uv run python -m pytest tests/test_generate.py tests/test_render.py tests/test_smoke.py tests/test_provision.py tests/test_framework.py tests/test_cli.py -q`
Expected: PASS (all). Then `ruff check src/phantasos/generator/sdk tests/test_generate.py tests/test_render.py tests/test_smoke.py tests/test_provision.py tests/test_framework.py` → All checks passed; `mypy src/phantasos/generator/sdk` → Success.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "refactor(phantasos): move SDK-gen pipeline modules into generator/sdk/"
```

---

## Task 2: Move `build()` orchestrator into `generator/sdk/build.py`

**Files:**
- Create: `src/phantasos/generator/sdk/build.py`
- Modify: `src/phantasos/generator/sdk/__init__.py`, `src/phantasos/__init__.py`, `src/phantasos/cli.py`, `tests/test_cli.py`

- [ ] **Step 1: Create `build.py` with the moved orchestrator**

Cut `_ABOUT` (lines 27-32), `build()` (35-135), and `_load_hooks()` (138-149) out of `src/phantasos/__init__.py` and paste them into a new `src/phantasos/generator/sdk/build.py` with this header + fixed imports:

```python
"""The SDK build orchestrator: preprocess -> generate -> patch -> vendor -> scaffold -> smoke."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from ...productconfig import LoadedProduct

# <paste _ABOUT, build(), _load_hooks() here verbatim>
```

Then fix the imports INSIDE the moved `build()`/`_load_hooks()`:
- `from . import generate, preprocess, render, smoke` → `from . import generate, preprocess, render, smoke` (UNCHANGED — they are siblings of build.py under sdk/).
- `from . import patches` → UNCHANGED (sibling).
- `from . import scaffold` → `from ... import scaffold` (scaffold is top-level `phantasos.scaffold`).
- Ensure `_load_hooks` keeps whatever imports it uses (it returns a hook module; check its body for any `from .` imports and re-point non-sibling ones to `from ...X`).

- [ ] **Step 2: Expose build from the package**

`src/phantasos/generator/sdk/__init__.py` becomes:
```python
"""SDK generation: preprocess -> generate (OAG) -> patch -> vendor -> scaffold -> smoke."""

from .build import build

__all__ = ["build"]
```

- [ ] **Step 3: Clean up `phantasos/__init__.py`**

After cutting build/_load_hooks/_ABOUT, `phantasos/__init__.py` keeps ONLY: the module docstring, `from .config import (CursorPagination, Facade, NestedError, OAuthClientCredentials)`, and `__all__`. Remove `from .productconfig import LoadedProduct` (no longer used) and remove `"build"` from `__all__`. Result:
```python
"""phantasos — generate native, self-contained Python SDKs from OpenAPI specs."""

from __future__ import annotations

from .config import (
    CursorPagination,
    Facade,
    NestedError,
    OAuthClientCredentials,
)

__all__ = [
    "CursorPagination",
    "Facade",
    "NestedError",
    "OAuthClientCredentials",
]
```

- [ ] **Step 4: Update the host CLI + tests to the new build import**

- `src/phantasos/cli.py:46`: `from . import build` → `from .generator.sdk import build`. (Leave the rest of argparse cli.py for Task 3.)
- `tests/test_cli.py`: the two direct `phantasos.build(loaded …)` calls (≈lines 129, 181) — change `import phantasos` + `phantasos.build(loaded)` to `from phantasos.generator.sdk import build` + `build(loaded …)`.

- [ ] **Step 5: Verify green**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-repro uv run python -m pytest tests/test_cli.py tests/test_generate.py tests/test_framework.py -q`
Expected: PASS. Confirm `python -c "from phantasos.generator.sdk import build"` works and `python -c "import phantasos; print(phantasos.__all__)"` no longer lists build. `ruff check src/phantasos` (lint rules) clean; `mypy src/phantasos/generator/sdk src/phantasos/cli.py` Success.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor(phantasos): move build() orchestrator into generator/sdk/build.py"
```

---

## Task 3: Migrate the host CLI to Typer (`phantasos sdk build`)

**Files:**
- Rewrite: `src/phantasos/cli.py`
- Rewrite: `tests/test_cli.py`

- [ ] **Step 1: Write the failing Typer-CLI tests**

Rewrite `tests/test_cli.py` so the existing product-fixture helpers stay, but invocations use the new tree and a removed `build`. Keep the existing fixture-building bodies; change the invocations + add the removal test. The key assertions (replace the old `["build", …]` ones):

```python
def test_sdk_build_returns_zero_on_success(tmp_path, monkeypatch, capsys):
    # ... existing acme product fixture setup ...
    monkeypatch.setattr("phantasos.generator.sdk.generate.generate", fake_generate)
    monkeypatch.chdir(tmp_path)
    assert cli.main(["sdk", "build", "acme", "--no-smoke"]) == 0
    assert "built acme" in capsys.readouterr().out


def test_sdk_build_missing_product_returns_2(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert cli.main(["sdk", "build", "nope"]) == 2


def test_removed_top_level_build_errors(tmp_path, monkeypatch):
    # `phantasos build` no longer exists -> usage error, exit 2
    monkeypatch.chdir(tmp_path)
    assert cli.main(["build", "acme"]) == 2


def test_sdk_build_invalid_sdk_yml_returns_2(...):   # ["sdk","build","acme"] == 2
def test_sdk_build_requires_project_block(...):       # ["sdk","build","acme","--no-smoke"] == 2
def test_sdk_build_requires_readme_override(...):     # ["sdk","build","acme","--no-smoke"] == 2
```

(Reuse the existing fixture bodies verbatim; only the `cli.main([...])` argument lists change from `["build",…]` to `["sdk","build",…]`, plus the new removal test. The two `phantasos.build(loaded)` direct-call tests from Task 2 stay as-is.)

- [ ] **Step 2: Run — verify they fail**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-repro uv run python -m pytest tests/test_cli.py -q`
Expected: FAIL (argparse `cli.main(["sdk","build",…])` is an unknown command today).

- [ ] **Step 3: Rewrite `cli.py` as a Typer app**

Replace `src/phantasos/cli.py` entirely with:

```python
"""phantasos host CLI: `sdk build`, `cli discover`, `cli build`."""

from __future__ import annotations

from pathlib import Path

import typer

from .productconfig import load_product

app = typer.Typer(no_args_is_help=True, add_completion=False)
sdk_app = typer.Typer(no_args_is_help=True)
cli_app = typer.Typer(no_args_is_help=True)
app.add_typer(sdk_app, name="sdk", help="build SDKs from a product's sdk.yml")
app.add_typer(cli_app, name="cli", help="generate / inspect a CLI from a built SDK")


@sdk_app.command("build")
def sdk_build(
    product: str = typer.Argument(..., help="product name (products/<name>/sdk.yml) or a path to sdk.yml"),
    no_smoke: bool = typer.Option(
        False, "--no-smoke", help="skip the isolated import-check (offline/locked-down builds)"
    ),
) -> None:
    """build an SDK from a product's sdk.yml"""
    from pydantic import ValidationError

    from .generator.sdk import build

    try:
        loaded = load_product(product)
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(2)
    except ValidationError as exc:
        typer.echo(f"ERROR: invalid sdk.yml:\n{exc}", err=True)
        raise typer.Exit(2)
    try:
        result = build(loaded, run_smoke=not no_smoke)
    except ValueError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(2)
    s = result["smoke"]
    pkg = loaded.config.package
    if s.get("skipped"):
        typer.echo(f"built {pkg}: smoke skipped; operations: {s['operations']}")
        return
    typer.echo(
        f"built {pkg}: imported {s['imported']} modules, "
        f"{s['failed']} failures; operations: {s['operations']}"
    )
    for name, err in s["failures"][:10]:
        typer.echo(f"  FAIL {name} {err}")
    if s["failed"]:
        raise typer.Exit(1)


@cli_app.command("discover")
def cli_discover(
    product: str = typer.Argument(..., help="product name (products/<name>/) or path to sdk.yml"),
    write_stub: bool = typer.Option(
        False, "--write-stub", help="write products/<name>/cli.yml.stub next to sdk.yml"
    ),
) -> None:
    """print the classification table + cli.yml stub"""
    from .generator.cli.classify import build_cli_ir
    from .generator.cli.cliconfig import load_cli_config
    from .generator.cli.discover import render_stub, render_table
    from .generator.cli.introspect import introspect

    try:
        loaded = load_product(product)
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(2)
    cfg = load_cli_config(Path(loaded.base_dir) / "cli.yml")
    try:
        inv = introspect(loaded.config.package, Path(loaded.output_dir))
    except ImportError as exc:
        typer.echo(f"ERROR: SDK not importable — build it first ({exc})", err=True)
        raise typer.Exit(2)
    ir, unmapped = build_cli_ir(inv, cfg)
    typer.echo(render_table(ir, unmapped))
    if write_stub:
        stub_path = Path(loaded.base_dir) / "cli.yml.stub"
        stub_path.write_text(render_stub(ir, unmapped), encoding="utf-8")
        typer.echo(f"\nwrote {stub_path}", err=True)


@cli_app.command("build")
def cli_build(
    product: str = typer.Argument(..., help="product name (products/<name>/) or path to sdk.yml"),
) -> None:
    """emit the CLI project from a built SDK"""
    from . import scaffold
    from .generator.cli.classify import build_cli_ir
    from .generator.cli.cliconfig import load_cli_config
    from .generator.cli.introspect import introspect
    from .generator.cli.render_cli import cli_overrides_dir, render_cli
    from .generator.cli.scaffold_context import build_cli_scaffold_context

    try:
        loaded = load_product(product)
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(2)
    cfg = load_cli_config(Path(loaded.base_dir) / "cli.yml")
    try:
        inv = introspect(loaded.config.package, Path(loaded.output_dir))
    except ImportError as exc:
        typer.echo(f"ERROR: SDK not importable — build it first ({exc})", err=True)
        raise typer.Exit(2)
    ir, unmapped = build_cli_ir(inv, cfg)
    if loaded.config.project is None and cfg.project is None:
        typer.echo(
            "ERROR: cli build needs project metadata to scaffold the CLI — add a "
            "'project:' block to sdk.yml or cli.yml (see docs/ONBOARDING.md)",
            err=True,
        )
        raise typer.Exit(2)
    scaffold_ctx = build_cli_scaffold_context(loaded, ir, cfg)
    cli_pkg = f"{loaded.config.package}_cli"
    out_dir = Path(loaded.output_dir).parent / str(scaffold_ctx["distribution"])
    written = render_cli(
        ir, package=cli_pkg, out_dir=out_dir, distribution=str(scaffold_ctx["distribution"])
    )
    written = written + scaffold.render_scaffold(
        scaffold.builtin_dir(), cli_overrides_dir(), out_dir, scaffold_ctx
    )
    typer.echo(f"emitted {len(written)} files to {out_dir} ({len(ir.commands)} commands)")
    if unmapped:
        typer.echo(f"note: {len(unmapped)} unmapped ops omitted (map in cli.yml)", err=True)


def main(argv: list[str] | None = None) -> int:
    # NOTE (verified against typer 0.26.7 / click 8.4.1): with standalone_mode=False,
    # Typer SWALLOWS `typer.Exit(N)` internally and RETURNS N as the call's result, so we
    # must capture and return it. Typer also reimplements click's exceptions under
    # `typer._click` — `isinstance(exc, click.ClickException)` is FALSE for them, and
    # `typer.Exit` is a RuntimeError, NOT a click.exceptions.Exit. So we duck-type on the
    # `.exit_code`/`.show()` attributes instead of catching concrete click classes. This
    # gives: success->0, typer.Exit(2)->2, typer.Exit(1)->1, unknown command->2, missing
    # argument->2, no-args(help)->2 (matching the old argparse `required=True` behavior).
    try:
        result = app(args=argv, standalone_mode=False)
        return result if isinstance(result, int) else 0
    except SystemExit as exc:
        return int(exc.code or 0)
    except Exception as exc:
        code = getattr(exc, "exit_code", None)
        if code is not None:
            if hasattr(exc, "show"):
                exc.show()  # type: ignore[attr-defined]  # prints Usage/Error to stderr
            return int(code or 0)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
```

This exact wrapper was empirically validated against typer 0.26.7 / click 8.4.1 — all six
cases above return the asserted exit codes.

- [ ] **Step 4: Run — verify green, and verify exit-code translation**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-repro uv run python -m pytest tests/test_cli.py -q`
Expected: PASS with the wrapper above (already validated). Do NOT revert to catching `click.ClickException`/`click.exceptions.Exit` — typer 0.26.7 uses its OWN exception classes (`typer._click.*`) that are not click subclasses, and it returns `typer.Exit`'s code as the call result rather than raising it. If any assert fails, debug the wrapper's duck-typing — DO NOT weaken the test assertions.

- [ ] **Step 5: Broader regression + lint/types**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-repro uv run python -m pytest tests/ -q` → all pass. `ruff check src/phantasos/cli.py tests/test_cli.py` clean; `mypy src/phantasos/cli.py` Success.

- [ ] **Step 6: Commit**

```bash
git add src/phantasos/cli.py tests/test_cli.py
git commit -m "feat(phantasos): host CLI -> Typer; SDK build moves to 'phantasos sdk build'"
```

---

## Task 4: Update noxfile + docs to `phantasos sdk build`

**Files:**
- Modify: `noxfile.py`, `README.md`, `docs/ARCHITECTURE.md`, `docs/ONBOARDING.md`, `docs/index.md`, `docs/AUTHORING_A_SPEC.md`, `docs/TODO.md`

- [ ] **Step 1: noxfile**

`noxfile.py:113-114`: `session.run("phantasos", "build", "prisma-browser")` → `session.run("phantasos", "sdk", "build", "prisma-browser")`; same for `adem`.

- [ ] **Step 2: docs**

In each doc file, replace the literal command `phantasos build <x>` → `phantasos sdk build <x>` (leave `phantasos cli build` untouched). Grep to find every occurrence:
```bash
grep -rn "phantasos build" README.md docs/
```
Edit each hit (skip historical plan/spec files under `docs/superpowers/` — those are point-in-time records; only update user-facing docs: README, ARCHITECTURE, ONBOARDING, index, AUTHORING_A_SPEC, TODO).

- [ ] **Step 3: Verify docs build (if applicable) + no stale refs**

Run: `grep -rn "phantasos build " README.md docs/ARCHITECTURE.md docs/ONBOARDING.md docs/index.md docs/AUTHORING_A_SPEC.md docs/TODO.md` → expect ZERO hits (all now `phantasos sdk build`). If a docs build exists: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-repro uv run mkdocs build --strict` (or skip if mkdocs deps absent).

- [ ] **Step 4: Commit**

```bash
git add noxfile.py README.md docs/ARCHITECTURE.md docs/ONBOARDING.md docs/index.md docs/AUTHORING_A_SPEC.md docs/TODO.md
git commit -m "docs(phantasos): phantasos build -> phantasos sdk build"
```

---

## Task 5: Final gate + real end-to-end + review

- [ ] **Step 1: Full suite + lint + types**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-repro uv run python -m pytest tests/ -q` → all pass.
`UV_PROJECT_ENVIRONMENT=/tmp/phantasos-repro uv run ruff check src/phantasos tests` → All checks passed.
`UV_PROJECT_ENVIRONMENT=/tmp/phantasos-repro uv run mypy src/phantasos` → Success.

- [ ] **Step 2: Real end-to-end `phantasos sdk build`**

Run (needs the prisma-browser product + network for JRE/OAG on first run; if offline, use `--no-smoke` and/or `nox -s smoke`):
`UV_PROJECT_ENVIRONMENT=/tmp/phantasos-repro uv run phantasos sdk build prisma-browser`
Expected: `built prisma_browser: …` summary, exit 0. Confirm `phantasos build prisma-browser` now errors (exit 2, usage), and `phantasos cli build prisma-browser` still works.

- [ ] **Step 3: Confirm the package shape**

```bash
ls src/phantasos/generator/sdk/   # build.py generate.py preprocess.py patches.py render.py smoke.py provision.py components/ __init__.py
ls src/phantasos/                  # no generate.py/render.py/etc.; scaffold.py scaffold/ productconfig.py config.py cli.py __init__.py remain
python -c "from phantasos.generator.sdk import build; import phantasos; assert 'build' not in phantasos.__all__"
```

- [ ] **Step 4: Commit any final touch-ups, then whole-implementation review**

(Dispatch the final reviewer per subagent-driven-development; then finishing-a-development-branch.)

---

## Self-review checklist

- [ ] **Spec coverage:** each spec decision row maps to a task — cutover+Typer (T3), module move (T1), build move (T3 import + T2), config stays / components move (T1/T2), shared stays (untouched), naming/git mv (T1), noxfile+docs (T4), verification (T5).
- [ ] **No placeholders:** every move has exact `git mv`; every import edit names the file + old→new; the full Typer `cli.py` is provided.
- [ ] **Type/path consistency:** `phantasos.generator.sdk.{generate,preprocess,patches,render,smoke,provision}` used identically across tasks; `build` exposed at `phantasos.generator.sdk.build`; `scaffold`/`productconfig`/`config` never moved.
- [ ] **Green at every commit:** T1, T2, T3 each end on a passing suite; T4 is docs-only; T5 is the gate.
