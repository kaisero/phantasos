# CLI Generator — Decouple `set` into `create`/`patch`/`update` (+ `del`→`delete`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the aggregated `set <object>` command (which dispatched create/patch/update via a `--id`/`--replace` heuristic) with three **single-binding** write verbs — `create` (POST), `patch` (PATCH), `update` (PUT) — and rename `del`→`delete`. Single-binding commands make Typer integration clean: required model fields become real `[required]` options, scalars get real types (int/bool/float), and enum fields surface their choices in `--help` + shell completion (**permissively** — see below).

**Architecture:** The classifier already tags each method `(verb, sub_verb)`. Today create/patch/update all map to `verb="set"` and aggregate into one `Command` with N bindings, dispatched at runtime. We remap so each write maps to its OWN verb (`create`/`patch`/`update`/`delete`); since `_command_key` includes the verb, every write `Command` then has exactly ONE binding — no other `_emit` change needed. That removes the runtime `--replace` flag and the write-dispatch heuristic, and lets the emitter render each flag with its real type / required-ness / completion. `show` keeps its benign get+list aggregation (`--id` selects get). `request`/`load`/`backup` unchanged.

**Permissive enums (locked decision):** enum body/query fields stay `str` options with a shell **completer** + the choices listed in `--help`. They are NOT validating Typer `Enum`s. The SDK enums are `LenientStrEnum` (unknown values pass through by design), so the CLI must not be stricter than the SDK — an unlisted value is accepted and forwarded. This matches the spec (`…design.md` "permissive enum" mandate) and `fields_to_flags`'s existing `py_type="str"` for enums.

**Tech Stack:** Python 3.11–3.14, Pydantic v2, Typer/Click, Jinja2, pytest. Runner: `uv run`.

**Spec:** `docs/superpowers/specs/2026-06-09-cli-generator-design.md` (this plan rewrites the grammar + "aggregated command model" sections; the permissive-enum stance is UNCHANGED). **Builds on:** branch `cli-generator` (Phases 1/2a/2b/3g/3a/3b + the .env + JSON-default fixes).

---

## Conventions (every task)
- Env: `export UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv` then `uv run …`.
- Repo `/home/ubuntu/git/phantasos`, branch `cli-generator`. **Do NOT `git checkout`/`switch`/`reset`.** Commit on the branch; `git show <sha>:<path>` for history.
- TDD; imports at top of test files; run `ruff check src/phantasos tests/` + `mypy src/phantasos/generator` before each commit.
- Fake SDK fixture `tests/fixtures/fakesdk/`; real SDK `/home/ubuntu/git/prisma-browser-sdk`.

## Scope decisions (baked in)
1. **Three write verbs, single binding each:** `create` (POST), `patch` (PATCH, `--id` + all-optional), `update` (PUT, `--id` + required like create). Emitted only where the SDK method exists per object.
2. **`del`→`delete`** everywhere (verb, registration, classifier, docs, tests).
3. **`set` and `--replace` removed.** No back-compat alias (CLI unreleased). Also remove the stale `"replace"` entry from `render_cli._RESERVED`.
4. **`show` unchanged** — keeps get+list under one command, `--id` selects get.
5. **`bulk_create`/`bulk_delete` DEFERRED** — removed from the classifier and `hide:`-listed for prisma (broken by the `list[Model]` gap; return under future `load`/`backup`). T5.
6. **Permissive enums** (see Architecture) — choices shown + completed, never validated.
7. **Variants carry over per-method:** `set application custom` → `create application custom` (POST) + `patch application custom` (PATCH). The `cli.yml variants:` map is keyed by method → no change.

## Centralized option rendering (the spine of T2–T4)
All three emission tasks funnel through ONE helper so the jinja stays a single branch and we never rewrite the option line three times. In `render_cli.py`, `_flag_view(f)` computes:
- `render_type`: the full annotation string. `--id`/`json`/`enum` kinds → `str`; scalar → mapped Python type (`int`/`bool`/`float`/`str`); wrapped in `Optional[...]` iff not required.
- `required`: bool (drives `typer.Option(...)` vs `typer.Option(None, …)`).
- `help_text`: base help, with `  [values: a, b, c]` appended for enum flags (permissive listing).
- `completion`: the choices list (or None) for the shell completer.

`commands.py.jinja` then emits each flag as ONE line:
```jinja
    {{ f.py_name }}: {{ f.render_type }} = typer.Option(
        {{ '...' if f.required else 'None' }}, {{ f.name|tojson }}
        {%- if f.help_text %}, help={{ f.help_text|tojson }}{% endif %}
        {%- if f.completion %}, autocompletion={{ f.completer_name }}{% endif %}),
```
(T2 introduces `render_type`/`required`/`help_text`; T3 fills the scalar `render_type`; T4 fills `help_text`/`completion`. Build the whole `_flag_view` contract in T2 with scalar/enum branches returning `str` for now, so later tasks only enrich.)

## File structure (this plan)
- `ir.py` — `Verb` literal (T1). (No new `Flag` fields — `required`/`choices`/`py_type` already exist.)
- `classify.py` — `_VERB_PREFIXES` remap + drop bulk (T1); `--id` required for patch/update via `_emit` post-process (T2).
- `inventory.py` + `introspect.py` — normalize body-field scalar types (T3).
- `render_cli.py` — `_flag_view` centralization (T2); remove `replace` from `_RESERVED` (T1); per-module completer emission (T4).
- `templates/_generated/commands.py.jinja` — centralized option line + completers (T2/T4); drop `--replace` (T1).
- `templates/_generated/runtime.py.jinja` — drop `replace` + `if replace:` (T1).
- `templates/_generated/app.py.jinja` — `_VERBS` (T1); drop `--replace` option (T1).
- `products/prisma-browser/cli.yml`, spec, roadmap — T5.
- Tests across `test_cli_classify/emitted/command/emitted_real`.

---

## Task 1: Decouple the write verbs + rename `del`→`delete` (core, atomic)

Touches the verb literal, classifier mapping, registration, and runtime dispatch together, plus migrates existing tests. After it, every write command is single-binding and the suite is green.

**Files:** `ir.py`, `classify.py`, `render_cli.py`, `runtime.py.jinja`, `app.py.jinja`, `commands.py.jinja`, existing tests.

- [ ] **Step 1: `Verb` in `ir.py`**
```python
Verb = Literal["create", "patch", "update", "delete", "show", "request", "load", "backup"]
```
(Remove `"set"`, `"del"`. `SubVerb` unchanged.)

- [ ] **Step 2: Remap `_VERB_PREFIXES` in `classify.py` + drop bulk**
```python
_VERB_PREFIXES: list[tuple[str, Verb, SubVerb]] = [
    ("create_", "create", "create"),
    ("update_", "update", "update"),
    ("patch_", "patch", "patch"),
    ("delete_", "delete", "delete"),
    ("get_", "show", "get"),
    ("list_", "show", "list"),
]
```
(Removed `bulk_create_`/`bulk_delete_` — they now return `None` from `classify_name` = "unmapped" until hidden in T5. No other `_emit`/`classify_name` change — distinct verb keys auto-produce single-binding write commands.)

- [ ] **Step 3: Drop `--replace` from the runtime** (`runtime.py.jinja`): remove the `replace: bool = False` param from `run(...)`; change `_pick_binding(cmd, present, replace)` → `_pick_binding(cmd, present)` and delete the `if replace:` block (~lines 84-86). (Single-binding writes → returns the lone binding; `show` get/list still selected by `--id` via the `requires`-subset logic.)

- [ ] **Step 4: Registration** (`app.py.jinja`): `_VERBS = ["create", "patch", "update", "delete", "show", "request"]`; remove the injected `replace: bool = typer.Option(False, "--replace")` line.

- [ ] **Step 5: `commands.py.jinja`**: remove the `--replace` option + `replace=replace` from the `run(...)` call. (Keep `--all`/`--dry-run`/`--verbose`/`--output`.)

- [ ] **Step 6: Remove stale `"replace"` from `render_cli._RESERVED`** (~line 22).

- [ ] **Step 7: Migrate existing tests.** `grep -rn '"set"\|set:\|"del"\|del:\|--replace\|replace=' tests/ src/` and update:
  - keys: a former `set:X` (create+patch+update bindings) → three single-binding commands `create:X`/`patch:X`/`update:X`; `del:X` → `delete:X`.
  - CliRunner: `["set", obj, …]` (create) → `["create", obj, …]`; `["set", obj, "--id", …]` (patch) → `["patch", obj, "--id", …]`; `["set", obj, "--id", "--replace", …]` (PUT) → `["update", obj, "--id", …]`; `["del", …]` → `["delete", …]`.
  - bindings: `set:application:custom` (create+patch) → `create:application:custom` (1 binding) + `patch:application:custom` (1 binding). Update `test_real_cli_yml_produces_variant_commands_and_no_unmapped` to assert both, single-binding each.
  - verb-group assertions: `set`→`create`/`patch`/`update`; `del`→`delete`.
  - **bulk:** the fakesdk fixture has NO bulk methods (verified), so the fakesdk suite is unaffected. For the real-SDK tests, prisma's bulk ops now land in `unmapped` until T5 hides them — TEMPORARILY relax any `unmapped == []` assertion to `set(unmapped) <= {<the bulk keys>}` with a `# TODO(T5): hidden in cli.yml, retighten to ==[]` and run `phantasos cli discover prisma-browser` to get the exact bulk keys.
  - State in your report exactly which tests you touched.

- [ ] **Step 8: Green + lint** — `pytest tests/ -q` to green, then `ruff check src/phantasos tests/` + `mypy src/phantasos/generator`. Confirm `grep -rn '"set"\|set:\|"del"\|--replace' src/ src/phantasos/generator/cli/templates` returns nothing stale (incl. `app.py.jinja` `_VERBS`, `render_cli._RESERVED`).

- [ ] **Step 9: Sanity build** — `phantasos cli build prisma-browser 2>&1 | tail -2`; `discover` shows `create/patch/update/delete <obj>`. (Bulk may show an `unmapped` note until T5.)

- [ ] **Step 10: Commit** `refactor(cli-gen): decouple set into create/patch/update single-binding verbs; del->delete; drop --replace`.

---

## Task 2: Required options + centralized `_flag_view` rendering

Required-ness is ALREADY in the IR (`fields_to_flags` sets `Flag.required=f.required`; verify). The gap is purely the emitter, which today drops it and hardcodes `Optional[str]`. This task builds the centralized `_flag_view` contract (used by T3/T4) and emits required options. It also makes `--id` required for `patch`/`update`.

**Files:** `render_cli.py` (`_flag_view`), `commands.py.jinja`, `classify.py` (`_emit` post-process for `--id`), tests.

- [ ] **Step 1: Confirm the IR already carries required** (quick check, no code):
`… python -c "from phantasos.generator.cli.introspect import introspect; from pathlib import Path; inv=introspect('fakesdk', Path('tests/fixtures/fakesdk')); op=next(o for o in inv.operations if o.method=='create_widget'); print([(f.name,f.required) for f in op.params])"` — expect `name` required=True.

- [ ] **Step 2: Failing tests** (`tests/test_cli_emitted.py`)
```python
def test_create_required_fields_render_required(emitted, tmp_path):
    # render fakesdk CLI to tmp and read the emitted command module
    from phantasos.generator.cli.introspect import introspect
    from phantasos.generator.cli.classify import build_cli_ir
    from phantasos.generator.cli.render_cli import render_cli
    from phantasos.generator.cli.cliconfig import CliConfig
    inv = introspect("fakesdk", FIXTURE)
    ir, _ = build_cli_ir(inv, CliConfig())
    render_cli(ir, package="fakesdk_cli", out_dir=tmp_path)
    code = (tmp_path / "fakesdk_cli" / "_generated" / "commands" / "widgets.py").read_text()
    import re
    create_fn = re.search(r"def create_widget\(.*?\n\) ->", code, re.S).group(0)
    assert "typer.Option(\n        ...," in create_fn or "typer.Option(..." in create_fn

def test_create_missing_required_errors_cleanly(emitted, monkeypatch):
    from typer.testing import CliRunner
    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: object()))
    res = CliRunner().invoke(main.app, ["create", "widget"])   # missing required --name
    assert res.exit_code != 0
    assert "Missing option" in res.output or "required" in res.output.lower()

def test_patch_requires_id(emitted, monkeypatch):
    from typer.testing import CliRunner
    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: object()))
    res = CliRunner().invoke(main.app, ["patch", "widget", "--name", "x"])  # no --id
    assert res.exit_code != 0
```

- [ ] **Step 3: Run → FAIL** (everything emits `Optional[str] = typer.Option(None, …)`; `--id` optional).

- [ ] **Step 4: `--id` required for patch/update** — in `classify.py` `_emit`, after building `cmd`, post-process:
```python
        if verb in ("patch", "update"):
            for f in cmd.path_params:
                if f.kind == "id":
                    f.required = True
```
(Do NOT change `_path_flags` — it's shared with `_emit_request`. `create` has no id flag; `show` keeps its id optional.)

- [ ] **Step 5: Centralize in `_flag_view`** (`render_cli.py`) — build the full contract now (scalar/enum branches return `str` for this task; T3/T4 enrich):
```python
_SCALAR_PY = {"int": "int", "bool": "bool", "float": "float", "str": "str"}

def _render_type(f: Flag) -> str:
    if f.kind == "scalar":
        base = _SCALAR_PY.get(f.py_type, "str")   # T3 makes py_type carry real scalar types
    else:
        base = "str"                                # id / json / enum stay str (permissive)
    return base if f.required else f"Optional[{base}]"

def _flag_view(f: Flag) -> dict[str, object]:
    return {
        "name": f.name, "param": f.param, "py_name": _py_name(f.param),
        "required": f.required, "render_type": _render_type(f),
        "help_text": f.help, "completion": None, "completer_name": None,  # T4 fills enum
    }
```

- [ ] **Step 6: Centralized option line in `commands.py.jinja`** — replace the hardcoded line with:
```jinja
    {{ f.py_name }}: {{ f.render_type }} = typer.Option({{ '...' if f.required else 'None' }}, {{ f.name|tojson }}{% if f.help_text %}, help={{ f.help_text|tojson }}{% endif %}{% if f.completion %}, autocompletion={{ f.completer_name }}{% endif %}),
```
(`Optional` is already imported in the template. `completion` is always None this task.)

- [ ] **Step 7: Run → PASS**, full suite green, ruff+mypy clean.
- [ ] **Step 8: Commit** `feat(cli-gen): required model fields + --id (patch/update) render as required options`.

---

## Task 3: Real scalar types (int/bool/float; datetime→str)

`_render_type` already maps `f.py_type`, but introspection under-populates body-field scalar types. `introspect._scalar_type` only emits `bool`/`int`/`str` (no `float`/`datetime`), and body `FieldInfo` carries `annotation` but no normalized `scalar_type`. Normalize it so int/bool/float bodies render as real types.

**Files:** `introspect.py`, `inventory.py` (`FieldInfo`), `classify.py` (`_body_flags_for`/`fields_to_flags`), tests.

- [ ] **Step 1: Failing test** — the fakesdk needs a scalar body field. Check `WidgetInput`; if it lacks an `int`/`bool`, add `priority: int` (required) and `enabled: Optional[bool]` to the fixture model `tests/fixtures/fakesdk/fakesdk/models.py`. Then:
```python
def test_scalar_body_flags_use_real_types(emitted, tmp_path):
    # render fakesdk CLI, read widgets.py
    … (render as in T2) …
    code = (tmp_path / "fakesdk_cli" / "_generated" / "commands" / "widgets.py").read_text()
    assert ": int = typer.Option(..." in code            # required int
    assert "Optional[bool]" in code                       # optional bool

def test_scalar_type_validated_by_typer(emitted, monkeypatch):
    from typer.testing import CliRunner
    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: object()))
    res = CliRunner().invoke(main.app, ["create", "widget", "--name", "w", "--priority", "abc"])
    assert res.exit_code != 0   # 'abc' is not a valid int
```

- [ ] **Step 2: Run → FAIL** (scalars render as `str`/`Optional[str]`).

- [ ] **Step 3: Normalize body-field scalar type in introspection** — add `scalar_type: str = "str"` to `inventory.FieldInfo`; in `introspect.py` where `FieldInfo`s are built, classify the (unwrapped) annotation: `bool`→"bool", `int`→"int", `float`→"float", everything else (str, datetime, UUID, etc.)→"str". Reuse/extend the existing `_scalar_type` helper to cover `float` (and leave datetime→str). For enum fields keep `scalar_type="str"` (permissive).

- [ ] **Step 4: Carry it to the Flag** — in `fields_to_flags` (`classify.py`), set `py_type = f.scalar_type` for scalar kind (currently `"str"` literal / enum forced to str). Enum/json/id stay `str`. `_render_type` (T2) then maps it.

- [ ] **Step 5: Run → PASS**, full suite, ruff+mypy.
- [ ] **Step 6: Commit** `feat(cli-gen): scalar body flags render with real types (int/bool/float)`.

---

## Task 4: Permissive enum choices (help listing + shell completion, no validation)

Surface enum choices so users discover valid values, WITHOUT a validating Typer `Enum` (the SDK is `LenientStrEnum`). Enum flags stay `str`; add the choices to `--help` and a shell completer.

**Files:** `render_cli.py` (`_flag_view`, per-module completer emission), `commands.py.jinja`, tests.

- [ ] **Step 1: Failing test** — `WidgetInput` has a `Literal`/enum field `mode` (per the fixture); if not, add a `Color`-typed enum field to a fixture body model with choices. Then:
```python
def test_enum_flag_lists_choices_in_help_and_accepts_unknown(emitted, monkeypatch):
    from typer.testing import CliRunner
    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade
    calls = []
    _, FakeClient = _fake_client(calls)
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: FakeClient()))
    h = CliRunner().invoke(main.app, ["create", "widget", "--help"]).output
    assert "values:" in h.lower() and "red" in h.lower()        # choices listed (adjust to fixture enum)
    # permissive: an unlisted value is ACCEPTED (SDK is LenientStrEnum), not rejected
    res = CliRunner().invoke(main.app, ["create", "widget", "--name", "w", "--color", "chartreuse"])
    assert res.exit_code == 0, res.output
```
(Adjust the enum flag name + a real choice to the fixture's enum field.)

- [ ] **Step 2: Run → FAIL** (no choices in help; no completer).

- [ ] **Step 3: Enrich `_flag_view`** for enum flags (those with `f.choices`):
```python
    choices = f.choices
    help_text = f.help
    completer_name = None
    if choices:
        listed = ", ".join(choices)
        help_text = (f"{f.help}  [values: {listed}]" if f.help else f"[values: {listed}]")
        completer_name = f"_complete_{_py_name(f.param)}"
    return {..., "help_text": help_text, "completion": choices, "completer_name": completer_name}
```

- [ ] **Step 4: Emit completers** — for each command module, render a module-level completer per enum flag (deduped by param), and reference it via `autocompletion=` (the template branch from the centralized line already does this when `f.completion`):
```jinja
{% for f in module_enum_flags %}
def {{ f.completer_name }}(incomplete: str) -> list[str]:
    return [c for c in {{ f.completion|tojson }} if c.startswith(incomplete)]
{% endfor %}
```
Collect `module_enum_flags` (deduped by `completer_name`) in `render_cli` alongside the per-module command views. The option stays `str` (render_type unchanged), so unknown values pass through to the SDK.

- [ ] **Step 5: Run → PASS**, full suite, ruff+mypy.
- [ ] **Step 6: Commit** `feat(cli-gen): enum flags list choices in --help + shell completion (permissive, no validation)`.

---

## Task 5: Config + docs — hide deferred bulk; rewrite spec grammar

**Files:** `products/prisma-browser/cli.yml`, spec, roadmap.

- [ ] **Step 1: Hide bulk in prisma cli.yml** — `phantasos cli discover prisma-browser` to list the exact bulk method keys, then:
```yaml
hide:
  # Deferred — bulk import/export returns via the future `load`/`backup` verbs (broken by the
  # list[Model] body introspection gap today). See roadmap.
  - applications.bulk_create_applications
  # (+ any other bulk_create_*/bulk_delete_* discover reports)
```
Then retighten the T1 `# TODO(T5)` test back to `unmapped == []`.

- [ ] **Step 2: Spec rewrite** — in `…design.md`, replace the `set`-aggregation grammar + dispatch sections: verb table (`create`/`patch`/`update`/`delete`/`show`/`request`), single-binding writes, `--id` required for patch/update, required+typed scalar flags, `set`/`--replace` removed, bulk deferred. **Leave the permissive-enum section as-is** (this plan honors it). Update the `Verb` literal reference.

- [ ] **Step 3: Roadmap** — decouple done; bulk → `load`/`backup` phase.
- [ ] **Step 4: Green; commit** `docs: decoupled write-verb grammar; hide deferred bulk ops`.

---

## Task 6: Real-SDK capstone — the device-group experience

**Files:** `tests/test_cli_emitted_real.py` (gated).

- [ ] **Step 1: Gated test**
```python
def test_real_device_group_crud_verbs(tmp_path, monkeypatch):
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
    assert {"create:device-group", "patch:device-group", "update:device-group",
            "delete:device-group", "show:device-group"} <= keys
    assert unmapped == []
    for k in ("create:device-group", "patch:device-group", "update:device-group"):
        assert len(next(c for c in ir.commands if c.key == k).bindings) == 1

    render_cli(ir, package="prisma_browser_cli", out_dir=tmp_path)
    sys.path.insert(0, str(tmp_path))
    for n in [n for n in sys.modules if n.startswith("prisma_browser_cli")]:
        del sys.modules[n]
    try:
        main = importlib.import_module("prisma_browser_cli.main")
        runner = CliRunner()
        h = runner.invoke(main.app, ["create", "device-group", "--help"]).output
        assert "--platform" in h and "Desktop Browser" in h          # choices listed (permissive)
        import prisma_browser.extras.facade as facade
        monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: MagicMock()))
        miss = runner.invoke(main.app, ["create", "device-group", "--name", "x"])  # no required --platform
        assert miss.exit_code != 0                                    # required enforced
        assert runner.invoke(main.app, ["patch", "device-group", "--name", "x"]).exit_code != 0  # patch needs --id
        # permissive enum: an unlisted platform is accepted (SDK is LenientStrEnum)
        ok = runner.invoke(main.app, ["create", "device-group", "--name", "x",
                                      "--platform", "Holographic Browser", "--dry-run"])
        assert ok.exit_code == 0, ok.output
    finally:
        sys.path.remove(str(tmp_path))
        for n in [n for n in sys.modules if n.startswith("prisma_browser_cli")]:
            del sys.modules[n]
```

- [ ] **Step 2: Run → PASS (not skip).** Adjust the `--help` choice assertion if Typer prints the `[values: …]` differently; keep asserting a real platform value appears and that an unlisted one is accepted.
- [ ] **Step 3: Full suite + ruff + mypy; commit** `test(cli-gen): real-SDK create/patch/update/delete device-group experience`.

---

## python-pro review (applied)
GO-WITH-CHANGES. Folded in: **(must-fix 1)** enums are PERMISSIVE — choices in help + shell completer, never a validating `Enum` (honors the documented `LenientStrEnum` decision); so no enum-class import capture and no `.value` coercion. **(must-fix 3)** required-ness is ALREADY in the IR (`fields_to_flags` sets it) — T2 is emitter-only, not an introspection change. **(must-fix 4)** `--id` required for patch/update via an `_emit` post-process (NOT `_path_flags`, which `_emit_request` shares). **(must-fix 5 / ordering)** the option-type computation is centralized once in `_flag_view.render_type` (T2), so T3/T4 only enrich it — no thrice-rewritten jinja; order is T2 (required+centralize) → T3 (scalar types) → T4 (permissive enum choices). **(should-fix)** remove stale `"replace"` from `render_cli._RESERVED` (T1); introspection must normalize `float`/`datetime` body scalars (T3) since `_scalar_type` only emits bool/int/str today; fakesdk has no bulk methods so only the real-SDK `unmapped` assertion needs the temporary T1→T5 loosening.

## Risks for the review pass
1. **Test-churn volume (T1):** confirm `grep -rn '"set"\|set:\|"del"\|--replace' tests/ src/` is clean post-T1 (incl. `app.py.jinja`, `render_cli._RESERVED`).
2. **`--id` required scope (T2):** patch/update yes; create has no id; show stays optional. Verify the post-process only flips `kind=="id"` flags.
3. **Variant split (T1/T6):** `create application <variant>` + `patch application <variant>` both single-binding; the runtime variant-discriminator injection (keys on `cmd.variant`/`variant_param`) still fires for the create POST union body — unaffected by the verb rename.
4. **`show` get/list (T1):** `_pick_binding(cmd, present)` (sans `replace`) selects get on `--id`, list otherwise.
5. **Scalar normalization (T3):** body `FieldInfo` gains a normalized `scalar_type`; datetime→str (Typer datetime parsing is brittle); confirm `runtime._coerce`'s `isinstance(v, str)` guards no-op cleanly when Typer delivers already-typed int/bool.
6. **Permissive enum (T4):** the option stays `str` so unlisted values pass through; the completer + `[values: …]` help are discoverability only. Confirm a dry-run with an unlisted enum value exits 0.
7. **bulk loosening (T1→T5):** the real-SDK `unmapped` assertion is relaxed in T1, retightened in T5 — don't forget.
