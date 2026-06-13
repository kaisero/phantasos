# CLI Generator — Phase 3b: the `request` namespace (non-CRUD actions) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Emit `request <object> <action>` commands from the per-product `cli.yml` `request:` mappings, so the ~16 non-CRUD operations (suspend/resume/restore/archive/force-reauth, publish, reorder-positions, user-request action/revoke) become runnable instead of merely reserved.

**Architecture:** A `request:` mapping `{object, action}` becomes a `Command` with `verb="request"`, `object=<object>`, and a **dedicated `action` field** (separate from the oneOf `variant` field). Each request command has ONE binding (the SDK method), built from its path id (if any) + body model. The emitter treats the leaf path segment as "`variant` or `action`" (both render as `<object> <leaf>`), so `request <object> <action>` registers exactly like a variant `set` — but the **runtime never branches on `action`** (it only looks at `variant`/`variant_param`), so the oneOf-discriminator logic provably never touches request commands. `build_cli_ir` stops skipping `cfg.request` and emits these commands; the emitted app gains a `request` verb sub-app.

**Tech Stack:** Python 3.11–3.14, Pydantic v2, Typer, Jinja2, pytest. Test runner: `uv run`.

**Spec:** `docs/superpowers/specs/2026-06-09-cli-generator-design.md` (verb-first `request <object> <action>`; `cli.yml request:` block). **Builds on:** Phases 1/2a/2b/3g/3a on branch `cli-generator`. The real `products/prisma-browser/cli.yml` already has the 16 `request:` mappings (Phase 3a) — this phase makes them emit.

---

## Conventions (every task)
- Env: `export UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv` then `uv run …`.
- Repo `/home/ubuntu/git/phantasos`, branch `cli-generator`. **Do NOT `git checkout`/`switch`/`reset`** — commit on the branch; `git show <sha>:<path>` for history.
- TDD; test imports at TOP of files; run `ruff check src/phantasos tests/` + `mypy src/phantasos/generator src/phantasos/cli.py` before each commit.
- Fake SDK fixture `tests/fixtures/fakesdk/`; real SDK `/home/ubuntu/git/prisma-browser-sdk`.

## Key design decisions
1. **Dedicated `Command.action: str | None` field** (NOT overloading `variant`) — chosen for IR clarity: `variant` stays exactly "the oneOf discriminator value," and the runtime's discriminator injection (`if cmd.variant and cmd.variant_param`) is provably never reached for request commands (their `variant` is `None`). The cost vs. the overload: the **emitter** (`render_cli`) must treat the leaf command segment as "`variant` or `action`" in three places (`variant_groups`, `_command_view.typer_path`, `_func_name`), and `discover.render_table` must show it. The runtime and `app.py` registration need NO action-specific code (they're segment-agnostic / variant-only).
2. **`MethodBinding.sub_verb` needs a value for non-CRUD methods.** Add `"action"` to the `SubVerb` Literal. Request bindings get `sub_verb="action"`; dispatch is single-binding so it's not used for selection; `paginated` stays False.
3. **Request body** is built from the method's body model directly (no oneOf wrapper, no discriminator). Existing `_body_flags_for` + runtime `_build_body` handle it. Path `id` (when present, e.g. action/revoke) becomes `--id`.

## File structure (this phase)
- Modify: `tests/fixtures/fakesdk/fakesdk/api.py` — add 2 request-able methods (body-only; id+body).
- Modify: `src/phantasos/generator/cli/ir.py` — `Command` gains `action: str | None`; `SubVerb` gains `"action"`.
- Modify: `src/phantasos/generator/cli/classify.py` — `_SUBVERB_PRIORITY["action"]`; `build_cli_ir` emits request commands (`_emit_request`).
- Modify: `src/phantasos/generator/cli/render_cli.py` — `variant_groups`, `_command_view.typer_path`, `_func_name` treat the leaf segment as `variant or action`.
- Modify: `src/phantasos/generator/cli/discover.py` — `render_table` shows the action segment.
- Modify: `src/phantasos/generator/cli/templates/_generated/app.py.jinja` — `_VERBS` gains `"request"`.
- Modify: `docs/superpowers/specs/2026-06-09-cli-generator-design.md` + roadmap — request namespace now emitted.
- Tests: `tests/test_cli_classify.py`, `tests/test_cli_emitted.py`, `tests/test_cli_emitted_real.py`.

---

## Task 1: Fixture — request-able methods

Add two non-CRUD methods to the fake SDK so request emission is testable: one body-only, one id+body (mirroring the real `suspend_devices` and `revoke_user_request` shapes).

**Files:**
- Modify: `tests/fixtures/fakesdk/fakesdk/api.py`

- [ ] **Step 1: Add the methods to `WidgetsApi`** (in `tests/fixtures/fakesdk/fakesdk/api.py`):

```python
    def suspend_widget(self, widget_input: WidgetInput):
        """Suspend widgets (body-only action)."""

    def revoke_widget(self, id: str, widget_input: WidgetInput):
        """Revoke a widget grant (id + body action)."""
```

(They reuse `WidgetInput` as the body model — fine for a fixture. `WidgetInput` is already imported in `api.py`.)

- [ ] **Step 2: Verify the fixture still imports + existing introspect tests pass**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/test_cli_introspect.py -q`
Expected: PASS (the new methods are introspected but unmapped by the classifier — no existing assertion breaks; they only matter once mapped under `request:`).

- [ ] **Step 3: Commit**

```bash
git add tests/fixtures/fakesdk/fakesdk/api.py
git commit -m "test(cli-gen): fixture gains request-able methods (suspend_widget, revoke_widget)"
```

---

## Task 2: `SubVerb` += "action"; `build_cli_ir` emits request commands

**Files:**
- Modify: `src/phantasos/generator/cli/ir.py`
- Modify: `src/phantasos/generator/cli/classify.py`
- Test: `tests/test_cli_classify.py`

- [ ] **Step 1: Write the failing test** (append to `tests/test_cli_classify.py`; `introspect`, `build_cli_ir`, `CliConfig`, `FIXTURE` already imported at top)

```python
def test_build_cli_ir_emits_request_commands():
    from phantasos.generator.cli.cliconfig import RequestMapping

    inv = introspect("fakesdk", FIXTURE)
    cfg = CliConfig(request={
        "widgets.suspend_widget": RequestMapping(object="widget", action="suspend"),
        "widgets.revoke_widget": RequestMapping(object="widget", action="revoke"),
    })
    ir, unmapped = build_cli_ir(inv, cfg)
    by_key = {c.key: c for c in ir.commands}

    # both mappings became request commands (verb=request, dedicated `action` field; variant=None)
    assert "request:widget:suspend" in by_key
    assert "request:widget:revoke" in by_key
    susp = by_key["request:widget:suspend"]
    assert susp.verb == "request" and susp.object == "widget"
    assert susp.action == "suspend"                # dedicated action field
    assert susp.variant is None and susp.variant_param is None  # NOT a oneOf variant
    assert [b.sub_verb for b in susp.bindings] == ["action"]
    assert susp.bindings[0].sdk_method == "suspend_widget"
    # body-only action: body flags from the model, no --id
    assert any(f.name == "--name" for f in susp.body_flags)
    assert not any(f.kind == "id" for f in susp.path_params)
    # id+body action: --id present
    rev = by_key["request:widget:revoke"]
    assert any(f.kind == "id" for f in rev.path_params)
    assert rev.bindings[0].sdk_method == "revoke_widget"
    # request ops are NOT reported as unmapped
    assert "widgets.suspend_widget" not in unmapped
    assert "widgets.revoke_widget" not in unmapped
    # N2: all command keys are distinct (no accidental request/CRUD key collision)
    keys = [c.key for c in ir.commands]
    assert len(keys) == len(set(keys))
```

- [ ] **Step 2: Run → FAIL**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/test_cli_classify.py::test_build_cli_ir_emits_request_commands -v`
Expected: FAIL — `request:widget:suspend` not in commands (currently `cfg.request` ops are skipped).

- [ ] **Step 3: In `src/phantasos/generator/cli/ir.py`, add `"action"` to `SubVerb` AND an `action` field to `Command`:**

```python
SubVerb = Literal[
    "create", "patch", "update", "get", "list", "delete",
    "bulk_create", "bulk_delete", "action",
]
```
In the `Command` model, add (right after the `variant` field):
```python
    action: str | None = None  # request-namespace action segment (e.g. "suspend"); distinct
                               # from `variant` (oneOf discriminator). Renders as <object> <action>.
```

- [ ] **Step 4: Add `"action"` to `_SUBVERB_PRIORITY` and emit request commands** in `src/phantasos/generator/cli/classify.py`.

Add `"action"` to the priority dict (any value; request commands are single-binding so it's never used for selection):
```python
_SUBVERB_PRIORITY = {
    "patch": 0, "create": 1, "update": 2, "delete": 3,
    "get": 4, "list": 5, "bulk_create": 6, "bulk_delete": 7, "action": 8,
}
```

In `build_cli_ir`, replace the request-skip branch:
```python
        if key0 in cfg.request:
            continue  # request-namespace handled in Phase 3
```
with emission of a request command. Add a helper near `_emit` and call it:
Mirror the existing `_emit` idiom (review S1 — clearer than create-in-`if`/append-after, and it merges flags on a collision instead of dropping them):
```python
def _emit_request(groups: dict[str, "Command"], op: "OperationInfo",
                  mapping: "RequestMapping") -> None:
    key = _command_key("request", mapping.object, mapping.action)
    id_param = detect_id_param(op.params)
    body_info = _body_param_info(op)
    body_model = body_info.body_model if body_info else None
    binding = MethodBinding(
        sdk_method=op.method, sub_verb="action",
        requires=_required_path_names(op.params),
        body_param=body_info.name if body_info else None,
        body_model=body_model, body_wrapper=None,
    )
    cmd = groups.get(key)
    if cmd is None:
        cmd = Command(
            verb="request", object=mapping.object, action=mapping.action,
            variant=None, variant_param=None, key=key, sdk_resource=op.resource,
            path_params=_path_flags(op.params, id_param),
            body_flags=_body_flags_for(op, body_model),
            query_flags=_query_flags(op.params),
            summary=op.summary, description=op.description, paginated=False,
        )
        groups[key] = cmd
    else:  # two ops → same (object, action): merge flags, both bindings kept
        _merge_flags(cmd.path_params, _path_flags(op.params, id_param))
        _merge_flags(cmd.body_flags, _body_flags_for(op, body_model))
        _merge_flags(cmd.query_flags, _query_flags(op.params))
    cmd.bindings.append(binding)
```
(`_merge_flags` already exists in classify.py.)
(Imports: `RequestMapping` from `.cliconfig`, `OperationInfo` already imported. Add `from .cliconfig import CliConfig, RequestMapping, VariantMap` — merge with the existing `.cliconfig` import.)

And in the `build_cli_ir` loop, where the old `continue` was:
```python
        if key0 in cfg.request:
            _emit_request(groups, op, cfg.request[key0])
            continue
```
Keep the precedence order: `hide` first, then this `request` branch must come BEFORE the `cls is None → unmapped` check so request-mapped ops (even ones the classifier skips, like `*_positions`) are emitted, not flagged unmapped. CONCRETELY, the current order is: `if key0 in cfg.hide: continue` → `ov = cfg.override.get(key0)` → `cls = classify_name(...)` → `if cls is None and key0 not in cfg.request: unmapped; continue` → `if key0 in cfg.request: continue`. Reorder so the request branch fires first:
```python
        if key0 in cfg.hide:
            continue
        if key0 in cfg.request:
            _emit_request(groups, op, cfg.request[key0])
            continue
        ov = cfg.override.get(key0)
        cls = classify_name(op.method)
        if cls is None:
            unmapped.append(key0)
            continue
        ...
```
(This drops the now-redundant `and key0 not in cfg.request` from the unmapped check — request keys are handled above.)

- [ ] **Step 5: Run → PASS**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/test_cli_classify.py -v`
Expected: the new test passes; all existing classify tests still pass (the reorder is behavior-preserving — `cfg.request` ops were skipped before and are now emitted; non-request ops are unaffected).

- [ ] **Step 6: Lint, type-check, full suite, commit**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run ruff check src/phantasos/generator tests/ && UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run mypy src/phantasos/generator && UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/ -q`
Expected: all green. NOTE: `tests/test_cli_discover.py`'s real-SDK smoke and `tests/test_cli_emitted_real.py::test_real_cli_yml_produces_variant_commands_and_no_unmapped` assert `unmapped == []`; with the real cli.yml's request mappings now EMITTED (not skipped), `unmapped` is still `[]` — but the command COUNT rises (request commands added). If any test asserted an exact command count or the ABSENCE of request commands, update it to reflect that request commands now exist. (The variant test only checks `set:application:*` + `unmapped == []`, both still true.)

```bash
git add src/phantasos/generator/cli/ir.py src/phantasos/generator/cli/classify.py tests/test_cli_classify.py
git commit -m "feat(cli-gen): build_cli_ir emits request <object> <action> commands from cli.yml"
```

---

## Task 3: Emit + register the `request` verb sub-app

**Files:**
- Modify: `src/phantasos/generator/cli/templates/_generated/app.py.jinja`
- Test: `tests/test_cli_emitted.py`

- [ ] **Step 1: Write the failing test** (append to `tests/test_cli_emitted.py`; `_fake_client`, `emitted` fixture, `monkeypatch` available)

The `emitted` fixture builds the fakesdk CLI; it must include the request mappings. Check how `emitted` builds its `CliConfig` (it sets gizmo variants). Add request mappings there OR add a dedicated fixture. To keep `emitted` shared, extend its `CliConfig` to also include the two request mappings (so request commands are emitted in the fakesdk CLI). Then:

```python
def test_cli_runner_request_actions(emitted, monkeypatch):
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    import fakesdk.extras.facade as facade

    calls: list = []
    _, FakeClient = _fake_client(calls)
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: FakeClient()))

    r = CliRunner()
    # M1: `request` is a registered top-level verb group
    assert "request" in r.invoke(main.app, ["--help"]).output
    # body-only action: request widget suspend --name X
    res = r.invoke(main.app, ["request", "widget", "suspend", "--name", "W", "--output", "json"])
    assert res.exit_code == 0, res.output
    # id+body action: request widget revoke --id W9 --name X
    res2 = r.invoke(main.app, ["request", "widget", "revoke", "--id", "W9", "--name", "X",
                               "--output", "json"])
    assert res2.exit_code == 0, res2.output

    names = [c[0] for c in calls]
    assert "suspend_widget" in names
    assert "revoke_widget" in names
    revoke_call = next(kw for n, kw in calls if n == "revoke_widget")
    assert revoke_call.get("id") == "W9"
```

To make `emitted` produce request commands, update the `emitted` fixture's `CliConfig(...)` (in `tests/test_cli_emitted.py`) to add:
```python
        request={
            "widgets.suspend_widget": RequestMapping(object="widget", action="suspend"),
            "widgets.revoke_widget": RequestMapping(object="widget", action="revoke"),
        },
```
and import `RequestMapping` at the top: `from phantasos.generator.cli.cliconfig import CliConfig, RequestMapping, VariantMap` (merge with the existing cliconfig import).

- [ ] **Step 2: Run → FAIL**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/test_cli_emitted.py::test_cli_runner_request_actions -v`
Expected: FAIL — `request` is not a registered verb (`No such command 'request'`).

- [ ] **Step 3a: Make the emitter `action`-aware** in `src/phantasos/generator/cli/render_cli.py`. The leaf command segment is now "`variant` or `action`". Add a tiny helper and use it in `_func_name`, `_command_view.typer_path`, and the `variant_groups` set.

Add near `_func_name`:
```python
def _leaf(c: Command) -> str | None:
    """The third command segment: a oneOf variant OR a request action (mutually exclusive)."""
    return c.variant or c.action
```
Change `_func_name` to use it:
```python
def _func_name(c: Command) -> str:
    base = f"{c.verb}_{c.object}".replace("-", "_")
    leaf = _leaf(c)
    return f"{base}_{leaf}".replace("-", "_") if leaf else base
```
Change `_command_view`'s `typer_path` head:
```python
    leaf = _leaf(c)
    if leaf:
        typer_path: list[str] = [c.object, leaf]
    elif (c.verb, c.object) in variant_groups:
        typer_path = [c.object, _primary_sub_verb(c)]
    else:
        typer_path = [c.object]
```
Change the `variant_groups` comprehension (where it's built before the `_command_view` calls):
```python
    variant_groups: set[tuple[str, str]] = {
        (c.verb, c.object) for c in ir.commands if c.variant or c.action
    }
```
(`app.py.jinja`'s registration is segment-agnostic — it walks `typer_path` — so it needs no change beyond `_VERBS`.)

- [ ] **Step 3b: Show the action segment in `discover`** — in `src/phantasos/generator/cli/discover.py`'s `render_table`, the per-command target line currently appends `c.variant`; make it append `c.variant or c.action`:
```python
        leaf = c.variant or c.action
        target = f"{c.verb} {c.object}" + (f" {leaf}" if leaf else "")
```

- [ ] **Step 3c: Add `"request"` to `_VERBS`** in `src/phantasos/generator/cli/templates/_generated/app.py.jinja`:
```jinja
_VERBS = ["set", "del", "show", "request"]
```
With 3a, request commands get `typer_path=[object, action]` (via `_leaf`), `variant_groups` includes `(request, <object>)`, and `build_generated_app` creates one object sub-Typer under the `request` verb app and registers each action as a leaf — the same registration path as variant `set` commands, but the runtime never inspects `action`.

- [ ] **Step 4: Run → PASS**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/test_cli_emitted.py -v`
Expected: the new request test passes; existing emitted tests still pass (adding request mappings to `emitted` only ADDS commands — set/del/show/variant tests are unaffected; if any existing test asserted the exact set of top-level verbs, update it to include `request`).

- [ ] **Step 5: Lint, full suite, commit**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/ -q && UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run ruff check src/phantasos/generator tests/`
```bash
git add src/phantasos/generator/cli/render_cli.py src/phantasos/generator/cli/discover.py \
        src/phantasos/generator/cli/templates/_generated/app.py.jinja tests/test_cli_emitted.py
git commit -m "feat(cli-gen): emit request <object> <action> (action-aware emitter + request verb sub-app)"
```

---

## Task 4: Real-SDK — request actions dispatch against prisma-browser

**Files:**
- Test: `tests/test_cli_emitted_real.py` (append, gated)

- [ ] **Step 1: Write the gated test**

```python
def test_real_request_commands_dispatch(tmp_path, monkeypatch):
    if not REAL_SDK.exists():
        pytest.skip("prisma-browser-sdk not built")
    from typer.testing import CliRunner
    from unittest.mock import MagicMock
    from phantasos.generator.cli.cliconfig import load_cli_config
    from phantasos.generator.cli.render_cli import render_cli

    try:
        inv = introspect("prisma_browser", REAL_SDK)
    except ImportError as exc:
        pytest.skip(f"SDK runtime deps unavailable: {exc}")
    cfg = load_cli_config(Path("products/prisma-browser/cli.yml"))
    ir, unmapped = build_cli_ir(inv, cfg)
    by_key = {c.key: c for c in ir.commands}
    # the cli.yml's request mappings are now real commands
    assert "request:device:suspend" in by_key
    assert "request:user-request:revoke" in by_key
    assert unmapped == []

    render_cli(ir, package="prisma_browser_cli", out_dir=tmp_path)
    sys.path.insert(0, str(tmp_path))
    for n in [n for n in sys.modules if n.startswith("prisma_browser_cli")]:
        del sys.modules[n]
    try:
        main = importlib.import_module("prisma_browser_cli.main")
        rt = importlib.import_module("prisma_browser_cli._generated.runtime")
        import prisma_browser.extras.facade as facade
        mock = MagicMock(name="Client")
        monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: mock))
        # request user-request revoke --id REQ-1 (id + body); supply a body field if required
        res = CliRunner().invoke(
            main.app, ["request", "user-request", "revoke", "--id", "REQ-1", "--output", "json"])
        assert res.exit_code == 0, res.output
        assert mock.user_requests.revoke_user_request.called
        kw = mock.user_requests.revoke_user_request.call_args.kwargs
        assert kw.get("id") == "REQ-1"
    finally:
        sys.path.remove(str(tmp_path))
        for n in [n for n in sys.modules if n.startswith("prisma_browser_cli")]:
            del sys.modules[n]
```

Note: `revoke_user_request(id, revoke_request_action: RevokeRequestAction)` — the body model may have required fields. If the invocation exits 1 due to a required body field, inspect `RevokeRequestAction.model_fields` and add the needed `--flag`(s) to the invoke args (or assert against a body-less action like a positions/publish command instead). Keep the test asserting a REAL dispatch through the facade boundary (mock at `facade.Client.from_env`, not `rt._client`).

- [ ] **Step 2: Run → PASS (not skip)**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/test_cli_emitted_real.py -k request -v`
Expected: PASS. If a request method's body validation blocks the call, adjust the invocation to supply required fields (do not weaken the dispatch assertion).

- [ ] **Step 3: Eyeball the real build**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run phantasos cli build prisma-browser; echo "exit=$?"; UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run phantasos cli discover prisma-browser 2>/dev/null | grep -E "^  request " | head`
Expected (M2 — explicit): `exit=0` and the build's stdout reports `emitted N files … (M commands)` with **NO `note: … unmapped ops omitted` line** (all 16 now EMIT, not skip). discover shows `request device suspend|resume|restore|archive|force-reauth`, `request user-request revoke|action`, `request configuration publish`, and `request <policy>-section reorder`. If any of the 16 fails to emit, it now surfaces as a build error/traceback (a real safety net) rather than a silent skip — investigate that op's shape (don't re-hide it).

- [ ] **Step 4: Full suite + lint + types + commit**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/ -q && UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run ruff check src/phantasos tests/ && UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run mypy src/phantasos/generator src/phantasos/cli.py`
```bash
git add tests/test_cli_emitted_real.py
git commit -m "test(cli-gen): real-SDK request <object> <action> dispatch (gated)"
```

---

## Task 5: Docs — request namespace is now emitted

**Files:**
- Modify: `docs/superpowers/specs/2026-06-09-cli-generator-design.md`
- Modify: `docs/superpowers/plans/2026-06-09-cli-generator-phase-3-roadmap.md`

- [ ] **Step 1:** In the spec, note that `request <object> <action>` commands are emitted from `cli.yml request:` mappings (verb-first; action carried in the command's third segment; one SDK method per action). In the roadmap §3b, mark it DONE and remove the "reserved but not emitted" caveat from §3a's note.

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/specs/2026-06-09-cli-generator-design.md docs/superpowers/plans/2026-06-09-cli-generator-phase-3-roadmap.md
git commit -m "docs: request namespace emitted (Phase 3b done)"
```

---

## Self-review (completed during authoring)

- **Spec coverage:** `request <object> <action>` emission via the dedicated `Command.action` field (Tasks 2,3a); built from id+body (Task 2 `_emit_request` handles both — verified against real `suspend_devices` (body) and `revoke_user_request` (id+body)); driven by `cli.yml request:` (authored in 3a) (Task 4 real test); emitter `_leaf` action-awareness + `request` verb sub-app (Task 3a/3c); discover shows the action (Task 3b). Out of scope (later phases): `load`/`backup`, COMMANDS.md, dynamic completion, dot-notation flags.
- **Placeholder scan:** none — every step has concrete code. Task 4 flags a real unknown (RevokeRequestAction required fields) with the test as the contract + a fallback (use a body-less action).
- **Type/name consistency:** `Command.action` (Task 2, ir.py) is set by `_emit_request` (Task 2) and read by `_leaf`/`_func_name`/`_command_view`/`variant_groups` (Task 3a) and `discover.render_table` (Task 3b); `SubVerb` gains `"action"` (Task 2, ir.py) used by the request binding + `_SUBVERB_PRIORITY` (Task 2, classify); `_emit_request` uses `_command_key`/`detect_id_param`/`_body_param_info`/`_path_flags`/`_body_flags_for`/`_query_flags`/`_merge_flags`/`MethodBinding`/`Command` — all already in classify.py; `RequestMapping` is the existing `cliconfig` model (`{object, action}`); `_VERBS += "request"` (Task 3c) matches the `verb="request"` set in Task 2; the `emitted` fixture gains request mappings (Task 3) consumed by the request CliRunner test.

## python-pro review (applied)
GO-WITH-CHANGES. The review traced the core mechanics against real code + live SDK introspection and confirmed: the `variant`-as-action overload produces `request <object> <action>` correctly (emitter `typer_path`/`variant_groups` + `app.py` object sub-Typers), `variant_param=None` reliably skips body-discriminator injection in `runtime.py`, the precedence reorder is behavior-preserving and correctly emits classifier-skipped `*_positions` ops, all 16 mapped ops have real-model bodies (no `dict`/`list[Model]` gap), and `sub_verb="action"` + `_pick_binding` (single binding) work. **Folded in:** `_emit_request` rewritten to the `_emit` idiom (S1 — clearer + merges flags on collision); Task 3 test asserts `request` is a registered verb group (M1); Task 2 test asserts distinct command keys (N2); Task 4 Step 3 build expectation made explicit — exit 0 + no unmapped line (M2). **Design choice (user decision):** we took the reviewer's S2 alternative — a **dedicated `Command.action` field**, NOT overloading `variant` — for IR clarity (the runtime's discriminator logic provably never touches request commands since their `variant` is `None`). The cost is emitter action-awareness: `render_cli` treats the leaf segment as `variant or action` in `_func_name`/`_command_view.typer_path`/`variant_groups` (Task 3a) and `discover.render_table` shows it (Task 3b). The runtime and `app.py` registration are unchanged (segment-agnostic). The Task-4 real dispatch test asserts `revoke` (body field `revoker_comment` optional) rather than `action` (required enum field) so a bare invocation succeeds (N1).

## Risks the review pass should scrutinize
1. **Explicit `action` field + emitter `_leaf` awareness** — confirm the `_leaf(c) = c.variant or c.action` helper is used consistently in `_func_name`, `_command_view.typer_path`, AND `variant_groups` (a miss in any one yields wrong registration/func-name). Confirm `variant` and `action` are never both set on one command (mutually exclusive by construction). Confirm `app.py` registration (segment-agnostic, walks `typer_path`) produces `request <object> <action>` for an object with multiple actions → one object sub-Typer. Confirm the runtime genuinely ignores `action` (no new branch needed).
2. **Precedence reorder** — moving the `cfg.request` branch above the `cls is None → unmapped` check: does it preserve all existing behavior for non-request ops? Does it correctly emit request ops that the classifier would otherwise SKIP (e.g. `*_positions`, which hit `_SKIP_FRAGMENTS`)? (The real cli.yml maps `update_security_positions` etc. under request — confirm they now emit and aren't unmapped.)
3. **Dup-key handling in `_emit_request`** — two request mappings to the same `(object, action)` would aggregate bindings; is that desired or should it error? (Real cli.yml has unique object+action pairs, but `security_policy` has both `update_security_positions` and `patch_security_positions` mapped to `(security-section, reorder)` vs `(security-section, reorder-patch)` — distinct actions, so no collision. Verify.)
4. **Request body required-field UX** — request methods with required body fields: does a bare `request device suspend` (no flags) produce a friendly error (ValidationError caught by H5) rather than a traceback? (Same mechanism as `set`; confirm.)
5. **Real-SDK action coverage** — do all 16 mapped ops emit without error (esp. the `dict`-bodied or `list`-bodied ones, if any)? `update_*_positions` bodies are real models (`UpdateSignInPositionsRequest`), so OK; confirm none hit the `dict`/`list[Model]` introspection gap.
