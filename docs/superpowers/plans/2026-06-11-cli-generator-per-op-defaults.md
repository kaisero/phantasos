# CLI Generator: Per-Op Query-Param Defaults (cli.yml `defaults:`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A cli.yml `defaults:` section that injects default values for query-param flags per SDK operation — used to default `sort=application.id, order=asc` on the two application list ops so `--all` cursor pagination works.

**Architecture:** cli.yml gains `defaults: {<resource>.<method>: {<query-param>: <value>}}`. `build_cli_ir` validates each entry (op must exist in the inventory; param must be one of that op's query params) and stamps the value into a NEW `Flag.cli_default` field — deliberately separate from the existing `Flag.default` (which carries SDK/model defaults that the emitted CLI must keep ignoring, see Critical Invariant). The commands template renders `cli_default` as the Typer option default, so it is user-overridable, appears in `--help` as `[default: …]`, and flows through the existing runtime untouched (non-None query values are already forwarded to the SDK call — no runtime change).

**Tech Stack:** existing pydantic/Jinja/Typer pipeline. No new dependencies.

**Branch / repo:** `cli-generator` at `/home/ubuntu/git/phantasos` (run all commands from there).

**Test invocation (sshfs venv workaround):** `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest ...`

---

## Why (root cause, e2e-validated 2026-06-11)

The PANW `ListApplications`/`ListApplicationsByType` endpoints only honor their pagination cursor when an explicit `sort`+`order` is supplied; without one the server issues a cursor it then resolves to an empty 200 page (`{"data": [], "pageInfo": {"hasNextPage": false}}`), so `paginate()` silently stops after page 1 (100 items). All other cursor-paginated endpoints (device-groups, devices, users, user-requests) resume fine unsorted — this is applications-specific. Validated end-to-end through the real CLI binary:

- `show application --all --name google --sort application.id --order asc` → **108/108 unique** (crosses the 100 boundary); `--name cloud` → **956/956 unique** (10 page-hops); table output identical.
- Negative control without sort → 100 (truncated).
- `application.id` chosen as the default sort key: unique (no cursor tie-break ambiguity) and ULID-ordered (≈ creation order, close to the server's unsorted presentation).

Decision (user, 2026-06-11): fix via cli.yml per-op defaults ONLY — no defensive change to the SDK's `paginate()`.

## Design decisions (locked)

1. **Defaults apply ALWAYS** (any invocation of a command binding that op), not just under `--all`: deterministic ordering everywhere, and a manually-copied `--cursor` resumes consistently. The user can override (`--sort application.name`) or has the SDK behavior available by other means; the flag default is visible in `--help`.
2. **New `Flag.cli_default` field, NOT reuse of `Flag.default`.** CRITICAL INVARIANT: `Flag.default` is already populated for body flags from pydantic model defaults (e.g. fakesdk `WidgetInput.mode` defaults to `"fast"`), and the template deliberately renders `None` for all optional flags. If model defaults ever became CLI flag defaults, every `update` (PATCH) would silently send those fields (`v is not None` → included in the body) — breaking partial-PATCH semantics. `cli_default` is set ONLY from cli.yml; everything else keeps rendering `None`.
3. **Build-time validation, build fails on violation** (consistent with `columns:`): unknown op key → ValueError; param not among that op's query params → ValueError listing the available ones. An entry for a hidden op is still validated against the inventory but has no effect (the op emits no command) — allowed, not an error.
4. **Scope: query params only.** Path/body defaults are out of scope (no use case; body defaults are dangerous per invariant above).

## File structure

| File | Change |
|---|---|
| `src/phantasos/generator/cli/cliconfig.py` | `CliConfig.defaults: dict[str, dict[str, Any]] = {}` |
| `src/phantasos/generator/cli/ir.py` | `Flag.cli_default: Any | None = None` |
| `src/phantasos/generator/cli/classify.py` | validate `cfg.defaults`; thread per-op defaults into `_query_flags` |
| `src/phantasos/generator/cli/render_cli.py` | `_py_literal()`; `_flag_view` gains `default_literal` |
| `src/phantasos/generator/cli/templates/_generated/commands.py.jinja` | render `default_literal` as the Option default |
| `products/prisma-browser/cli.yml` | `defaults:` entries for the two application list ops |
| `docs/superpowers/specs/2026-06-09-cli-generator-design.md` | spec sync |
| Tests | `tests/test_cli_config.py`, `tests/test_cli_ir.py`, `tests/test_cli_classify.py`, `tests/test_cli_emitted.py`, `tests/test_cli_emitted_real.py` |

No fakesdk fixture changes: tests use `list_widgets`' existing `name` (str) and `limit` (int) query params to cover both literal types.

---

### Task 1: cliconfig — `defaults:` section

**Files:**
- Modify: `src/phantasos/generator/cli/cliconfig.py`
- Test: `tests/test_cli_config.py`

- [ ] **Step 1: Write the failing test** (append to `tests/test_cli_config.py`, matching its tmp-yaml pattern):

```python
def test_defaults_section_loads(tmp_path):
    from phantasos.generator.cli.cliconfig import load_cli_config

    p = tmp_path / "cli.yml"
    p.write_text(
        "defaults:\n"
        "  applications.list_applications:\n"
        "    sort: application.id\n"
        "    order: asc\n"
        "  widgets.list_widgets:\n"
        "    limit: 50\n",
        encoding="utf-8",
    )
    cfg = load_cli_config(p)
    assert cfg.defaults["applications.list_applications"] == {
        "sort": "application.id", "order": "asc",
    }
    assert cfg.defaults["widgets.list_widgets"] == {"limit": 50}  # int preserved
```

- [ ] **Step 2: Run it, verify FAIL** (CliConfig forbids extra key `defaults`):

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/test_cli_config.py -q`

- [ ] **Step 3: Implement** — in `cliconfig.py`, add to `CliConfig` (after `columns`):

```python
    # op ("resource.method") -> query-param defaults injected into the emitted
    # flags (user-overridable; e.g. a default sort that makes cursor pagination
    # work on endpoints that require one). Query params only.
    defaults: dict[str, dict[str, Any]] = {}
```

and mention `defaults` in the module docstring's section enumeration.

- [ ] **Step 4: Run test → PASS.**

- [ ] **Step 5: Commit:**

```bash
git add src/phantasos/generator/cli/cliconfig.py tests/test_cli_config.py
git commit -m "feat(cli-gen): cli.yml defaults: section (per-op query-param defaults)"
```

---

### Task 2: IR — `Flag.cli_default`

**Files:**
- Modify: `src/phantasos/generator/cli/ir.py`
- Test: `tests/test_cli_ir.py`

- [ ] **Step 1: Write the failing test** (append to `tests/test_cli_ir.py`):

```python
def test_flag_cli_default_roundtrip():
    from phantasos.generator.cli.ir import Flag

    f = Flag(name="--sort", param="sort", py_type="str", kind="enum",
             required=False, cli_default="application.id")
    back = Flag.model_validate_json(f.model_dump_json())
    assert back.cli_default == "application.id"
    assert back.default is None  # SDK/model default stays separate
```

- [ ] **Step 2: Run it, verify FAIL** (unknown field `cli_default`, extra=forbid).

- [ ] **Step 3: Implement** — in `ir.py`, add to `Flag` (after `default`):

```python
    # cli.yml-injected flag default (rendered as the Typer option default and
    # therefore sent to the SDK unless overridden). Distinct from `default`,
    # which records the SDK/model default and is NEVER rendered — body flags
    # must stay None-by-default or PATCH would silently send model defaults.
    cli_default: Any | None = None
```

- [ ] **Step 4: Run test → PASS.** (ir.py is copied verbatim to emitted `_generated/spec.py`, so the field ships automatically.)

- [ ] **Step 5: Commit:**

```bash
git add src/phantasos/generator/cli/ir.py tests/test_cli_ir.py
git commit -m "feat(cli-gen): Flag.cli_default in the IR (cli.yml-injected flag default)"
```

---

### Task 3: classify — validate + apply defaults to query flags

**Files:**
- Modify: `src/phantasos/generator/cli/classify.py`
- Test: `tests/test_cli_classify.py`

- [ ] **Step 1: Write the failing tests** (append to `tests/test_cli_classify.py`; it already imports `build_cli_ir`, `CliConfig`, `introspect` and uses the fakesdk fixture path — match its idiom):

```python
def test_defaults_stamp_cli_default_on_query_flags():
    from pathlib import Path

    from phantasos.generator.cli.classify import build_cli_ir
    from phantasos.generator.cli.cliconfig import CliConfig
    from phantasos.generator.cli.introspect import introspect

    fixture = Path(__file__).parent / "fixtures" / "fakesdk"
    inv = introspect("fakesdk", fixture)
    cfg = CliConfig(defaults={
        "widgets.list_widgets": {"name": "gadget", "limit": 50},
    })
    ir, _ = build_cli_ir(inv, cfg)
    show = next(c for c in ir.commands if c.key == "show:widget")
    by_param = {f.param: f for f in show.query_flags}
    assert by_param["name"].cli_default == "gadget"     # str preserved
    assert by_param["limit"].cli_default == 50          # int preserved
    # untouched flags stay None; body flags never gain cli_default
    assert all(f.cli_default is None for f in show.body_flags)
    create = next(c for c in ir.commands if c.key == "create:widget")
    assert all(f.cli_default is None for f in create.body_flags)


def test_defaults_validation_errors():
    from pathlib import Path

    import pytest

    from phantasos.generator.cli.classify import build_cli_ir
    from phantasos.generator.cli.cliconfig import CliConfig
    from phantasos.generator.cli.introspect import introspect

    fixture = Path(__file__).parent / "fixtures" / "fakesdk"
    inv = introspect("fakesdk", fixture)

    with pytest.raises(ValueError, match="unknown operation"):
        build_cli_ir(inv, CliConfig(defaults={"widgets.no_such_op": {"limit": 1}}))

    with pytest.raises(ValueError, match="not a query param"):
        build_cli_ir(inv, CliConfig(
            defaults={"widgets.list_widgets": {"bogus": "x"}}))
```

- [ ] **Step 2: Run them, verify FAIL** (no validation; `cli_default` stays None).

- [ ] **Step 3: Implement** in `src/phantasos/generator/cli/classify.py`:

(a) Change `_query_flags` to accept per-op defaults:

```python
def _query_flags(
    params: list[ParamInfo], defaults: dict[str, Any] | None = None
) -> list[Flag]:
    defaults = defaults or {}
    return [
        Flag(name=_flag_name(p.name), param=p.name,
             # Enum query params stay permissive (str + choices), like fields_to_flags.
             # Plain int/bool scalars get their real type for _coerce to work correctly.
             py_type="str" if p.enum_values else p.scalar_type,
             kind="enum" if p.enum_values else "scalar",
             required=False, default=p.default, help=p.description,
             choices=p.enum_values,
             cli_default=defaults.get(p.name))
        for p in params if p.location == "query"
    ]
```

(b) In `build_cli_ir`, validate ONCE near the top (before the `for op in inv.operations:` loop):

```python
    # cli.yml defaults: validate op keys and param names up front (build fails
    # on a typo rather than silently ignoring it).
    ops_index = {f"{op.resource}.{op.method}": op for op in inv.operations}
    for op_key, params_map in cfg.defaults.items():
        op_info = ops_index.get(op_key)
        if op_info is None:
            raise ValueError(
                f"cli.yml defaults: unknown operation {op_key!r}"
            )
        query_names = {p.name for p in op_info.params if p.location == "query"}
        unknown = set(params_map) - query_names
        if unknown:
            raise ValueError(
                f"cli.yml defaults.{op_key}: {', '.join(sorted(unknown))}"
                f" is not a query param (available:"
                f" {', '.join(sorted(query_names)) or 'none'})"
            )
```

NOTE: the columns second pass (added 2026-06-10) builds its own `ops_by_key` map later in this function — reuse `ops_index` there and delete the duplicate comprehension while you're in the file (rename uses accordingly; behavior identical).

(c) Thread defaults into both `_query_flags` call sites. In `_emit` and `_emit_request`, the op is in scope; compute the key and pass:

```python
            query_flags=_query_flags(
                op.params, cfg.defaults.get(f"{op.resource}.{op.method}")
            ),
```

(both the `Command(...)` constructions AND the `_merge_flags(cmd.query_flags, _query_flags(...))` merge lines — all four places `_query_flags` is invoked).

- [ ] **Step 4: Run the full suite** — new tests PASS, all others green (defaults absent → `cli_default=None` everywhere → no behavior change). Then `ruff check src/ tests/` + `mypy src`.

- [ ] **Step 5: Commit:**

```bash
git add src/phantasos/generator/cli/classify.py tests/test_cli_classify.py
git commit -m "feat(cli-gen): validate + apply cli.yml defaults to query flags"
```

---

### Task 4: render — emit `cli_default` as the Typer option default

**Files:**
- Modify: `src/phantasos/generator/cli/render_cli.py`
- Modify: `src/phantasos/generator/cli/templates/_generated/commands.py.jinja`
- Test: `tests/test_cli_emitted.py`

- [ ] **Step 1: Write the failing tests** (append to `tests/test_cli_emitted.py`). The `emitted` fixture builds the fakesdk CLI with the module-level `_FAKESDK_CLI_CONFIG`; ADD a defaults entry to that config (this is config for the fixture, not a behavioral test edit):

In `_FAKESDK_CLI_CONFIG` (top of file), add alongside `variants=`/`request=`:

```python
    defaults={"widgets.list_widgets": {"name": "gadget", "limit": 50}},
```

Then append the tests:

```python
def test_query_default_is_injected_and_overridable(emitted, monkeypatch):
    from typer.testing import CliRunner

    app_mod = importlib.import_module("fakesdk_cli._generated.app")
    rt = importlib.import_module("fakesdk_cli._generated.runtime")

    calls = []

    class _W:
        def list_widgets(self, **kw):
            calls.append(kw)
            return []

    class _Client:
        widgets = _W()

    monkeypatch.setattr(rt, "_client", lambda: _Client())
    runner = CliRunner()

    # no flags -> cli.yml defaults flow into the SDK call (int correctly typed)
    res = runner.invoke(app_mod.build_generated_app(), ["show", "widget"])
    assert res.exit_code == 0, res.output
    assert calls[-1] == {"name": "gadget", "limit": 50}

    # user override wins
    res = runner.invoke(app_mod.build_generated_app(),
                        ["show", "widget", "--name", "other", "--limit", "7"])
    assert res.exit_code == 0, res.output
    assert calls[-1] == {"name": "other", "limit": 7}


def test_query_default_shown_in_help(emitted):
    from typer.testing import CliRunner

    app_mod = importlib.import_module("fakesdk_cli._generated.app")
    res = CliRunner().invoke(app_mod.build_generated_app(),
                             ["show", "widget", "--help"])
    assert res.exit_code == 0
    assert "gadget" in res.output      # [default: gadget] in rich help


def test_model_body_defaults_still_not_rendered(emitted):
    """CRITICAL INVARIANT: pydantic model defaults (Flag.default) must never
    become CLI flag defaults — PATCH would silently send them. WidgetInput.mode
    defaults to 'fast' in the model; the emitted option must stay None."""
    import pathlib

    src = (pathlib.Path(emitted) / "fakesdk_cli" / "_generated" / "commands"
           / "widgets.py").read_text(encoding="utf-8")
    # the --mode option (body flag with a model default) is emitted with None
    mode_lines = [ln for ln in src.splitlines() if '"--mode"' in ln]
    assert mode_lines, "expected a --mode option in the emitted widgets module"
    for line in mode_lines:
        assert '"fast"' not in line     # model default must NOT be rendered
        assert "None" in line           # option default stays None
```

(Formatting-robust contract: ruff may reflow the emitted source, but the `typer.Option(None, "--mode"...)` call stays on one line at 88 cols for this fixture; if it ever wraps, relax to scanning the 2-line window after the match — the contract is "mode's default is None, not the model default".)

- [ ] **Step 2: Run them, verify FAIL** (defaults not rendered → SDK called with `{}` / help lacks "gadget").

- [ ] **Step 3: Implement:**

(a) `render_cli.py` — add near `_render_type`:

```python
def _py_literal(value: object) -> str:
    """Python source literal for a flag default. json.dumps gives correct
    quoting for str and is wrong for bool/None — handle those explicitly."""
    if value is None:
        return "None"
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, (int, float)):
        return repr(value)
    return json.dumps(str(value))
```

(b) `_flag_view` — add to the returned dict:

```python
        "default_literal": (
            _py_literal(f.cli_default) if f.cli_default is not None else None
        ),
```

(c) `commands.py.jinja` line 17 — replace the Option default expression:

```jinja
    {{ f.py_name }}: {{ f.render_type }} = typer.Option({{ f.default_literal or ('...' if f.required else 'None') }}, {{ f.name|tojson }}{% if f.help_literal %}, help={{ f.help_literal }}{% endif %}{% if f.completion %}, autocompletion={{ f.completer_name }}{% endif %}{% if f.panel %}, rich_help_panel={{ f.panel|tojson }}{% endif %}),
```

(`default_literal` is a ready-to-paste Python literal string; `Flag.default`/model defaults never reach it.)

- [ ] **Step 4: Run** `tests/test_cli_emitted.py` → new tests PASS; FULL suite green; ruff + mypy src clean. The emitted modules are ruff-formatted post-render — if the `--help` assertion is flaky due to wrapping, assert on `"default:" in res.output and "gadget" in res.output` instead.

- [ ] **Step 5: Commit:**

```bash
git add src/phantasos/generator/cli/render_cli.py src/phantasos/generator/cli/templates/_generated/commands.py.jinja tests/test_cli_emitted.py
git commit -m "feat(cli-gen): render cli.yml defaults as Typer option defaults"
```

---

### Task 5: prisma-browser cli.yml + gated real-SDK test + real build

**Files:**
- Modify: `products/prisma-browser/cli.yml`
- Test: `tests/test_cli_emitted_real.py`

- [ ] **Step 1: Append to `products/prisma-browser/cli.yml`:**

```yaml
# Server quirk (verified 2026-06-11): the application list endpoints only honor
# their pagination cursor when an explicit sort+order is supplied — without one,
# page 2 comes back empty and --all silently truncates at 100. application.id is
# unique (no cursor ties) and ULID-ordered (~creation order). Other endpoints
# (device-groups, devices, users) paginate fine unsorted.
defaults:
  applications.list_applications:
    sort: application.id
    order: asc
  applications.list_applications_by_type:
    sort: application.id
    order: asc
```

NOTE: check whether `applications.list_applications_by_type` is in the cli.yml `hide:` list. If it is hidden, KEEP the defaults entry anyway (validated, harmless, future-proof) and note it in the commit message; the visible `list_applications` is the one users hit via `show application`.

- [ ] **Step 2: Extend the gated test** (append to `tests/test_cli_emitted_real.py`, reusing its existing skip-gating and SDK path/package constants — read the file first, e.g. the `test_real_ir_carries_columns` test added 2026-06-10 shows the exact idiom including `load_cli_config`):

```python
def test_real_ir_carries_query_defaults():
    """The shipped defaults: make application --all pagination work (server
    honors cursors only under an explicit sort)."""
    from phantasos.generator.cli.classify import build_cli_ir
    from phantasos.generator.cli.cliconfig import load_cli_config
    from phantasos.generator.cli.introspect import introspect

    cfg = load_cli_config(
        Path(__file__).parent.parent / "products" / "prisma-browser" / "cli.yml"
    )
    ir, _ = build_cli_ir(introspect(REAL_SDK_PACKAGE, REAL_SDK_PATH), cfg)
    show_app = next(c for c in ir.commands if c.key == "show:application")
    by_param = {f.param: f for f in show_app.query_flags}
    assert by_param["sort"].cli_default == "application.id"
    assert by_param["order"].cli_default == "asc"
    # the defaults are surgical: no other command gains them
    show_dg = next(c for c in ir.commands if c.key == "show:device-group")
    assert all(f.cli_default is None for f in show_dg.query_flags)
```

(substitute the file's actual constants/skip marker for `REAL_SDK_PACKAGE`/`REAL_SDK_PATH`).

- [ ] **Step 3: Run:** the gated test (must RUN and PASS here), the FULL suite, ruff, mypy src. Then rebuild the real CLI:

```bash
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run phantasos cli build prisma-browser
```

Expected: clean build, 0 unmapped. Spot-check: `grep -n "application.id" /home/ubuntu/git/prisma-browser-cli/prisma_browser_cli/_generated/commands/applications.py` shows the rendered default.

- [ ] **Step 4: Commit:**

```bash
git add products/prisma-browser/cli.yml tests/test_cli_emitted_real.py
git commit -m "fix(cli-gen): default sort for application listings — --all pagination works (server cursor quirk)"
```

---

### Task 6: LIVE verification + spec sync + gate

**Files:**
- Modify: `docs/superpowers/specs/2026-06-09-cli-generator-design.md`

- [ ] **Step 1: LIVE verification of the rebuilt CLI** (credentials in `/home/ubuntu/git/prisma-browser-cli/.env`; READ-ONLY list calls only). Run WITHOUT any sort flags — the injected defaults must do the work now:

```bash
cd /home/ubuntu/git/prisma-browser-cli
UV_PROJECT_ENVIRONMENT=/tmp/pbcli-venv uv run prisma-browser-cli show application --all --name google 2>/dev/null \
  | python3 -c "import json,sys; items=json.load(sys.stdin); ids={(i.get('actual_instance') or i).get('id') for i in items}; print(len(items), 'items,', len(ids), 'unique')"
```

Expected: `108 items, 108 unique` (was 100 before the fix). Also confirm `--help` shows the default:

```bash
UV_PROJECT_ENVIRONMENT=/tmp/pbcli-venv uv run prisma-browser-cli show application --help | grep -A1 -- "--sort"
```

Expected: shows `application.id` as the default. Paste BOTH actual outputs in the report (evidence before assertions).

- [ ] **Step 2: Spec sync** — append to the "Table output & columns" area of `docs/superpowers/specs/2026-06-09-cli-generator-design.md` (or a sibling section "Per-op query-param defaults"): the `defaults:` section shape, always-applied + user-overridable semantics, `Flag.cli_default` vs `Flag.default` invariant (model defaults never rendered — PATCH safety), build-time validation, and the motivating applications-cursor server quirk with the workaround-now-default. Match the spec's concise decision-oriented style.

- [ ] **Step 3: Full gate:**

```bash
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run ruff check src/ tests/
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run mypy src
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/ -q
```

All clean / all pass (expect 236+ passed).

- [ ] **Step 4: Commit:**

```bash
git add docs/superpowers/specs/2026-06-09-cli-generator-design.md
git commit -m "docs(spec): per-op query-param defaults (cli.yml defaults:, applications cursor quirk)"
```

---

## Out of scope (explicitly)

- Defensive `paginate()` in the SDK (user decision: cli.yml-only fix).
- Path/body param defaults (no use case; body defaults would break PATCH semantics).
- Upstream bug report to PANW (separate action; evidence is in this plan's "Why" section).
- Streaming/progressive output for huge `--all` runs (the server caps pages at 100 items regardless of `limit`; an unfiltered application `--all` is inherently a multi-minute, many-request run — performance is server-bound and unrelated to this fix).

## Known risks / notes for the implementer

- **The invariant test (Task 4, `test_model_body_defaults_still_not_rendered`) is the load-bearing one.** If a refactor ever wires `Flag.default` into the template, PATCH commands would silently send model defaults. Keep `default` and `cli_default` separate.
- `_merge_flags` is first-wins across bindings: `sort`/`order` exist only on the list op, so no conflict today; if two bindings ever expose the same query param with different cli_defaults, the first emitted wins — acceptable, don't engineer around it.
- Typer renders `[default: …]` automatically for options with non-None defaults; enum flags stay permissive `str` (choices are completer/help only), so a default like `application.id` needs no enum coercion.
- The emitted files are ruff-formatted post-render; source-inspection assertions must be formatting-robust (substring per line, not exact layout).
