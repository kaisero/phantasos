# phantasos-cli

Validated against 82e4e5d on 2026-06-14 · Purpose: the host CLI entry point — `phantasos sdk build`, `phantasos cli discover`, `phantasos cli build`.

## Purpose & responsibilities

`src/phantasos/cli.py` is the **host CLI** — phantasos's own command-line interface,
distinct from the CLIs it *generates*. It is a thin Typer dispatch layer: it resolves
the product spec, delegates to the generator subsystem, and maps exceptions to exit
codes. It owns no build logic itself.

## Command tree

```
phantasos
├── sdk
│   └── build <product>  [--no-smoke]
└── cli
    ├── discover <product>  [--write-stub]
    └── build <product>
```

All three commands accept either a product name (`acme` → resolved relative to
`products/acme/sdk.yml` from the CWD) or a path directly to an `sdk.yml` file
(via `load_product` in `productconfig.py`).

### `phantasos sdk build <product>` `[--no-smoke]`

Builds a Python SDK from the product's `sdk.yml`. Delegates to
`phantasos.generator.sdk.build.build(loaded, run_smoke=...)`. See `sdk-generator.md`
for the full pipeline. `--no-smoke` sets `run_smoke=False`, skipping the isolated
import-check (useful for offline / locked-down builds).

Exit codes: 0 on success, 1 if smoke failures were detected, 2 on bad product
name / unresolvable `sdk.yml` / `ValidationError` from pydantic / missing project
block / missing README override.

### `phantasos cli discover <product>` `[--write-stub]`

Introspects the built SDK, classifies its facade operations, and prints the
classification table to stdout. With `--write-stub`, also writes a `cli.yml.stub`
file next to `sdk.yml`. Delegates to the introspect→classify→discover path
(`generator/cli/introspect.py`, `classify.py`, `discover.py`). See `cli-generator.md`.

Requires the SDK to be importable (built first). Exit code 2 if the product is
missing or the SDK cannot be imported.

### `phantasos cli build <product>`

Emits a full Typer + Rich CLI project from a built SDK. Delegates to
introspect→classify→`render_cli`→`scaffold.render_scaffold`. See `cli-generator.md`
for the full pipeline.

Exit code 2 if the product is missing, the SDK is not importable, or neither
`sdk.yml` nor `cli.yml` supplies a `project:` block. Prints the file count and
command count on success; warns on unmapped ops (stderr).

## `main(argv) -> int` wrapper

```python
def main(argv: list[str] | None = None) -> int: ...
```

The Typer `app` is invoked with `standalone_mode=False`, which causes `typer.Exit(N)`
to be *returned* (not raised) as the int code. The wrapper duck-types on `.exit_code`
(not concrete exception classes) because typer 0.26.7 reimplements click exceptions
under `typer._click`, making them non-subclasses of `click.ClickException`. The
wrapper exists for two reasons:

1. **Entry point shape** — `pyproject.toml` declares `phantasos = "phantasos.cli:main"`,
   so `main` is the console-script target.
2. **Test interface** — tests call `cli.main(["sdk", "build", ...]) == N`; the int
   return lets test assertions stay simple.

Exit-code contract (validated empirically against typer 0.26.7 / click 8.4.1):
- success → 0
- `typer.Exit(1)` (smoke failures) → 1
- `typer.Exit(2)` (bad args / config errors) → 2
- unknown command (e.g. `["build", "x"]` — the old top-level `build` is removed) → 2
- missing required argument → 2
- no-args invocation → 2

## Console entry point

Declared in `pyproject.toml` under `[project.scripts]`:

```toml
phantasos = "phantasos.cli:main"
```

## Build / run pointers

- `phantasos --help` — top-level help.
- `phantasos sdk build <name> --no-smoke` — build without smoke check.
- `phantasos cli discover <name> --write-stub` — inspect + dump stub.
- `phantasos cli build <name>` — emit CLI project.
- Unit tests: `tests/test_cli.py` (drives `cli.main([...])` directly; generators are monkeypatched).

## Public API

<!-- GENERATED:api -->
- `cli.py`
  - `sdk_build(product, no_smoke)` — build an SDK from a product's sdk.yml
  - `cli_discover(product, write_stub)` — print the classification table + cli.yml stub
  - `cli_build(product)` — emit the CLI project from a built SDK
  - `main(argv)`
<!-- /GENERATED:api -->

## See also

- Design: `docs/specs/2026-06-12-sdk-generator-package-and-cli-restructure-design.md`
  (Typer migration rationale, exit-code contract, `main` wrapper design).
- SDK pipeline: `sdk-generator.md`.
- CLI generator pipeline: `cli-generator.md`.
- Product loader: `product-config.md` (`productconfig.py`).
- Entry point: `pyproject.toml` `[project.scripts]`.
