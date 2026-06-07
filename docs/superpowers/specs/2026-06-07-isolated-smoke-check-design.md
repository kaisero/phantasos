# Design: Isolated Smoke Check (decouple the generator from its artifact's deps)

**Date:** 2026-06-07
**Status:** Draft for review
**Branch:** `isolated-smoke-venv`

## Problem analysis

`phantasos build` ends with a **smoke** step (`__init__.py` step 6 → `smoke.smoke()`) that
**imports the generated SDK in phantasos's own process** to verify it. The generated code
does `from pydantic import …`, so phantasos's environment is forced to contain the
*artifact's* runtime dependencies.

### Does a PyPI user hit this? Yes.

`pip install phantasos` installs only the base deps (`ruamel.yaml`, `jinja2`). Extras are
opt-in, so a user who runs `pip install phantasos` then `phantasos build <spec>` gets the
exact `ModuleNotFoundError: No module named 'pydantic'` at the smoke step. They would need
`pip install "phantasos[generated]"`. The local/editable install is not special — the same
wall exists from PyPI.

### Why this is a design smell

1. **The generator carries its output's dependencies.** phantasos never imports pydantic/
   urllib3 itself; it only needs them to import-check its output in-process. A generator
   should be dependency-light.
2. **The `generated` extra is a hardcoded guess** (`pydantic + urllib3 + python-dateutil +
   typing_extensions`). That set only matches the `library=urllib3`/pydantic flavor. A
   different OpenAPI Generator `library` or config produces different runtime deps, so the
   extra can be wrong — a hard-coded-config anti-pattern.
3. **The artifact already declares its own deps** — every generated SDK ships `setup.py`
   (`install_requires=REQUIRES`) and `requirements.txt`. The correct dependency source is
   in the artifact; the smoke step ignores it in favor of phantasos's environment.

So the smoke step conflates "deps the generator needs" with "deps the artifact needs."

## Chosen approach: Option A — isolated import-check in a throwaway venv

Run the **import-walk** part of the smoke check in a fresh, isolated virtual environment
that has the *SDK's own* declared dependencies installed. phantasos then needs **none** of
the artifact's runtime deps, and the check is correct for any generator config.

### Key decomposition (smaller blast radius)

`smoke()` does two independent things; only one needs the deps:

| Part | Needs SDK deps? | Where it runs |
|---|---|---|
| **Import-walk** — `import` every generated module, count ok/failures | **yes** | isolated subprocess (NEW) |
| **Operations count** — regex over `api/*_api.py` text | no (reads files) | in-process (unchanged) |

So we move only the import-walk into isolation and keep the ops-count in-process.

### Mechanism

1. Create a throwaway venv (stdlib `venv`, `with_pip=True`) under a context-managed temp
   dir (or a cached, requirements-hashed dir — see Open Decisions).
2. `pip install <project_dir>` into it — the generated SDK's `setup.py` pulls the SDK **and**
   its declared `install_requires`. (Reads the artifact's real deps; no hardcoded list.)
3. Run the import-walk as a **subprocess** using the venv's interpreter (absolute path),
   emitting a small JSON document (`{"imported", "failed", "failures"}`) on stdout.
4. Parse the JSON back; combine with the in-process ops-count; return the existing result
   shape so `cli.py` and `build()` are unchanged downstream.
5. Tear the venv down (context manager) unless caching.

### What changes

- `smoke.py`: split into `_count_operations(project_dir, package)` (in-process) and an
  isolated `_import_walk(project_dir, package) -> dict` that provisions the venv + subprocess.
- The `generated` optional-dependency extra and the `smoke` dependency group's SDK-runtime
  entries become unnecessary → drop (or deprecate). phantasos's base deps stay `ruamel.yaml`
  + `jinja2`.
- Docs: remove the "`pip install .[generated]`" requirement; the smoke check is now
  self-contained.

## python-pro / python-anti-patterns validation

**Removes an existing anti-pattern.** The hard-coded `generated` dep set (anti-patterns:
"Hard-Coded Configuration") is replaced by reading the artifact's declared deps. The fix is
a net reduction in coupling, not new coupling.

**python-pro alignment (apply during implementation):**
- *Stdlib before external deps:* baseline uses the stdlib `venv` module + the venv's `pip`;
  uv is an optional fast-path, never a hard requirement (a PyPI/pip user may not have uv).
- *Context managers for resources:* the temp venv lives in a `tempfile.TemporaryDirectory`
  (or an explicit try/finally for a cached dir) so it is always cleaned up.
- *Custom exceptions, specific catches:* a `SmokeError(RuntimeError)` for provisioning/parse
  failures; catch `subprocess.CalledProcessError`/`json.JSONDecodeError`, never bare `except`.
- *Capture partial failures:* the subprocess reports per-module failures (mirrors today's
  behavior) rather than aborting on the first import error.
- *Types + structured results:* keep the typed return; consider a small dataclass instead of
  the loose `dict[str, Any]` (optional, to avoid churn in `cli.py`).
- *Performance:* venv create + cold `pip install` adds seconds per build; mitigate with a
  cache keyed by a hash of the SDK's `requirements.txt`, and/or the uv fast-path.

**Test design (anti-patterns: avoid over-mocking, test error paths):**
- Pure helpers (env sanitization, command construction, JSON parsing) → fast unit tests.
- One real integration test that builds a throwaway venv around a *trivial* generated-shaped
  package (a tiny `pkg/__init__.py` + a module importing a small dep) and asserts the walk
  result — exercises the real venv/subprocess path without mocking it away.
- Error paths: missing `setup.py`/`requirements.txt`, a module that fails to import (must be
  counted as a failure, not crash), and a non-zero subprocess exit.

## "A temp venv inside an existing venv" — do we expect issues?

**No fundamental problem.** venvs are not recursively "nested" — the throwaway venv is an
independent directory with its own interpreter and `site-packages`. Creating one while
another is active is normal. But spawning it from inside an active venv has **specific
gotchas**, and getting them wrong silently defeats the isolation:

1. **Environment-variable leakage (the main risk).** The parent process likely has
   `VIRTUAL_ENV`, and may have `PYTHONPATH`, `PYTHONHOME`, `PYTHONSTARTUP`, `PIP_*`, `UV_*`.
   If the subprocess inherits these:
   - `PYTHONPATH` can inject the *parent's* importable paths (e.g. our `PYTHONPATH=src`),
     shadowing the temp venv and hiding a genuinely-missing dep.
   - `PYTHONHOME` can break the child interpreter outright.
   - `VIRTUAL_ENV` can make `pip`/`uv` target the *parent* venv instead of the temp one.
   → **Mitigation:** run the subprocess with a sanitized env — strip `VIRTUAL_ENV`,
     `PYTHONHOME`, `PYTHONPATH`, `PYTHONSTARTUP` (and don't set them); invoke the venv's
     interpreter by absolute path. This is the single most important detail.
2. **Use the venv's own interpreter/pip by absolute path** (`<venv>/bin/python`,
   `Scripts\python.exe` on Windows) — never rely on `PATH` resolution, which the parent venv
   has hijacked.
3. **Full isolation, not `--system-site-packages`.** We *want* the check to see only the
   SDK's declared deps so a missing dep is actually caught. Default venv isolation is correct.
4. **Cleanup on failure:** context-manage the temp dir so a failed install/import still
   removes it (resource anti-pattern otherwise).
5. **Windows layout:** scripts live in `Scripts\` not `bin/`; derive the path from the
   `venv` builder context rather than hardcoding `bin/`.
6. **No recursion:** the subprocess only imports the SDK package; it never re-invokes
   `phantasos build`, so there is no venv-spawns-build loop.

Net: safe, provided the subprocess env is sanitized and the venv interpreter is addressed by
absolute path.

## Open decisions (please confirm before the plan)

1. **Provisioner: stdlib `venv`+`pip` baseline, with an optional uv fast-path? Or uv-only?**
   Recommend **stdlib baseline + uv fast-path if available** (don't assume pip users have uv).
2. **Cache the smoke venv** (keyed by a hash of the SDK's `requirements.txt`) to amortize the
   pip install across builds, or create-and-destroy each build? Recommend **cached** under
   `~/.cache/phantasos/smoke-envs/<hash>`.
3. **Offline / opt-out:** add a `--no-smoke` flag (and/or `PHANTASOS_SKIP_SMOKE`) so a build
   in an air-gapped/locked-down env can skip the isolated check? Recommend **yes** — the
   isolated check needs network to install deps the first time.
4. **Drop the `generated` extra entirely, or keep it deprecated** as an in-process fast-path?
   Recommend **drop** (it's the coupling we're removing); keep base deps unchanged.

## Out of scope

- Changing what OpenAPI Generator emits, or the operations-count logic.
- Replacing the generator (separate concern).
