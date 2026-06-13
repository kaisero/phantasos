# CLI Generator — Decouple `set` into `create`/`update`/`delete` Verbs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the aggregated `set <object>` command (which dispatched create/patch/update via a `--id`/`--replace` heuristic) with **single-binding** verbs: `create` (POST), `update` (PATCH), and `delete` (renamed from `del`). Single-binding commands make Typer integration clean: required model fields become real `[required]` options, scalars get real types, and enum fields surface their choices in `--help` + shell completion (permissively).

**Architecture:** The classifier tags each method `(verb, sub_verb)`. Today create/patch/update map to `verb="set"` and aggregate into one multi-binding `Command`. We remap so each write maps to its OWN verb; since `_command_key` includes the verb, every write `Command` has exactly ONE binding — no other `_emit` change needed. This removes the runtime `--replace` flag and write-dispatch heuristic, and lets the emitter render each flag with its real type / required-ness / completion. `show` keeps its benign get+list aggregation (`--id` selects get). `request`/`load`/`backup` unchanged.

**Verb scheme (locked):**
| Verb | HTTP | Notes |
|---|---|---|
| `create <obj> [variant]` | POST | required fields enforced; no `--id` |
| `update <obj> --id [variant]` | **PATCH** | `--id` required; all body fields optional |
| `delete <obj> --id` | DELETE | |
| `show <obj>` | GET/list | `--id` selects get |
| `request <obj> <action>` | — | unchanged |

No `set`, no `patch`/`put` verb, no `--replace`. **Deferred to roadmap:** all PUT (`update_*`) methods — both the PUT-fallback for objects lacking a PATCH and full-replace when a PATCH exists (future `update`-fallback / `replace` verb); `bulk_create`/`bulk_delete` (future `load`/`backup`). PUT and bulk methods become unmapped → `hide:`-listed for prisma (T5).

**Permissive enums (locked):** enum body/query fields stay `str` options with a shell completer + choices listed in `--help`. NOT validating Typer `Enum`s — the SDK uses `LenientStrEnum` (unknowns pass through), so the CLI must not be stricter than the SDK. Matches the spec's permissive-enum mandate.

**Tech Stack:** Python 3.11–3.14, Pydantic v2, Typer/Click, Jinja2, pytest. Runner: `uv run`.

**Spec:** `docs/superpowers/specs/2026-06-09-cli-generator-design.md` (rewrites grammar + aggregated-command sections; permissive-enum stance unchanged). **Builds on:** branch `cli-generator`.

---

## Conventions (every task)
- Env: `export UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv` then `uv run …`.
- Repo `/home/ubuntu/git/phantasos`, branch `cli-generator`. **Do NOT `git checkout`/`switch`/`reset`.** Commit on the branch; `git show <sha>:<path>` for history.
- TDD; imports at top of test files; `ruff check src/phantasos tests/` + `mypy src/phantasos/generator` before each commit.
- Fake SDK fixture `tests/fixtures/fakesdk/`; real SDK `/home/ubuntu/git/prisma-browser-sdk`.

## Centralized option rendering (spine of T2–T4)
All flag-emission tasks funnel through ONE helper. In `render_cli.py`, `_flag_view(f)` computes: `render_type` (full annotation incl. `Optional[...]` iff not required; `--id`/`json`/`enum`→`str`; scalar→mapped Python type), `required` (bool), `help_text` (base help + `  [values: a, b, c]` for enums), `completion`/`completer_name` (enum choices). `commands.py.jinja` emits ONE line per flag:
```jinja
    {{ f.py_name }}: {{ f.render_type }} = typer.Option({{ '...' if f.required else 'None' }}, {{ f.name|tojson }}{% if f.help_text %}, help={{ f.help_text|tojson }}{% endif %}{% if f.completion %}, autocompletion={{ f.completer_name }}{% endif %}),
```
T2 builds the contract (scalar/enum → `str`); T3 fills scalar types; T4 fills enum help/completion.

---

## Task 1: Decouple verbs + `del`→`delete` (core, atomic)

**Files:** `ir.py`, `classify.py`, `render_cli.py`, `runtime.py.jinja`, `app.py.jinja`, `commands.py.jinja`, existing tests.

- [ ] **Step 1: `Verb` in `ir.py`**
```python
Verb = Literal["create", "update", "delete", "show", "request", "load", "backup"]
```
(Remove `"set"`, `"del"`. `SubVerb` unchanged — the `update` verb's binding carries `sub_verb="patch"`.)

- [ ] **Step 2: Remap `_VERB_PREFIXES` in `classify.py`** (`patch_`→verb `update`; `update_`/bulk NOT mapped → deferred/unmapped):
```python
_VERB_PREFIXES: list[tuple[str, Verb, SubVerb]] = [
    ("create_", "create", "create"),
    ("patch_", "update", "patch"),
    ("delete_", "delete", "delete"),
    ("get_", "show", "get"),
    ("list_", "show", "list"),
]
```
So `patch_device_group` → `update device-group` (PATCH, all-optional). `update_*` (PUT) + `bulk_*` → `classify_name` returns `None` → unmapped (deferred; hidden for prisma in T5). Genuine non-CRUD `update_*_positions` are in `cfg.request` (handled by the request branch before classify) — unaffected.

- [ ] **Step 3: Drop `--replace` from the runtime** (`runtime.py.jinja`): remove `replace: bool = False` from `run(...)`; `_pick_binding(cmd, present, replace)` → `_pick_binding(cmd, present)`; delete the `if replace:` block. (Writes single-binding; `show` get/list still selected by `--id`.)

- [ ] **Step 4: Registration** (`app.py.jinja`): `_VERBS = ["create", "update", "delete", "show", "request"]`; remove the injected `replace: bool = typer.Option(False, "--replace")`. In `commands.py.jinja` remove `--replace` + `replace=replace` from the `run(...)` call. Remove stale `"replace"` from `render_cli._RESERVED`.

- [ ] **Step 5: Migrate existing tests.** `grep -rn '"set"\|set:\|"del"\|del:\|--replace\|replace=' tests/ src/` and update:
  - keys: former `set:X` (create+patch+update bindings) → `create:X` (POST) + `update:X` (PATCH, from the patch binding); the old `update`(PUT) binding is gone (deferred). `del:X` → `delete:X`.
  - CliRunner: `["set", obj, …]` (create) → `["create", obj, …]`; `["set", obj, "--id", …]` (patch) → `["update", obj, "--id", …]`; `["set", obj, "--id", "--replace", …]` (PUT) → REMOVE (PUT deferred — the object's PATCH is now `update`); `["del", …]` → `["delete", …]`.
  - bindings: `set:application:custom` (create+patch) → `create:application:custom` (1 binding) + `update:application:custom` (1 binding, sub_verb patch).
  - verb groups: `set`→`create`/`update`; `del`→`delete`.
  - **unmapped now includes deferred PUT + bulk:** the fakesdk fixture has `update_widget` (PUT) → now unmapped, and no bulk methods. Tests asserting `unmapped` via `in` are fine; fix any that assert an exact `unmapped` set/count (now also contains `widgets.update_widget`). For the real-SDK tests, prisma's `update_*` (PUT) + `bulk_*` land in `unmapped` until T5 hides them — TEMPORARILY relax `unmapped == []` to `set(unmapped) <= {<those keys>}` with `# TODO(T5): hidden in cli.yml`. Run `phantasos cli discover prisma-browser` to enumerate them.
  - Report exactly which tests you touched.

- [ ] **Step 6: Green + lint** — `pytest tests/ -q` green; `ruff` + `mypy`. Confirm `grep -rn '"set"\|set:\|"del"\|--replace' src/` (incl. `app.py.jinja`, `render_cli._RESERVED`) is clean.

- [ ] **Step 7: Sanity build** — `phantasos cli build prisma-browser 2>&1 | tail -2`; `discover` shows `create/update/delete <obj>` (update = PATCH). PUT/bulk show in the unmapped note until T5.

- [ ] **Step 8: Commit** `refactor(cli-gen): decouple set into create/update(PATCH)/delete; del->delete; drop --replace; defer PUT`.

---

## Task 2: Required options + centralized `_flag_view` rendering

Required-ness is ALREADY in the IR (`fields_to_flags` sets `Flag.required=f.required`; verify). The gap is purely the emitter, which drops it and hardcodes `Optional[str]`. Build the centralized `_flag_view` contract (used by T3/T4) and emit required options; make `--id` required for `update`.

**Files:** `render_cli.py` (`_flag_view`), `commands.py.jinja`, `classify.py` (`_emit` post-process), tests.

- [ ] **Step 1: Confirm IR carries required** — `… python -c "from phantasos.generator.cli.introspect import introspect; from pathlib import Path; inv=introspect('fakesdk', Path('tests/fixtures/fakesdk')); op=next(o for o in inv.operations if o.method=='create_widget'); print([(f.name,f.required) for f in op.params])"` → `name` required True.

- [ ] **Step 2: Failing tests** (`tests/test_cli_emitted.py`)
```python
def test_create_missing_required_errors_cleanly(emitted, monkeypatch):
    from typer.testing import CliRunner
    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: object()))
    res = CliRunner().invoke(main.app, ["create", "widget"])       # missing required --name
    assert res.exit_code != 0 and ("Missing option" in res.output or "required" in res.output.lower())

def test_update_requires_id(emitted, monkeypatch):
    from typer.testing import CliRunner
    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: object()))
    res = CliRunner().invoke(main.app, ["update", "widget", "--name", "x"])   # no --id
    assert res.exit_code != 0
```

- [ ] **Step 3: Run → FAIL** (everything emits `Optional[str] = typer.Option(None, …)`; `--id` optional).

- [ ] **Step 4: `--id` required for the update verb** — in `classify.py` `_emit`, after building `cmd`:
```python
        if verb == "update":
            for f in cmd.path_params:
                if f.kind == "id":
                    f.required = True
```
(Do NOT touch `_path_flags` — shared with `_emit_request`. `create` has no id; `show` keeps optional id. `delete --id` is naturally required by the SDK call; if a `delete X` without `--id` currently 500s rather than erroring cleanly, also include `"delete"` in the condition — verify and decide.)

- [ ] **Step 5: Centralize in `_flag_view`** (`render_cli.py`):
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

- [ ] **Step 6: Centralized option line** in `commands.py.jinja` (the spine snippet; `completion` None this task).

- [ ] **Step 7: Run → PASS**, full suite, ruff+mypy. **Commit** `feat(cli-gen): required fields + --id (update) render as required options`.

---

## Task 3: Real scalar types (int/bool/float; datetime→str)

`introspect._scalar_type` only emits bool/int/str today, and body `FieldInfo` carries no normalized scalar type. Normalize so int/bool/float bodies render as real Typer types.

**Files:** `introspect.py`, `inventory.py` (`FieldInfo`), `classify.py` (`fields_to_flags`), `tests/fixtures/fakesdk/fakesdk/models.py`, tests.

- [ ] **Step 1: Failing test** — ensure a fixture body model has scalar non-str fields (add `priority: int` (required) + `enabled: Optional[bool]` to `WidgetInput` if absent). Render fakesdk to tmp; assert the `create_widget` option uses `: int`/`Optional[bool]`; and `create widget --name w --priority abc` → exit≠0.

- [ ] **Step 2: Run → FAIL** (scalars render as `str`).

- [ ] **Step 3: Normalize** — add `scalar_type: str = "str"` to `inventory.FieldInfo`; in `introspect.py` classify the unwrapped annotation: `bool`→"bool", `int`→"int", `float`→"float", else (str/datetime/UUID/…)→"str" (extend `_scalar_type` with `float`; datetime→str). Enum fields keep `"str"`.

- [ ] **Step 4: Carry to Flag** — in `fields_to_flags`, set `py_type=f.scalar_type` for scalar kind (enum/json/id stay `str`). `_render_type` (T2) maps it.

- [ ] **Step 5: Run → PASS**, full suite, ruff+mypy. **Commit** `feat(cli-gen): scalar body flags render with real types (int/bool/float)`.

---

## Task 4: Permissive enum choices (help listing + shell completion)

Surface enum choices without a validating Enum (SDK is `LenientStrEnum`). Enum flags stay `str`; add choices to `--help` + a shell completer; unlisted values pass through.

**Files:** `render_cli.py` (`_flag_view`, per-module completer emission), `commands.py.jinja`, tests.

- [ ] **Step 1: Failing test** — use the fixture's enum body field (`WidgetInput` has a `Color`/`Literal mode` field; else add a `Color` enum field with choices). Assert `--help` lists the values AND an unlisted value is ACCEPTED (exit 0 on a mocked `--dry-run` create).

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

## Task 5: Config + docs — hide deferred PUT + bulk; rewrite spec grammar

**Files:** `products/prisma-browser/cli.yml`, spec, roadmap.

- [ ] **Step 1: Hide deferred ops in prisma cli.yml** — `phantasos cli discover prisma-browser` to list the exact `update_*` (PUT) + `bulk_*` keys; add a `hide:` block for them with a comment (deferred — PUT→future `replace`/update-fallback, bulk→`load`/`backup`). Retighten the T1 `# TODO(T5)` tests to `unmapped == []`.

- [ ] **Step 2: Spec rewrite** — in `…design.md`, replace the `set`-aggregation grammar/dispatch sections with the verb table (`create`/`update`/`delete`/`show`/`request`), single-binding writes, `update`=PATCH, `--id` required for update, required+typed scalar flags, `set`/`--replace` removed. **Keep the permissive-enum section.** Note deferred: all PUT (future `replace` / `update`-fallback) + bulk (`load`/`backup`). Update the `Verb` literal reference.

- [ ] **Step 3: Roadmap** — decouple done; future: PUT support (`update`-fallback when no PATCH + full-replace `replace` verb); bulk → `load`/`backup`.

- [ ] **Step 4: Green; commit** `docs: decoupled create/update/delete grammar; hide deferred PUT+bulk`.

---

## Task 6: Real-SDK capstone — the device-group experience

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
    # device-group has patch_ -> update is a single PATCH binding (all-optional + --id)
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

- [ ] **Step 2: Run → PASS (not skip).** Adjust the `--help` choice assertion to match Typer's rendering if needed (still assert a real platform value + an unlisted one accepted).
- [ ] **Step 3: Full suite + ruff + mypy; commit** `test(cli-gen): real-SDK create/update/delete device-group experience`.

---

## python-pro review (applied) + scheme
GO-WITH-CHANGES, folded in: permissive enums (no validating Enum / import / `.value`); required-ness already in IR → emitter-only (T2); `--id` required via `_emit` post-process (not `_path_flags`); centralized `_flag_view.render_type` once (T2) so T3/T4 only enrich; introspection normalizes float/datetime scalars (T3); stale `"replace"` removed from `_RESERVED` (T1). **User scheme (final):** `update` = PATCH only; ALL PUT deferred to roadmap (no fallback in this work); `delete` renamed; no `set`/`patch`/`put` verbs.

## Risks for the review pass
1. **Test-churn (T1):** `grep` clean post-T1 (incl. `app.py.jinja`, `_RESERVED`); fakesdk `update_widget` (PUT) now unmapped — fix exact-set `unmapped` assertions.
2. **`--id` required scope (T2):** update yes; create none; show optional; decide delete.
3. **Variant split:** `create application <variant>` + `update application <variant>` (PATCH) both single-binding; runtime variant-discriminator injection (keys on `cmd.variant`/`variant_param`) still fires for the create POST union body.
4. **Scalar normalization (T3):** datetime→str; `runtime._coerce` `isinstance(v,str)` guards no-op when Typer delivers typed int/bool.
5. **Permissive enum (T4):** option stays `str`; unlisted values pass through; dry-run with an unlisted enum exits 0.
6. **Deferred PUT+bulk loosening (T1→T5):** real-SDK `unmapped` relaxed in T1, retightened in T5 — don't forget.
