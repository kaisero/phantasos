# Help-Panel Rename Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** De-suffix the generated CLI's tagged help panels — `Filter Options → Filters`, `Pagination Options → Pagination`, `Common Options → Common` — while keeping the default `Options` panel untouched (the conventional anchor; renaming it was reviewed and rejected).

**Architecture:** Pure string rename in the two production sites that mint panel titles (`render_cli._query_panel` and `commands.py.jinja` tags), with the existing structural tests updated first (TDD red→green). Zero behavior change. A spec addendum records the decision and the rejected `Options → Command` alternative.

**Tech Stack:** Jinja template, Typer rich help panels, pytest.

---

## Process notes

- Work from `/home/ubuntu/git/phantasos`, branch `cli-generator`. NEVER `git checkout/switch/reset`.
- Tests: `export UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv` then `uv run pytest …`.
- Suite baseline: 271 passed, ruff + mypy clean.
- Older spec/plan docs mention the old names — they are dated historical artifacts; do NOT rewrite them. Only the addendum in the current spec changes.

## Rename map (complete occurrence inventory, verified by grep)

| Old | New | Sites |
|---|---|---|
| `Filter Options` | `Filters` | `render_cli.py:36`; tests `test_cli_emitted.py:762,776`, `test_cli_emitted_real.py:453` (+ comments 456-457) |
| `Pagination Options` | `Pagination` | `render_cli.py:36`; `commands.py.jinja:20`; tests `test_cli_emitted.py:763,776,1313,1318,1319`, `test_cli_emitted_real.py:453` |
| `Common Options` | `Common` | `commands.py.jinja:22,31,34,37,43`; tests `test_cli_emitted.py:764,766,1292-1301,1313-1319` (+ comments) |
| `Options` (default) | **unchanged** | — |

---

### Task 1: Spec addendum + rename (tests first)

**Files:**
- Modify: `docs/specs/2026-06-11-cli-common-options-panel-design.md` (append addendum)
- Modify: `tests/test_cli_emitted.py`, `tests/test_cli_emitted_real.py` (expectations first → red)
- Modify: `src/phantasos/generator/cli/render_cli.py:36`, `src/phantasos/generator/cli/templates/_generated/commands.py.jinja` (→ green)

- [ ] **Step 1: Append the addendum to the spec**

Append to `docs/specs/2026-06-11-cli-common-options-panel-design.md`:

```markdown
## Addendum (2026-06-11): panel de-suffixing

User-confirmed follow-up after UX review: the "Options" suffix is redundant on the
tagged panels (every panel contains options). Renames: `Filter Options → Filters`,
`Pagination Options → Pagination`, `Common Options → Common`. The DEFAULT `Options`
panel is deliberately KEPT: renaming it (proposal: "Command") was reviewed and
rejected — "Commands" conventionally means subcommands (the root help has exactly
that panel), and the default title is Typer's, so changing it requires either a
global `typer.rich_utils.OPTIONS_PANEL_TITLE` override (leaks into root/config
screens, version-coupled) or tagging every domain flag (orphans Click's auto
`--help` in a one-line residual panel). Resulting leaf layout:
`Options / Filters / Pagination / Common`.
```

- [ ] **Step 2: Update the test expectations (red first)**

In `tests/test_cli_emitted.py`:

(a) `test_show_flags_grouped_into_panels` (~lines 762-766) — replace the four panel assertions:

```python
    assert 'rich_help_panel="Filters"' in show_fn   # --name (filter query param)
    assert 'rich_help_panel="Pagination"' in show_fn  # --limit + --all
    # --id (path) is NOT panelled; --output joined "Common" (2026-06-11)
    assert re.search(r'--id".*rich_help_panel', show_fn) is None
    assert re.search(r'--output", rich_help_panel="Common"', show_fn)
```

(b) `test_show_help_renders_panels` (~line 776) — replace the substring assertions with the structural helper that already exists in this file:

```python
    titles = _panel_titles(out)
    assert "Filters" in titles and "Pagination" in titles
    assert "Options" in titles  # default panel kept (domain flags + --help)
```

(NOTE: `_panel_titles` is defined lower in the file than this test — Python resolves it at call time, so referencing it here is fine.)

(c) `test_common_options_panel_renders_last` (~lines 1285-1302) — replace every `"Common Options"` with `"Common"` (three assertions + the `res.output.index(...)` anchor + comments). The flag-membership loop and the `--id`/`--help` position assertions are unchanged. The `index("Common")` anchor is safe: the only place the bare title appears in help output is the panel header (option help texts don't contain the word "Common").

(d) `test_pagination_panel_precedes_common_on_non_list_commands` (~lines 1305-1319) — replace `"Common Options"` → `"Common"` and `"Pagination Options"` → `"Pagination"` (three assertions + comment).

In `tests/test_cli_emitted_real.py` (~line 453), inside `test_real_cli_build_emits_full_project`'s help check:

```python
        assert "─ Filters " in out and "─ Pagination " in out
```

(Box-char-anchored substrings — the bare word "Filter" appears in option help texts like "Filter by device group name", so anchor on the rendered panel header. Update the stale comment lines 456-457 to match.)

- [ ] **Step 3: Run to verify red**

Run: `cd /home/ubuntu/git/phantasos && UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/test_cli_emitted.py -q -k "grouped_into_panels or renders_panels or common_options or precedes_common"`
Expected: 4 FAILED (old names still emitted).

- [ ] **Step 4: Rename the production sites**

(a) `src/phantasos/generator/cli/render_cli.py:36`:

```python
def _query_panel(f: Flag) -> str:
    return "Pagination" if f.param in _PAGINATION_PARAMS else "Filters"
```

(b) `src/phantasos/generator/cli/templates/_generated/commands.py.jinja` — in the injected block: `rich_help_panel="Pagination Options"` → `rich_help_panel="Pagination"` (the `--all` line), and all five `rich_help_panel="Common Options"` → `rich_help_panel="Common"`.

- [ ] **Step 5: Run green + full gate**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/ -q && UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run ruff check src tests && UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run mypy src`
Expected: all pass (gated real tests included — they re-render the CLI from the changed template) / clean / clean. Then confirm no stragglers:
`grep -rn "Filter Options\|Pagination Options\|Common Options" src/ tests/ --include="*.py" --include="*.jinja"` → no output.

- [ ] **Step 6: Commit**

```bash
git add docs/specs/2026-06-11-cli-common-options-panel-design.md \
        src/phantasos/generator/cli/render_cli.py \
        src/phantasos/generator/cli/templates/_generated/commands.py.jinja \
        tests/test_cli_emitted.py tests/test_cli_emitted_real.py
git commit -m "refactor(cli-gen): de-suffix help panels — Filters/Pagination/Common (Options kept)"
```

---

### Task 2: Real CLI rebuild + verification + memory

**Files:**
- Regenerates: `/home/ubuntu/git/prisma-browser-cli` (sibling — do NOT commit it)

- [ ] **Step 1: Rebuild and eyeball**

```bash
cd /home/ubuntu/git/phantasos
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run phantasos cli build prisma-browser
cd /home/ubuntu/git/prisma-browser-cli
export UV_PROJECT_ENVIRONMENT=/tmp/prisma-browser-cli-venv
uv sync -q --reinstall-package prisma-browser-cli
mkdir -p /tmp/pr-home
HOME=/tmp/pr-home uv run prisma-browser-cli show device-group --help 2>/dev/null | grep "╭─"
HOME=/tmp/pr-home uv run prisma-browser-cli create device-group --help 2>/dev/null | grep "╭─"
```

Expected panel headers, in order — `show`: `Options`, `Filters`, `Pagination`, `Common`; `create`: `Options`, `Pagination`, `Common`. Paste both sequences in the report.

- [ ] **Step 2: Emitted project suite green**

```bash
HOME=/tmp/pr-home uv run pytest tests/ -q
rm -rf /tmp/pr-home
```
Expected: 3 passed.

- [ ] **Step 3: Update memory**

Append to the `prisma-browser-cli-generator-design` memory entry: panel rename shipped (date, HEAD, `Options/Filters/Pagination/Common` final layout, the rejected `Options→Command` rationale captured in the spec addendum). Handoff: sibling regenerated, uncommitted.

---

## Self-review (done at planning time)

- **Coverage:** every grep hit is mapped in the rename table; the default-panel non-change is explicit; spec addendum records both the decision and the rejected alternative.
- **Placeholders:** none — all assertions and production strings inline.
- **Consistency:** new titles used identically across tests (`Filters`/`Pagination`/`Common` exact, `─ Filters ` box-anchored only in the real-SDK substring test where help texts contain the bare word "Filter").
