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
  (the Stop hook sets a per-checkout default automatically). For venv-backed
  nox sessions (e.g. `live`, `smoke`) also set `NOX_ENVDIR=/tmp/phantasos-nox`
  to relocate the session venvs off sshfs.

## Adding a CLI configuration option (generated CLIs)

Every user-facing setting of a GENERATED CLI follows one layered flow — packaged
defaults <- `~/.{distribution}/config.yml` <- `.env` / shell env <- per-invocation
flags (where applicable). To add an option:

1. **Model field** — `src/phantasos/generator/cli/templates/_generated/config.py.jinja`:
   add the field to the right section model (frozen pydantic; a NEW section gets its
   own `XxxConfig` model wired into `CliConfiguration` via `Field(default_factory=…)`).
2. **Default + docs** — `default_config.yml.jinja`: add the commented entry. The YAML
   defaults MUST mirror the model defaults — the defaults-sync test
   (`test_config_packaged_defaults_match_models`) enforces it.
3. **Env var** — add an `_ENV_MAP` row named `{PREFIX}_{SECTION}_{KEY}` (the
   `configuration` wrapper is skipped). Booleans also join `_BOOL_PATHS`; ints ride
   pydantic lax coercion. `.env` works automatically: `load_config()` loads it first.
4. **`effective_dict()`** — extend it (drives `config show`).
5. **Tests** — behavioral, through the emitted package (`tests/test_cli_emitted.py`
   `emitted` fixture). Config is cached at command-module IMPORT: set HOME/env
   BEFORE `importlib.import_module`, and call `load_config.cache_clear()` after
   mutating the environment mid-test.
6. **Consumers** read via `_config.get().<section>.<key>` — never re-read files or
   env directly.
