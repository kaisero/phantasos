# CLI Generated Docs — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate a standalone MkDocs site (quickstart + per-object command reference + guides) into each generated CLI project, rendered from the CLI IR at build time, mirroring the SDK docs feature (#30/#33).

**Architecture:** A new CLI-owned docs stage (`generator/cli/docs.py` + `generator/cli/examples.py` + `generator/cli/templates/docs/`) builds a docs context from the already-resolved `CliIR` and renders concrete markdown + the CLI `mkdocs.yml` inside `render_cli` (no mkdocstrings, no gen-files). The emitted CLI's flag grouping and the docs reference share one helper module (`generator/cli/flags.py`) so the reference can never drift from `--help`. A dedicated `cli_docs` scaffold flag gates generic infra (docs dependency group, `docs` nox session, Pages workflow, README link); the SDK doc templates are never touched (`has_docs` stays `False` for CLI builds).

**Tech Stack:** Python 3.11+, pydantic v2, Jinja2 (StrictUndefined), Typer/Rich (the emitted CLI), MkDocs-Material, nox + uv, pytest.

**Spec:** `docs/specs/2026-06-21-cli-generated-docs-design.md` (decisions D1–D17). **ADR:** `docs/adr/0001-cli-docs-ir-driven-generate-time.md`.

**This plan was revised after two independent expert reviews (python-pro + python-anti-patterns).** Their key findings are folded in: CLI docs tests live under `tests/cli/` (the existing root `tests/test_cli_docs.py` is an SDK-docs test and is left untouched); a shared `tests/cli/conftest.py` `emit_cli` factory (no cross-module `__import__`); a shared `flags.py` so `docs.py` cannot drift from the emitted CLI; `render_cli` types `docs` properly with a normal import (no real circular import exists); the `cli-docs` nox session derives the CLI output dir authoritatively.

## Global Constraints

- **Separation of duty (D7):** the CLI value strategy lives in `generator/cli/examples.py` and is **NOT** imported from / shared with `generator/sdk/examples.py`, even though logic is duplicated. (Sharing *within* the CLI path — `generator/cli/flags.py` — is fine and intended.)
- **SDK docs untouched (D11):** never edit `generator/sdk/docs.py`, `generator/sdk/examples.py`, `scaffold/docs/**`, `scaffold/mkdocs.yml.jinja`, or `scaffold/docs/scripts/**`. The CLI must never emit `client.<object>` content, mkdocstrings, gen-files, or literate-nav.
- **Do not touch the existing `tests/test_cli_docs.py`** — it is the committed SDK docs-context test from #33. All NEW CLI docs tests live under `tests/cli/`.
- **Frozen oracles:** never edit a file matching `protected_globs` in `.claude/harness.toml` to make work pass. If an oracle looks wrong, STOP and surface it.
- **`has_docs` stays `False` for CLI builds.** CLI docs are driven by a new, independent `cli_docs` flag (`cfg.docs is not None`).
- **IR-driven, generate-time (D2/D3):** the reference is rendered from `CliIR`; no live CLI import is needed to build the docs markdown.
- **Reference depth (D9):** per-object pages; flag tables show the FULL surface; synthesized examples are REQUIRED-only.
- **TDD, DRY, YAGNI, frequent commits.** Evidence before assertions: show real command output before claiming a pass.
- **Env quirk:** run nox/uv with an explicit env dir on sshfs checkouts. All commands below assume `UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run ...` from the repo root; for venv-backed nox sessions also prefix `NOX_ENVDIR=/tmp/phantasos-nox`.
- **Branching:** work on `feature/cli-docs`; record user-facing changes under `## [Unreleased]` in `CHANGELOG.md`; do NOT bump `version`.
- **Test discovery:** `tests/` is NOT a package (no `__init__.py`); `pyproject.toml` sets `testpaths=["tests"]` (recursive). New files under `tests/cli/` are discovered automatically as long as their basenames are unique repo-wide (they are: `test_docs_*`, `test_exit_codes.py`). Do NOT add `__init__.py`.

---

### Task 0: Verify adem CLI buildability (prerequisite for D17 rollout)

**Why first:** D17 enrolls prisma-browser, adem, posture in the `cli-docs` gate, which requires `phantasos cli build <product>` to succeed. Memory `pr33-ci-wrapper-branch-gaps` records adem non-CRUD ops as unbuildable under the clean-wrapper classifier. De-risk the rollout before any framework code; if adem can't build, Task 12 enrolls only the products that can and files a follow-up.

**Files:**
- Possibly modify: `products/adem/cli.yml` (add `hide`/`request` entries for non-CRUD ops — only if the build reports unmapped/unbuildable ops)

- [ ] **Step 1: Build all three product SDKs, then their CLIs, capturing output**

```bash
cd /home/ubuntu/git/phantasos
for p in prisma-browser adem posture; do
  echo "=== $p sdk ==="; UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run phantasos sdk build "$p" --no-smoke || echo "SDK BUILD FAILED: $p"
  echo "=== $p cli ==="; UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run phantasos cli build "$p" || echo "CLI BUILD FAILED: $p"
done
```
Expected: each prints `emitted N files ... (M commands)`. Note any `unmapped ops omitted` line or a non-zero exit.

- [ ] **Step 2: If adem reports unmapped/unbuildable ops, classify them in `products/adem/cli.yml`**

For each unmapped op named in the output, add a `hide:` entry (exclude) or a `request:` entry (expose as a non-CRUD action), following existing `cli.yml` patterns and memory `cli-override-cannot-classify-unmapped` (raw-operationId ops must be renamed in `sdk.yml`, not `cli.yml`). Re-run Step 1 for adem until it builds cleanly.

- [ ] **Step 3: Record the result**

If all three build: proceed; Task 12 enrolls all three. If adem cannot be made to build within this task's scope: note it in the PR description, enroll only the buildable products in Task 12, and leave a `# adem: pending buildability` comment in `nox.toml [cli-docs]`. Do NOT block framework tasks (1–11) on this.

- [ ] **Step 4: Commit any cli.yml changes** (skip if none were needed)

```bash
git add products/adem/cli.yml
git commit -m "fix(adem): classify non-CRUD ops so the CLI builds (cli-docs prereq)"
```

---

### Task 1: `CliDocsConfig` model + `docs` field on `CliConfig`

**Files:**
- Modify: `src/phantasos/generator/cli/cliconfig.py`
- Test: `tests/cli/test_docs_config.py` (NEW — do NOT use `tests/test_cli_docs.py`, which exists and is an SDK test)

**Interfaces:**
- Produces: `CliDocsConfig(showcase_object: str, showcase_variant: str | None = None, site_name: str | None = None, examples: dict[str, str] = {})`; `CliConfig.docs: CliDocsConfig | None = None`.

- [ ] **Step 1: Write the failing test**

```python
# tests/cli/test_docs_config.py
from pathlib import Path

import pytest
from pydantic import ValidationError

from phantasos.generator.cli.cliconfig import CliConfig, CliDocsConfig, load_cli_config


def test_cli_config_parses_docs_block(tmp_path: Path) -> None:
    p = tmp_path / "cli.yml"
    p.write_text(
        "docs:\n"
        "  showcase_object: widget\n"
        "  showcase_variant: simple\n"
        "  site_name: Acme CLI\n"
        "  examples:\n"
        '    "create:widget": acmecli create widget --name foo\n',
        encoding="utf-8",
    )
    cfg = load_cli_config(p)
    assert cfg.docs == CliDocsConfig(
        showcase_object="widget",
        showcase_variant="simple",
        site_name="Acme CLI",
        examples={"create:widget": "acmecli create widget --name foo"},
    )


def test_cli_docs_absent_is_none(tmp_path: Path) -> None:
    p = tmp_path / "cli.yml"
    p.write_text("hide: []\n", encoding="utf-8")
    assert load_cli_config(p).docs is None


def test_cli_docs_requires_showcase_object() -> None:
    with pytest.raises(ValidationError):
        CliDocsConfig()  # type: ignore[call-arg]


def test_cli_docs_forbids_unknown_key() -> None:
    with pytest.raises(ValidationError):
        CliDocsConfig(showcase_object="widget", bogus=1)  # type: ignore[call-arg]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run pytest tests/cli/test_docs_config.py -v`
Expected: FAIL with `ImportError: cannot import name 'CliDocsConfig'`.

- [ ] **Step 3: Add the model + field**

In `src/phantasos/generator/cli/cliconfig.py`, add after `class CustomPointer` (~line 53):

```python
class CliDocsConfig(BaseModel):
    """Opt-in CLI documentation generation (cli.yml `docs:` block).

    Independent of the SDK's sdk.yml `docs:` block. `showcase_object` is a CLI
    command object (validated against the CliIR at build time). `examples` maps a
    command key ("verb:object[:variant_or_action]") to a verbatim invocation that
    overrides the synthesized example for that command. (A bare `= {}` default is
    safe here: pydantic v2 deep-copies field defaults per instance.)
    """

    model_config = ConfigDict(extra="forbid")
    showcase_object: str
    showcase_variant: str | None = None
    site_name: str | None = None
    examples: dict[str, str] = {}
```

Add to `class CliConfig` (after `defaults`, ~line 70):

```python
    docs: CliDocsConfig | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run pytest tests/cli/test_docs_config.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generator/cli/cliconfig.py tests/cli/test_docs_config.py
git commit -m "feat(cli-docs): add CliDocsConfig + cli.yml docs block"
```

---

### Task 2: Extract shared flag helpers (`flags.py`) + refactor `render_cli` to use them

**Why:** `render_cli._command_view` and the new `docs.py` both need the exact same path/body/query dedup and Filters/Pagination split. Two independent copies would let the reference drift from `--help`, breaking D2. Extract one source of truth. This is a behavior-preserving refactor of `render_cli` — existing tests (`test_cli_render.py`, `test_cli_emitted.py`, `test_cli_command.py`) are the regression guard.

**Files:**
- Create: `src/phantasos/generator/cli/flags.py`
- Modify: `src/phantasos/generator/cli/render_cli.py` (import from `flags.py`; replace inline dedup)
- Test: `tests/cli/test_flags.py` (NEW)

**Interfaces:**
- Produces: `flags.query_panel(f: Flag) -> str`, `flags.leaf(c: Command) -> str | None`, `flags.dedupe_flags(c: Command) -> tuple[list[Flag], list[Flag]]` (returns `(body, query)` deduped), `flags.PAGINATION_PARAMS: frozenset[str]`.
- `render_cli` continues to expose `_query_panel` and `_leaf` names (now aliases) so unchanged internal callers keep working.

- [ ] **Step 1: Write the failing test**

```python
# tests/cli/test_flags.py
from phantasos.generator.cli.flags import dedupe_flags, leaf, query_panel
from phantasos.generator.cli.ir import Command, Flag


def _f(name, *, required=True):
    return Flag(name=f"--{name}", param=name, py_type="str", kind="scalar", required=required)


def test_query_panel_splits_pagination_from_filters() -> None:
    assert query_panel(_f("limit")) == "Pagination"
    assert query_panel(_f("name")) == "Filters"


def test_leaf_prefers_variant_then_action() -> None:
    assert leaf(Command(verb="create", object="g", variant="simple", key="k", sdk_resource="g")) == "simple"
    assert leaf(Command(verb="request", object="w", action="suspend", key="k", sdk_resource="w")) == "suspend"
    assert leaf(Command(verb="show", object="w", key="k", sdk_resource="w")) is None


def test_dedupe_flags_path_then_body_wins() -> None:
    c = Command(
        verb="update", object="w", key="k", sdk_resource="w",
        path_params=[_f("id"), _f("type")],
        body_flags=[_f("type"), _f("name")],         # 'type' shadows the path param
        query_flags=[_f("name"), _f("limit")],        # 'name' shadows the body flag
    )
    body, query = dedupe_flags(c)
    assert [f.param for f in body] == ["name"]
    assert [f.param for f in query] == ["limit"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run pytest tests/cli/test_flags.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'phantasos.generator.cli.flags'`.

- [ ] **Step 3: Create `flags.py`**

```python
# src/phantasos/generator/cli/flags.py
"""Shared flag-grouping helpers for the CLI generator.

Both the emitted command modules (render_cli) and the docs command reference
(docs.py) import these so the reference's flag set and grouping can never drift
from the emitted `--help` (design D2). NOT shared with the SDK generator path.
"""

from __future__ import annotations

from .ir import Command, Flag

# Well-known pagination/sort query params get their own help panel; the rest are filters.
PAGINATION_PARAMS = frozenset(
    {
        "limit",
        "offset",
        "cursor",
        "page",
        "page_size",
        "per_page",
        "sort",
        "order",
        "sort_by",
        "order_by",
        "sort_order",
    }
)


def query_panel(f: Flag) -> str:
    return "Pagination" if f.param in PAGINATION_PARAMS else "Filters"


def leaf(c: Command) -> str | None:
    """The third command segment: a oneOf variant OR a request action (mutually exclusive)."""
    return c.variant or c.action


def dedupe_flags(c: Command) -> tuple[list[Flag], list[Flag]]:
    """Return (body, query) flags deduped against path params (path wins), then
    query deduped against body — exactly the flag set the emitted command exposes."""
    path_names = {f.param for f in c.path_params}
    body = [f for f in c.body_flags if f.param not in path_names]
    body_names = {f.param for f in body}
    query = [
        f
        for f in c.query_flags
        if f.param not in path_names and f.param not in body_names
    ]
    return body, query
```

- [ ] **Step 4: Refactor `render_cli.py` to use `flags.py`**

(a) Replace the `_PAGINATION_PARAMS` block (lines 38–53), `_query_panel` (56–57), and `_leaf` (67–71) with a single import after `from .ir import CliIR, Command, Flag` (line 16):

```python
from .flags import PAGINATION_PARAMS, dedupe_flags  # noqa: F401  (PAGINATION_PARAMS re-exported)
from .flags import leaf as _leaf
from .flags import query_panel as _query_panel
```

(b) In `_command_view` (lines 228–240), replace the inline dedup:

```python
    deduped_body, deduped_query = dedupe_flags(c)
```

(remove the `path_param_names` / `deduped_body` / `deduped_query` comprehension lines; keep everything after that unchanged — `deduped_body`/`deduped_query` are still referenced below).

- [ ] **Step 5: Run the regression tests + new test**

Run:
```bash
UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run pytest tests/cli/test_flags.py tests/test_cli_render.py tests/test_cli_emitted.py tests/test_cli_command.py -q
```
Expected: PASS (the refactor is behavior-preserving). If any emitted-CLI test changes output, STOP — the extraction changed behavior; reconcile before continuing.

- [ ] **Step 6: Commit**

```bash
git add src/phantasos/generator/cli/flags.py src/phantasos/generator/cli/render_cli.py tests/cli/test_flags.py
git commit -m "refactor(cli): extract shared flag helpers (single source for render + docs)"
```

---

### Task 3: CLI example value strategy + invocation renderer

**Files:**
- Create: `src/phantasos/generator/cli/examples.py`
- Test: `tests/cli/test_docs_examples.py` (NEW)

**Interfaces:**
- Consumes: `Command`, `Flag` (`ir.py`); `flags.leaf` (Task 2).
- Produces: `example_value(flag: Flag) -> str`; `render_invocation(command: Command, *, distribution: str, override: str | None = None) -> str`.

- [ ] **Step 1: Write the failing test**

```python
# tests/cli/test_docs_examples.py
from phantasos.generator.cli.examples import example_value, render_invocation
from phantasos.generator.cli.ir import Command, Flag


def _flag(name, *, py_type="str", kind="scalar", required=True, choices=None) -> Flag:
    return Flag(
        name=name, param=name.lstrip("-").replace("-", "_"), py_type=py_type,
        kind=kind, required=required, choices=choices,
    )


def test_example_value_by_type() -> None:
    assert example_value(_flag("--name", py_type="str")) == '"example"'
    assert example_value(_flag("--count", py_type="int")) == "0"
    assert example_value(_flag("--ratio", py_type="float")) == "0.0"
    assert example_value(_flag("--on", py_type="bool")) == "true"
    assert example_value(_flag("--color", kind="enum", choices=["red", "blue"])) == "red"
    assert example_value(_flag("--body", kind="json")) == "'{}'"
    assert example_value(_flag("--file", kind="file")) == "./file"
    assert example_value(_flag("--id", kind="id")) == '"example"'


def test_render_invocation_required_only() -> None:
    cmd = Command(
        verb="create", object="widget", key="create:widget", sdk_resource="widgets",
        path_params=[_flag("--id")],
        body_flags=[_flag("--name"), _flag("--note", required=False)],
        query_flags=[_flag("--limit", py_type="int", required=False)],
    )
    assert render_invocation(cmd, distribution="acmecli") == (
        'acmecli create widget --id "example" --name "example"'
    )


def test_render_invocation_leaf_and_override() -> None:
    variant = Command(
        verb="create", object="gizmo", variant="simple", key="create:gizmo:simple",
        sdk_resource="gizmos", body_flags=[_flag("--name")],
    )
    assert render_invocation(variant, distribution="acmecli") == (
        'acmecli create gizmo simple --name "example"'
    )
    assert render_invocation(variant, distribution="acmecli", override="acmecli foo") == "acmecli foo"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run pytest tests/cli/test_docs_examples.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'phantasos.generator.cli.examples'`.

- [ ] **Step 3: Write the module**

```python
# src/phantasos/generator/cli/examples.py
"""Synthesize illustrative CLI invocations from the resolved command IR.

Deliberately NOT shared with generator/sdk/examples.py: the SDK path synthesizes
Python constructor expressions; this path renders shell invocations. Keeping the
value strategy duplicated keeps the two generator paths independently evolvable
(see docs/adr/0001-cli-docs-ir-driven-generate-time.md). It DOES share intra-CLI
helpers from flags.py.
"""

from __future__ import annotations

from .flags import dedupe_flags, leaf
from .ir import Command, Flag

# Honest placeholder values rendered as shell tokens. Required-only examples stay
# short and copy-pasteable; full flag detail lives in the reference flag tables.
_SCALARS: dict[str, str] = {
    "int": "0",
    "float": "0.0",
    "bool": "true",
    "str": '"example"',
}


def example_value(flag: Flag) -> str:
    """A shell-safe example value token for one flag."""
    if flag.choices:
        return flag.choices[0]
    if flag.kind == "json":
        return "'{}'"
    if flag.kind == "file":
        return "./file"
    if flag.kind == "id":
        return '"example"'
    return _SCALARS.get(flag.py_type, '"example"')


def _required_flags(c: Command) -> list[Flag]:
    """Required flags the command exposes, in path → body → query order.

    Built on flags.dedupe_flags so the synthesized example can't drift from the
    reference table / `--help` (one source of truth for the command's flag set)."""
    body, query = dedupe_flags(c)
    return [f for f in (*c.path_params, *body, *query) if f.required]


def render_invocation(
    command: Command, *, distribution: str, override: str | None = None
) -> str:
    """A one-line invocation example (required flags only) or the verbatim override."""
    if override is not None:
        return override.strip()
    parts = [distribution, command.verb, command.object]
    third = leaf(command)
    if third:
        parts.append(third)
    for f in _required_flags(command):
        parts.append(f"{f.name} {example_value(f)}")
    return " ".join(parts)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run pytest tests/cli/test_docs_examples.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generator/cli/examples.py tests/cli/test_docs_examples.py
git commit -m "feat(cli-docs): CLI example value strategy + invocation renderer"
```

---

### Task 4: CLI docs context builder (+ drift guard + key-contract test)

**Files:**
- Create: `src/phantasos/generator/cli/docs.py`
- Test: `tests/cli/test_docs_context.py` (NEW)

**Interfaces:**
- Consumes: `CliIR`, `Command`, `Flag` (`ir.py`); `CliDocsConfig` (Task 1); `render_invocation` (Task 3); `flags.dedupe_flags`, `flags.query_panel`, `flags.leaf` (Task 2).
- Produces: `build_cli_docs_context(ir, docs, *, distribution, site_name) -> dict[str, object]`. Context keys: `cli_docs`, `site_name`, `distribution`, `objects` (`[{object, commands}]`), `showcase`, `has_auth`, `show_pagination_guide`, `credentials`, `error_envelope`. Command-view keys: `key, usage, summary, description, path_flags, body_flags, filter_flags, pagination_flags, example, paginated, get_by_id_only, columns`.

- [ ] **Step 1: Write the failing test**

```python
# tests/cli/test_docs_context.py
import pytest

from phantasos.generator.cli.cliconfig import CliDocsConfig
from phantasos.generator.cli.docs import CONTEXT_KEYS, build_cli_docs_context
from phantasos.generator.cli.ir import CliIR, Command, CredentialField, Flag
from phantasos.generator.cli.render_cli import _command_view


def _flag(name, **kw):
    kw.setdefault("param", name.lstrip("-").replace("-", "_"))
    kw.setdefault("py_type", "str")
    kw.setdefault("kind", "scalar")
    kw.setdefault("required", True)
    return Flag(name=name, **kw)


def _ir() -> CliIR:
    return CliIR(
        sdk_package="acme",
        sdk_version="1",
        credential_fields=[CredentialField(name="token", env_var="ACME_TOKEN")],
        commands=[
            Command(verb="create", object="widget", key="create:widget",
                    sdk_resource="widgets", summary="Create a widget.",
                    body_flags=[_flag("--name")]),
            Command(verb="show", object="widget", key="show:widget",
                    sdk_resource="widgets", summary="List widgets.", paginated=True,
                    query_flags=[_flag("--limit", py_type="int", required=False),
                                 _flag("--name", required=False)]),
        ],
    )


def test_context_groups_by_object_and_gates_guides() -> None:
    ctx = build_cli_docs_context(
        _ir(), CliDocsConfig(showcase_object="widget"),
        distribution="acmecli", site_name="Acme CLI",
    )
    assert ctx["cli_docs"] is True
    assert ctx["site_name"] == "Acme CLI"
    assert [o["object"] for o in ctx["objects"]] == ["widget"]
    assert ctx["has_auth"] is True
    assert ctx["show_pagination_guide"] is True
    create = ctx["objects"][0]["commands"][0]
    assert create["usage"] == "acmecli create widget [OPTIONS]"
    assert create["example"] == 'acmecli create widget --name "example"'
    assert ctx["showcase"]["object"] == "widget"
    assert ctx["showcase"]["has_create"] is True


def test_context_key_set_is_the_documented_contract() -> None:
    ctx = build_cli_docs_context(
        _ir(), CliDocsConfig(showcase_object="widget"),
        distribution="acmecli", site_name="x",
    )
    assert set(ctx) == CONTEXT_KEYS


def test_docs_flags_match_emitted_help() -> None:
    """D2 guard: the reference flag set per command equals the emitted CLI's."""
    ir = _ir()
    variant_groups = {(c.verb, c.object) for c in ir.commands if c.variant or c.action}
    ctx = build_cli_docs_context(
        ir, CliDocsConfig(showcase_object="widget"), distribution="acmecli", site_name="x"
    )
    docs_by_key = {cmd["key"]: cmd for o in ctx["objects"] for cmd in o["commands"]}
    for c in ir.commands:
        emitted = {f["name"] for f in _command_view(c, variant_groups)["all_flags"]}
        d = docs_by_key[c.key]
        rendered = {
            f["name"]
            for grp in ("path_flags", "body_flags", "filter_flags", "pagination_flags")
            for f in d[grp]
        }
        assert rendered == emitted, c.key


def test_query_flags_split_filters_vs_pagination() -> None:
    """D16/D9 guard: the Filters/Pagination split (not just membership) is correct."""
    ctx = build_cli_docs_context(
        _ir(), CliDocsConfig(showcase_object="widget"), distribution="acmecli", site_name="x"
    )
    show = next(
        c for o in ctx["objects"] for c in o["commands"] if c["key"] == "show:widget"
    )
    assert [f["name"] for f in show["pagination_flags"]] == ["--limit"]
    assert [f["name"] for f in show["filter_flags"]] == ["--name"]


def test_unknown_showcase_object_raises() -> None:
    with pytest.raises(ValueError, match="not a CLI object"):
        build_cli_docs_context(
            _ir(), CliDocsConfig(showcase_object="nope"),
            distribution="acmecli", site_name="x",
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run pytest tests/cli/test_docs_context.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'phantasos.generator.cli.docs'`.

- [ ] **Step 3: Write the module**

```python
# src/phantasos/generator/cli/docs.py
"""Build the CLI docs render context from the resolved CliIR (IR-driven, generate-time).

No live CLI import and no mkdocstrings: the command reference is a pure function of
the CliIR. Shares flag grouping with the emitted CLI via flags.py so the reference
cannot drift from `--help` (D2). The SDK docs path (generator/sdk/docs.py) is NOT
reused (see docs/adr/0001-cli-docs-ir-driven-generate-time.md).
"""

from __future__ import annotations

from .cliconfig import CliDocsConfig
from .examples import render_invocation
from .flags import dedupe_flags, leaf, query_panel
from .ir import CliIR, Command, Flag

CONTEXT_KEYS = frozenset(
    {
        "cli_docs",
        "site_name",
        "distribution",
        "objects",
        "showcase",
        "has_auth",
        "show_pagination_guide",
        "credentials",
        "error_envelope",
        "repo_url",
        "description",
    }
)


def _usage(c: Command, distribution: str) -> str:
    parts = [distribution, c.verb, c.object]
    third = leaf(c)
    if third:
        parts.append(third)
    parts.append("[OPTIONS]")
    return " ".join(parts)


def _flag_row(f: Flag) -> dict[str, object]:
    return {
        "name": f.name,
        "type": f.py_type,
        "required": f.required,
        "choices": f.choices,
        "help": f.help,
    }


def _command_view(c: Command, *, distribution: str, override: str | None) -> dict[str, object]:
    body, query = dedupe_flags(c)
    filters = [f for f in query if query_panel(f) == "Filters"]
    pagination = [f for f in query if query_panel(f) == "Pagination"]
    return {
        "key": c.key,
        "usage": _usage(c, distribution),
        "summary": c.summary,
        "description": c.description,
        "path_flags": [_flag_row(f) for f in c.path_params],
        "body_flags": [_flag_row(f) for f in body],
        "filter_flags": [_flag_row(f) for f in filters],
        "pagination_flags": [_flag_row(f) for f in pagination],
        "example": render_invocation(c, distribution=distribution, override=override),
        "paginated": c.paginated,
        "get_by_id_only": c.get_by_id_only,
        "columns": [{"header": col.header, "path": col.path} for col in c.columns],
    }


def _showcase(commands: list[Command], obj: str) -> dict[str, object]:
    verbs = {c.verb for c in commands if c.object == obj}
    return {
        "object": obj,
        "has_create": "create" in verbs,
        "has_show": "show" in verbs,
        "has_update": "update" in verbs,
        "has_delete": "delete" in verbs,
    }


def build_cli_docs_context(
    ir: CliIR,
    docs: CliDocsConfig,
    *,
    distribution: str,
    site_name: str,
    repo_url: str | None = None,
    description: str = "",
) -> dict[str, object]:
    objects = sorted({c.object for c in ir.commands})
    if docs.showcase_object not in objects:
        raise ValueError(
            f"docs.showcase_object {docs.showcase_object!r} is not a CLI object; "
            f"available objects: {objects}"
        )
    grouped: list[dict[str, object]] = [
        {
            "object": obj,
            "commands": [
                _command_view(
                    c, distribution=distribution, override=docs.examples.get(c.key)
                )
                for c in ir.commands
                if c.object == obj
            ],
        }
        for obj in objects
    ]
    env = ir.error_envelope
    return {
        "cli_docs": True,
        "site_name": site_name,
        "distribution": distribution,
        "repo_url": repo_url,
        "description": description,
        "objects": grouped,
        "showcase": _showcase(ir.commands, docs.showcase_object),
        "has_auth": bool(ir.credential_fields),
        "show_pagination_guide": any(c.paginated for c in ir.commands),
        "credentials": [
            {"name": f.name, "env_var": f.env_var, "secret": f.secret, "required": f.required}
            for f in ir.credential_fields
        ],
        "error_envelope": {
            "wrappers": list(env.wrappers),
            "error_field": env.error_field,
            "errors_field": env.errors_field,
            "message_field": env.message_field,
            "code_field": env.code_field,
            "fallback_keys": list(env.fallback_keys),
        },
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run pytest tests/cli/test_docs_context.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generator/cli/docs.py tests/cli/test_docs_context.py
git commit -m "feat(cli-docs): IR-driven docs context + drift/key-contract guards"
```

---

### Task 5: Wire docs into `render_cli` + shared `emit_cli` fixture + Home & Quickstart

**Files:**
- Modify: `src/phantasos/generator/cli/render_cli.py`
- Create: `src/phantasos/generator/cli/templates/docs/index.md.jinja`
- Create: `src/phantasos/generator/cli/templates/docs/quickstart.md.jinja`
- Create: `tests/cli/conftest.py` (the `emit_cli` factory — replaces the broken cross-module import idea)
- Create: `tests/cli/test_docs_emitted.py`

**Interfaces:**
- Consumes: `build_cli_docs_context` (Task 4); `CliDocsConfig` (Task 1). No real circular import exists (`docs.py` imports `flags`/`examples`/`cliconfig`/`ir`, none import `render_cli`), so import normally at module top.
- Produces: `render_cli(..., docs: CliDocsConfig | None = None, docs_site_name: str | None = None)`. When `docs` is None, NO docs files are written (every existing caller omits it). The `emit_cli` fixture: `emit_cli(*, docs=None, auth=None) -> Path`.

- [ ] **Step 1: Create `tests/cli/conftest.py`**

```python
# tests/cli/conftest.py
"""Shared factory for emitting the fakesdk CLI in CLI-docs tests.

Scoped to tests/cli/ (a deliberate small copy of the fakesdk CLI config rather
than importing the private constant from tests/test_cli_emitted.py, which is not
an importable package). Takes `auth` so tests can exercise the credential-gated
guides."""

from pathlib import Path

import pytest

from phantasos.config import ScmOAuth
from phantasos.generator.cli.classify import build_cli_ir, cli_operations
from phantasos.generator.cli.cliconfig import CliConfig, RequestMapping, VariantMap

FIXTURE = Path(__file__).parent.parent / "fixtures" / "fakesdk"

_FAKESDK_CLI_CONFIG = CliConfig(
    variants={
        "gizmos.create_gizmo": VariantMap(
            path_param="type",
            map={"simple": "SimpleGizmoInput", "complex": "ComplexGizmoInput"},
        )
    },
    request={
        "widgets.suspend_widget": RequestMapping(object="widget", action="suspend"),
        "widgets.revoke_widget": RequestMapping(object="widget", action="revoke"),
    },
    defaults={"widgets.list_widgets": {"name": "gadget", "limit": 50}},
)


@pytest.fixture
def emit_cli(tmp_path: Path):
    from phantasos.generator.cli.render_cli import render_cli

    def _emit(*, docs=None, auth=None) -> Path:
        ir = build_cli_ir(cli_operations("fakesdk", FIXTURE), _FAKESDK_CLI_CONFIG)[0]
        render_cli(
            ir, package="fakesdk_cli", out_dir=tmp_path, env_prefix="FAKESDK",
            distribution="fakesdk",
            auth=ScmOAuth(type="scm_oauth") if auth else None,
            docs=docs, docs_site_name="Fakesdk CLI",
        )
        return tmp_path

    return _emit
```

- [ ] **Step 2: Write the failing test**

```python
# tests/cli/test_docs_emitted.py
"""Behavioral tests for the emitted CLI docs site (IR-driven markdown)."""

from pathlib import Path

from phantasos.generator.cli.cliconfig import CliDocsConfig


def test_no_docs_when_config_absent(emit_cli) -> None:
    out = emit_cli(docs=None)
    assert not (out / "docs").exists()
    assert not (out / "mkdocs.yml").exists()


def test_home_and_quickstart_emitted(emit_cli) -> None:
    out = emit_cli(docs=CliDocsConfig(showcase_object="widget"))
    index = (out / "docs" / "index.md").read_text()
    assert "Fakesdk CLI" in index
    assert "| `create` |" in index and "| `show` |" in index  # verbs table
    quickstart = (out / "docs" / "quickstart.md").read_text()
    assert "fakesdk create widget" in quickstart
```

- [ ] **Step 3: Run test to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run pytest tests/cli/test_docs_emitted.py -v`
Expected: FAIL with `TypeError: render_cli() got an unexpected keyword argument 'docs'`.

- [ ] **Step 4: Add the `docs` params + docs render pass to `render_cli`**

(a) Add imports after `from .flags import ...` (added in Task 2):

```python
from .cliconfig import CliDocsConfig
from .docs import build_cli_docs_context
```

(b) Change the `render_cli` signature (line 314) to add four keyword params:

```python
    docs: CliDocsConfig | None = None,
    docs_site_name: str | None = None,
    docs_repo_url: str | None = None,
    docs_description: str = "",
```

(c) At the END of `render_cli`, AFTER the `for rel in _HANDOWNED:` loop and BEFORE `_format_generated(...)`, insert the docs pass. **In THIS task add only the index + quickstart `render_doc` lines** shown below. Tasks 6/7/8 each append their own `render_doc(...)` calls inside this same `if docs is not None:` block — in order: the per-object reference loop (Task 6), the four guides (Task 7), then `mkdocs.yml` (Task 8). Do NOT paste those later lines now (their templates don't exist yet, and StrictUndefined would fail the build).

```python
    if docs is not None:
        dist = distribution or package
        site_name = docs.site_name or docs_site_name or dist
        doc_ctx = build_cli_docs_context(
            ir,
            docs,
            distribution=dist,
            site_name=site_name,
            repo_url=docs_repo_url,
            description=docs_description,
        )
        merged = {**ctx, **doc_ctx}

        def render_doc(template: str, rel: str, **extra: object) -> None:
            dest = out_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(
                env.get_template(template).render(**merged, **extra), encoding="utf-8"
            )
            written.append(rel)

        render_doc("docs/index.md.jinja", "docs/index.md")
        render_doc("docs/quickstart.md.jinja", "docs/quickstart.md")
```

- [ ] **Step 5: Create `templates/docs/index.md.jinja`**

```jinja
# {{ site_name }}

{{ description }}

`{{ distribution }}` is a command-line interface over the **{{ ir.sdk_package }}** API.

## Install

```bash
uv tool install {{ distribution }}
```
{% if repo_url %}
Source: [{{ repo_url }}]({{ repo_url }})
{% endif %}
## Command model

Commands are **verb-first**: a verb, then an object, then options.

| Verb | Purpose |
| --- | --- |
| `create` | create a new object |
| `update` | modify an existing object |
| `delete` | remove an object |
| `show` | list objects or fetch one by id |
| `request` | run a non-CRUD action on an object |

```bash
{{ distribution }} <verb> <object> [OPTIONS]
{{ distribution }} --help
```

## Where to go next

- [Quickstart](quickstart.md) — configure credentials and run your first commands.
{% if has_auth %}- [Authentication & environments](guides/authentication.md){% endif %}
- [Output & formatting](guides/output.md)
{% if show_pagination_guide %}- [Pagination](guides/pagination.md){% endif %}
- [Errors & diagnostics](guides/errors.md)
```

- [ ] **Step 6: Create `templates/docs/quickstart.md.jinja`**

```jinja
# Quickstart

## 1. Install

```bash
uv tool install {{ distribution }}
```

{% if has_auth %}## 2. Configure credentials

```bash
{% for c in credentials %}export {{ c.env_var }}={% if c.secret %}<{{ c.name }}>{% else %}your-{{ c.name }}{% endif %}
{% endfor %}```

Or use a named environment:

```bash
{{ distribution }} config environment create prod {% for c in credentials %}--{{ c.name | replace("_", "-") }} ...{% if not loop.last %} {% endif %}{% endfor %}
{{ distribution }} show {{ showcase.object }} --environment prod
```

{% endif %}## {% if has_auth %}3{% else %}2{% endif %}. Run your first commands

{% for obj in objects if obj.object == showcase.object %}{% for cmd in obj.commands %}{% if cmd.key.startswith("show:") and showcase.has_show %}List or fetch {{ showcase.object }}s:

```bash
{{ cmd.example }}
```

{% endif %}{% if cmd.key.startswith("create:") and showcase.has_create %}Create a {{ showcase.object }}:

```bash
{{ cmd.example }}
```

{% endif %}{% endfor %}{% endfor %}## {% if has_auth %}4{% else %}3{% endif %}. Choose an output format

```bash
{{ distribution }} show {{ showcase.object }} --output json
{{ distribution }} show {{ showcase.object }} --output table
```

See [Output & formatting](guides/output.md).
```

(Note: `cmd.key.startswith(...)` is valid Jinja — it calls the real `str` method on the key; do not "fix" it to a filter.)

- [ ] **Step 7: Run test to verify it passes**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run pytest tests/cli/test_docs_emitted.py -v`
Expected: PASS (2 passed).

- [ ] **Step 8: Commit**

```bash
git add src/phantasos/generator/cli/render_cli.py \
        src/phantasos/generator/cli/templates/docs/index.md.jinja \
        src/phantasos/generator/cli/templates/docs/quickstart.md.jinja \
        tests/cli/conftest.py tests/cli/test_docs_emitted.py
git commit -m "feat(cli-docs): render Home + Quickstart; shared emit_cli fixture"
```

---

### Task 6: Per-object Command Reference pages

**Files:**
- Modify: `src/phantasos/generator/cli/render_cli.py` (add the reference loop `render_doc(...)` lines — see Task 5 Step 4 final shape)
- Create: `src/phantasos/generator/cli/templates/docs/reference_object.md.jinja`
- Test: extend `tests/cli/test_docs_emitted.py`

- [ ] **Step 1: Write the failing test (append)**

```python
def test_reference_page_per_object(emit_cli) -> None:
    out = emit_cli(docs=CliDocsConfig(showcase_object="widget"))
    text = (out / "docs" / "reference" / "widget.md").read_text()
    assert "fakesdk create widget [OPTIONS]" in text
    # the flag table header is FLUSH (no leading spaces) so Markdown renders it as a table
    assert "\n| Flag | Type | Required | Description |\n" in text
    assert "`--name`" in text
    assert "fakesdk create widget --name" in text
```

- [ ] **Step 2: Run to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run pytest tests/cli/test_docs_emitted.py::test_reference_page_per_object -v`
Expected: FAIL (no `reference/widget.md`).

- [ ] **Step 3: Add the reference loop to the docs pass** (inside the `if docs is not None:` block, after the index/quickstart lines)

```python
        for obj in doc_ctx["objects"]:
            render_doc(
                "docs/reference_object.md.jinja",
                f"docs/reference/{obj['object']}.md",
                obj=obj,
            )
```

- [ ] **Step 4: Create `templates/docs/reference_object.md.jinja`** (macro HOISTED above the loop; whitespace-controlled so tables stay flush)

```jinja
{% macro flag_table(rows) -%}
| Flag | Type | Required | Description |
| --- | --- | --- | --- |
{% for f in rows -%}
| `{{ f.name }}` | `{{ f.type }}` | {{ "yes" if f.required else "no" }} | {{ f.help }}{% if f.choices %} _(values: {{ f.choices | join(", ") }})_{% endif %} |
{% endfor -%}
{%- endmacro -%}
# `{{ obj.object }}`

{% for cmd in obj.commands %}
## `{{ cmd.usage }}`

{% if cmd.summary %}{{ cmd.summary }}

{% endif %}{% if cmd.description and cmd.description != cmd.summary %}{{ cmd.description }}

{% endif %}{% if cmd.path_flags %}**Arguments**

{{ flag_table(cmd.path_flags) }}

{% endif %}{% if cmd.body_flags %}**Body**

{{ flag_table(cmd.body_flags) }}

{% endif %}{% if cmd.filter_flags %}**Filters**

{{ flag_table(cmd.filter_flags) }}

{% endif %}{% if cmd.pagination_flags %}**Pagination**

{{ flag_table(cmd.pagination_flags) }}

{% endif %}{% if cmd.columns %}Default table columns: {% for c in cmd.columns %}`{{ c.header }}`{% if not loop.last %}, {% endif %}{% endfor %}.

{% endif %}**Example**

```bash
{{ cmd.example }}
```

{% endfor %}
```

- [ ] **Step 5: Run to verify it passes**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run pytest tests/cli/test_docs_emitted.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/phantasos/generator/cli/render_cli.py \
        src/phantasos/generator/cli/templates/docs/reference_object.md.jinja \
        tests/cli/test_docs_emitted.py
git commit -m "feat(cli-docs): per-object command reference pages"
```

---

### Task 7: Guides (auth, output, pagination, errors) with gating

**Files:**
- Modify: `src/phantasos/generator/cli/render_cli.py` (add the guide `render_doc(...)` lines)
- Create: `templates/docs/guides/{authentication,output,pagination,errors}.md.jinja`
- Test: extend `tests/cli/test_docs_emitted.py`

- [ ] **Step 1: Write the failing tests (append) — exercise BOTH gating arms**

```python
from phantasos.config import ScmOAuth  # noqa: E402  (top of file is fine too)


def test_guides_always_present_and_auth_gating(emit_cli) -> None:
    no_auth = emit_cli(docs=CliDocsConfig(showcase_object="widget"))
    g = no_auth / "docs" / "guides"
    assert (g / "output.md").exists()
    assert (g / "errors.md").exists()
    assert not (g / "authentication.md").exists()  # gated OFF without credentials

    with_auth = emit_cli(docs=CliDocsConfig(showcase_object="widget"), auth=True)
    assert (with_auth / "docs" / "guides" / "authentication.md").exists()


def test_errors_guide_documents_exit_codes(emit_cli) -> None:
    out = emit_cli(docs=CliDocsConfig(showcase_object="widget"))
    errors = (out / "docs" / "guides" / "errors.md").read_text()
    for code in ("| `0` |", "| `1` |", "| `2` |"):  # structural, not prose
        assert code in errors
```

- [ ] **Step 2: Run to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run pytest tests/cli/test_docs_emitted.py::test_guides_always_present_and_auth_gating -v`
Expected: FAIL (guides dir absent).

- [ ] **Step 3: Add guide rendering to the docs pass**

```python
        render_doc("docs/guides/output.md.jinja", "docs/guides/output.md")
        render_doc("docs/guides/errors.md.jinja", "docs/guides/errors.md")
        if doc_ctx["has_auth"]:
            render_doc("docs/guides/authentication.md.jinja", "docs/guides/authentication.md")
        if doc_ctx["show_pagination_guide"]:
            render_doc("docs/guides/pagination.md.jinja", "docs/guides/pagination.md")
```

- [ ] **Step 4: Create the four guide templates**

`templates/docs/guides/output.md.jinja`:
```jinja
# Output & formatting

Every command supports an output format and a column selection.

```bash
{{ distribution }} show <object> --output json     # machine-readable JSON
{{ distribution }} show <object> --output yaml      # YAML
{{ distribution }} show <object> --output table     # human-readable table (default)
```

Pick table columns with a JMESPath per column:

```bash
{{ distribution }} show <object> --columns '{"ID":"id","Name":"name"}'
```

Long output is paged automatically when stdout is a TTY; disable with `--no-pager`
(or `{{ distribution }} config set pager.enabled false`).
```

`templates/docs/guides/pagination.md.jinja`:
```jinja
# Pagination

List commands fetch one page by default.

```bash
{{ distribution }} show <object> --limit 100   # cap the number of rows
{{ distribution }} show <object> --all          # fetch every page
```
```

`templates/docs/guides/authentication.md.jinja`:
```jinja
# Authentication & environments

## Credentials

`{{ distribution }}` reads these from the environment (or a named environment):

| Credential | Environment variable | Required | Secret |
| --- | --- | --- | --- |
{% for c in credentials %}| `{{ c.name }}` | `{{ c.env_var }}` | {{ "yes" if c.required else "no" }} | {{ "yes" if c.secret else "no" }} |
{% endfor %}

## Named environments

```bash
{{ distribution }} config environment create prod {% for c in credentials %}--{{ c.name | replace("_", "-") }} ...{% if not loop.last %} {% endif %}{% endfor %}
{{ distribution }} config environment list
{{ distribution }} show <object> --environment prod
```

## Configuration layering

Settings resolve in order (later wins): packaged defaults →
`~/.{{ distribution }}/config.yml` → `.env` / shell env → per-command flags.

```bash
{{ distribution }} config show          # effective merged config + its sources
{{ distribution }} config set output.format json
{{ distribution }} config unset output.format
```
```

`templates/docs/guides/errors.md.jinja`:
```jinja
# Errors & diagnostics

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | success |
| `1` | the operation failed (server/API error, authentication failure, or a file-write error) |
| `2` | bad input or usage error (invalid flag value, unknown config key, no matching operation; also argument-parse errors) |

## Diagnostics

Errors and warnings print to **stderr** as a styled line (`✖` error, `⚠` warning,
`ℹ` info), falling back to plain text when piped or when `NO_COLOR` is set.

- `--verbose` prints the full Python traceback for an unexpected error.
- `--quiet` suppresses everything below errors.

{% if error_envelope.error_field or error_envelope.errors_field or error_envelope.wrappers %}## API error messages

Error responses are reduced to a one-line headline by reading
{% if error_envelope.wrappers %}(after peeling {% for w in error_envelope.wrappers %}`{{ w }}`{% if not loop.last %}/{% endif %}{% endfor %}) {% endif %}{% if error_envelope.error_field %}the `{{ error_envelope.error_field }}.{{ error_envelope.message_field }}` field{% elif error_envelope.errors_field %}the first entry of the `{{ error_envelope.errors_field }}` list{% endif %}. If absent, these keys are tried in order: {% for k in error_envelope.fallback_keys %}`{{ k }}`{% if not loop.last %}, {% endif %}{% endfor %}.

{% endif %}## Command history

```bash
{{ distribution }} show cli history            # recent commands (id, time, command, status)
{{ distribution }} show cli history --entry 3   # one entry as full JSON
```

History is stored at `~/.{{ distribution }}/history.jsonl`; authentication headers are
never recorded.

## Logs

Structured JSON-Lines logs (rotated, gzipped) are written to
`~/.{{ distribution }}/logs/{{ distribution }}.jsonl`.

```bash
{{ distribution }} config set logging.level debug
{{ distribution }} config set logging.file /path/to/log.jsonl
```

(or `{{ env_prefix }}_LOGGING_LEVEL` / `{{ env_prefix }}_LOGGING_FILE`.)
```

- [ ] **Step 5: Run to verify it passes**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run pytest tests/cli/test_docs_emitted.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/phantasos/generator/cli/render_cli.py \
        src/phantasos/generator/cli/templates/docs/guides/ \
        tests/cli/test_docs_emitted.py
git commit -m "feat(cli-docs): output/pagination/auth/errors guides with gating"
```

---

### Task 8: CLI `mkdocs.yml` with explicit IR-generated nav

**Files:**
- Modify: `src/phantasos/generator/cli/render_cli.py` (add the `render_doc("docs/mkdocs.yml.jinja", "mkdocs.yml")` line)
- Create: `src/phantasos/generator/cli/templates/docs/mkdocs.yml.jinja`
- Test: extend `tests/cli/test_docs_emitted.py`

- [ ] **Step 1: Write the failing test (append)**

```python
import yaml  # PyYAML — already a framework dependency


def test_mkdocs_yml_nav(emit_cli) -> None:
    out = emit_cli(docs=CliDocsConfig(showcase_object="widget"))
    cfg = yaml.safe_load((out / "mkdocs.yml").read_text())
    assert cfg["site_name"] == "Fakesdk CLI"
    assert cfg["theme"]["name"] == "material"
    plugin_names = [p if isinstance(p, str) else list(p)[0] for p in cfg["plugins"]]
    assert "mkdocstrings" not in plugin_names and "gen-files" not in plugin_names
    ref = next(s["Command Reference"] for s in cfg["nav"] if "Command Reference" in s)
    assert {"widget": "reference/widget.md"} in ref
```

- [ ] **Step 2: Run to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run pytest tests/cli/test_docs_emitted.py::test_mkdocs_yml_nav -v`
Expected: FAIL (`mkdocs.yml` absent).

- [ ] **Step 3: Add the mkdocs render (last in the docs pass)**

```python
        render_doc("docs/mkdocs.yml.jinja", "mkdocs.yml")
```

- [ ] **Step 4: Create `templates/docs/mkdocs.yml.jinja`**

```jinja
site_name: {{ site_name | tojson }}
{% if repo_url %}repo_url: {{ repo_url }}
{% endif %}theme:
  name: material
  features:
    - content.code.copy
    - navigation.sections
    - navigation.top
    - search.suggest
    - toc.follow
  palette:
    - media: "(prefers-color-scheme: light)"
      scheme: default
      toggle: {icon: material/brightness-7, name: Switch to dark mode}
    - media: "(prefers-color-scheme: dark)"
      scheme: slate
      toggle: {icon: material/brightness-4, name: Switch to light mode}

nav:
  - Home: index.md
  - Quickstart: quickstart.md
  - Guides:
{% if has_auth %}      - Authentication & environments: guides/authentication.md
{% endif %}      - Output & formatting: guides/output.md
{% if show_pagination_guide %}      - Pagination: guides/pagination.md
{% endif %}      - Errors & diagnostics: guides/errors.md
  - Command Reference:
{% for obj in objects %}      - {{ obj.object }}: reference/{{ obj.object }}.md
{% endfor %}

plugins:
  - search

markdown_extensions:
  - admonition
  - pymdownx.highlight
  - pymdownx.superfences
  - toc:
      permalink: true
```

- [ ] **Step 5: Run the full docs-emitted suite**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run pytest tests/cli/test_docs_emitted.py -v`
Expected: PASS (all).

- [ ] **Step 6: Commit**

```bash
git add src/phantasos/generator/cli/render_cli.py \
        src/phantasos/generator/cli/templates/docs/mkdocs.yml.jinja \
        tests/cli/test_docs_emitted.py
git commit -m "feat(cli-docs): emit CLI mkdocs.yml with explicit IR nav"
```

---

### Task 9: `cli_docs` scaffold flag + shared infra branches + `cli build` wiring

**Files:**
- Modify: `src/phantasos/generator/cli/scaffold_context.py`
- Modify: `src/phantasos/cli.py`
- Modify: `src/phantasos/scaffold/pyproject.toml.jinja`
- Modify: `src/phantasos/scaffold/noxfile.py.jinja`
- Modify: `src/phantasos/scaffold/.github/workflows/docs.yml.jinja`
- Modify: `src/phantasos/generator/cli/cli_overrides/README.md.jinja`
- Test: `tests/cli/test_docs_scaffold.py` (NEW)

**Interfaces:**
- Consumes: `CliConfig.docs` (Task 1).
- Produces: `build_cli_scaffold_context(...)["cli_docs"] == cfg.docs is not None`; `cli build` passes `docs=cfg.docs, docs_site_name=<title> CLI`; the emitted CLI gets a `docs` group of just `mkdocs-material`, `docs`/`docs-serve` nox sessions, a Pages workflow, and a README "Documentation" section — only when `cli_docs`.

- [ ] **Step 1: Write the failing test**

```python
# tests/cli/test_docs_scaffold.py
from pathlib import Path
from types import SimpleNamespace

from phantasos import scaffold
from phantasos.generator.cli.cliconfig import CliConfig, CliDocsConfig
from phantasos.generator.cli.render_cli import cli_overrides_dir
from phantasos.generator.cli.scaffold_context import build_cli_scaffold_context


def _loaded(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        context={
            "package": "acme", "distribution": "acme-sdk", "spec_title": "Acme",
            "has_pagination": True, "description": "d", "author": "A",
            "author_email": "a@b.c", "repo_url": "https://x", "license": "Apache-2.0",
            "python_versions": ["3.12"],
        },
        output_dir=str(tmp_path / "acme-sdk"),
        auth=None,
    )


def test_cli_docs_flag(tmp_path: Path) -> None:
    on = build_cli_scaffold_context(
        _loaded(tmp_path), ir=None, cli_cfg=CliConfig(docs=CliDocsConfig(showcase_object="w"))
    )
    assert on["cli_docs"] is True
    assert on["has_docs"] is False  # SDK docs stay off for the CLI
    off = build_cli_scaffold_context(_loaded(tmp_path), ir=None, cli_cfg=CliConfig())
    assert off["cli_docs"] is False


def test_emitted_docs_infra(tmp_path: Path) -> None:
    ctx = build_cli_scaffold_context(
        _loaded(tmp_path), ir=None, cli_cfg=CliConfig(docs=CliDocsConfig(showcase_object="w"))
    )
    out = tmp_path / "out"
    scaffold.render_scaffold(scaffold.builtin_dir(), cli_overrides_dir(), out, ctx)
    pyproject = (out / "pyproject.toml").read_text()
    assert '"mkdocs-material>=9.5",' in pyproject
    assert "mkdocstrings" not in pyproject          # SDK-only dep absent for the CLI
    assert "def docs(" in (out / "noxfile.py").read_text()
    assert "## Documentation" in (out / "README.md").read_text()
```

- [ ] **Step 2: Run to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run pytest tests/cli/test_docs_scaffold.py -v`
Expected: FAIL with `KeyError: 'cli_docs'`.

- [ ] **Step 3: Set `cli_docs` in `build_cli_scaffold_context`**

In `scaffold_context.py`, in the `ctx.update(...)` block (after `has_docs=False,`, line 72):

```python
        cli_docs=getattr(cli_cfg, "docs", None) is not None,
```

- [ ] **Step 4: Branch the shared infra templates**

(a) `scaffold/pyproject.toml.jinja` — replace the docs group (lines 35–43):

```jinja
{%- if has_docs | default(false) %}
docs = [
    "mkdocs-material>=9.5",
    "mkdocstrings[python]>=0.26",
    "mkdocs-gen-files>=0.5",
    "mkdocs-literate-nav>=0.6",
    "griffe-pydantic>=1.0.0",
]
{%- elif cli_docs | default(false) %}
docs = [
    "mkdocs-material>=9.5",
]
{%- endif %}
```

(b) `scaffold/noxfile.py.jinja` — change line 28 guard to:
```jinja
{% if (has_docs | default(false)) or (cli_docs | default(false)) %}
```

(c) `scaffold/.github/workflows/docs.yml.jinja` — change line 1 guard to:
```jinja
{% if (has_docs | default(false)) or (cli_docs | default(false)) %}
```

(d) `generator/cli/cli_overrides/README.md.jinja` — append after the file's final line (use it as the exact `Edit` anchor — it reads, verbatim: `` > `phantasos cli build`; hand-written commands/overrides live in `main.py`, `custom/`, and `hooks.py`. ``); add:
```jinja

{% if cli_docs | default(false) %}
## Documentation

Full guides and a per-object command reference live in `docs/`. Build and preview
the site locally:

```bash
uv run nox -s docs-serve
```
{% endif %}
```

- [ ] **Step 5: Wire `cli build` to pass docs**

In `cli.py` `cli_build`, after `scaffold_ctx = build_cli_scaffold_context(...)` (line 134), change the `render_cli(...)` call to add docs args:

```python
    docs_site_name = (
        f"{scaffold_ctx.get('spec_title')} CLI" if scaffold_ctx.get("spec_title") else None
    )
    written = render_cli(
        ir,
        package=cli_pkg,
        out_dir=out_dir,
        distribution=str(scaffold_ctx["distribution"]),
        auth=loaded.auth,
        errors=loaded.errors,
        docs=cfg.docs,
        docs_site_name=docs_site_name,
        docs_repo_url=scaffold_ctx.get("repo_url"),
        docs_description=scaffold_ctx.get("description") or "",
    )
```

- [ ] **Step 6: Run to verify it passes**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run pytest tests/cli/test_docs_scaffold.py -v`
Expected: PASS (2 passed).

- [ ] **Step 7: Commit**

```bash
git add src/phantasos/generator/cli/scaffold_context.py src/phantasos/cli.py \
        src/phantasos/scaffold/pyproject.toml.jinja src/phantasos/scaffold/noxfile.py.jinja \
        src/phantasos/scaffold/.github/workflows/docs.yml.jinja \
        src/phantasos/generator/cli/cli_overrides/README.md.jinja \
        tests/cli/test_docs_scaffold.py
git commit -m "feat(cli-docs): cli_docs scaffold flag + shared infra branches + build wiring"
```

---

### Task 10: Exit-code drift-guard test

**Files:**
- Test: `tests/cli/test_exit_codes.py` (NEW)

- [ ] **Step 1: Write the test (this IS the deliverable)**

```python
# tests/cli/test_exit_codes.py
"""Guard: the Errors guide's static exit-code table (0/1/2) must not drift from
the emitted runtime. Exit codes are inline literals (no ExitCode enum), so this
greps ALL CLI templates (not just _generated/, since main.py/hooks.py are
hand-owned templates outside it). If a new code appears, update BOTH the runtime
AND docs/guides/errors.md.jinja, then this guard."""

import re
from pathlib import Path

TEMPLATES = (
    Path(__file__).parent.parent.parent
    / "src" / "phantasos" / "generator" / "cli" / "templates"
)


def test_runtime_uses_only_documented_exit_codes() -> None:
    allowed_code = {"1", "2"}
    offenders: list[str] = []
    for tmpl in TEMPLATES.rglob("*.jinja"):
        if "/docs/" in tmpl.as_posix():
            continue  # docs templates aren't runtime
        text = tmpl.read_text()
        for m in re.finditer(r"SystemExit\(\s*(\d+)\s*\)", text):
            if m.group(1) not in allowed_code | {"0"}:
                offenders.append(f"{tmpl.name}: SystemExit({m.group(1)})")
        for m in re.finditer(r"typer\.Exit\(\s*(\d+)\s*\)", text):
            if m.group(1) not in allowed_code | {"0"}:
                offenders.append(f"{tmpl.name}: typer.Exit({m.group(1)})")
        for m in re.finditer(r"\bcode\s*=\s*(\d+)\b", text):
            if m.group(1) not in allowed_code:
                offenders.append(f"{tmpl.name}: code={m.group(1)}")
    assert not offenders, (
        "Undocumented exit codes; update docs/guides/errors.md.jinja and this guard:\n  "
        + "\n  ".join(offenders)
    )
```

- [ ] **Step 2: Run the test**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run pytest tests/cli/test_exit_codes.py -v`
Expected: PASS. (If FAIL: the runtime uses a code the docs don't mention — reconcile the Errors guide + this guard; do not force it green.)

- [ ] **Step 3: Commit**

```bash
git add tests/cli/test_exit_codes.py
git commit -m "test(cli-docs): guard exit-code table against runtime drift"
```

---

### Task 11: `cli-docs` nox session (+ shared assert helper) + CI job

**Files:**
- Modify: `noxfile.py` (extract `_run_content_asserts`; refactor `sdk_docs` to use it; add `cli_docs` session)
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Extract the shared content-assert helper in `noxfile.py`**

Add near the other helpers (after `_stage_asserts`, line 75):

```python
def _run_content_asserts(session: nox.Session, stage: str, product: str, site: Path) -> None:
    """Run nox.toml per-product content guards against a built `site/` dir."""
    for check in _stage_asserts(stage, product):
        target = site / check["file"]
        text = target.read_text() if target.exists() else ""
        if "contains" in check and check["contains"] not in text:
            session.error(f"{product}: {check['file']} is missing {check['contains']!r}")
        if "not_contains" in check and check["not_contains"] in text:
            session.error(
                f"{product}: {check['file']} unexpectedly contains {check['not_contains']!r}"
            )
```

Then in `sdk_docs` replace the inline assert loop (lines 311–322) with:

```python
        _run_content_asserts(session, "sdk-docs", product, site)
```

- [ ] **Step 2: Add the `cli-docs` session** (after `sdk_docs`)

```python
@nox.session(name="cli-docs", venv_backend="uv")
def cli_docs(session: nox.Session) -> None:
    """Build each enrolled CLI + its docs and run ``mkdocs build --strict``.

    Products are in nox.toml ``[cli-docs]``. Opt-in integration gate (NOT in
    nox.options.sessions). The CLI docs markdown is rendered at ``cli build`` time,
    so the mkdocs build needs only ``mkdocs-material`` (the CLI's ``docs`` group).
    The CLI output dir is derived authoritatively (same path the build uses), NOT
    by string-munging the SDK output dir name.
    """
    import shutil

    from phantasos.generator.cli.cliconfig import load_cli_config
    from phantasos.generator.cli.scaffold_context import build_cli_scaffold_context
    from phantasos.productconfig import load_product, sdk_runtime_deps

    _sync(session)
    session.install(*sdk_runtime_deps())  # `cli build` introspects the built SDK
    root = Path.cwd()
    for product in _stage_products("cli-docs"):
        loaded = load_product(product)
        cli_cfg = load_cli_config(Path(loaded.base_dir) / "cli.yml")
        ctx = build_cli_scaffold_context(loaded, ir=None, cli_cfg=cli_cfg)
        cli_out = Path(loaded.output_dir).parent / str(ctx["distribution"])
        if (cli_out / "site").exists():
            shutil.rmtree(cli_out / "site")
        session.run("phantasos", "sdk", "build", product, "--no-smoke")
        session.run("phantasos", "cli", "build", product)
        if not cli_out.is_dir():
            session.error(f"{product}: CLI was not emitted at {cli_out}")
        build_env = f"{session.virtualenv.location}-clibuild-{product}"
        docs_env = {**os.environ, "UV_PROJECT_ENVIRONMENT": build_env}
        session.chdir(str(cli_out))
        session.run(
            "uv", "run", "--group", "docs", "mkdocs", "build", "--strict",
            external=True, env=docs_env,
        )
        session.chdir(str(root))
        site = cli_out / "site"
        if not (site / "reference").exists():
            session.error(f"{product}: CLI command reference was not generated")
        _run_content_asserts(session, "cli-docs", product, site)
```

- [ ] **Step 3: Add a CI job to `.github/workflows/ci.yml`** (after `cli-smoke`, line 84). Read the `smoke` job first; if it has a Java-provisioning step (the OAG needs a JRE to build SDKs), copy that step into this job before the build step.

```yaml
  cli-docs:
    name: CLI docs (strict)
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@df4cb1c069e1874edd31b4311f1884172cec0e10 # v6.0.3
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@fac544c07dec837d0ccb6301d7b5580bf5edae39 # v8.2.0
        with:
          enable-cache: true
      - name: Build each enrolled CLI + docs (strict)
        run: uv run nox -s cli-docs
```

- [ ] **Step 4: Verify discoverability + the sdk-docs refactor didn't regress**

Run:
```bash
UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run nox -l            # cli-docs listed
UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run python -c "import noxfile"   # imports clean
```
Expected: `cli-docs` appears; no import error. (Full run happens in Task 12 once a product is enrolled.)

- [ ] **Step 5: Commit**

```bash
git add noxfile.py .github/workflows/ci.yml
git commit -m "feat(cli-docs): cli-docs nox gate (shared assert helper) + CI job"
```

---

### Task 12: Enroll + validate prisma-browser, adem, posture

**Files:**
- Modify: `products/prisma-browser/cli.yml`, `products/adem/cli.yml`, `products/posture/cli.yml`
- Modify: `nox.toml`

- [ ] **Step 1: Pick a showcase object per product**

```bash
UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run phantasos cli discover prisma-browser
UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run phantasos cli discover adem
UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run phantasos cli discover posture
```
Choose an object with a `create` (ideally also `show`). Add to each `cli.yml`:

```yaml
docs:
  showcase_object: <object>   # e.g. application for prisma-browser
```

- [ ] **Step 2: Enroll in `nox.toml`** (only products confirmed buildable in Task 0)

```toml
[cli-docs]
products = ["prisma-browser", "adem", "posture"]

[[cli-docs.assert]]
product = "prisma-browser"
file = "index.html"
contains = "Command model"

[[cli-docs.assert]]
product = "prisma-browser"
file = "reference/application/index.html"   # match the real showcase object
contains = "[OPTIONS]"
```

- [ ] **Step 3: Run the gate**

```bash
NOX_ENVDIR=/tmp/phantasos-nox UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run nox -s cli-docs
```
Expected: each enrolled product builds its SDK + CLI, `mkdocs build --strict` succeeds, and guards pass. Show the real output.

- [ ] **Step 4: Offline gate**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run nox -s gate`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add products/*/cli.yml nox.toml
git commit -m "feat(cli-docs): enable + enroll prisma-browser/adem/posture CLI docs"
```

---

### Task 13: Context deep-dive, CHANGELOG, final verification

**Files:**
- Modify: `.agents/context/cli-generator.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Update the CLI-generator deep-dive narrative**

Add a "docs sub-stage" section to `.agents/context/cli-generator.md`: `cli.yml` `docs:` → `generator/cli/docs.py` builds an IR-driven context (sharing `flags.py` with the emitted command modules so the reference can't drift from `--help`) → `generator/cli/examples.py` synthesizes invocations → `render_cli` renders `templates/docs/**` + `mkdocs.yml` → the `cli_docs` scaffold flag gates shared infra → `cli-docs` nox gate. State it is IR-driven/generate-time and does NOT use mkdocstrings/gen-files (cross-ref `docs/adr/0001`).

- [ ] **Step 2: Refresh + check the generated blocks**

```bash
UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run nox -s context
UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run nox -s context -- --check
```
Expected: `--check` passes.

- [ ] **Step 3: CHANGELOG entry under `## [Unreleased]`**

```markdown
### Added
- Generated CLIs can emit a documentation site (quickstart + per-object command
  reference + guides), opt-in via a `docs:` block in `cli.yml`. Built strict in CI
  via the new `cli-docs` nox session.
```

- [ ] **Step 4: Full offline gate + the CLI docs suite**

```bash
UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run nox -s gate
UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run pytest tests/cli -v
```
Expected: all PASS. Show real output.

- [ ] **Step 5: Integration validation**

```bash
NOX_ENVDIR=/tmp/phantasos-nox UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run nox -s cli-docs
```
Expected: PASS for every enrolled product. Confirm `gate` + `cli-docs` are green before declaring done.

- [ ] **Step 6: Commit**

```bash
git add .agents/context/cli-generator.md CHANGELOG.md
git commit -m "docs(cli-docs): context deep-dive + changelog"
```

---

## Self-Review (completed by plan author)

**Spec coverage:** D1 → Tasks 5–8; D2 → Tasks 2+4 (shared `flags.py` + drift test); D3 → Task 5; D4/D8 → Tasks 5–7; D5 → Task 1; D6 → Tasks 4–5; D7 → Task 3 (duplicated value strategy; shares only intra-CLI `flags.py`); D9 → Task 6; D10/D11 → Task 9; D12 → Tasks 5–11; D13 → Task 8; D14 → Tasks 5 & 9; D15 → Task 9; D16 → Tasks 7 & 10; D17 → Tasks 0 & 12.

**Review findings addressed:** C1 (existing `tests/test_cli_docs.py` untouched; new tests under `tests/cli/`); C2/auth (`emit_cli(auth=...)` + both gating arms); dedup-drift (Task 2 `flags.py` + Task 4 drift test); false circular import (removed; normal imports; typed `docs: CliDocsConfig | None`; no `assert isinstance`); nox path (Task 11 derives via `build_cli_scaffold_context`); macro hoisted + flush-table assertion; exit-code glob broadened to all CLI templates; brittle asserts loosened to structural; `_run_content_asserts` extracted; `_leaf` consolidated into `flags.py`; README exact anchor; key-contract test added.

**Type consistency:** `CliDocsConfig` identical across Tasks 1/4/5/9. The command-view keys produced in Task 4 are exactly those consumed by the Task 6 reference template and Task 5 quickstart/index; verified by `CONTEXT_KEYS` + the key-contract test. `render_cli`'s new `docs`/`docs_site_name` params (Task 5) match the Task 9 call site. `flags.dedupe_flags`/`query_panel`/`leaf` consumed identically by `render_cli` and `docs.py`.

**Known follow-up (not a blocker):** the emitted `README.md` still advertises stale verbs (`set`/`del`); the canonical verbs explainer now lives on the docs Home page. Out of scope here.
