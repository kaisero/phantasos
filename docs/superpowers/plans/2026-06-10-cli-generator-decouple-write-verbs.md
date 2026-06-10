# CLI Generator — Decouple `set` into `create`/`update`/`delete` Verbs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the aggregated `set <object>` command (which dispatched create/patch/update via a `--id`/`--replace` heuristic) with **single-binding** verbs: `create` (POST), `update` (PATCH, falling back to PUT when no PATCH exists), and `delete` (renamed from `del`). Single-binding commands make Typer integration clean: required model fields become real `[required]` options, scalars get real types, and enum fields surface their choices in `--help` + shell completion (permissively).

**Architecture:** The classifier tags each method `(verb, sub_verb)`. Today create/patch/update map to `verb="set"` and aggregate into one multi-binding `Command`. We remap so each write maps to its OWN verb; since `_command_key` includes the verb, every write `Command` has exactly ONE binding. The `update` verb is **PATCH-preferred**: `patch_*` → `update`; a `update_*` (PUT) method only becomes the `update` command for an object that has NO PATCH (a fallback pass), otherwise the PUT is dropped (deferred). This removes the runtime `--replace` flag and write-dispatch heuristic. `show` keeps its benign get+list aggregation (`--id` selects get). `request`/`load`/`backup` unchanged.

**Verb scheme (locked):**
| Verb | HTTP | Notes |
|---|---|---|
| `create <obj> [variant]` | POST | required fields enforced; no `--id` |
| `update <obj> --id [variant]` | PATCH, else PUT fallback | `--id` required. PATCH body = all-optional; PUT-fallback body = required like create |
| `delete <obj> --id` | DELETE | |
| `show <obj>` | GET/list | `--id` selects get |
| `request <obj> <action>` | — | unchanged |

No `set`, no `patch` verb, no `put`/standalone-PUT verb, no `--replace`. **Deferred to roadmap:** full-replace PUT semantics where a PATCH already exists (future `replace` verb); `bulk_create`/`bulk_delete` (future `load`/`backup`).

**Permissive enums (locked):** enum body/query fields stay `str` options with a shell completer + choices listed in `--help`. NOT validating Typer `Enum`s — the SDK uses `LenientStrEnum` (unknowns pass through), so the CLI must not be stricter than the SDK. Matches the spec's permissive-enum mandate.

**Tech Stack:** Python 3.11–3.14, Pydantic v2, Typer/Click, Jinja2, pytest. Runner: `uv run`.

**Spec:** `docs/superpowers/specs/2026-06-09-cli-generator-design.md` (rewrites grammar + aggregated-command sections; permissive-enum stance unchanged). **Builds on:** branch `cli-generator`.

---

## Conventions (every task)
- Env: `export UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv` then `uv run …`.
- Repo `/home/ubuntu/git/phantasos`, branch `cli-generator`. **Do NOT `git checkout`/`switch`/`reset`.** Commit on the branch; `git show <sha>:<path>` for history.
- TDD; imports at top of test files; `ruff check src/phantasos tests/` + `mypy src/phantasos/generator` before each commit.
- Fake SDK fixture `tests/fixtures/fakesdk/`; real SDK `/home/ubuntu/git/prisma-browser-sdk`.

## Centralized option rendering (spine of T3–T5)
All flag-emission tasks funnel through ONE helper. In `render_cli.py`, `_flag_view(f)` computes: `render_type` (full annotation incl. `Optional[...]` iff not required; `--id`/`json`/`enum`→`str`; scalar→mapped Python type), `required` (bool), `help_text` (base help + `  [values: a, b, c]` for enums), `completion`/`completer_name` (enum choices). `commands.py.jinja` emits ONE line per flag:
```jinja
    {{ f.py_name }}: {{ f.render_type }} = typer.Option({{ '...' if f.required else 'None' }}, {{ f.name|tojson }}{% if f.help_text %}, help={{ f.help_text|tojson }}{% endif %}{% if f.completion %}, autocompletion={{ f.completer_name }}{% endif %}),
```
T3 builds the contract (scalar/enum → `str`); T4 fills scalar types; T5 fills enum help/completion.

---

## Task 1: Decouple verbs + `del`→`delete` + PUT-fallback for `update` (core, atomic)

**Files:** `ir.py`, `classify.py`, `render_cli.py`, `runtime.py.jinja`, `app.py.jinja`, `commands.py.jinja`, `tests/fixtures/fakesdk/fakesdk/{api,models}.py`, existing tests.

- [ ] **Step 1: `Verb` in `ir.py`**
```python
Verb = Literal["create", "update", "delete", "show", "request", "load", "backup"]
```
(Remove `"set"`, `"del"`. `SubVerb` unchanged — bindings still carry `patch`/`update`/etc.)

- [ ] **Step 2: Remap `_VERB_PREFIXES` in `classify.py`** (note `patch_`→verb `update`; `update_`/bulk are NOT here):
```python
_VERB_PREFIXES: list[tuple[str, Verb, SubVerb]] = [
    ("create_", "create", "create"),
    ("patch_", "update", "patch"),
    ("delete_", "delete", "delete"),
    ("get_", "show", "get"),
    ("list_", "show", "list"),
]
```
So `patch_device_group` → `update device-group` (PATCH). `update_*`(PUT) + `bulk_*` now return `None` from `classify_name` (handled in Step 3 / deferred).

- [ ] **Step 3: PUT-fallback pass in `build_cli_ir`.** A `update_<resource>` (PUT) method becomes the `update` command ONLY for an object lacking a PATCH. Implementation:
  - In the main loop, when `classify_name(op.method)` is `None` AND `op.method.startswith("update_")` AND `key0 not in cfg.hide` AND `key0 not in cfg.request`: collect `op` into a `put_fallback: list[OperationInfo]` instead of appending to `unmapped`. (Genuine non-CRUD `update_*_positions` are in `cfg.request`, handled by the earlier request branch, so they won't reach here.)
  - After the main loop, for each `op` in `put_fallback`: derive its noun the same way `classify_name` does (strip `update_`, `.replace("_","-")`); resolve variants via `resolve_variants(op, cfg.variants.get(key0))`; for each resulting `(object, variant)`, if NO command with key `_command_key("update", object, variant)` already exists, `_emit("update", object, variant, op, "update", <body model>)` (PUT body — required fields). If it DOES exist (a PATCH already produced it), DROP the PUT op silently (deferred — it's redundant with patch). Append a one-line `log`/comment noting dropped PUTs is optional; do NOT add them to `unmapped`.
  - Add the helper `_put_noun(method) -> str` (or reuse the existing noun extraction from `classify_name` — refactor the noun-stripping into a shared function if cleaner).

- [ ] **Step 4: Drop `--replace` from the runtime** (`runtime.py.jinja`): remove `replace: bool = False` from `run(...)`; `_pick_binding(cmd, present, replace)` → `_pick_binding(cmd, present)`; delete the `if replace:` block. (Writes are single-binding; `show` get/list still selected by `--id`.)

- [ ] **Step 5: Registration** (`app.py.jinja`): `_VERBS = ["create", "update", "delete", "show", "request"]`; remove the injected `--replace` option. In `commands.py.jinja` remove `--replace` + `replace=replace` from the `run(...)` call. Remove stale `"replace"` from `render_cli._RESERVED`.

- [ ] **Step 6: Fixture — add a PUT-only resource to test the fallback.** In `tests/fixtures/fakesdk/fakesdk/api.py`, give `ThingsApi` a `create_thing(self, thing_input: ThingInput)` (POST) and `update_thing(self, thing_id: str, thing_input: ThingInput)` (PUT), with **NO** `patch_thing`. In `models.py` add `class ThingInput(BaseModel)` with a required field (e.g. `label: str`) and an optional one. (Widget keeps `patch_widget` → `update widget` uses PATCH; Thing has only PUT → `update thing` uses the PUT fallback.) Confirm `get_thing`/`delete_thing` already exist.

- [ ] **Step 7: Migrate existing tests.** `grep -rn '"set"\|set:\|"del"\|del:\|--replace\|replace=' tests/ src/` and update:
  - keys: former `set:X` (create+patch+update bindings) → `create:X` (POST) + `update:X` (PATCH, from the patch binding); `del:X` → `delete:X`. The old `update`(PUT) binding is gone (folded into the fallback — for objects with a PATCH it's dropped).
  - CliRunner: `["set", obj, …]`→`["create", obj, …]`; `["set", obj, "--id", …]` (patch)→`["update", obj, "--id", …]`; `["set", obj, "--id", "--replace", …]` (PUT) → REMOVE (PUT no longer a separate path; the object's PATCH is `update`); `["del", …]`→`["delete", …]`.
  - bindings: `set:application:custom` (create+patch) → `create:application:custom` (1) + `update:application:custom` (1, sub_verb patch).
  - verb groups: `set`→`create`/`update`; `del`→`delete`.
  - bulk: fakesdk has no bulk methods (verified) — fakesdk suite unaffected. Real-SDK `unmapped == []` assertions: prisma's `bulk_*` now land in `unmapped` until T6 hides them; TEMPORARILY relax to `set(unmapped) <= {<bulk keys>}` with `# TODO(T6): hidden in cli.yml`. (PUT-fallback handles `update_*` — they should NOT be in `unmapped`.)
  - Report exactly which tests you touched.

- [ ] **Step 8: Green + lint** — `pytest tests/ -q` green; `ruff` + `mypy`. Confirm `grep` shows nothing stale (incl. `app.py.jinja` `_VERBS`, `render_cli._RESERVED`).

- [ ] **Step 9: Sanity build** — `phantasos cli build prisma-browser 2>&1 | tail -2`; `discover` shows `create/update/delete <obj>` and NO `update_*` unmapped (fallback consumed pure-PUT objects; PATCH+PUT objects show only `update`).

- [ ] **Step 10: Commit** `refactor(cli-gen): decouple set into create/update(+PUT fallback)/delete; drop set/--replace`.

---

## Task 2: Verify single-binding + the PUT fallback (classify-level lock)

**Files:** `tests/test_cli_classify.py`.

- [ ] **Step 1: Tests**
```python
def test_update_verb_prefers_patch_single_binding():
    inv = introspect("fakesdk", FIXTURE)
    ir, unmapped = build_cli_ir(inv, CliConfig())
    by_key = {c.key: c for c in ir.commands}
    # widget HAS patch_widget -> update widget is a single PATCH binding
    assert "update:widget" in by_key
    assert [b.sub_verb for b in by_key["update:widget"].bindings] == ["patch"]
    assert "create:widget" in by_key
    # PUT update_widget is dropped (redundant with patch) -> not unmapped, no separate command
    assert "widgets.update_widget" not in unmapped

def test_update_verb_falls_back_to_put_when_no_patch():
    inv = introspect("fakesdk", FIXTURE)
    ir, unmapped = build_cli_ir(inv, CliConfig())
    by_key = {c.key: c for c in ir.commands}
    # thing has create + update(PUT) + get/delete, NO patch -> update thing uses PUT
    assert "update:thing" in by_key
    assert [b.sub_verb for b in by_key["update:thing"].bindings] == ["update"]
    assert by_key["update:thing"].bindings[0].sdk_method == "update_thing"
    assert "things.update_thing" not in unmapped
```

- [ ] **Step 2: Run → PASS** (logic already in T1). If it fails, fix the T1 fallback. Then full suite + ruff + mypy.
- [ ] **Step 3: Commit** `test(cli-gen): lock update-verb PATCH-preference + PUT fallback`.

---

## Task 3: Required options + centralized `_flag_view` rendering

Required-ness is ALREADY in the IR (`fields_to_flags` sets `Flag.required=f.required`; verify). The gap is purely the emitter. Build the centralized `_flag_view` contract (used by T4/T5) and emit required options; make `--id` required for the `update` verb.

**Files:** `render_cli.py` (`_flag_view`), `commands.py.jinja`, `classify.py` (`_emit` post-process), tests.

- [ ] **Step 1: Confirm IR carries required** — `… python -c "from phantasos.generator.cli.introspect import introspect; from pathlib import Path; inv=introspect('fakesdk', Path('tests/fixtures/fakesdk')); op=next(o for o in inv.operations if o.method=='create_widget'); print([(f.name,f.required) for f in op.params])"` → `name` required True.

- [ ] **Step 2: Failing tests** (`tests/test_cli_emitted.py`) — render fakesdk to tmp + read module; and behavioral:
```python
def test_create_missing_required_errors_cleanly(emitted, monkeypatch):
    from typer.testing import CliRunner
    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: object()))
    res = CliRunner().invoke(main.app, ["create", "widget"])      # missing required --name
    assert res.exit_code != 0 and ("Missing option" in res.output or "required" in res.output.lower())

def test_update_requires_id(emitted, monkeypatch):
    from typer.testing import CliRunner
    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: object()))
    res = CliRunner().invoke(main.app, ["update", "widget", "--name", "x"])  # no --id
    assert res.exit_code != 0
```

- [ ] **Step 3: `--id` required for the update verb** — in `classify.py` `_emit`, after building `cmd`:
```python
        if verb == "update":
            for f in cmd.path_params:
                if f.kind == "id":
                    f.required = True
```
(Do NOT touch `_path_flags` — shared with `_emit_request`. `create` has no id; `show`/`delete` id stays as-is — though `delete --id` is naturally required by the SDK; keep `delete` id required too if it isn't: extend the condition to `verb in ("update", "delete")` — verify delete already requires id at the model level, else include it.)

- [ ] **Step 4: Centralize in `_flag_view`** (`render_cli.py`):
```python
_SCALAR_PY = {"int": "int", "bool": "bool", "float": "float", "str": "str"}

def _render_type(f: Flag) -> str:
    base = _SCALAR_PY.get(f.py_type, "str") if f.kind == "scalar" else "str"
    return base if f.required else f"Optional[{base}]"

def _flag_view(f: Flag) -> dict[str, object]:
    return {"name": f.name, "param": f.param, "py_name": _py_name(f.param),
            "required": f.required, "render_type": _render_type(f),
            "help_text": f.help, "completion": None, "completer_name": None}
```

- [ ] **Step 5: Centralized option line** in `commands.py.jinja` (replace the hardcoded `Optional[str]` line with the spine snippet above; `completion` is None this task).

- [ ] **Step 6: Run → PASS**, full suite, ruff+mypy. **Commit** `feat(cli-gen): required fields + --id (update) render as required options`.

---

## Task 4: Real scalar types (int/bool/float; datetime→str)

`introspect._scalar_type` only emits bool/int/str today, and body `FieldInfo` carries no normalized scalar type. Normalize so int/bool/float bodies render as real Typer types.

**Files:** `introspect.py`, `inventory.py` (`FieldInfo`), `classify.py` (`fields_to_flags`), `tests/fixtures/fakesdk/fakesdk/models.py`, tests.

- [ ] **Step 1: Failing test** — ensure a fixture body model has scalar non-str fields (add `priority: int` (required) + `enabled: Optional[bool]` to `WidgetInput` if absent). Then assert the emitted `create_widget` option uses `: int`/`Optional[bool]`, and `--priority abc` → exit≠0.

- [ ] **Step 2: Run → FAIL** (scalars render as `str`).

- [ ] **Step 3: Normalize** — add `scalar_type: str = "str"` to `inventory.FieldInfo`; in `introspect.py` classify the unwrapped annotation: `bool`→"bool", `int`→"int", `float`→"float", else (str/datetime/UUID/…)→"str" (extend `_scalar_type` to add `float`; datetime→str). Enum fields keep `"str"`.

- [ ] **Step 4: Carry to Flag** — in `fields_to_flags`, set `py_type=f.scalar_type` for scalar kind (enum/json/id stay `str`). `_render_type` (T3) maps it.

- [ ] **Step 5: Run → PASS**, full suite, ruff+mypy. **Commit** `feat(cli-gen): scalar body flags render with real types (int/bool/float)`.

---

## Task 5: Permissive enum choices (help listing + shell completion)

Surface enum choices without a validating Enum (SDK is `LenientStrEnum`). Enum flags stay `str`; add choices to `--help` + a shell completer; unlisted values pass through.

**Files:** `render_cli.py` (`_flag_view`, per-module completer emission), `commands.py.jinja`, tests.

- [ ] **Step 1: Failing test** — use the fixture's enum body field (`WidgetInput` has a `Color`/`Literal mode` field; else add a `Color` enum field). Assert `--help` lists the values AND an unlisted value is ACCEPTED (exit 0 on `--dry-run`).

- [ ] **Step 2: Run → FAIL** (no choices in help, no completer).

- [ ] **Step 3: Enrich `_flag_view`** for flags with `f.choices`: append `  [values: a, b, c]` to `help_text`; set `completion=f.choices`, `completer_name=f"_complete_{_py_name(f.param)}"`.

- [ ] **Step 4: Emit completers** — in `commands.py.jinja`, render a module-level completer per enum flag (deduped by `completer_name`); the centralized option line already references `autocompletion={{ f.completer_name }}` when `f.completion`. Collect the deduped enum-flag list per module in `render_cli`. Option stays `str` → unlisted values pass through.
```jinja
{% for f in module_enum_flags %}
def {{ f.completer_name }}(incomplete: str) -> list[str]:
    return [c for c in {{ f.completion|tojson }} if c.startswith(incomplete)]
{% endfor %}
```

- [ ] **Step 5: Run → PASS**, full suite, ruff+mypy. **Commit** `feat(cli-gen): enum flags list choices in --help + completion (permissive)`.

---

## Task 6: Config + docs

**Files:** `products/prisma-browser/cli.yml`, spec, roadmap.

- [ ] **Step 1: Hide bulk in prisma cli.yml** — `phantasos cli discover prisma-browser` to list the exact `bulk_*` keys; add a `hide:` block for them with a comment (deferred → `load`/`backup`). Retighten the T1 `# TODO(T6)` test to `unmapped == []`. (PUT `update_*` need NO hiding — the fallback consumes pure-PUT objects and silently drops PATCH-redundant PUTs.)

- [ ] **Step 2: Spec rewrite** — in `…design.md`, replace the `set`-aggregation grammar/dispatch sections with the verb table (`create`/`update`/`delete`/`show`/`request`), single-binding writes, the `update` PATCH-preference + PUT-fallback, `--id` required for update, required+typed scalar flags, `set`/`--replace` removed. **Keep the permissive-enum section.** Note deferred: full-replace PUT (future `replace` verb) + bulk (`load`/`backup`). Update the `Verb` literal reference.

- [ ] **Step 3: Roadmap** — decouple done; future `replace` verb (full-replace PUT when a PATCH exists); bulk → `load`/`backup`.

- [ ] **Step 4: Green; commit** `docs: decoupled create/update/delete grammar; PUT fallback; hide deferred bulk`.

---

## Task 7: Real-SDK capstone — the device-group experience

**Files:** `tests/test_cli_emitted_real.py` (gated).

- [ ] **Step 1: Gated test**
```python
def test_real_create_update_delete_verbs(tmp_path, monkeypatch):
    if not REAL_SDK.exists():
        pytest.skip("prisma-browser-sdk not built")
    from typer.testing import CliRunner
    from unittest.mock import MagicMock
    from phantasos.generator.cli.cliconfig import load_cli_config
    try:
        inv = introspect("prisma_browser", REAL_SDK)
    except ImportError as exc:
        pytest.skip(str(exc))
    ir, unmapped = build_cli_ir(inv, load_cli_config(Path("products/prisma-browser/cli.yml")))
    keys = {c.key for c in ir.commands}
    assert {"create:device-group", "update:device-group",
            "delete:device-group", "show:device-group"} <= keys
    assert "patch:device-group" not in keys and "set:device-group" not in keys
    assert unmapped == []
    # device-group has patch -> update is single PATCH binding (all-optional + --id)
    upd = next(c for c in ir.commands if c.key == "update:device-group")
    assert [b.sub_verb for b in upd.bindings] == ["patch"]

    render_cli(ir, package="prisma_browser_cli", out_dir=tmp_path)
    sys.path.insert(0, str(tmp_path))
    for n in [n for n in sys.modules if n.startswith("prisma_browser_cli")]:
        del sys.modules[n]
    try:
        main = importlib.import_module("prisma_browser_cli.main")
        runner = CliRunner()
        h = runner.invoke(main.app, ["create", "device-group", "--help"]).output
        assert "--platform" in h and "Desktop Browser" in h          # enum choices listed (permissive)
        import prisma_browser.extras.facade as facade
        monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: MagicMock()))
        assert runner.invoke(main.app, ["create", "device-group", "--name", "x"]).exit_code != 0  # platform required
        assert runner.invoke(main.app, ["update", "device-group", "--name", "x"]).exit_code != 0  # update needs --id
        ok = runner.invoke(main.app, ["create", "device-group", "--name", "x",
                                      "--platform", "Holographic Browser", "--dry-run"])
        assert ok.exit_code == 0, ok.output                          # permissive enum accepts unlisted
    finally:
        sys.path.remove(str(tmp_path))
        for n in [n for n in sys.modules if n.startswith("prisma_browser_cli")]:
            del sys.modules[n]
```

- [ ] **Step 2: Run → PASS (not skip).** Adjust the `--help` choice assertion to match Typer's rendering if needed (still assert a real platform value appears + an unlisted one is accepted).
- [ ] **Step 3: Full suite + ruff + mypy; commit** `test(cli-gen): real-SDK create/update/delete device-group experience`.

---

## python-pro review (applied) + scheme refinements
GO-WITH-CHANGES, folded in: permissive enums (no validating Enum / no import / no `.value`); required-ness already in IR → emitter-only (T3); `--id` required via `_emit` post-process (not `_path_flags`); centralized `_flag_view.render_type` once (T3) so T4/T5 only enrich; introspection must normalize float/datetime scalars (T4); stale `"replace"` removed from `_RESERVED` (T1). **User scheme (final):** `update` = PATCH-preferred with PUT-fallback (T1 Step 3 + T2 lock); no `patch`/`put`/`set` verbs; full-replace PUT (when a PATCH exists) deferred → future `replace` verb.

## Risks for the review pass
1. **PUT fallback (T1/T2):** confirm the post-loop pass (a) emits `update:X` from PUT only when no PATCH-built `update:X` exists, (b) silently drops PATCH-redundant PUTs (not into `unmapped`), (c) applies `resolve_variants` consistently, (d) handles the `update_*_positions` request methods correctly (they're in `cfg.request`, handled before classify — never reach the fallback). Verify noun extraction matches `classify_name`'s.
2. **Test-churn (T1):** `grep` clean post-T1 (incl. `app.py.jinja`, `_RESERVED`).
3. **`--id` required scope (T3):** update (and delete) yes; create none; show optional.
4. **Variant split:** `create application <variant>` + `update application <variant>` (PATCH) both single-binding; runtime variant-discriminator injection (keys on `cmd.variant`/`variant_param`) still fires for the create POST union body.
5. **Scalar normalization (T4):** datetime→str; `runtime._coerce` `isinstance(v,str)` guards no-op when Typer delivers typed int/bool.
6. **Permissive enum (T5):** option stays `str`; unlisted values pass through; dry-run with an unlisted enum exits 0.
7. **bulk loosening (T1→T6):** real-SDK `unmapped` relaxed in T1, retightened in T6.
