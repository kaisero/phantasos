# scaffold

Validated against 5ef7aee on 2026-06-14 · Purpose: how `phantasos` renders a complete project scaffold around a generated SDK or CLI.

## Purpose & responsibilities

`phantasos/scaffold.py` is the shared scaffold engine used by **both** `phantasos sdk build` and `phantasos cli build`. Given a set of Jinja templates (built-in) and optional per-product overrides, it renders a complete, phantasos-grade Python project — `pyproject.toml`, `noxfile.py`, GitHub workflows, community docs, `mkdocs.yml`, `.gitignore`, `.editorconfig`, gated component tests, etc. — into the output directory alongside the generated package.

The generated SDK (and CLI) is a pure build artifact. All customisation lives either in `src/phantasos/scaffold/` (shared across every product) or in `products/<name>/overrides/` (per-product). Nothing survives across regenerations unless it lives in one of those two places.

## How it works

`scaffold.py` is intentionally small — two public functions and one private helper:

1. **`builtin_dir()`** returns the `Path` to `src/phantasos/scaffold/`, the built-in template tree shipped inside the package (`_BUILTIN = Path(__file__).parent / "scaffold"`).

2. **`render_scaffold(builtin, overrides, out_dir, context)`** is the render entry point. It collects file→source mappings from `builtin` and from `overrides` (if provided) via the private `_collect()` helper (a recursive `rglob("*")`). Because `files.update(_collect(overrides))` runs after `_collect(builtin)`, **overrides win by relative-path key** — a file at the same relative path in `overrides/` silently replaces the built-in version. The Jinja `FileSystemLoader` receives `[overrides, builtin]` in that order so same-name template resolution follows the same precedence. For each collected file:
   - `.jinja` files are rendered via the Jinja `Environment` (with `StrictUndefined` — any missing context key raises an error at render time) and written with the `.jinja` suffix stripped.
   - Non-`.jinja` files are copied verbatim with `shutil.copyfile`.
   - **A template that renders to only-whitespace is silently skipped.** This is the gating mechanism: component-test templates (`test_auth.py.jinja`, etc.) check context booleans (`has_auth`, `has_pagination`, …) and emit nothing when the component is absent, so no empty test files land in the output.

### Same-path-wins

Any file placed at the same relative path inside `products/<name>/overrides/` replaces its built-in counterpart. `README.md.jinja` is the mandatory per-product override (there is no built-in `README.md.jinja`). Additional per-product tests go under `overrides/tests/` and are rendered alongside the built-in gated tests.

### Jinja context

The context dict is constructed externally and passed verbatim to `render_scaffold`. For SDK builds it comes from `loaded.context` (a `LoadedProduct`); for CLI builds `build_cli_scaffold_context()` in `generator/cli/scaffold_context.py` derives it from `loaded.context` and overrides CLI-specific keys (`package`, `distribution`, `dependencies`, `scripts`, `has_auth`, `has_pagination`, etc.). Because the environment uses `StrictUndefined`, every variable referenced in any template must be present in the context.

## Built-in template inventory (`src/phantasos/scaffold/`)

Characterised by category — not enumerated exhaustively:

| Category | Files |
|----------|-------|
| Project metadata | `pyproject.toml.jinja`, `CHANGELOG.md.jinja`, `CONTRIBUTING.md.jinja`, `SECURITY.md.jinja`, `LICENSE.jinja` |
| Dev tooling | `noxfile.py.jinja`, `.pre-commit-config.yaml`, `.editorconfig`, `.gitignore` |
| Docs | `mkdocs.yml.jinja` |
| GitHub Actions (6 workflows) | `.github/workflows/ci.yml.jinja`, `release.yml.jinja`, `audit.yml.jinja`, `secrets.yml.jinja`, `codeql.yml.jinja`, `docs.yml.jinja` |
| CLI env example | `.env.example.jinja` |
| Gated component tests | `tests/conftest.py.jinja`, `tests/test_auth.py.jinja`, `tests/test_errors.py.jinja`, `tests/test_facade.py.jinja`, `tests/test_pagination.py.jinja`, `tests/test_retry.py.jinja` |

`README.md.jinja` is **not** built-in — it is the mandatory per-product override under `products/<name>/overrides/`.

## Build / run pointers

- **`phantasos sdk build <name>`** — invokes `scaffold.render_scaffold(scaffold.builtin_dir(), overrides, project_dir, loaded.context)` in `generator/sdk/build.py` (step 4b of the pipeline; requires a `project:` block in `sdk.yml`).
- **`phantasos cli build <name>`** — invokes the same engine in `cli.py` with the CLI-adapted context from `scaffold_context.build_cli_scaffold_context()` and CLI-specific overrides returned by `render_cli.cli_overrides_dir()`.
- **Unit tests**: `tests/test_scaffold.py` (engine behaviour), `tests/test_cli_scaffold.py` (CLI scaffold path).
- **Freshness gate**: `uv run nox -s context -- --check` verifies generated blocks; `uv run nox -s gate` runs the full offline test suite.

## Public API

<!-- GENERATED:api -->
- `scaffold.py`
  - `builtin_dir()`
  - `render_scaffold(builtin, overrides, out_dir, context)` — Render built-in scaffold + overrides into out_dir. Overrides win by rel-path.
<!-- /GENERATED:api -->

## Gotchas / invariants

- **`StrictUndefined`** — any context variable referenced in a template but absent from the dict raises a Jinja `UndefinedError` at render time. The CLI path explicitly copies all SDK context keys before overriding so every variable is present.
- **Whitespace-only gate** — component test templates render to empty when the relevant boolean flag (`has_auth`, `has_pagination`, `has_errors`, `has_facade`, `has_retry`) is falsy. No stub files are emitted; the gate is purely render-time.
- **Non-Jinja files are copied verbatim** — `.pre-commit-config.yaml`, `.editorconfig`, and `.gitignore` have no `.jinja` suffix and are byte-copied; overrides can replace them with per-product versions.
- **`overrides/README.md.jinja` is mandatory for SDK builds** — `generator/sdk/build.py` checks for its existence and raises `ValueError` before calling `render_scaffold` if it is missing.
- **The scaffold is idempotent** — `render_scaffold` overwrites existing output files unconditionally; re-running a build is safe.

## See also

- `docs/authoring.md` — the `overrides/` section (per-product scaffold templates, same-path-wins; the generated SDK is a pure build artifact)
- `src/phantasos/generator/sdk/build.py` — SDK orchestrator that calls into this engine
- `src/phantasos/cli.py` — `phantasos cli build` path that calls into this engine
- `src/phantasos/generator/cli/scaffold_context.py` — builds the CLI-specific Jinja context
- `tests/test_scaffold.py`, `tests/test_cli_scaffold.py` — scaffold test suites
- `sdk-generator.md` — full SDK build pipeline (scaffold is step 4b)
