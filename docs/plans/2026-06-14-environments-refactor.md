# Environments refactor — dedicated file + command-surface changes

> Lightweight spec + plan. Builds on the named-environments feature (PR #19, branch `feature/cli-auth-environments`). Refined via grill-me on 2026-06-14.

## Spec

### Goal
Decouple named environments from `config.yml` into a dedicated `environments.yml`, and tidy the `environment` command surface: drop `current`, rename `list`→`show`, add `delete`.

### File layout (per generated CLI, under `~/.{distribution}/`)
- `config.yml` — **unchanged**: `configuration:` (pager/output/history). No longer holds any environment keys.
- `environments.yml` — **new**, self-contained, holds both top-level keys:
  ```yaml
  default_environment: prod        # null/absent when none
  environments:
    prod: { client_id: ..., client_secret: ${PROD_SECRET}, scope: ..., base_url: ... }
    staging: { ... }
  ```
  Written `0o600` (holds secrets), parent dir `0o700`, via the existing atomic temp-file+rename. Created on first `environment create`; absent otherwise.

### Command surface (top-level `environment` group, "CLI" `--help` panel)
- `create <name>` — **unchanged** behaviour (per-field options from the descriptor; secret fields prompted hidden; values stored verbatim incl. `${VAR}`; first env auto-activates; existing name → exit 2 unless `--force`). Now writes `environments.yml`.
- `activate <name>` — **unchanged**; sets `default_environment` in `environments.yml`; undefined name → exit 2.
- `show` — **renamed from `list`**: lists environment names, marking the active/default one (`prod (active)`); never prints field values/secrets. Absorbs the removed `current` via the marker.
- `delete <name>` — **new**:
  - No confirmation prompt (the explicit name + the default-guard are sufficient).
  - Name not found → `_diag.fail(..., code=2)`.
  - If `<name>` is the active/default env → `_diag.fail(code=2)` with: *"'X' is the active environment; run 'environment activate <other>' first, or pass --force to delete it (auth then falls back to environment variables)."*
  - `--force` → delete even if default; if it **was** the default, unset `default_environment` (remove the key) so the next run falls back to ambient env-var auth.
  - Deleting a non-default env never needs `--force`. Deleting the last env leaves `environments: {}` (file kept, not removed).
- `current` — **removed**.

### Runtime / resolution (unchanged behaviour, new source)
- Selection precedence (`-e` flag > `{PREFIX}_ENVIRONMENT` > `default_environment`), env-vars-win per-field resolution, and the selected-but-undefined-environment guard all stay — they just read from `environments.yml` now. The guard's hint message becomes `run 'environment show'`.
- `config show` stays config-only (environments were never in `effective_dict`; even more cleanly separate now).

### Out of scope / non-goals
- No migration/back-compat reading of the old in-`config.yml` location — the whole feature is unreleased.
- No per-env detail view / secret redaction (`show` is names-only).

---

## Plan

Branch `feature/cli-auth-environments`. After each task: `ruff check . && ruff format --check . && mypy && pytest -q`, and `nox -s cli-smoke` after Task 2/3.

### Task 1 — Point env reads at `environments.yml` (`config.py.jinja`)
**Files:** `templates/_generated/config.py.jinja`; `tests/test_cli_emitted.py`.
- Add `environments_path() -> Path` → `Path.home() / f".{_DISTRIBUTION}" / "environments.yml"`.
- Add `_read_env_file() -> dict[str, Any]` (safe-load `environments_path()`, `{}` if missing/unreadable/not-a-mapping) and repoint `_raw_environments()` → `_read_env_file().get("environments") or {}` and `default_environment()` → `_read_env_file().get("default_environment")`. `resolve_environment()` is unchanged (it already builds on `_raw_environments()`).
- **Remove** `_raw_config()` (was only used for env reads) and the two `merged.pop("environments"/"default_environment", None)` lines in `load_config()` (config.yml no longer carries env keys).
- Tests: env resolution + `default_environment()` read from `environments.yml`; a config.yml without env keys is unaffected; `${VAR}` still resolves.

### Task 2 — Writer + command-surface changes (`environment_commands.py.jinja`)
**Files:** `templates/_generated/environment_commands.py.jinja`; `tests/test_cli_emitted.py`.
- Replace `_write_raw_config` with `_write_environments_file(data: dict)` writing `environments_path()` (atomic, `0o600`, dir `0o700`). The env file is env-only, so no need to preserve unrelated top-level keys — read the env-file dict, mutate `environments`/`default_environment`, write back.
- `create` / `activate`: read+write via the env-file helpers (behaviour unchanged).
- **Remove `current`**; **rename `list`→`show`** (same names-only + active-marker body).
- **Add `delete`**:
  ```python
  @environment_app.command("delete")
  def delete(name: str, force: bool = typer.Option(False, "--force", ...)) -> None:
      data = _config._read_env_file()
      envs = data.get("environments") or {}
      if name not in envs:
          _diag.fail(f"no such environment: '{name}'", code=2)
      if data.get("default_environment") == name and not force:
          _diag.fail(
              f"'{name}' is the active environment; run "
              f"'environment activate <other>' first, or pass --force to delete "
              f"it (auth then falls back to environment variables)",
              code=2,
          )
      del envs[name]
      data["environments"] = envs
      if data.get("default_environment") == name:   # only reachable with --force
          data.pop("default_environment", None)
      _write_environments_file(data)
      _diag.info(f"removed environment '{name}'")
  ```
- Tests (via `emitted_auth` + `CliRunner`): `show` lists + marks active (no values); `delete` non-default removes it; `delete` of default → exit 2 + message; `delete --force` of default removes it and unsets `default_environment`; `delete` unknown → exit 2; `current` no longer exists (help has no `current`).

### Task 3 — Runtime hint, packaged default, docs, smoke (`runtime.py.jinja`, `default_config.yml.jinja`, CHANGELOG, smoke)
**Files:** `templates/_generated/runtime.py.jinja`, `templates/_generated/default_config.yml.jinja`, `CHANGELOG.md`, `tests/cli_isolated_smoke.py`, docs mentioning the commands.
- `runtime.py.jinja`: unknown-environment guard hint `run 'environment list'` → `run 'environment show'` (resolution already flows through the repointed `config.py` helpers).
- `default_config.yml.jinja`: remove the commented `environments:`/`default_environment:` example block (they live in `environments.yml` now); optionally add a one-line pointer comment.
- `CHANGELOG.md` (`[Unreleased]`): note environments live in `environments.yml`; commands are `create/activate/show/delete`.
- `tests/cli_isolated_smoke.py`: `environment list` → `environment show`; add a `delete` step; the config-content assertion now reads `~/.{distribution}/environments.yml` (not `config.yml`); keep the `0o600` check on `environments.yml`.

### Notes
- `app.py.jinja` needs no change — the top-level `environment` group registration is unchanged; only its leaf commands change (defined in `environment_commands.py.jinja`).
- The static import-scan test and `cli-smoke` gate continue to apply unchanged.
- The 3 tasks are a single cohesive refactor (not independently shippable — after Task 1 the writer/commands still reference removed symbols). Implement together; gate on `pytest -q` + `nox -s cli-smoke` at the end.

### Review corrections (plan review 2026-06-14 — must-fix punch list)
- **A (tests, must-fix):** the shared test helpers write env state into `config.yml` — `_write_user_config()` (`tests/test_cli_emitted.py` ~L93) and `_read_config_yml()` (~L2758). Add parallel `_write_user_env_file(home, body)` → `environments.yml` and `_read_environments_yml(home)`, and switch EVERY env test that writes/reads env state to them. Affected env tests (write env YAML via `_write_user_config` or assert via `_read_config_yml`): `test_env_resolve_environment_expands_refs`, `test_env_no_spurious_unknown_key_warning` (G: make it write to the env file so it actually exercises the path), `test_env_vars_override_active_environment`, `test_env_empty_exported_var_still_wins`, `test_env_selection_precedence`, `test_env_option_in_help_and_threads_selection`, `test_env_unknown_selected_environment_errors`, and the create/activate/show/delete write-path tests. (`_write_user_config` stays for config-only tests.)
- **B (must-fix):** `environment_commands.py.jinja` calls `_config._raw_config()` in `_create_environment` (~L63) and `activate` (~L125) — switch BOTH to `_config._read_env_file()` (since `_raw_config` is removed).
- **C (must-fix):** `_create_environment` success message (~L90) prints `_config.config_path()` — change to `_config.environments_path()`.
- **D (must-fix):** `test_env_group_emitted_and_visible_in_help` (~L3081) asserts the leaf set `("create","activate","list","current")` — change to `("create","activate","show","delete")`.
- **E (must-fix, smoke):** `tests/cli_isolated_smoke.py` — the config-content path (`cfg = .../config.yml` ~L124 and the inline `verify` script ~L128–135) must read `environments.yml`; `0o600` check (~L136) moves to `environments.yml`; `environment list`→`show`; add a `delete` step.
- **Confirmed safe (no action):** removing the commented env block from `default_config.yml.jinja` does NOT break `test_config_packaged_defaults_match_models` (env keys were outside the `configuration:` tree). The runtime guard/resolution flows through the repointed `config.py` helpers — only the hint text changes.
