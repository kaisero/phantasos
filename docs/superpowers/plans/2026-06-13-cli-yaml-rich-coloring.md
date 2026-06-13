# Rich Coloring for YAML Output (CLI) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** In a generated CLI, render `--output yaml` (and `config show`) through `rich` so it is syntax-colored on a terminal — consistent with `--output json` — while staying byte-clean, round-tripping plain YAML when piped/redirected/`NO_COLOR`. Implements #13.

**Architecture:** One shared `output.print_yaml(text)` helper (`rich.syntax.Syntax` + `_console.print(..., soft_wrap=True)`) is the single "YAML → terminal" path; both `output.render()`'s YAML branch and `config_commands.config_show()` call it. `soft_wrap=True` is mandatory — off-TTY, `Syntax` otherwise crops lines to width 80 and truncates long values.

**Tech Stack:** Python 3.11+, `rich` (`Syntax`), `pygments` (yaml lexer, via rich), Jinja2 templates, pytest. Spec: `docs/superpowers/specs/2026-06-13-cli-yaml-rich-coloring-design.md`.

**Branch:** `feature/yaml-rich-coloring` (already created off `develop`). PR `--base develop`; do NOT bump the version.

**Test-runner note:** sshfs checkout — prefix uv with `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-uv`. Tests exercise the EMITTED CLI via the `emitted` fixture, which re-renders the templates each test, so editing a `.jinja` template is picked up on the next run. Run a single test: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-uv uv run --no-sync python -m pytest tests/test_cli_emitted.py::<name> -q -p no:cacheprovider --no-header`.

## File structure

- `src/phantasos/generator/cli/templates/_generated/output.py.jinja` — add `Syntax` import + `print_yaml` helper; route the `render()` YAML branch through it.
- `src/phantasos/generator/cli/templates/_generated/config_commands.py.jinja` — route `config show` through `output.print_yaml`.
- `src/phantasos/generator/cli/scaffold_context.py` — add `"pygments>=2"` to `_CLI_DEPS` (the emitted CLI now imports the yaml lexer directly).
- `tests/test_cli_emitted.py` — new behavioral tests; keep `test_yaml_output_has_no_trailing_blank_line`.

---

## Task 1: `print_yaml` helper + route `render()` YAML through it

**Files:**
- Modify: `src/phantasos/generator/cli/templates/_generated/output.py.jinja`
- Modify: `src/phantasos/generator/cli/scaffold_context.py`
- Test: `tests/test_cli_emitted.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_cli_emitted.py` (near `test_yaml_output_has_no_trailing_blank_line`):

```python
def test_yaml_output_colored_on_terminal(emitted: Path) -> None:
    import io

    from rich.console import Console

    out = importlib.import_module("fakesdk_cli._generated.output")

    class _Model:
        def model_dump(self, mode: str = "python") -> dict[str, Any]:
            return {"name": "widget-1", "enabled": True}

    buf = io.StringIO()
    out._console = Console(file=buf, force_terminal=True)  # force a TTY-like console
    out.render(_Model(), fmt="yaml")
    assert "\x1b[" in buf.getvalue()  # ANSI styling present on a terminal


def test_yaml_output_plain_and_round_trips_when_piped(
    emitted: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import yaml

    out = importlib.import_module("fakesdk_cli._generated.output")
    payload = {"name": "widget-1", "enabled": True, "tags": ["a", "b"]}

    class _Model:
        def model_dump(self, mode: str = "python") -> dict[str, Any]:
            return payload

    out.render(_Model(), fmt="yaml")
    text = capsys.readouterr().out
    assert "\x1b[" not in text  # no ANSI off a terminal
    assert text.endswith("\n") and not text.endswith("\n\n")  # exactly one newline
    assert yaml.safe_load(text) == payload


def test_yaml_output_long_line_not_truncated_when_piped(
    emitted: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Regression guard: rich Syntax crops to width 80 off-TTY unless soft_wrap=True.
    import yaml

    out = importlib.import_module("fakesdk_cli._generated.output")
    payload = {"url": "https://example.com/" + "x" * 300}

    class _Model:
        def model_dump(self, mode: str = "python") -> dict[str, Any]:
            return payload

    out.render(_Model(), fmt="yaml")
    text = capsys.readouterr().out
    assert yaml.safe_load(text) == payload  # full value, no truncation
```

- [ ] **Step 2: Run them — verify the colored test fails**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-uv uv run --no-sync python -m pytest tests/test_cli_emitted.py::test_yaml_output_colored_on_terminal -q -p no:cacheprovider --no-header`
Expected: FAIL — current YAML branch uses `_console.out(..., highlight=False)`, so no ANSI appears even on a forced terminal (`assert "\x1b[" in ...` fails). (The two piped tests pass on the old plain path; they guard the new path.)

- [ ] **Step 3: Add the `Syntax` import**

In `output.py.jinja`, the rich imports are:
```python
from rich.console import Console
from rich.pager import Pager
from rich.table import Table
```
Insert `Syntax` (isort order — between `pager` and `table`):
```python
from rich.console import Console
from rich.pager import Pager
from rich.syntax import Syntax
from rich.table import Table
```

- [ ] **Step 4: Add the `print_yaml` helper**

In `output.py.jinja`, immediately before `def render(` add:
```python
def print_yaml(text: str) -> None:
    """Emit YAML to the console: syntax-highlighted on a terminal, byte-clean plain
    YAML when piped/redirected/NO_COLOR (rich strips styling off-TTY). soft_wrap=True
    stops rich's Syntax from cropping long lines to the off-TTY fallback width."""
    _console.print(
        Syntax(
            text.rstrip("\n"),
            "yaml",
            theme="ansi_dark",
            background_color="default",
            word_wrap=False,
            line_numbers=False,
        ),
        soft_wrap=True,
    )
```

- [ ] **Step 5: Route the `render()` YAML branch through it**

In `output.py.jinja`, replace:
```python
    if fmt == "yaml":
        _console.out(
            yaml.safe_dump(data, sort_keys=False, default_flow_style=False),
            highlight=False,
            end="",
        )
        return
```
with:
```python
    if fmt == "yaml":
        print_yaml(yaml.safe_dump(data, sort_keys=False, default_flow_style=False))
        return
```

- [ ] **Step 6: Add `pygments` to the emitted CLI deps**

In `src/phantasos/generator/cli/scaffold_context.py`, in `_CLI_DEPS`, add `"pygments>=2"` after `"rich>=13"`:
```python
_CLI_DEPS = [
    "typer>=0.12",
    "rich>=13",
    "pygments>=2",
    "pyyaml>=6",
    "python-dotenv>=1.0",
    "jmespath>=1.0",
    "pydantic>=2.11",
]
```

- [ ] **Step 7: Run the Task-1 tests + the kept invariant — verify green**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-uv uv run --no-sync python -m pytest tests/test_cli_emitted.py -k "yaml_output" -q -p no:cacheprovider --no-header`
Expected: PASS — `test_yaml_output_colored_on_terminal`, `test_yaml_output_plain_and_round_trips_when_piped`, `test_yaml_output_long_line_not_truncated_when_piped`, and `test_yaml_output_has_no_trailing_blank_line` all green.

- [ ] **Step 8: Lint the touched files**

Run: `/tmp/phantasos-nox/lint/bin/ruff check tests/test_cli_emitted.py src/phantasos/generator/cli/scaffold_context.py && /tmp/phantasos-nox/lint/bin/ruff format --check tests/test_cli_emitted.py src/phantasos/generator/cli/scaffold_context.py`
Expected: All checks passed (templates aren't ruff-checked; the emitted-then-formatted code is exercised by the suite).

- [ ] **Step 9: Commit**

```bash
git add src/phantasos/generator/cli/templates/_generated/output.py.jinja \
        src/phantasos/generator/cli/scaffold_context.py tests/test_cli_emitted.py
git commit -m "feat(cli): syntax-color --output yaml via shared print_yaml helper (#13)"
```

---

## Task 2: Route `config show` through `print_yaml`

**Files:**
- Modify: `src/phantasos/generator/cli/templates/_generated/config_commands.py.jinja`
- Test: `tests/test_cli_emitted.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_cli_emitted.py`:
```python
def test_config_show_yaml_routes_through_shared_console(
    emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import io

    from rich.console import Console
    from typer.testing import CliRunner

    monkeypatch.setenv("HOME", str(tmp_path))
    main = importlib.import_module("fakesdk_cli.main")

    # piped (non-TTY): plain YAML, no ANSI, content intact
    res = CliRunner().invoke(main.app, ["config", "show"])
    assert res.exit_code == 0
    assert "\x1b[" not in res.output and "format: json" in res.output

    # forced terminal: config show YAML is colored via the shared _console
    out = importlib.import_module("fakesdk_cli._generated.output")
    buf = io.StringIO()
    out._console = Console(file=buf, force_terminal=True)
    res2 = CliRunner().invoke(main.app, ["config", "show"])
    assert res2.exit_code == 0
    assert "\x1b[" in buf.getvalue()  # YAML went through print_yaml -> _console
```

- [ ] **Step 2: Run it — verify the colored half fails**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-uv uv run --no-sync python -m pytest tests/test_cli_emitted.py::test_config_show_yaml_routes_through_shared_console -q -p no:cacheprovider --no-header`
Expected: FAIL — `config show` still uses `typer.echo`, so the YAML never reaches the forced `_console`; `buf` stays empty and `assert "\x1b[" in buf.getvalue()` fails.

- [ ] **Step 3: Import `output` in `config_commands.py.jinja`**

After `from . import diagnostics as _diag` add:
```python
from . import output as _output
```

- [ ] **Step 4: Route `config_show` through `print_yaml`**

In `config_commands.py.jinja`, replace:
```python
    typer.echo(
        yaml.safe_dump(
            _config.effective_dict(), sort_keys=False, default_flow_style=False
        ),
        nl=False,
    )
```
with:
```python
    _output.print_yaml(
        yaml.safe_dump(
            _config.effective_dict(), sort_keys=False, default_flow_style=False
        )
    )
```
(`yaml` and `typer` imports stay — both are still used elsewhere in the file.)

- [ ] **Step 5: Run the new test + the existing config-show test — verify green**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-uv uv run --no-sync python -m pytest tests/test_cli_emitted.py::test_config_show_yaml_routes_through_shared_console tests/test_cli_emitted.py::test_config_init_and_show_commands -q -p no:cacheprovider --no-header`
Expected: PASS — routing works on a terminal; piped output stays plain with `format: json` present; the existing `config init`/`show` test is unaffected (content unchanged; `merged from:` stays on stderr, mixed into `res.output` by CliRunner).

- [ ] **Step 6: Commit**

```bash
git add src/phantasos/generator/cli/templates/_generated/config_commands.py.jinja \
        tests/test_cli_emitted.py
git commit -m "feat(cli): config show YAML uses the shared colored output mechanism (#13)"
```

---

## Task 3: Full offline gate + open PR

**Files:** none (verification + delivery)

- [ ] **Step 1: Full offline gate (managed pythons)**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-uv NOX_ENVDIR=/tmp/phantasos-nox UV_PYTHON_PREFERENCE=only-managed uv run nox --envdir /tmp/phantasos-nox`
Expected: `lint`, `type_check`, `tests` (3.11–3.14), `docs` all succeed. (Confirms the scaffold dep change + the emitted-code change pass the whole suite, including the `test_cli_scaffold.py` membership assertions and the `test_cli_emitted_real.py` real-SDK YAML paths.)

- [ ] **Step 2: Push the branch**

```bash
git push "https://x-access-token:$(gh auth token)@github.com/kaisero/phantasos.git" HEAD:feature/yaml-rich-coloring
```

- [ ] **Step 3: Open the PR into `develop`**

```bash
GH_TOKEN="$(gh auth token)" gh pr create --base develop --head feature/yaml-rich-coloring \
  --title "feat(cli): rich coloring for YAML output (#13)" \
  --body "Closes #13. Single output.print_yaml() helper (rich Syntax, ansi_dark, transparent bg, word_wrap=False, soft_wrap=True) used by both \`--output yaml\` and \`config show\`. Colored on a terminal; byte-clean, round-tripping plain YAML when piped/NO_COLOR (long lines included). Spec: docs/superpowers/specs/2026-06-13-cli-yaml-rich-coloring-design.md."
```

- [ ] **Step 4: Confirm PR CI is green**

Run: `gh pr checks <PR#>` (wait for completion). Expected: all checks pass. Stop here — leave the merge (into `develop`) to the maintainer.

---

## Self-review checklist

- [ ] **Spec coverage:** shared `print_yaml` helper (T1); `Syntax(ansi_dark, bg=default, word_wrap=False, line_numbers=False, soft_wrap=True)` (T1 step 4); `render()` routed (T1); `config show` routed (T2); `pygments` dep explicit (T1 step 6); colored-on-TTY + piped-plain + long-line round-trip + no-trailing-blank tests (T1); config-show routing test (T2); branch off develop / PR `--base develop` / no version bump (T3).
- [ ] **No placeholders:** every code + test block is complete; exact files, commands, and expected output given.
- [ ] **Consistency:** helper named `print_yaml` everywhere; `out._console` force-terminal pattern matches the diagnostics test; `_CLI_DEPS` edit matches the real list; the `render()` old-text matches the current template.
