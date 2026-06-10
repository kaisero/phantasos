# CLI Generator — Decouple `set` into `create`/`patch`/`update` (+ `del`→`delete`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the aggregated `set <object>` command (which dispatched create/patch/update via a `--id`/`--replace` heuristic) with three **single-binding** write verbs — `create` (POST), `patch` (PATCH), `update` (PUT) — and rename `del`→`delete`. Single-binding commands make Typer integration clean: required model fields become real `[required]` options, enums become real typed choices, and scalars get real types.

**Architecture:** The classifier already tags each method with a `(verb, sub_verb)`. Today create/patch/update all map to `verb="set"` and aggregate into one `Command` with N bindings, dispatched at runtime. We change the verb mapping so each write maps to its OWN verb (`create`/`patch`/`update`/`delete`), so `_command_key` produces distinct keys and every write `Command` has exactly ONE binding. That removes the runtime `--replace` flag and the `_pick_binding` write-dispatch heuristic for writes, and lets the emitter render each flag with its real type / required-ness / enum choices. `show` keeps its benign get+list aggregation (read-only, `--id` selects). `request`/`load`/`backup` unchanged.

**Tech Stack:** Python 3.11–3.14, Pydantic v2, Typer, Jinja2, pytest. Runner: `uv run`.

**Spec:** `docs/superpowers/specs/2026-06-09-cli-generator-design.md` (this plan rewrites the grammar + "aggregated command model" sections). **Builds on:** branch `cli-generator` (Phases 1/2a/2b/3g/3a/3b + the .env + JSON-default fixes).

---

## Conventions (every task)
- Env: `export UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv` then `uv run …`.
- Repo `/home/ubuntu/git/phantasos`, branch `cli-generator`. **Do NOT `git checkout`/`switch`/`reset`.** Commit on the branch; `git show <sha>:<path>` for history.
- TDD; imports at top of test files; run `ruff check src/phantasos tests/` + `mypy src/phantasos/generator` before each commit.
- Fake SDK fixture `tests/fixtures/fakesdk/`; real SDK `/home/ubuntu/git/prisma-browser-sdk`.

## Scope decisions (baked in — flagged for review)
1. **Three write verbs, single binding each:** `create` (POST), `patch` (PATCH, `--id` + all-optional), `update` (PUT, `--id` + required like create). Emitted only where the SDK method exists per object.
2. **`del`→`delete`** everywhere (verb name, registration, classifier, docs, tests).
3. **`set` and `--replace` removed.** No back-compat alias (CLI unreleased).
4. **`show` unchanged** — keeps get+list under one command, `--id` selects get. (Read-only; no required/destructive tension, so no need to split.)
5. **`bulk_create`/`bulk_delete` DEFERRED.** They can't be single-binding alongside single create/delete on the same object, and are already broken by the `list[Model]` body gap. They're removed from the classifier and `hide:`-listed for prisma, to return under the future `load`/`backup` verbs. (Documented in T5.)
6. **Variants carry over per-method:** `set application custom` → `create application custom` (POST binding) + `patch application custom` (PATCH binding). The `cli.yml variants:` map is keyed by method, so it needs no change.

## File structure (this plan)
- `src/phantasos/generator/cli/ir.py` — `Verb` literal; `Command.action` stays; (no new Flag fields until T3).
- `src/phantasos/generator/cli/classify.py` — `_VERB_PREFIXES` remap; drop bulk; `_emit` unchanged mechanics (now produces single-binding write commands); `Flag.required` (T2); enum import capture (T3).
- `src/phantasos/generator/cli/inventory.py` + `introspect.py` — capture enum class import path (T3).
- `src/phantasos/generator/cli/render_cli.py` + `templates/_generated/commands.py.jinja` — typed/required/enum option emission (T2–T4).
- `src/phantasos/generator/cli/templates/_generated/runtime.py.jinja` — drop `replace`; enum `.value` coercion (T3).
- `src/phantasos/generator/cli/templates/_generated/app.py.jinja` — `_VERBS`; drop `--replace` option.
- `products/prisma-browser/cli.yml`, spec, roadmap — T5.
- Tests across `test_cli_classify/emitted/command/emitted_real`.

---

## Task 1: Decouple the write verbs + rename `del`→`delete` (core, atomic)

This is the cohesive core: it touches the verb literal, the classifier mapping, registration, and the runtime dispatch together, plus updates all existing tests' verb expectations. After it, every write command is single-binding and the suite is green.

**Files:** `ir.py`, `classify.py`, `templates/_generated/runtime.py.jinja`, `templates/_generated/app.py.jinja`, and existing tests.

- [ ] **Step 1: Update `Verb` in `ir.py`**
```python
Verb = Literal["create", "patch", "update", "delete", "show", "request", "load", "backup"]
```
(Remove `"set"`, `"del"`. `SubVerb` stays as-is — bindings still carry `create/patch/update/get/list/delete/action`.)

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
Removed the `bulk_create_`/`bulk_delete_` rows (deferred — they now return `None` from `classify_name`, i.e. "unmapped" unless hidden; T5 hides them for prisma). No other change to `classify_name` or `_emit` — because `_command_key` includes the verb, create/patch/update for one object now produce three distinct keys → three single-binding commands automatically.

- [ ] **Step 3: Drop `--replace` from the runtime** (`runtime.py.jinja`)
  - `run(...)`: remove the `replace: bool = False` parameter.
  - `_pick_binding(cmd, present, replace)` → `_pick_binding(cmd, present)`; delete the `if replace:` block (lines ~84–86). It now just picks the binding whose `requires` ⊆ `present` with the most specific match (still correct for `show` get vs list via `--id`; write commands have a single binding so it returns that one).
  - Remove `replace` from the `run(...)` call sites / the `_SUBVERB_PRIORITY` update tiebreak comment.

- [ ] **Step 4: Update registration** (`app.py.jinja`)
```jinja
_VERBS = ["create", "patch", "update", "delete", "show", "request"]
```
  - Remove the injected `--replace` option line (`replace: bool = typer.Option(False, "--replace")`) and drop `replace=replace` from the `run(...)` call in the command body template (`commands.py.jinja`).

- [ ] **Step 5: Update `commands.py.jinja`** — remove the `--replace` option + its pass-through to `run(...)`. (Keep `--all`, `--dry-run`, `--verbose`, `--output`.)

- [ ] **Step 6: Migrate existing tests.** Grep and update verb expectations across the suite:
  - `grep -rn '"set"\|set:\|"del"\|del:\|--replace\|replace=' tests/` — for each:
    - command-key assertions: `set:device-group` → `create:device-group` / `patch:device-group` / `update:device-group` (split — a former `set:X` with create+patch+update bindings becomes three single-binding commands); `del:X` → `delete:X`.
    - CliRunner invocations: `["set", obj, ...]` (create) → `["create", obj, ...]`; `["set", obj, "--id", ...]` (patch) → `["patch", obj, "--id", ...]`; `["set", obj, "--id", "--replace", ...]` → `["update", obj, "--id", ...]`; `["del", ...]` → `["delete", ...]`.
    - binding assertions: a former `set:application:custom` (bindings create+patch) → `create:application:custom` (1 binding, sub_verb create) and `patch:application:custom` (1 binding, sub_verb patch). Update `test_cli_emitted_real.py::test_real_cli_yml_produces_variant_commands_and_no_unmapped` accordingly (assert `create:application:custom` + `patch:application:custom`, each single-binding).
    - Any test asserting `set` is a verb group → `create`/`patch`/`update`.
    - bulk: tests asserting a `set <obj>` bulk leaf or `bulk_create` binding — remove/adjust (bulk deferred). If the fakesdk fixture has a `bulk_create_*`/`bulk_delete_*` method, it now classifies as unmapped; update the affected test configs to `hide` it OR assert it in `unmapped` (whichever the test intends). Confirm `tests/test_cli_emitted_real.py` `unmapped == []` still holds after T5 hides prisma's bulk ops — but T5 runs later, so in THIS task, temporarily allow prisma's bulk ops in `unmapped` (the real-SDK test may need `unmapped` to contain the 1–2 bulk ops until T5). Mark that assertion with a `# TODO(T5): hidden in cli.yml` and tighten it in T5. (State clearly in your report which tests you touched and why.)

- [ ] **Step 7: Run + iterate to green**
`UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/ -q` — fix until green. Then `ruff check src/phantasos tests/` + `mypy src/phantasos/generator`.

- [ ] **Step 8: Sanity-build the real CLI**
`UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run phantasos cli build prisma-browser 2>&1 | tail -2` — should emit; `discover` shows `create device-group`, `patch device-group`, `update device-group`, `delete <obj>`. (Bulk ops may show an `unmapped` note until T5 — OK for now.)

- [ ] **Step 9: Commit**
```bash
git add -A
git commit -m "refactor(cli-gen): decouple set into create/patch/update single-binding verbs; del->delete; drop --replace"
```

---

## Task 2: Required model fields → real `[required]` Typer options

Now that write commands are single-binding, a field required by `create`/`update`'s body model can be a true required option.

**Files:** `classify.py` (`_body_flags_for`), `render_cli.py` (`_flag_view`), `commands.py.jinja`, tests.

- [ ] **Step 1: Failing test** (append to `tests/test_cli_emitted.py`)
```python
def test_create_required_fields_are_required(emitted):
    # The fakesdk create_widget body (WidgetInput) has a required `name`.
    code = (EMITTED_DIR / "fakesdk_cli" / "_generated" / "commands" / "widgets.py").read_text()
    # required field → typer.Option(...) (Ellipsis), optional → typer.Option(None)
    import re
    create_fn = re.search(r"def create_widget\(.*?\n\)", code, re.S).group(0)
    assert "typer.Option(..." in create_fn        # at least one required option
```
(Adjust `EMITTED_DIR` to the fixture's emitted path used by the `emitted` fixture — find how other tests reference emitted files. If the fixture doesn't expose the dir, render via `render_cli` to a tmp dir in the test instead and read the file.)

Also a behavioral test:
```python
def test_create_missing_required_errors_cleanly(emitted, monkeypatch):
    from typer.testing import CliRunner
    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: object()))
    res = CliRunner().invoke(main.app, ["create", "widget"])   # missing required --name
    assert res.exit_code != 0
    assert "Missing option" in res.output or "required" in res.output.lower()
```

- [ ] **Step 2: Run → FAIL** (all flags currently emit `Optional[str] = typer.Option(None, …)`).

- [ ] **Step 3: Propagate `required` into the Flag** — in `classify.py` `_body_flags_for`, stop hardcoding `required=False`; use the field's real required-ness:
```python
            flags.append(Flag(name=_flag_name(p.name), param=p.name, py_type=py_type,
                              kind=kind, required=p.required, help=p.description,
                              choices=p.enum_values))
```
(The `--id` path flag stays `required=False` at the Flag level — `--id` requiredness is handled separately for patch/update; see note. `p` here is a `FieldInfo` which has `.required`.)
**Important — patch keeps everything optional:** `patch`'s body model (`*PatchRequest`) already has all-optional fields, so `p.required` is naturally `False` for patch. `create`/`update` bodies carry the real required flags. No verb-special-casing needed — it falls out of the per-binding model. **`--id` for patch/update:** mark the id path flag required for `patch`/`update` commands (you can't patch/update without an id). Set the id flag's `required=True` when the command verb is `patch` or `update` (do this in `_path_flags`/`_emit` where the verb is known, or post-process in `_emit`). Add a test that `patch widget` without `--id` errors.

- [ ] **Step 4: Surface `required` in the emitter** — `_flag_view` returns `required` + `py_type`; `commands.py.jinja` emits required vs optional:
```python
# render_cli._flag_view
def _flag_view(f: Flag) -> dict[str, object]:
    return {"name": f.name, "param": f.param, "py_name": _py_name(f.param),
            "help": f.help, "required": f.required, "py_type": f.py_type,
            "kind": f.kind, "choices": f.choices}
```
```jinja
{%- for f in c.all_flags %}
{%- if f.required %}
    {{ f.py_name }}: str = typer.Option(..., {{ f.name|tojson }}{% if f.help %}, help={{ f.help|tojson }}{% endif %}),
{%- else %}
    {{ f.py_name }}: Optional[str] = typer.Option(None, {{ f.name|tojson }}{% if f.help %}, help={{ f.help|tojson }}{% endif %}),
{%- endif %}
{%- endfor %}
```
(Types stay `str` here — real scalar/enum typing comes in T3/T4. This task only adds required-ness.)

- [ ] **Step 5: Run → PASS**, full suite green, ruff+mypy clean.
- [ ] **Step 6: Commit** `feat(cli-gen): required model fields render as required CLI options (create/update)`.

---

## Task 3: Enum fields → real Typer enum types (shown + validated)

**Files:** `inventory.py`, `introspect.py`, `ir.py` (Flag), `classify.py`, `render_cli.py`, `commands.py.jinja`, `runtime.py.jinja`, tests.

- [ ] **Step 1: Failing test** (`tests/test_cli_emitted_real.py`, gated; the real `device-group` create has enum `platform`)
```python
def test_create_device_group_platform_is_enum(tmp_path):
    if not REAL_SDK.exists():
        pytest.skip("prisma-browser-sdk not built")
    from phantasos.generator.cli.cliconfig import load_cli_config
    try:
        inv = introspect("prisma_browser", REAL_SDK)
    except ImportError as exc:
        pytest.skip(str(exc))
    ir, _ = build_cli_ir(inv, load_cli_config(Path("products/prisma-browser/cli.yml")))
    render_cli(ir, package="prisma_browser_cli", out_dir=tmp_path)
    code = (tmp_path / "prisma_browser_cli" / "_generated" / "commands" / "device_groups.py").read_text()
    assert "DeviceGroupPlatform" in code           # the enum class imported + used as the option type
    assert "from prisma_browser.models import" in code
```
And a CliRunner test that an invalid `--platform` is rejected and `--help` shows the choices:
```python
    # (in an emitted-fakesdk test if the fixture has an enum field; else assert via real build help)
```
(If the fakesdk fixture lacks an enum body field, add one: give `WidgetInput` a `mode: Literal[...]` or an enum field — check; the summary says WidgetInput has a Literal `mode`. Use that for a fast emitted CliRunner enum test: `create widget --mode bogus` → exit≠0; `--help` shows `[a|b]`.)

- [ ] **Step 2: Run → FAIL** (enum emitted as `str`/TEXT, no import).

- [ ] **Step 3: Capture the enum import path in introspection** — `inventory.FieldInfo` and `ParamInfo` gain:
```python
    enum_import: str | None = None   # e.g. "prisma_browser.models"
    enum_class: str | None = None    # e.g. "DeviceGroupPlatform"
```
In `introspect.py`, when a field/param annotation is (or unwraps to) an `enum.Enum` subclass, record `enum_class = cls.__name__` and `enum_import = cls.__module__`. (Keep `enum_values` too, for help/fallback.)

- [ ] **Step 4: Carry it onto `Flag`** — `ir.Flag` gains `enum_import: str | None = None`, `enum_class: str | None = None`; `classify._body_flags_for`/`_query_flags` set them from the field/param. For enum flags set `py_type = f.enum_class` (the rendered annotation is now the enum class name).

- [ ] **Step 5: Emit enum imports + typed options** — in `render_cli`, collect per-command-module the set of `(enum_import, enum_class)` across its flags and pass to the template; `commands.py.jinja` emits `from <enum_import> import <enum_class>` (deduped) at the module top, and the option becomes:
```jinja
{%- if f.enum_class %}
    {{ f.py_name }}: {% if not f.required %}Optional[{% endif %}{{ f.enum_class }}{% if not f.required %}]{% endif %} = typer.Option({% if f.required %}...{% else %}None{% endif %}, {{ f.name|tojson }}{% if f.help %}, help={{ f.help|tojson }}{% endif %}),
{%- elif f.required %} … (T2 required str branch) …
```
(Typer renders an Enum option as `[val1|val2|…]` and validates; values with spaces are quoted by the user.)

- [ ] **Step 6: Coerce enum members in the runtime** — when building `path`/`body`/`query` dicts, a Typer enum option arrives as an `Enum` member; convert to its `.value` so the SDK/body model gets the plain value. In `runtime.py.jinja` where kwargs/body are assembled, add a small helper:
```python
def _unwrap(v):
    import enum
    return v.value if isinstance(v, enum.Enum) else v
```
and apply `_unwrap` to each path/body/query value. (Pydantic would also accept the member, but `.value` keeps dry-run output and JSON clean.)

- [ ] **Step 7: Run → PASS**, full suite, ruff+mypy. Rebuild real CLI: `… phantasos cli build prisma-browser` then `prisma_browser_cli ... create device-group --help` shows `--platform [Desktop Browser|Mobile Browser|Browser Extension|Chromebook]` and `--name`/`--platform` as required. (You can't run the binary here without sync, but assert via the emitted file + a CliRunner test on the fixture enum.)
- [ ] **Step 8: Commit** `feat(cli-gen): enum body/query fields render as typed Typer choices`.

---

## Task 4: Typed scalar flags (int/bool/float/datetime → real types)

**Files:** `render_cli.py`, `commands.py.jinja`, tests.

- [ ] **Step 1: Failing test** — pick a fixture scalar non-str field (e.g. an int/bool on a body model; add one to `WidgetInput` if none exists, e.g. `priority: int` / `enabled: bool`). Assert the emitted option uses the real type:
```python
def test_scalar_flags_use_real_types(emitted):
    code = (… widgets.py …).read_text()
    assert "Optional[int]" in code or ": int " in code   # priority renders as int, not str
```
And a CliRunner test that `--priority abc` (non-int) is rejected by Typer.

- [ ] **Step 2: Run → FAIL** (scalars emit as `str`).

- [ ] **Step 3: Emit `py_type` for scalar/id kinds** — in `commands.py.jinja`, for `f.kind in ("scalar",)` use `f.py_type` as the annotation (mapping the IR's `scalar_type` strings — `int`/`float`/`bool`/`str`/`datetime`→`str`) instead of hardcoding `str`. Keep `kind in ("json",)` (complex/list/union/nested) and `--id` as `str` (the user passes JSON / an id string). Centralize the annotation choice in `_flag_view` (compute a `render_type` field: enum→class, json→`str`, scalar→mapped py_type) so the template stays simple. Map unknown/`datetime` scalar types to `str` (safe).

- [ ] **Step 4: Run → PASS**, full suite, ruff+mypy.
- [ ] **Step 5: Commit** `feat(cli-gen): scalar flags render with real types (int/bool/float)`.

---

## Task 5: Config + docs — hide deferred bulk; rewrite spec grammar

**Files:** `products/prisma-browser/cli.yml`, spec, roadmap.

- [ ] **Step 1: Hide bulk in prisma cli.yml** — add the bulk ops to a `hide:` block so the real build is clean (0 unmapped) and the deferred-bulk decision is explicit:
```yaml
hide:
  # Deferred — bulk import/export returns via the future `load`/`backup` verbs (broken by the
  # list[Model] body introspection gap today). See roadmap.
  - applications.bulk_create_applications
  # (+ any other bulk_create_*/bulk_delete_* discover reports)
```
Run `phantasos cli discover prisma-browser` to list the exact bulk method keys; add each. Then tighten the T1 `# TODO(T5)` test back to `unmapped == []`.

- [ ] **Step 2: Spec rewrite** — in `docs/superpowers/specs/2026-06-09-cli-generator-design.md`, replace the `set`-aggregation grammar + "Variant"/dispatch sections: document the verb table (`create`/`patch`/`update`/`delete`/`show`/`request`), single-binding writes, required+enum+typed flags, `--id` required for patch/update, `set`/`--replace` removed, bulk deferred. Update the `Verb` literal reference.

- [ ] **Step 3: Roadmap** — note the decouple is done; bulk → `load`/`backup` phase.

- [ ] **Step 4: Full suite green; commit** `docs: decoupled write-verb grammar; hide deferred bulk ops`.

---

## Task 6: Real-SDK capstone — the device-group experience

**Files:** `tests/test_cli_emitted_real.py` (gated).

- [ ] **Step 1: Gated test** proving the end state on the real SDK:
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
    # each write command is single-binding
    for k in ("create:device-group", "patch:device-group", "update:device-group"):
        assert len([c for c in ir.commands if c.key == k][0].bindings) == 1

    render_cli(ir, package="prisma_browser_cli", out_dir=tmp_path)
    sys.path.insert(0, str(tmp_path))
    for n in [n for n in sys.modules if n.startswith("prisma_browser_cli")]:
        del sys.modules[n]
    try:
        main = importlib.import_module("prisma_browser_cli.main")
        runner = CliRunner()
        # required + enum surfaced in help
        h = runner.invoke(main.app, ["create", "device-group", "--help"]).output
        assert "--platform" in h and "Desktop Browser" in h
        # missing required → clean error
        import prisma_browser.extras.facade as facade
        monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: MagicMock()))
        miss = runner.invoke(main.app, ["create", "device-group", "--name", "x"])  # no --platform
        assert miss.exit_code != 0
        # patch requires --id
        assert runner.invoke(main.app, ["patch", "device-group", "--name", "x"]).exit_code != 0
    finally:
        sys.path.remove(str(tmp_path))
        for n in [n for n in sys.modules if n.startswith("prisma_browser_cli")]:
            del sys.modules[n]
```

- [ ] **Step 2: Run → PASS (not skip).** If `--help` enum rendering differs (Typer version), adjust the assertion to match how Typer prints enum choices (still assert a real platform value appears).
- [ ] **Step 3: Full suite + ruff + mypy; commit** `test(cli-gen): real-SDK create/patch/update/delete device-group experience`.

---

## Self-review (completed during authoring)
- **Spec coverage:** decouple (T1), required (T2), enum (T3), scalar types (T4), del→delete (T1), drop set/--replace (T1), bulk deferred + spec/roadmap (T5), real-SDK validation (T6).
- **Placeholder scan:** none — concrete code per step. T1 Step 6 + T2 Step 1 note real unknowns (exact test sites; the fixture's emitted-dir accessor) with a discover/grep-first instruction rather than a guess.
- **Type/name consistency:** `Verb` gains create/patch/update/delete (T1); `_VERB_PREFIXES` maps to them (T1); `Flag` gains `enum_import`/`enum_class` (T3); `_flag_view` returns required/py_type/kind/choices/enum (T2–T4) consumed by `commands.py.jinja`; `_unwrap` (T3) used in runtime body/path/query assembly; `_VERBS` (T1) matches the emitted verbs; bulk hidden (T5) makes `unmapped == []` true for T6.

## Risks for the review pass
1. **Test churn volume (T1):** many `set:`/`del:`/`--replace` references. Risk of a missed site → confirm full green + `grep -rn '"set"\|set:\|"del"\|--replace' tests/ src/` returns nothing stale after T1.
2. **`--id` required for patch/update (T2):** ensure the id flag is required for patch/update but NOT for create (create has no id) and NOT over-required for show. Verify where verb is known when building path flags.
3. **Enum with spaces (T3):** Typer/Click choice rendering + the user quoting `"Desktop Browser"`; `_unwrap` → `.value`. Confirm a real dispatch passes the value the SDK expects.
4. **Variants under the split (T1/T6):** `create application <variant>` + `patch application <variant>` both exist and are single-binding; the variant discriminator injection (variant_param) still fires for create (POST union body) — confirm the runtime still injects it (that logic keys on `cmd.variant`/`variant_param`, unaffected by the verb rename).
5. **`show` still aggregates get/list** — confirm `_pick_binding` (sans `replace`) still selects get on `--id`, list otherwise.
6. **bulk removal → unmapped during T1:** the real-SDK `unmapped==[]` assertion is temporarily loosened in T1 and retightened in T5 — don't forget T5.
