# SDK Generator Package + Host-CLI Restructure — Design

**Date:** 2026-06-12
**Status:** Approved design (grilled with user; all decisions below are user-confirmed)
**Scope:** phantasos host package (`src/phantasos/`) — a structural refactor, no SDK-build behavior change. Done before the first merge of the CLI-generator work to `main`.

## Motivation

SDK-generation logic is scattered across top-level `src/phantasos/*.py` modules, while the
CLI generator already lives cleanly in `src/phantasos/generator/cli/`. The host CLI exposes
SDK build at the bare `phantasos build`, asymmetric with `phantasos cli build`. This refactor
(1) relocates SDK-gen logic into a sibling `src/phantasos/generator/sdk/` package, and
(2) moves the command to `phantasos sdk build`, migrating the host CLI from argparse to Typer.

## Decisions (user-confirmed)

| # | Topic | Decision |
|---|---|---|
| 1 | Command cutover | **Hard cutover** — SDK build only at `phantasos sdk build`; the top-level `phantasos build` is removed. `phantasos cli discover`/`cli build` unchanged. |
| 2 | Modules → `generator/sdk/` | `generate.py`, `preprocess.py`, `patches.py`, `render.py`, `smoke.py`, `provision.py`, and `components/`. |
| 3 | `build()` orchestrator | Moves to `generator/sdk/build.py` (with `_ABOUT` + `_load_hooks`); `generator/sdk/__init__.py` does `from .build import build`. **No** `phantasos.__init__` re-export — host `cli.py` + tests import `from phantasos.generator.sdk import build`. |
| 4 | `config.py` / `components/` | `config.py` STAYS top-level (imported by the shared `productconfig.py`). `components/` MOVES into `generator/sdk/`. |
| 5 | Shared infra | `scaffold.py`, `scaffold/`, `productconfig.py`, `config.py` stay at top level (`src/phantasos/`). |
| 6 | Host CLI | Migrate `cli.py` to a **Typer** app with `sdk` + `cli` sub-apps. Preserve every current behavior, message, and exit code (0/1/2). `main(argv) -> int` kept as a wrapper so the entry point + tests are unchanged in shape. |
| 7 | Naming | Keep module names; relocate with `git mv`. Imports change `phantasos.X` → `phantasos.generator.sdk.X`. |
| 8 | Verification | Full existing suite green after moves + import updates; new Typer-CLI dispatch tests; one real end-to-end `phantasos sdk build` (or `nox -s smoke`). |

## Target tree

```
src/phantasos/
  __init__.py            EDIT   keep docstring + config re-exports; remove build()/_load_hooks/_ABOUT + "build" from __all__
  cli.py                 REWRITE  Typer app: sdk build / cli discover / cli build; main(argv)->int wrapper
  scaffold.py  scaffold/ KEEP   shared scaffold engine (used by SDK build AND cli build)
  productconfig.py       KEEP   shared sdk.yml loader
  config.py              KEEP   shared component-config models (productconfig imports it)
  render.py …            MOVED ↓
  generator/
    cli/                 (unchanged)
    sdk/                 NEW package
      __init__.py        NEW    `from .build import build`  +  __all__ = ["build"]
      build.py           NEW    build() + _load_hooks() + _ABOUT (moved from phantasos/__init__.py)
      generate.py        git mv (from src/phantasos/generate.py)
      preprocess.py      git mv
      patches.py         git mv
      render.py          git mv
      smoke.py           git mv
      provision.py       git mv
      components/        git mv (dir)
```

## Import rewrites (the blast radius)

**Internal to `generator/sdk/` (relative imports among siblings):**
- `generate.py`: `from . import provision` → unchanged (now siblings under sdk/).
- `smoke.py`: `from . import provision` → unchanged.
- `render.py`: `from .productconfig import LoadedProduct` → `from ...productconfig import LoadedProduct` (productconfig stays top-level).
- `build.py`: `from . import generate, preprocess, render, smoke` / `from . import patches` → unchanged (siblings); `from . import scaffold` → `from ... import scaffold`; `from ...productconfig import LoadedProduct` for the type hint.

**Production importers outside the move:**
- `phantasos/__init__.py`: drop `from .productconfig import LoadedProduct` (only build used it) and the `build` entry from `__all__`; KEEP `from .config import (...)` re-exports.
- `cli.py`: import `from .generator.sdk import build` (was `from . import build`); `from . import scaffold` stays.

**Test importers (update string paths + `from` imports):**
| File | Change |
|---|---|
| `tests/test_generate.py` | `from phantasos import generate` → `from phantasos.generator.sdk import generate`; `phantasos.provision.*` → `phantasos.generator.sdk.provision.*`; `phantasos.generate.subprocess.run` → `phantasos.generator.sdk.generate.subprocess.run` |
| `tests/test_render.py` | `from phantasos import render` → `from phantasos.generator.sdk import render` (the `from phantasos.productconfig import …` line STAYS) |
| `tests/test_smoke.py` | `from phantasos import smoke` / `from phantasos.smoke import SmokeError` → `phantasos.generator.sdk.smoke` |
| `tests/test_provision.py` | `from phantasos import provision` / `from phantasos.provision import ProvisionError` → `phantasos.generator.sdk.provision` |
| `tests/test_framework.py` | `from phantasos import patches, preprocess, render` → `from phantasos.generator.sdk import patches, preprocess, render` |
| `tests/test_cli.py` | REWRITE for Typer + `sdk build`: monkeypatch targets `phantasos.generate.*`→`phantasos.generator.sdk.generate.*` etc.; `phantasos.scaffold.render_scaffold` STAYS; `phantasos.build`→`phantasos.generator.sdk.build`; `cli.main(["build",…])`→`cli.main(["sdk","build",…])` + a new test that `cli.main(["build","x"]) == 2` (command removed) |
| `tests/test_scaffold.py` | UNCHANGED (`from phantasos import scaffold` stays) |

**Docs / nox:**
- `noxfile.py:113-114`: `session.run("phantasos","build", …)` → `("phantasos","sdk","build", …)`.
- Docs literal `phantasos build <x>` → `phantasos sdk build <x>` in: `README.md`, `docs/ARCHITECTURE.md`, `docs/ONBOARDING.md`, `docs/index.md`, `docs/AUTHORING_A_SPEC.md`, `docs/TODO.md`. (`phantasos cli build` unchanged.)

## Host CLI (Typer) design

`cli.py` becomes a Typer app; command bodies are moved near-verbatim from the current
argparse dispatch, with error `return N` → `raise typer.Exit(N)`:

```python
app = typer.Typer(no_args_is_help=True, add_completion=False)
sdk_app = typer.Typer(no_args_is_help=True)
cli_app = typer.Typer(no_args_is_help=True)
app.add_typer(sdk_app, name="sdk", help="build SDKs from a product's sdk.yml")
app.add_typer(cli_app, name="cli", help="generate / inspect a CLI from a built SDK")

@sdk_app.command("build")
def sdk_build(product: str,
              no_smoke: bool = typer.Option(False, "--no-smoke",
                  help="skip the isolated import-check (offline/locked-down builds)")):
    # body moved from cli.py:43-72; build imported from phantasos.generator.sdk;
    # error returns become `raise typer.Exit(2)`, smoke-failure becomes `raise typer.Exit(1)`.

@cli_app.command("discover")
def cli_discover(product: str,
                 write_stub: bool = typer.Option(False, "--write-stub", help="…")):
    # body moved from cli.py:74-101; errors → raise typer.Exit(2)

@cli_app.command("build")
def cli_build(product: str):
    # body moved from cli.py:103-156; errors → raise typer.Exit(2)
```

**`main(argv) -> int` wrapper** (keeps the entry point `phantasos.cli:main` and the
`cli.main([...]) == N` test interface):

```python
def main(argv: list[str] | None = None) -> int:
    # typer 0.26.7: standalone_mode=False RETURNS typer.Exit(N)'s code as the call result
    # (not raised); and typer reimplements click's exceptions under typer._click, so they
    # are NOT click.ClickException subclasses and typer.Exit is a RuntimeError. Duck-type
    # on .exit_code/.show() rather than catching concrete click classes.
    try:
        result = app(args=argv, standalone_mode=False)
        return result if isinstance(result, int) else 0
    except SystemExit as exc:
        return int(exc.code or 0)
    except Exception as exc:
        code = getattr(exc, "exit_code", None)
        if code is not None:
            if hasattr(exc, "show"):
                exc.show()   # prints Usage/Error to stderr
            return int(code or 0)
        raise
```

(Validated empirically against typer 0.26.7 / click 8.4.1: success→0, typer.Exit(2)→2,
typer.Exit(1)→1, unknown command `["build","x"]`→2, missing argument→2, no-args→2.)

## Behavior preservation (must-hold invariants)

- `phantasos sdk build <product>` produces byte-identical output to the old `phantasos build <product>` (same messages, `_about.py`, scaffold, smoke summary, exit codes).
- `phantasos cli discover` / `phantasos cli build` behavior unchanged.
- The shared `scaffold` engine remains importable by BOTH `generator.sdk.build` and the host's `cli build` path.
- `from phantasos import OAuthClientCredentials` (and the other config re-exports) still work.

## Testing

- The full existing suite (308) must pass after the moves + import updates — that is the
  behavior-preservation proof for the relocated, otherwise-unchanged modules.
- `tests/test_cli.py` rewritten to drive the Typer app via `cli.main([...])` (int return):
  `sdk build` success (exit 0), missing product (2), invalid sdk.yml (2), no project block (2),
  no README override (2), smoke-failure (1); `phantasos build` removed → `cli.main(["build","x"]) == 2`;
  `cli discover`/`cli build` smoke (exit 0 with stubbed introspect).
- One real end-to-end: `phantasos sdk build prisma-browser` (or `nox -s smoke`) succeeds.

## Out of scope

- Renaming any moved module (e.g. `render.py`→`vendor.py`) — separable.
- Moving shared infra under `generator/common/` — top-level is the chosen home.
- Any change to SDK-build pipeline behavior, or to `generator/cli/`.
