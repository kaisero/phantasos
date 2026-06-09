# CLI Generator — Phase 2b: Emission (set/del/show) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Emit a standalone, installable Typer+Rich CLI project from the aggregated `CliIR`, with working `set`/`del`/`show` commands that call the built SDK, plus config/auth/output, the generated-vs-hand-owned split, and the `phantasos cli build` command.

**Architecture:** Static codegen via Jinja (matching `src/phantasos/render.py`/`scaffold.py`). A generator-side `render_cli(ir, loaded, out_dir)` writes a project: a disposable `_generated/` subpackage (commands, runtime, output, config, `ir.json`) plus emit-once-if-missing hand-owned files (`main.py`, `custom/`, `hooks.py`, `pyproject.toml`). The emitted **`runtime.py`** holds all dispatch logic (typed Python, not templates): it loads `ir.json`, picks the right `MethodBinding` from the args supplied, builds the SDK call (path params + a body model constructed from body flags), invokes `client.<resource>.<method>`, and renders the result. Templates stay thin.

**Tech Stack:** Python 3.11–3.14, Jinja2 (already a dep), Typer + Rich + PyYAML (new deps of the *generated* CLI), Pydantic v2, pytest + Typer's `CliRunner`. Test runner: `uv run pytest`.

**Spec:** `docs/superpowers/specs/2026-06-09-cli-generator-design.md` (Augmentation & extensibility; Generated CLI project; the aggregated `CliIR`). **Builds on:** Phase 2a (aggregated IR), committed on branch `cli-generator`.

---

## Conventions for every task

- Environment: `export UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv` then use `uv run ...` (the repo `.venv` can't hold symlinks).
- Repo root `/home/ubuntu/git/phantasos`, branch `cli-generator`. **Do NOT `git checkout`/`switch`/`reset`** — commit on the current branch; use `git show <sha>:<path>` to view history (a detached-HEAD incident happened once).
- TDD: failing test first; all new imports at the TOP of test files (ruff E402); run `ruff check src/phantasos tests/` AND `mypy src/phantasos/generator` before committing (both clean, mypy strict).
- The fake SDK fixture lives at `tests/fixtures/fakesdk/`; the real SDK at `/home/ubuntu/git/prisma-browser-sdk` (importable as `prisma_browser`).

---

## Design decisions resolved up front (from the Phase-2a review)

1. **Variant→param mapping: CARRY it in the IR.** `Command.variant_param: str | None` is populated from `cli.yml`'s `VariantMap.path_param`. The runtime sets `kwargs[variant_param] = command.variant`.
2. **Per-binding call metadata:** `MethodBinding` gains `body_param: str | None` (the SDK body parameter name) and `body_model: str | None` (the model class to construct). Captured at introspect time.
3. **Aggregated body flags are OPTIONAL at the CLI layer.** Requiredness is enforced by the SDK's Pydantic body model at call time (a missing required field → a friendly error), because a field required by `create` is not required by `patch`.
4. **Dispatch:** the binding whose `requires` (required path-param names) are all present in the supplied args, choosing the most specific (largest `requires`); fall back to the unique zero-`requires` binding (create/list). Ambiguity or no match → a clear error.
5. **`ir.json` is the single runtime source** (provenance + dispatch), loaded once via `importlib.resources`.

---

## File structure (this phase)

Generator side (in this repo):
- Modify: `src/phantasos/generator/cli/ir.py` — `Command.variant_param`; `MethodBinding.body_param`/`body_model`.
- Modify: `src/phantasos/generator/cli/inventory.py` — `ParamInfo` already has `body_model`; add nothing (reuse).
- Modify: `src/phantasos/generator/cli/introspect.py` — record body param name on the body `ParamInfo` (already has `name`+`body_model`); expose the body param name for bindings.
- Modify: `src/phantasos/generator/cli/classify.py` — populate `variant_param`, `MethodBinding.body_param`/`body_model`; assert merged bindings share `sdk_resource`.
- Create: `src/phantasos/generator/cli/render_cli.py` — the emitter (`render_cli(ir, loaded, out_dir)`).
- Create: `src/phantasos/generator/cli/templates/` — Jinja templates (see tasks).
- Modify: `src/phantasos/cli.py` — `cli build` subcommand.
- Test: `tests/test_cli_render.py`, `tests/test_cli_emitted.py` (emit→import→CliRunner), extend `tests/test_cli_command.py`.

Emitted project (written to `../prisma-browser-cli/`):
```
prisma_browser_cli/
  _generated/  __init__.py  app.py  runtime.py  output.py  config.py  ir.json  commands/<resource>.py
  main.py   custom/__init__.py   hooks.py        # hand-owned, emit-once
pyproject.toml                                   # hand-owned, emit-once (console_scripts)
docs/COMMANDS.md                                 # generated reference (Task 10)
```

---

## Task 1: IR enrichment — `variant_param`, binding `body_param`/`body_model`

**Files:**
- Modify: `src/phantasos/generator/cli/ir.py`
- Modify: `src/phantasos/generator/cli/introspect.py`
- Modify: `src/phantasos/generator/cli/classify.py`
- Test: `tests/test_cli_classify.py`

- [ ] **Step 1: Write the failing test** (append to `tests/test_cli_classify.py`; imports already present):

```python
def test_bindings_carry_body_and_variant_metadata():
    inv = introspect("fakesdk", FIXTURE)
    cfg = CliConfig(
        variants={
            "gizmos.create_gizmo": VariantMap(
                path_param="type",
                map={"simple": "SimpleGizmoInput", "complex": "ComplexGizmoInput"},
            )
        }
    )
    ir, _ = build_cli_ir(inv, cfg)
    by_key = {c.key: c for c in ir.commands}

    # set widget create binding carries its body param + model
    set_widget = by_key["set:widget"]
    create = next(b for b in set_widget.bindings if b.sub_verb == "create")
    assert create.body_param == "widget_input"
    assert create.body_model == "WidgetInput"

    # variant command records which path param the variant value fills
    assert by_key["set:gizmo:simple"].variant_param == "type"
    # non-variant command has no variant_param
    assert set_widget.variant_param is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_cli_classify.py::test_bindings_carry_body_and_variant_metadata -v`
Expected: FAIL (`MethodBinding` has no `body_param`; `Command` has no `variant_param`).

- [ ] **Step 3: Extend the IR models** in `src/phantasos/generator/cli/ir.py` — add two fields to `MethodBinding` and one to `Command`:

```python
class MethodBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sdk_method: str
    sub_verb: SubVerb
    requires: list[str] = []
    body_param: str | None = None   # SDK body parameter name, e.g. "widget_input"
    body_model: str | None = None   # body model class to construct, e.g. "WidgetInput"
```

In `Command`, add (after `variant`):
```python
    variant_param: str | None = None  # path param the variant value fills (e.g. "type")
```

- [ ] **Step 4: Populate the metadata in `classify.py`.** The body `ParamInfo` already carries `name` (the body param) and `body_model`. In `build_cli_ir`'s `_emit`, find the body param of the op and set it on the binding; set `variant_param` when emitting a variant. Replace the binding construction and `_emit` Command creation:

```python
def _body_param_info(op: OperationInfo) -> ParamInfo | None:
    return next((p for p in op.params if p.location == "body"), None)


# inside _emit(...), build the binding with body metadata:
        body_info = _body_param_info(op)
        binding = MethodBinding(
            sdk_method=op.method, sub_verb=sub_verb,
            requires=_required_path_names(op.params),
            body_param=body_info.name if body_info else None,
            body_model=(body_model or (body_info.body_model if body_info else None)),
        )
```

And pass `variant_param` through `_emit`. Change `_emit`'s signature to accept it and set it on the seed Command:

```python
    def _emit(verb: Verb, obj: str, variant: str | None, op: OperationInfo,
              sub_verb: SubVerb, body_model: str | None,
              variant_param: str | None) -> None:
        ...
        if cmd is None:
            cmd = Command(
                verb=verb, object=obj, variant=variant, key=key,
                variant_param=variant_param,
                sdk_resource=op.resource,
                ...
            )
        else:
            assert cmd.sdk_resource == op.resource, (
                f"command {key} aggregates methods from different resources: "
                f"{cmd.sdk_resource} vs {op.resource}"
            )
            ...
```

At the call sites, pass the variant's path param for variant commands, `None` otherwise:
```python
        vmap = cfg.variants.get(key0)
        variants = resolve_variants(op, vmap)
        if variants:
            for v in variants:
                _emit(verb, obj, v.name, op, cls.sub_verb, v.model,
                      vmap.path_param if vmap else None)
        else:
            _emit(verb, obj, None, op, cls.sub_verb, None, None)
```

Note: the `assert` is for an "impossible by construction" invariant (object nouns are resource-derived); ruff `tests/**` allows S101 but `src/**` does not — use an explicit `raise ValueError(...)` instead of `assert` in `src/`:
```python
        elif cmd.sdk_resource != op.resource:
            raise ValueError(
                f"command {key} aggregates methods from different resources: "
                f"{cmd.sdk_resource} vs {op.resource}"
            )
```
(Place this check before the flag-merge in the `else` branch.)

- [ ] **Step 5: Run the test + full classify/ir suite**

Run: `uv run pytest tests/test_cli_classify.py tests/test_cli_ir.py -v`
Expected: PASS (new test + all prior; prior tests unaffected — the new fields default to None).

- [ ] **Step 6: Lint, type-check, commit**

Run: `uv run ruff check src/phantasos/generator tests/ && uv run mypy src/phantasos/generator && uv run pytest tests/ -q`
Expected: clean; all pass.
```bash
git add src/phantasos/generator/cli/ir.py src/phantasos/generator/cli/classify.py tests/test_cli_classify.py
git commit -m "feat(cli-gen): IR carries variant_param + per-binding body_param/body_model"
```

---

## Task 2: Emitter skeleton + regen contract (`render_cli.py`)

Write the emitter that lays down the project tree: wipe+rebuild `_generated/`, emit-once the hand-owned files, write `ir.json`. Start with just the package skeleton + `ir.json`; later tasks add templates.

**Files:**
- Create: `src/phantasos/generator/cli/render_cli.py`
- Create: `src/phantasos/generator/cli/templates/_generated/__init__.py.jinja` (one-line docstring)
- Create: `src/phantasos/generator/cli/templates/main.py.jinja` (hand-owned stub)
- Create: `src/phantasos/generator/cli/templates/hooks.py.jinja` (hand-owned stub)
- Create: `src/phantasos/generator/cli/templates/custom/__init__.py.jinja` (empty)
- Test: `tests/test_cli_render.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_render.py
import json
from pathlib import Path

from phantasos.generator.cli.classify import build_cli_ir
from phantasos.generator.cli.cliconfig import CliConfig
from phantasos.generator.cli.introspect import introspect
from phantasos.generator.cli.render_cli import render_cli

FIXTURE = Path(__file__).parent / "fixtures" / "fakesdk"


def _ir():
    return build_cli_ir(introspect("fakesdk", FIXTURE), CliConfig())[0]


def test_render_cli_lays_down_project(tmp_path):
    render_cli(_ir(), package="fakesdk_cli", out_dir=tmp_path)
    gen = tmp_path / "fakesdk_cli" / "_generated"
    assert (gen / "__init__.py").exists()
    assert (gen / "ir.json").exists()
    # ir.json round-trips to the same command keys
    data = json.loads((gen / "ir.json").read_text())
    assert {c["key"] for c in data["commands"]} == {c.key for c in _ir().commands}
    # hand-owned files are emitted once
    assert (tmp_path / "fakesdk_cli" / "main.py").exists()
    assert (tmp_path / "fakesdk_cli" / "hooks.py").exists()


def test_render_cli_wipes_generated_but_preserves_handowned(tmp_path):
    render_cli(_ir(), package="fakesdk_cli", out_dir=tmp_path)
    main = tmp_path / "fakesdk_cli" / "main.py"
    main.write_text("# user edits\n", encoding="utf-8")
    stale = tmp_path / "fakesdk_cli" / "_generated" / "stale.py"
    stale.write_text("# stale\n", encoding="utf-8")
    render_cli(_ir(), package="fakesdk_cli", out_dir=tmp_path)
    assert main.read_text() == "# user edits\n"      # hand-owned preserved
    assert not stale.exists()                          # _generated wiped
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_cli_render.py -v`
Expected: FAIL (`render_cli` undefined).

- [ ] **Step 3: Implement `render_cli.py`**

```python
# src/phantasos/generator/cli/render_cli.py
"""Emit a Typer CLI project from a CliIR (static codegen via Jinja)."""

from __future__ import annotations

import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from .ir import CliIR

_TEMPLATES = Path(__file__).parent / "templates"


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATES)),
        keep_trailing_newline=True,
        autoescape=select_autoescape(),  # renders Python source, not HTML
        undefined=StrictUndefined,
    )


# Hand-owned files: emitted only if absent, then never overwritten.
_HANDOWNED = ["main.py", "hooks.py", "custom/__init__.py"]


def render_cli(ir: CliIR, package: str, out_dir: Path) -> list[str]:
    env = _env()
    pkg = out_dir / package
    gen = pkg / "_generated"
    # 1. wipe + rebuild _generated (path-guarded)
    if gen.exists():
        if not gen.resolve().is_relative_to(pkg.resolve()):
            raise ValueError("refusing to wipe a path outside the package")
        shutil.rmtree(gen)
    (gen / "commands").mkdir(parents=True, exist_ok=True)
    ctx = {"ir": ir, "package": package}
    written: list[str] = []

    def render(template: str, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(env.get_template(template).render(**ctx), encoding="utf-8")
        written.append(str(dest.relative_to(out_dir)))

    render("_generated/__init__.py.jinja", gen / "__init__.py")
    (gen / "ir.json").write_text(ir.model_dump_json(indent=2), encoding="utf-8")
    written.append(str((gen / "ir.json").relative_to(out_dir)))

    # 2. hand-owned: emit once if missing
    for rel in _HANDOWNED:
        dest = pkg / rel
        if not dest.exists():
            render(f"{rel}.jinja", dest)
    return written
```

- [ ] **Step 4: Create the templates**

`src/phantasos/generator/cli/templates/_generated/__init__.py.jinja`:
```jinja
"""Generated by phantasos cli build. Do not edit — re-run the build instead."""
```

`src/phantasos/generator/cli/templates/main.py.jinja`:
```jinja
"""{{ package }} entrypoint (hand-owned — safe to edit; not overwritten by rebuilds).

Compose the generated app with your own commands/overrides here.
"""

from {{ package }}._generated.app import build_generated_app

app = build_generated_app()

# Examples:
#   from {{ package }}.custom import doctor
#   app.add_typer(doctor.app)
# To replace a generated command, exclude it then register your own:
#   app = build_generated_app(exclude={"set:application"})

if __name__ == "__main__":
    app()
```

`src/phantasos/generator/cli/templates/hooks.py.jinja`:
```jinja
"""Cross-cutting hooks (hand-owned). Define any subset; the runtime no-ops if absent.

    before_call(method, payload, ctx) -> payload | None
    after_call(method, result, ctx) -> result | None
    confirm_delete(object, ident, ctx) -> bool
    render_override(command, result, ctx) -> bool
"""
```

`src/phantasos/generator/cli/templates/custom/__init__.py.jinja`:
```jinja
```
(empty file — a single blank line is fine.)

- [ ] **Step 5: Run the test**

Run: `uv run pytest tests/test_cli_render.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Lint, type-check, commit**

Run: `uv run ruff check src/phantasos/generator tests/ && uv run mypy src/phantasos/generator/cli/render_cli.py`
Expected: clean.
```bash
git add src/phantasos/generator/cli/render_cli.py src/phantasos/generator/cli/templates tests/test_cli_render.py
git commit -m "feat(cli-gen): emitter skeleton + regen contract (_generated wipe, hand-owned emit-once)"
```

---

## Task 3: Emit `config.py` (config.yaml + env + flag precedence)

**Files:**
- Create: `src/phantasos/generator/cli/templates/_generated/config.py.jinja`
- Modify: `src/phantasos/generator/cli/render_cli.py` (render it)
- Test: `tests/test_cli_emitted.py` (new — the emit→import harness)

- [ ] **Step 1: Write the failing test** (this establishes the emitted-code test harness reused by later tasks):

```python
# tests/test_cli_emitted.py
import importlib
import sys
from pathlib import Path

import pytest

from phantasos.generator.cli.classify import build_cli_ir
from phantasos.generator.cli.cliconfig import CliConfig
from phantasos.generator.cli.introspect import introspect
from phantasos.generator.cli.render_cli import render_cli

FIXTURE = Path(__file__).parent / "fixtures" / "fakesdk"


@pytest.fixture
def emitted(tmp_path):
    """Emit the fakesdk CLI into tmp_path, importable as `fakesdk_cli`."""
    ir = build_cli_ir(introspect("fakesdk", FIXTURE), CliConfig())[0]
    render_cli(ir, package="fakesdk_cli", out_dir=tmp_path)
    sys.path.insert(0, str(tmp_path))
    try:
        # drop any previously-imported fakesdk_cli modules for a clean import
        for name in [n for n in sys.modules if n.startswith("fakesdk_cli")]:
            del sys.modules[name]
        yield tmp_path
    finally:
        sys.path.remove(str(tmp_path))
        for name in [n for n in sys.modules if n.startswith("fakesdk_cli")]:
            del sys.modules[name]


def test_config_precedence(emitted, monkeypatch):
    cfg = importlib.import_module("fakesdk_cli._generated.config")
    # default
    assert cfg.resolve("output", flag=None, default="table") == "table"
    # config file value beats default
    (emitted / "cfg.yaml").write_text("output: json\n", encoding="utf-8")
    monkeypatch.setattr(cfg, "_config_path", lambda: emitted / "cfg.yaml")
    assert cfg.resolve("output", flag=None, default="table") == "json"
    # env beats config file
    monkeypatch.setenv("FAKESDK_OUTPUT", "yaml")
    assert cfg.resolve("output", flag=None, default="table") == "yaml"
    # explicit flag beats everything
    assert cfg.resolve("output", flag="table", default="table") == "table"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_cli_emitted.py -v`
Expected: FAIL (no `_generated/config.py`).

- [ ] **Step 3: Create `config.py.jinja`**

`src/phantasos/generator/cli/templates/_generated/config.py.jinja`:
```jinja
"""Config resolution: flag > env ({{ package|upper }}_<KEY>) > config.yaml > default."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

_ENV_PREFIX = "{{ package|upper }}"


def _config_path() -> Path:
    return Path.home() / ".config" / "{{ package }}" / "config.yaml"


def _load_file() -> dict[str, Any]:
    path = _config_path()
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def resolve(key: str, *, flag: Any | None, default: Any) -> Any:
    if flag is not None:
        return flag
    env = os.environ.get(f"{_ENV_PREFIX}_{key.upper()}")
    if env is not None:
        return env
    file_val = _load_file().get(key)
    if file_val is not None:
        return file_val
    return default
```

- [ ] **Step 4: Render it** — in `render_cli.py`, after the `_generated/__init__.py` render, add:
```python
    render("_generated/config.py.jinja", gen / "config.py")
```

- [ ] **Step 5: Run the test**

Run: `uv run pytest tests/test_cli_emitted.py -v`
Expected: PASS (1 passed).

- [ ] **Step 6: Lint, type-check, commit**

Run: `uv run ruff check src/phantasos/generator tests/ && uv run mypy src/phantasos/generator/cli/render_cli.py && uv run pytest tests/ -q`
```bash
git add src/phantasos/generator/cli/templates/_generated/config.py.jinja src/phantasos/generator/cli/render_cli.py tests/test_cli_emitted.py
git commit -m "feat(cli-gen): emit config.py (flag>env>file>default precedence)"
```

---

## Task 4: Emit `output.py` (Rich table / json / yaml)

**Files:**
- Create: `src/phantasos/generator/cli/templates/_generated/output.py.jinja`
- Modify: `src/phantasos/generator/cli/render_cli.py`
- Test: `tests/test_cli_emitted.py`

- [ ] **Step 1: Write the failing test** (append):

```python
def test_output_formats(emitted, capsys):
    out = importlib.import_module("fakesdk_cli._generated.output")

    class _Model:
        def model_dump(self, mode="python"):
            return {"id": "a1", "name": "slack"}

    out.render(_Model(), fmt="json")
    assert '"name": "slack"' in capsys.readouterr().out
    out.render([_Model()], fmt="yaml")
    assert "name: slack" in capsys.readouterr().out
    out.render([_Model()], fmt="table")
    table = capsys.readouterr().out
    assert "id" in table and "name" in table and "a1" in table
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_cli_emitted.py::test_output_formats -v`
Expected: FAIL.

- [ ] **Step 3: Create `output.py.jinja`**

`src/phantasos/generator/cli/templates/_generated/output.py.jinja`:
```jinja
"""Render SDK results as a Rich table (default), JSON, or YAML."""

from __future__ import annotations

import json
from typing import Any

import yaml
from rich.console import Console
from rich.table import Table

_console = Console()


def _to_data(obj: Any) -> Any:
    if isinstance(obj, list):
        return [_to_data(o) for o in obj]
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    return obj


def render(result: Any, fmt: str = "table") -> None:
    data = _to_data(result)
    if fmt == "json":
        _console.print_json(json.dumps(data, default=str))
        return
    if fmt == "yaml":
        print(yaml.safe_dump(data, sort_keys=False, default_flow_style=False), end="")
        return
    _render_table(data)


def _render_table(data: Any) -> None:
    rows = data if isinstance(data, list) else [data]
    rows = [r for r in rows if isinstance(r, dict)]
    if not rows:
        _console.print(data)
        return
    # column order: id, name first, then remaining scalar keys
    keys: list[str] = []
    for pref in ("id", "name"):
        if pref in rows[0]:
            keys.append(pref)
    for k, v in rows[0].items():
        if k not in keys and not isinstance(v, (dict, list)):
            keys.append(k)
    table = Table(*keys)
    for r in rows:
        table.add_row(*[str(r.get(k, "")) for k in keys])
    _console.print(table)
```

- [ ] **Step 4: Render it** — in `render_cli.py` add `render("_generated/output.py.jinja", gen / "output.py")`.

- [ ] **Step 5–6: Run, lint, type-check, commit**

Run: `uv run pytest tests/test_cli_emitted.py -v && uv run ruff check src/phantasos/generator tests/`
```bash
git add src/phantasos/generator/cli/templates/_generated/output.py.jinja src/phantasos/generator/cli/render_cli.py tests/test_cli_emitted.py
git commit -m "feat(cli-gen): emit output.py (Rich table / json / yaml)"
```

---

## Task 5: Emit `runtime.py` (dispatch + SDK call + errors) — the core

The runtime loads `ir.json`, picks the binding from supplied args, builds the call, invokes the SDK, renders. This is the heart of emission.

**Files:**
- Create: `src/phantasos/generator/cli/templates/_generated/runtime.py.jinja`
- Modify: `src/phantasos/generator/cli/render_cli.py`
- Test: `tests/test_cli_emitted.py`

- [ ] **Step 1: Write the failing test** (append — exercises dispatch against a mocked client):

```python
def test_runtime_dispatch_create_vs_patch(emitted, monkeypatch):
    rt = importlib.import_module("fakesdk_cli._generated.runtime")

    calls = []

    class _Api:
        def create_widget(self, widget_input):
            calls.append(("create", widget_input))
            return {"id": "w1"}

        def patch_widget(self, id, widget_input):
            calls.append(("patch", id, widget_input))
            return {"id": id}

    class _Client:
        widgets = _Api()

    monkeypatch.setattr(rt, "_client", lambda: _Client())

    # no --id => create binding
    rt.run("set:widget", path={}, body={"name": "foo"}, query={}, output="json",
           paginate_all=False, dry_run=False, verbose=False)
    # --id => patch binding
    rt.run("set:widget", path={"id": "w9"}, body={"name": "bar"}, query={}, output="json",
           paginate_all=False, dry_run=False, verbose=False)

    assert calls[0][0] == "create"
    assert calls[1][0] == "patch" and calls[1][1] == "w9"


def test_runtime_dry_run_does_not_call(emitted, monkeypatch, capsys):
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    called = []
    class _Api:
        def create_widget(self, widget_input):
            called.append(True)
    class _Client:
        widgets = _Api()
    monkeypatch.setattr(rt, "_client", lambda: _Client())
    rt.run("set:widget", path={}, body={"name": "x"}, query={}, output="json",
           paginate_all=False, dry_run=True, verbose=False)
    assert called == []
    assert "set:widget" in capsys.readouterr().out  # dry-run prints the planned call
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_cli_emitted.py -k runtime -v`
Expected: FAIL.

- [ ] **Step 3: Create `runtime.py.jinja`**

`src/phantasos/generator/cli/templates/_generated/runtime.py.jinja`:
```jinja
"""Command runtime: load ir.json, dispatch to the right SDK method, render results."""

from __future__ import annotations

import functools
import importlib
import importlib.resources
import json
import sys
from typing import Any

from . import output as _output

_SDK_PACKAGE = "{{ ir.sdk_package }}"


@functools.lru_cache(maxsize=1)
def _ir() -> dict[str, Any]:
    text = importlib.resources.files(__package__).joinpath("ir.json").read_text()
    data = json.loads(text)
    return {c["key"]: c for c in data["commands"]}


@functools.lru_cache(maxsize=1)
def _client() -> Any:
    mod = importlib.import_module(_SDK_PACKAGE)
    return mod.Client.from_env()


def _hooks() -> Any | None:
    try:
        return importlib.import_module("{{ package }}.hooks")
    except ModuleNotFoundError:
        return None


def _build_model(model_name: str, body: dict[str, Any]) -> Any:
    models = importlib.import_module(f"{_SDK_PACKAGE}.models")
    cls = getattr(models, model_name)
    parsed = {k: _maybe_json(v) for k, v in body.items() if v is not None}
    return cls(**parsed)


def _maybe_json(v: Any) -> Any:
    """JSON-string flags arrive as str; parse objects/arrays, pass scalars through."""
    if isinstance(v, str) and v[:1] in "[{":
        try:
            return json.loads(v)
        except json.JSONDecodeError:
            return v
    return v


def _pick_binding(cmd: dict[str, Any], present: set[str]) -> dict[str, Any]:
    candidates = [b for b in cmd["bindings"] if set(b["requires"]) <= present]
    if not candidates:
        raise SystemExit(
            f"error: no operation for '{cmd['key']}' matches the given arguments"
        )
    # most specific (largest satisfied requires) wins; deterministic tie-break by method
    return max(candidates, key=lambda b: (len(b["requires"]), b["sdk_method"]))


def run(key: str, *, path: dict[str, Any], body: dict[str, Any],
        query: dict[str, Any], output: str, paginate_all: bool,
        dry_run: bool, verbose: bool) -> None:
    cmd = _ir()[key]
    present = {k for k, v in path.items() if v is not None}
    binding = _pick_binding(cmd, present)

    kwargs: dict[str, Any] = {k: v for k, v in path.items() if v is not None}
    if cmd.get("variant") and cmd.get("variant_param"):
        kwargs[cmd["variant_param"]] = cmd["variant"]
    kwargs.update({k: v for k, v in query.items() if v is not None})
    if binding.get("body_model"):
        kwargs[binding["body_param"]] = _build_model(binding["body_model"], body)

    if dry_run:
        print(f"DRY-RUN {key} -> {cmd['sdk_resource']}.{binding['sdk_method']}({kwargs})")
        return

    hooks = _hooks()
    api = getattr(_client(), cmd["sdk_resource"])
    method = getattr(api, binding["sdk_method"])
    try:
        if hooks and (pre := getattr(hooks, "before_call", None)):
            kwargs = pre(binding["sdk_method"], kwargs, cmd) or kwargs
        result = method(**kwargs)
        if binding["sub_verb"] == "list" and paginate_all:
            result = list(_client().paginate(method, **kwargs))
        if hooks and (post := getattr(hooks, "after_call", None)):
            result = post(binding["sdk_method"], result, cmd) or result
    except Exception as exc:  # SDK ApiException and friends
        if verbose:
            raise
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    _output.render(result, fmt=output)
```

Notes for the implementer:
- The test monkeypatches `rt._client`; the real `_client` uses `Client.from_env()`. Keep `_client` a module-level function (so it's patchable) — the `lru_cache` means the test must patch before first call; the fixture re-imports the module fresh per test, so the cache is clean. If `lru_cache` interferes with monkeypatch, drop the cache on `_client` (simpler/testable) — prefer correctness: **remove `@functools.lru_cache` from `_client`** and just construct per call (the CLI is one-shot). Keep the cache on `_ir` only.
- `paginate` is best-effort for `--all`; if the SDK lacks `paginate`, guard with `getattr`.

- [ ] **Step 4: Render it** — in `render_cli.py` add `render("_generated/runtime.py.jinja", gen / "runtime.py")`.

- [ ] **Step 5: Run the runtime tests**

Run: `uv run pytest tests/test_cli_emitted.py -k runtime -v`
Expected: PASS.

- [ ] **Step 6: Lint, type-check, commit**

Run: `uv run ruff check src/phantasos/generator tests/ && uv run pytest tests/ -q`
```bash
git add src/phantasos/generator/cli/templates/_generated/runtime.py.jinja src/phantasos/generator/cli/render_cli.py tests/test_cli_emitted.py
git commit -m "feat(cli-gen): emit runtime.py (binding dispatch, model build, errors, dry-run)"
```

---

## Task 6: Emit command modules + `app.py` factory

Per resource, a module of Typer commands (one per command-key); `app.py` builds the verb sub-apps and registers commands, exposing `build_generated_app(exclude=...)`.

**Files:**
- Create: `src/phantasos/generator/cli/templates/_generated/commands.py.jinja` (rendered once per resource)
- Create: `src/phantasos/generator/cli/templates/_generated/app.py.jinja`
- Modify: `src/phantasos/generator/cli/render_cli.py` (group commands by resource; render a module each; render app.py)
- Test: `tests/test_cli_emitted.py`

- [ ] **Step 1: Write the failing test** (append — end-to-end via Typer's CliRunner against a mocked client):

```python
def test_cli_runner_show_and_set(emitted, monkeypatch):
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    rt = importlib.import_module("fakesdk_cli._generated.runtime")

    calls = []
    class _Widgets:
        def list_widgets(self, **kw): calls.append(("list", kw)); return []
        def get_widget_by_id(self, **kw): calls.append(("get", kw)); return {"id": kw["id"]}
        def create_widget(self, **kw): calls.append(("create", kw)); return {"id": "new"}
    class _Client:
        widgets = _Widgets()
        def paginate(self, m, **kw): return iter([])
    monkeypatch.setattr(rt, "_client", lambda: _Client())

    r = CliRunner()
    assert r.invoke(main.app, ["show", "widget", "--output", "json"]).exit_code == 0
    assert r.invoke(main.app, ["show", "widget", "--id", "w1", "--output", "json"]).exit_code == 0
    assert r.invoke(main.app, ["set", "widget", "--name", "foo", "--output", "json"]).exit_code == 0

    kinds = [c[0] for c in calls]
    assert "list" in kinds and "get" in kinds and "create" in kinds
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_cli_emitted.py::test_cli_runner_show_and_set -v`
Expected: FAIL (no app/commands yet).

- [ ] **Step 3: Create the command-module template**

`src/phantasos/generator/cli/templates/_generated/commands.py.jinja` (rendered with `ctx["commands"]` = the commands for one resource, `ctx["resource"]`):
```jinja
"""Generated commands for resource '{{ resource }}'. Do not edit."""

from __future__ import annotations

from typing import Optional

import typer

from .. import _generated as _g  # noqa: F401  (namespace marker)
from . import runtime as _rt

{% for c in commands %}
def {{ c.func_name }}(
{%- for f in c.all_flags %}
    {{ f.py_name }}: Optional[str] = typer.Option(None, "{{ f.name }}"{% if f.help %}, help={{ f.help|tojson }}{% endif %}),
{%- endfor %}
    output: str = typer.Option("table", "--output"),
    all_: bool = typer.Option(False, "--all"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    verbose: bool = typer.Option(False, "--verbose"),
) -> None:
    {%- if c.summary %}
    """{{ c.summary }}"""
    {%- endif %}
    _rt.run(
        "{{ c.key }}",
        path={ {% for f in c.path_params %}"{{ f.param }}": {{ f.py_name }}, {% endfor %} },
        body={ {% for f in c.body_flags %}"{{ f.param }}": {{ f.py_name }}, {% endfor %} },
        query={ {% for f in c.query_flags %}"{{ f.param }}": {{ f.py_name }}, {% endfor %} },
        output=output, paginate_all=all_, dry_run=dry_run, verbose=verbose,
    )

{% endfor %}
```

Note: `c.func_name`, `c.all_flags`, and `f.py_name` are computed by the emitter (Task 6 Step 4) — Jinja only iterates. `f.py_name` is the SDK param name (a valid Python identifier). `all_flags` = path_params + body_flags + query_flags. Flag names are unique within a command (the aggregation de-dups by flag name), so no Python param collisions.

`src/phantasos/generator/cli/templates/_generated/app.py.jinja`:
```jinja
"""Builds the generated Typer app. Compose it from a hand-owned entrypoint."""

from __future__ import annotations

import typer

{% for resource in resources %}
from .commands import {{ resource }} as _cmd_{{ resource }}
{%- endfor %}

# (verb, object[, variant]) -> (typer name, sub-app verb, function)
_REGISTRY = [
{%- for c in ir.commands %}
    ("{{ c.key }}", "{{ c.verb }}", "{{ c.object }}{% if c.variant %} {{ c.variant }}{% endif %}", _cmd_{{ c.sdk_resource }}.{{ c.func_name }}),
{%- endfor %}
]

_VERBS = ["set", "del", "show"]


def build_generated_app(exclude: set[str] | None = None) -> typer.Typer:
    exclude = exclude or set()
    app = typer.Typer(no_args_is_help=True)
    sub = {v: typer.Typer(no_args_is_help=True) for v in _VERBS}
    for verb, t in sub.items():
        app.add_typer(t, name=verb)
    for key, verb, name, fn in _REGISTRY:
        if key in exclude or verb not in sub:
            continue
        sub[verb].command(name)(fn)
    return app
```

Note: command names with a variant are `"object variant"` — Typer command names can't contain spaces. The emitter must instead register variant commands as a nested sub-app: `set <object> <variant>`. SIMPLIFY for Phase 2b set/del/show: register the Typer command name as the object, and for variant commands use a per-object sub-app. The emitter computes a `typer_path` per command (`[object]` or `[object, variant]`); `app.py` walks it. **Implementer:** adjust `_REGISTRY` to carry the path as a list and register by walking sub-apps (create an object-level `typer.Typer` when a variant exists). Keep the registration logic in `app.py` (generated) minimal; the path list comes from the emitter.

- [ ] **Step 4: Emitter changes** — in `render_cli.py`, compute per-command derived fields and group by resource. Add before rendering:
```python
def _func_name(cmd) -> str:
    base = f"{cmd.verb}_{cmd.object}".replace("-", "_")
    return f"{base}_{cmd.variant}".replace("-", "_") if cmd.variant else base


def _py_name(flag) -> str:
    return flag.param  # SDK param names are valid identifiers
```
Build a render context per resource: for each command attach `func_name`, `all_flags` (path+body+query), and a `typer_path` (`[object]` or `[object, variant]`); render one `commands/<resource>.py` per resource; render `app.py` with `resources` = sorted distinct `sdk_resource` and the registry. Use Jinja's `tojson` filter for help strings. Add to `render_cli`:
```python
    resources = sorted({c.sdk_resource for c in ir.commands})
    for resource in resources:
        cmds = [c for c in ir.commands if c.sdk_resource == resource]
        env.get_template(...)  # render commands.py.jinja with attached fields
    # render app.py with resources + registry
```
Attach the derived fields by wrapping each `Command` in a small dict/SimpleNamespace for the template (do NOT mutate the pydantic model): e.g. build `view = {"key":..., "func_name":..., "all_flags":[...], "path_params":..., "body_flags":..., "query_flags":..., "summary":..., "verb":..., "object":..., "variant":..., "variant_param":..., "sdk_resource":...}` and pass lists of views.

- [ ] **Step 5: Run the CliRunner test**

Run: `uv run pytest tests/test_cli_emitted.py::test_cli_runner_show_and_set -v`
Expected: PASS.

- [ ] **Step 6: Lint, type-check, commit**

Run: `uv run ruff check src/phantasos/generator tests/ && uv run pytest tests/ -q`
```bash
git add src/phantasos/generator/cli/templates src/phantasos/generator/cli/render_cli.py tests/test_cli_emitted.py
git commit -m "feat(cli-gen): emit command modules + build_generated_app factory"
```

---

## Task 7: Emit `pyproject.toml` + verify the project installs

**Files:**
- Create: `src/phantasos/generator/cli/templates/pyproject.toml.jinja` (hand-owned, emit-once)
- Modify: `src/phantasos/generator/cli/render_cli.py` (add to `_HANDOWNED`; needs distribution metadata)
- Test: `tests/test_cli_render.py`

- [ ] **Step 1: Write the failing test** (append to `tests/test_cli_render.py`):

```python
def test_emits_pyproject_with_console_script(tmp_path):
    render_cli(_ir(), package="fakesdk_cli", out_dir=tmp_path,
               distribution="fakesdk-cli", sdk_dependency="fakesdk")
    pyproject = (tmp_path / "pyproject.toml").read_text()
    assert "fakesdk-cli" in pyproject
    assert "typer" in pyproject and "rich" in pyproject
    assert "fakesdk_cli.main:app" in pyproject  # console_scripts entrypoint
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_cli_render.py::test_emits_pyproject_with_console_script -v`
Expected: FAIL (`render_cli` has no `distribution`/`sdk_dependency` kwargs; no pyproject).

- [ ] **Step 3: Add params + template.** Update `render_cli(...)` signature to `render_cli(ir, package, out_dir, *, distribution=None, sdk_dependency=None)`; default `distribution = package.replace("_","-")`, `sdk_dependency = ir.sdk_package`. Add `"pyproject.toml"` handling (it lives at project root, not under the package): emit-once at `out_dir / "pyproject.toml"` with context `{distribution, package, sdk_dependency}`.

`src/phantasos/generator/cli/templates/pyproject.toml.jinja`:
```jinja
[project]
name = "{{ distribution }}"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "typer>=0.12",
    "rich>=13",
    "pyyaml>=6",
    "{{ sdk_dependency }}",
]

[project.scripts]
{{ distribution }} = "{{ package }}.main:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

- [ ] **Step 4: Run the test**

Run: `uv run pytest tests/test_cli_render.py -v`
Expected: PASS.

- [ ] **Step 5: Lint, type-check, commit**

Run: `uv run ruff check src/phantasos/generator tests/ && uv run mypy src/phantasos/generator/cli/render_cli.py && uv run pytest tests/ -q`
```bash
git add src/phantasos/generator/cli/templates/pyproject.toml.jinja src/phantasos/generator/cli/render_cli.py tests/test_cli_render.py
git commit -m "feat(cli-gen): emit pyproject.toml with console_scripts entrypoint"
```

---

## Task 8: Wire `phantasos cli build <product>`

**Files:**
- Modify: `src/phantasos/cli.py`
- Test: `tests/test_cli_command.py`

- [ ] **Step 1: Write the failing test** (append):

```python
def test_cli_build_emits_project(tmp_path, monkeypatch):
    import phantasos.cli as climod

    class _Loaded:
        class config:  # noqa: N801
            package = "fakesdk"
        base_dir = FIXTURE
        output_dir = tmp_path / "fakesdk-cli"
        class project:  # noqa: N801
            distribution = "fakesdk-cli"

    monkeypatch.setattr(climod, "load_product", lambda name: _Loaded())
    rc = main(["cli", "build", "fakesdk"])
    assert rc == 0
    assert (tmp_path / "fakesdk-cli" / "fakesdk" / "_generated" / "app.py").exists()
    assert (tmp_path / "fakesdk-cli" / "pyproject.toml").exists()
```

Note: the generated CLI package name = `<sdk_package>` here for the fixture (`fakesdk`); for prisma it'd be `prisma_browser_cli` per `cli.yml`/product config. Use `loaded` to resolve package + distribution + output dir (see Step 3).

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_cli_command.py::test_cli_build_emits_project -v`
Expected: FAIL (no `cli build`).

- [ ] **Step 3: Add the `build` sub-subcommand** under the existing `cli` parser in `main()`:
```python
    bld = cli_sub.add_parser("build", help="emit the CLI project from a built SDK")
    bld.add_argument("product", help="product name (products/<name>/) or path to sdk.yml")
```
And the dispatch branch (before the final `return 0`):
```python
    if args.cmd == "cli" and args.cli_cmd == "build":
        from pathlib import Path

        from .generator.cli.classify import build_cli_ir
        from .generator.cli.cliconfig import load_cli_config
        from .generator.cli.introspect import introspect
        from .generator.cli.render_cli import render_cli

        try:
            loaded = load_product(args.product)
        except (FileNotFoundError, ValueError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        cfg = load_cli_config(Path(loaded.base_dir) / "cli.yml")
        try:
            inv = introspect(loaded.config.package, Path(loaded.output_dir))
        except ImportError as exc:
            print(f"ERROR: SDK not importable — build it first ({exc})", file=sys.stderr)
            return 2
        ir, unmapped = build_cli_ir(inv, cfg)
        # CLI package + output: convention <sdk_package>_cli into a sibling dir,
        # overridable via product config (project.distribution).
        cli_pkg = f"{loaded.config.package}_cli"
        out_dir = Path(loaded.output_dir).parent / f"{loaded.config.package}-cli"
        written = render_cli(ir, package=cli_pkg, out_dir=out_dir)
        print(f"emitted {len(written)} files to {out_dir} ({len(ir.commands)} commands)")
        if unmapped:
            print(f"note: {len(unmapped)} unmapped ops omitted (map in cli.yml)",
                  file=sys.stderr)
        return 0
```
(For the test's `_Loaded`, `output_dir` is `tmp_path/"fakesdk-cli"`, so `out_dir = tmp_path` and `cli_pkg = "fakesdk_cli"`; the assertion paths match. Confirm the path math against the test and adjust the convention if needed — keep the test as the contract.)

- [ ] **Step 4: Run the test**

Run: `uv run pytest tests/test_cli_command.py -v`
Expected: PASS (existing discover test + new build test).

- [ ] **Step 5: Lint, type-check, full suite, commit**

Run: `uv run ruff check src/phantasos tests/ && uv run mypy src/phantasos/generator src/phantasos/cli.py && uv run pytest tests/ -q`
```bash
git add src/phantasos/cli.py tests/test_cli_command.py
git commit -m "feat(cli-gen): wire 'phantasos cli build' command"
```

---

## Task 9: End-to-end against the real SDK (gated) + emitted-app smoke

**Files:**
- Test: `tests/test_cli_emitted.py` (append a gated real-SDK emit+import+CliRunner test)

- [ ] **Step 1: Write the gated test**

```python
REAL_SDK = Path(__file__).parent.parent.parent / "prisma-browser-sdk"


@pytest.mark.skipif(not REAL_SDK.exists(), reason="prisma-browser-sdk not built")
def test_emit_real_cli_and_help(tmp_path, monkeypatch):
    from typer.testing import CliRunner

    from phantasos.generator.cli.cliconfig import VariantMap

    cfg = CliConfig(variants={
        "applications.create_application": VariantMap(
            path_param="type",
            map={"custom": "CustomApplicationInput", "private": "PrivateApplicationInput",
                 "non-web": "NonWebApplicationInput",
                 "localdesktopcustom": "LocalDesktopApplicationInput"},
        )
    })
    try:
        ir = build_cli_ir(introspect("prisma_browser", REAL_SDK), cfg)[0]
    except ImportError as exc:
        pytest.skip(f"SDK runtime deps unavailable: {exc}")
    render_cli(ir, package="prisma_browser_cli", out_dir=tmp_path)
    sys.path.insert(0, str(tmp_path))
    try:
        for n in [n for n in sys.modules if n.startswith("prisma_browser_cli")]:
            del sys.modules[n]
        main = importlib.import_module("prisma_browser_cli.main")
        res = CliRunner().invoke(main.app, ["--help"])
        assert res.exit_code == 0
        assert "set" in res.output and "show" in res.output and "del" in res.output
        # a known object is reachable
        res2 = CliRunner().invoke(main.app, ["show", "--help"])
        assert "application" in res2.output
    finally:
        sys.path.remove(str(tmp_path))
        for n in [n for n in sys.modules if n.startswith("prisma_browser_cli")]:
            del sys.modules[n]
```

- [ ] **Step 2: Run it**

Run: `uv run pytest tests/test_cli_emitted.py::test_emit_real_cli_and_help -v`
Expected: PASS (the emitted real CLI imports and its `--help` lists verbs + a real object). If it FAILS on an emission/dispatch shape the fixture missed, debug the emitter/templates (do not weaken the test); if a template can't handle a real flag type, fix the template.

- [ ] **Step 3: Full suite + commit**

Run: `uv run pytest tests/ -q && uv run ruff check src/phantasos tests/ && uv run mypy src/phantasos/generator src/phantasos/cli.py`
```bash
git add tests/test_cli_emitted.py
git commit -m "test(cli-gen): gated end-to-end emit of the real prisma-browser CLI"
```

---

## Task 10: Generate `COMMANDS.md` reference

**Files:**
- Modify: `src/phantasos/generator/cli/render_cli.py` (post-emit: run `typer ... utils docs` into `docs/COMMANDS.md`)
- Test: `tests/test_cli_render.py`

- [ ] **Step 1: Write the failing test** (append):

```python
def test_command_reference_generated(tmp_path):
    render_cli(_ir(), package="fakesdk_cli", out_dir=tmp_path, write_docs=True)
    md = tmp_path / "docs" / "COMMANDS.md"
    assert md.exists()
    text = md.read_text()
    assert "set" in text and "show" in text
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_cli_render.py::test_command_reference_generated -v`
Expected: FAIL (`write_docs` kwarg / no docs).

- [ ] **Step 3: Implement.** Add `write_docs: bool = False` to `render_cli`. When true, after emitting, generate the reference. Since `typer utils docs` needs an importable app and the SDK installed, do it **in-process** (more robust than subprocess in tests): import the emitted app via a temporary `sys.path` insert and call Typer's docs generator. Implement a helper:
```python
def _write_docs(out_dir: Path, package: str) -> None:
    import sys as _sys
    from typer.main import get_command  # Typer -> Click command
    inserted = str(out_dir) not in _sys.path
    if inserted:
        _sys.path.insert(0, str(out_dir))
    try:
        for n in [n for n in _sys.modules if n.startswith(package)]:
            del _sys.modules[n]
        main = importlib.import_module(f"{package}.main")
        from click.testing import CliRunner as _Click  # noqa
        # Use Click's context to render help recursively into markdown.
        md = _render_click_help(get_command(main.app), package)
        docs = out_dir / "docs"
        docs.mkdir(exist_ok=True)
        (docs / "COMMANDS.md").write_text(md, encoding="utf-8")
    finally:
        if inserted:
            _sys.path.remove(str(out_dir))
```
Provide a minimal `_render_click_help(cmd, name, level=1)` that walks the Click command tree and emits markdown headers + each command's `--help` text (Click's `get_help()` via a `click.Context`). This avoids depending on the external `typer` CLI binary at build time and works in tests. (If the importing requires the fakesdk on the path, the test fixture already emits into tmp_path; ensure `fakesdk` is importable — the test adds `tests/fixtures/fakesdk` via the `introspect` step's path handling, but `_write_docs` imports `<package>.main` which imports the SDK Client lazily only at runtime, NOT at import — confirm `main.py`/`app.py` import is side-effect-free w.r.t. the SDK, which it is, since `_client()` is called only on command execution.)

- [ ] **Step 4: Run the test**

Run: `uv run pytest tests/test_cli_render.py -v`
Expected: PASS.

- [ ] **Step 5: Wire `--docs` into `cli build`** (optional flag) and full suite + commit

Add to the `build` parser: `bld.add_argument("--docs", action="store_true", help="also write docs/COMMANDS.md")` and pass `write_docs=args.docs` to `render_cli`.
Run: `uv run pytest tests/ -q && uv run ruff check src/phantasos tests/ && uv run mypy src/phantasos/generator src/phantasos/cli.py`
```bash
git add src/phantasos/generator/cli/render_cli.py src/phantasos/cli.py tests/test_cli_render.py
git commit -m "feat(cli-gen): generate docs/COMMANDS.md command reference"
```

---

## Self-review (completed during authoring)

- **Spec coverage:** emission via Jinja (Tasks 2–7); `_generated/`-vs-hand-owned split + regen contract (Task 2); `build_generated_app(exclude=)` factory + hooks (Tasks 5–6); runtime dispatch using bindings/requires + `--id`/variant (Task 5); config.yaml+env+flag precedence (Task 3); Rich/json/yaml output (Task 4); permissive enum flags (emitted as `str` Options — Task 6); `--dry-run` (Task 5); `phantasos cli build` (Task 8); pyproject + console_scripts (Task 7); COMMANDS.md (Task 10); end-to-end real-SDK proof (Task 9). The recorded Phase-2a review inputs are resolved in Task 1 (variant_param carried; body_param/body_model per binding; aggregated body flags optional; same-resource guard). **Out of scope (Phase 3, stated):** `request`/`load`/`backup`, dynamic completion, dot-notation nested flags, named profiles, full scaffold/mkdocs site.
- **Placeholder scan:** none — every step has concrete code. Two steps (Task 6 variant sub-app registration, Task 10 `_render_click_help`) explicitly delegate a small, well-described derivation to the implementer with the test as the contract; these are flagged, not vague.
- **Type consistency:** `MethodBinding.body_param`/`body_model` + `Command.variant_param` (Task 1) are consumed by the runtime template (Task 5) and emitter (Task 6); `render_cli(ir, package, out_dir, *, distribution, sdk_dependency, write_docs)` signature is introduced in Task 2 and extended in Tasks 3–7/10 consistently; the emitted `runtime.run(key, *, path, body, query, output, paginate_all, dry_run, verbose)` signature matches its call site in `commands.py.jinja` (Task 6) and the tests (Task 5).

## Risks / things the review passes should scrutinize

1. **Generating valid Python function signatures from flags (Task 6)** — the trickiest emission. Edge cases: a flag whose `param` is a Python keyword/`output`/`all_`/`dry_run`/`verbose` collision; flags needing distinct CLI names that map to the same `param`. Mitigation to verify: prefix reserved names, assert flag-`param` uniqueness per command (the aggregation de-dups by flag *name* but two different params could share neither — confirm).
2. **Variant commands as `set <object> <variant>`** — Typer can't have spaces in a command name; needs object-level sub-apps. Task 6 calls this out; the review should confirm the registration design is sound.
3. **`importlib.resources` for `ir.json`** inside `_generated` — confirm the package is importable as a resource anchor (`__package__`).
4. **`_client()` cache vs monkeypatch** — Task 5 note removes the cache; confirm tests don't rely on caching.
5. **`COMMANDS.md` without the external `typer` binary** — Task 10 renders via Click in-process; the review should confirm this is robust and doesn't import the SDK at module load.
6. **Body model construction** — `_build_model` drops `None` and JSON-parses `[`/`{` strings; confirm this is correct for scalar-vs-json flags and that a missing required model field yields a friendly error (caught by the `except` in `run`).
