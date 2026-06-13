# Common Options Help Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every generated-CLI leaf command's `--help` shows the five injected cross-cutting options (`--output`, `--columns`, `--dry-run`, `--verbose`, `--pager`) in a dedicated "Common Options" panel rendered last, leaving the default Options panel to domain flags.

**Architecture:** Pure help-metadata change in ONE Jinja template (`commands.py.jinja`): tag the five options with `rich_help_panel="Common Options"` and move the `all_` declaration above `output` so Pagination Options' first occurrence always precedes Common Options (Typer renders panels in first-occurrence declaration order — verified empirically). Zero behavioral change.

**Tech Stack:** Jinja template, Typer rich help panels, pytest (fake-SDK emitted-CLI tests).

**Spec:** `docs/specs/2026-06-11-cli-common-options-panel-design.md` — read first; decisions are user-confirmed (panel name "Common Options"; `--all` stays in Pagination Options; `--help` stays stock).

---

## Process notes

- Work from `/home/ubuntu/git/phantasos`, branch `cli-generator`. NEVER `git checkout/switch/reset`.
- Tests: `export UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv` then `uv run pytest …`.
- Behavioral tests go through the emitted package (`emitted` fixture in tests/test_cli_emitted.py renders the fakesdk CLI per test and purges `sys.modules`). Set HOME via monkeypatch BEFORE `importlib.import_module` (config loads at import).
- Suite baseline: 270 passed, ruff + mypy clean.

## File map

| File | Change |
|---|---|
| `src/phantasos/generator/cli/templates/_generated/commands.py.jinja` | tag 5 options with the panel; move `all_` above `output` |
| `tests/test_cli_emitted.py` | panel-title parser helper + 2 structural tests |

---

### Task 1: Panel tags + declaration reorder (TDD)

**Files:**
- Modify: `src/phantasos/generator/cli/templates/_generated/commands.py.jinja` (the injected-options block)
- Test: `tests/test_cli_emitted.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_cli_emitted.py` (module already imports `importlib`; add `re` to the top-of-file imports if not present):

```python
_PANEL_RE = re.compile(r"╭─+\s(.+?)\s─+╮")


def _panel_titles(help_output: str) -> list[str]:
    """Rich panel titles in render order from a --help screen."""
    titles = []
    for line in help_output.splitlines():
        m = _PANEL_RE.search(line)
        if m:
            titles.append(m.group(1).strip())
    return titles


def test_common_options_panel_renders_last(emitted, monkeypatch, tmp_path):
    from typer.testing import CliRunner

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    main = importlib.import_module("fakesdk_cli.main")
    res = CliRunner().invoke(main.app, ["show", "widget", "--help"])
    assert res.exit_code == 0
    titles = _panel_titles(res.output)
    assert "Common Options" in titles
    assert titles[-1] == "Common Options"  # the lowest container
    # the five members appear after the Common Options header...
    idx = res.output.index("Common Options")
    tail = res.output[idx:]
    for flag in ("--output", "--columns", "--dry-run", "--verbose", "--pager"):
        assert flag in tail
    # ...and the domain flag stays in the default Options panel above it
    assert "--id" in res.output[:idx]
    # --help remains stock (default panel, i.e. before Common Options)
    assert "--help" in res.output[:idx]


def test_pagination_panel_precedes_common_on_non_list_commands(
    emitted, monkeypatch, tmp_path
):
    from typer.testing import CliRunner

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    main = importlib.import_module("fakesdk_cli.main")
    # create has NO pagination query params; --all alone must still anchor the
    # Pagination Options panel BEFORE Common Options (the declaration-reorder fix)
    res = CliRunner().invoke(main.app, ["create", "widget", "--help"])
    assert res.exit_code == 0
    titles = _panel_titles(res.output)
    assert titles[-1] == "Common Options"
    assert "Pagination Options" in titles
    assert titles.index("Pagination Options") < titles.index("Common Options")
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd /home/ubuntu/git/phantasos && UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/test_cli_emitted.py -q -k "common_options or precedes_common"`
Expected: FAIL — `"Common Options" in titles` assertion (panel doesn't exist yet).

- [ ] **Step 3: Implement the template change**

In `src/phantasos/generator/cli/templates/_generated/commands.py.jinja`, the injected block currently reads:

```python
    output: str = typer.Option(_cfg.default_output(), "--output"),
    columns: list[str] | None = typer.Option(
        None,
        "--columns",
        help=(
            "Table columns as comma-separated JMESPath expressions"
            " (implies --output table). 'HEADER=expr' names a column."
        ),
    ),
    all_: bool = typer.Option(False, "--all", rich_help_panel="Pagination Options"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    verbose: bool = typer.Option(False, "--verbose"),
    pager: bool | None = typer.Option(
        None,
        "--pager/--no-pager",
        help="Page output taller than the terminal (default from config).",
    ),
```

Replace with (`all_` FIRST — this guarantees Pagination Options' first occurrence precedes Common Options on commands without pagination query params; then the five, each tagged):

```python
    all_: bool = typer.Option(False, "--all", rich_help_panel="Pagination Options"),
    output: str = typer.Option(
        _cfg.default_output(), "--output", rich_help_panel="Common Options"
    ),
    columns: list[str] | None = typer.Option(
        None,
        "--columns",
        help=(
            "Table columns as comma-separated JMESPath expressions"
            " (implies --output table). 'HEADER=expr' names a column."
        ),
        rich_help_panel="Common Options",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", rich_help_panel="Common Options"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", rich_help_panel="Common Options"
    ),
    pager: bool | None = typer.Option(
        None,
        "--pager/--no-pager",
        help="Page output taller than the terminal (default from config).",
        rich_help_panel="Common Options",
    ),
```

The `_rt.run(...)` call below the signature is UNCHANGED (keyword args; declaration order is invisible at runtime). If the current template text differs from the "currently reads" snippet, adapt minimally and report the difference.

- [ ] **Step 4: Run the new tests, then the full gate**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/test_cli_emitted.py -q -k "common_options or precedes_common"`
Expected: PASS.

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/ -q && UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run ruff check src tests && UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run mypy src`
Expected: all pass / clean. If an existing help-related test breaks on panel placement (candidates: any test asserting `--output`/`--pager` near specific help text), read it and update ONLY its location expectations — never its behavioral meaning. Report exactly what changed.

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generator/cli/templates/_generated/commands.py.jinja tests/test_cli_emitted.py
git commit -m "feat(cli-gen): Common Options help panel (renders last) for injected leaf options"
```

---

### Task 2: Real CLI rebuild + verification + wrap

**Files:**
- Regenerates: `/home/ubuntu/git/prisma-browser-cli` (sibling — do NOT commit it)

- [ ] **Step 1: Rebuild and eyeball the real help screens**

```bash
cd /home/ubuntu/git/phantasos
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run phantasos cli build prisma-browser
cd /home/ubuntu/git/prisma-browser-cli
export UV_PROJECT_ENVIRONMENT=/tmp/prisma-browser-cli-venv
uv sync --reinstall-package prisma-browser-cli
HOME=/tmp/cop-home uv run prisma-browser-cli show device-group --help
HOME=/tmp/cop-home uv run prisma-browser-cli create device-group --help
rm -rf /tmp/cop-home
```

Check: `show device-group --help` panels in order — Options (domain + --help), Filter Options (if any), Pagination Options (query params + --all), **Common Options last** with exactly `--output --columns --dry-run --verbose --pager/--no-pager`. `create device-group --help`: Pagination Options (just --all) ABOVE Common Options. Paste both screens (or their panel-title sequence) in the report.

- [ ] **Step 2: Emitted project suite still green**

```bash
HOME=/tmp/cop-home2 uv run pytest tests/ -q; rm -rf /tmp/cop-home2
```
Expected: 3 passed (smoke + 2 config tests).

- [ ] **Step 3: Update memory + report**

Append to the `prisma-browser-cli-generator-design` memory entry: Common Options panel shipped (date, HEAD, the all_-reorder rationale, the rejected alternatives root-only/dual-registration + scrapped --help move — so a future session doesn't re-litigate). Handoff note: sibling regenerated, uncommitted.

---

## Self-review (done at planning time)

- **Spec coverage:** panel membership/name/position → Task 1 Step 3; last-render guarantee (reorder) → Step 3 + the non-list test; scope boundaries (root/config untouched) → no changes outside commands.py.jinja; acceptance criteria 1-4 → Task 1 Steps 1/4 + Task 2.
- **Placeholders:** none; full template block and test code inline.
- **Type consistency:** `_panel_titles` helper used by both tests; flag names match the emitted options.
