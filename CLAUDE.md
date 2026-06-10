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
