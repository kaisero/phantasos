# Test-suite hardening — behavior-preserving refactors (Recs 2–5)

## Goal

Turn four pytest-suite review findings into tiny, independently-committable,
**behavior-preserving** refactors. The whole suite must still pass with the same
(or higher) pass count, and **no assertion may be weakened** — every parametrized
or rewritten test is equally or MORE strict, and no test may become vacuous.

- **Rec 2** — make ring-3 "darkness" loud: a terminal-summary warning when
  `real_sdk` tests skip *for staleness* (not for "SDK absent").
- **Rec 3** — an `isolated_home` fixture + route the leaky `cache_real`/`cache_live`
  `sys.path` inserts through the existing seam.
- **Rec 4** — dedup the fixture constants (conftest = single source) and finish the
  `_imported` migration for the inline `del sys.modules` loops.
- **Rec 5** — parametrize the dispatch matrices; kill the weak/vacuous asserts;
  replace a brittle source-string assert with its behavioral twin; hoist the
  help-determinism env dict to conftest.

## Architecture (what these tests exercise)

phantasos is a codegen pipeline: OpenAPI spec → Python SDK → Typer CLI. The CLI
tests render a CLI package into a `tmp_path`, put it on `sys.path`, import it as
`fakesdk_cli` / `prisma_browser_cli`, drive it with `typer.testing.CliRunner`, then
purge the package from `sys.modules`. Two established seams already own that dance:

- `tests/conftest.py::_imported(out_dir, package)` — a context manager that inserts
  `out_dir` on `sys.path`, purges `package`/`package.*` from `sys.modules`, imports
  and yields the package, then re-purges and restores `sys.path` on exit. Exposed to
  tests as the `render_and_import` fixture (`conftest.py:157-160`).
- `phantasos.generator.opmodel._pathutil.on_sys_path(path)` — insert-once /
  remove-on-exit context manager for putting an SDK fixture on `sys.path`.

Ring-3 ("real artifact") tests request the `real_sdk` fixture
(`conftest.py:89-104`), which `pytest.skip`s when the sibling `../prisma-browser-sdk`
is absent OR stale. Staleness is computed by `_stale_sdk_reason()`
(`conftest.py:36-86`): it diffs the generator worktree against the SHA in the SDK's
`.build-stamp`. The `real_sdk` marker is auto-applied via
`pytest_collection_modifyitems` (`conftest.py:107-113`). Ring-3 runs in CI only in
the `smoke` job (`noxfile.py:225-256`, `pytest -m real_sdk`); the offline gate
(`nox -s gate` → `pytest -q -m "not slow"`) SKIPS them.

**Verified current fact:** the built SDK is stale right now (`.build-stamp` =
`c9391989`, HEAD `f34dedba`; `git diff` over `src/phantasos`+`products/prisma-browser`
returns rc=1). So the Rec-2 warning is directly demonstrable, and Rec-5's
ring-3 changes must be verified against a built SDK (they do not run in the gate).

## Tech Stack

- pytest 8, `addopts = "-ra --strict-markers --strict-config"`, `pythonpath = ["."]`,
  `testpaths = ["tests"]`, markers `slow` + `real_sdk` (`pyproject.toml:176-186`).
- **`from conftest import <name>` works** in this repo (prepend import mode; pytest
  imports `tests/conftest.py` first, putting `tests/` on `sys.path`). Verified with a
  throwaway probe test. This is the sanctioned way to share the conftest constants
  the plan introduces.

## Global Constraints (apply to every task)

- Run tests as `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/rev uv run ...`. Do **not** set
  `TMPDIR` (a phantasos test truncates config paths to width and fails on longer
  `tmp_path`s). Relocate only the venv.
- **FULL gate green before each commit:** `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/rev uv run nox -s gate`.
- Commit **specific paths** (never `git add -A`). No `Claude-Session:` trailer.
- **Never** edit frozen oracles: `.claude/harness.toml`, `tests/golden/**`,
  `tests/fixtures/**`.
- **No assertion may be weakened.** For every pure refactor (parametrize / dedup /
  isolation-swap) the verification is: run the affected file(s) **before and after**
  and confirm an **identical or higher** pass count, with no test turned vacuous.
- **Ring-3 caveat:** the gate does NOT execute `real_sdk` tests. For any task that
  touches a ring-3 test (Tasks 2, 3, 5-help-real), additionally run them against a
  built SDK and show the result:
  `PHANTASOS_ALLOW_STALE_SDK=1 UV_PROJECT_ENVIRONMENT=$HOME/.tmp/rev uv run pytest <file> -q`
  (quick, uses the current build), and/or `uv run nox -s smoke` (authoritative rebuild).

---

## Task 1 — Rec 2: loud ring-3 staleness warning (`conftest.py` + new test)

**Files:** `tests/conftest.py`, `tests/test_conftest_hooks.py` (new).

Add a `pytest_terminal_summary` hook that prints ONE hard-to-miss line to the
terminal summary when ≥1 `real_sdk` test skipped **for staleness**. It stays quiet
when the SDK is merely absent (fresh checkout / CI `tests` job) or up to date. The
message logic is a pure, unit-tested helper that reuses the existing per-test skip
reason (which already carries the built SHA + rebuild hint).

**Step 1 (TDD, red):** add `tests/test_conftest_hooks.py`:

```python
"""Unit tests for the pytest_terminal_summary ring-3 staleness banner."""

from __future__ import annotations

from conftest import _STALE_SENTINEL, _ring3_stale_summary, _stale_reason_text


def test_banner_fires_on_staleness_skip() -> None:
    # Feed the REAL reason string (the same pure builder _stale_sdk_reason uses),
    # NOT a hand-copied literal — so a reword of the reason is caught here.
    reason = "Skipped: " + _stale_reason_text("abcd1234", "ef567890")
    line = _ring3_stale_summary([reason])
    assert line is not None
    assert line.startswith("⚠ ring-3 OFF:")
    assert "abcd1234" in line and "ef567890" in line  # built + HEAD shas
    assert "nox -s smoke" in line                       # rebuild hint
    assert "Skipped:" not in line                       # prefix stripped


def test_banner_quiet_when_sdk_absent_not_stale() -> None:
    # the "absent" skip reason must NOT trigger the loud line
    assert _ring3_stale_summary(
        ["Skipped: prisma-browser-sdk not built (run: nox -s smoke)"]
    ) is None


def test_banner_quiet_when_no_skips() -> None:
    assert _ring3_stale_summary([]) is None


def test_sentinel_is_a_substring_of_the_real_reason() -> None:
    # Drift guard that is NOT a tautology: the reason is BUILT from the sentinel,
    # so this can only pass while _ring3_stale_summary's match key really appears
    # in the text _stale_sdk_reason emits. Reword the reason without the sentinel
    # and BOTH this and test_banner_fires_on_staleness_skip go red.
    assert _stale_reason_text("x", "y").startswith(_STALE_SENTINEL + ":")
```

**Step 2 (green):** in `conftest.py`, (a) extend `_stale_sdk_reason()` so the reason
also names the HEAD short-SHA, and (b) add the sentinel, the pure helper, and the
hook. Extend the return of `_stale_sdk_reason()` (currently `conftest.py:82-86`):

```python
    try:
        head = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--short=8", "HEAD"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        head = "unknown"
    return _stale_reason_text(built[:8], head)
```

Then add (near the other ring-3 machinery) the SINGLE source of the reason text —
`_stale_sdk_reason` (above), the banner hook, AND both unit tests all go through
`_stale_reason_text`, so the sentinel cannot drift from the emitted reason:

```python
_STALE_SENTINEL = "prisma-browser-sdk is stale"


def _stale_reason_text(built_sha8: str, head_sha8: str) -> str:
    """The one place the staleness reason string is built (composed FROM the
    sentinel, so _STALE_SENTINEL is a substring by construction)."""
    return (
        f"{_STALE_SENTINEL}: the generator (src/phantasos or products/prisma-browser)"
        f" changed since it was built at {built_sha8} (HEAD {head_sha8}) — rebuild: "
        f"nox -s smoke (or set PHANTASOS_ALLOW_STALE_SDK=1)"
    )


def _ring3_stale_summary(skip_reasons: Iterable[str]) -> str | None:
    """One loud terminal-summary line when a ring-3 test skipped for SDK *staleness*.

    Returns ``None`` when no skip was a staleness skip (SDK absent, or the ring
    actually ran), so a fresh checkout and CI's SDK-less ``tests`` job stay quiet.
    Reuses the per-test staleness reason verbatim — it already carries the built +
    HEAD short shas and the ``rebuild: nox -s smoke`` hint — behind a ⚠ marker.
    """
    for reason in skip_reasons:
        if _STALE_SENTINEL in reason:
            return f"⚠ ring-3 OFF: {reason.removeprefix('Skipped: ')}"
    return None


def pytest_terminal_summary(
    terminalreporter: Any, exitstatus: int, config: pytest.Config
) -> None:
    """Print the ring-3 staleness banner (stderr/summary only; never fails a run)."""
    reasons = [
        rep.longrepr[2] if isinstance(rep.longrepr, tuple) else str(rep.longrepr)
        for rep in terminalreporter.stats.get("skipped", [])
    ]
    if line := _ring3_stale_summary(reasons):
        terminalreporter.write_line(line, red=True, bold=True)
```

(`Iterable` is already importable via `collections.abc`; add it to the existing
import at `conftest.py:13` if not present. `Any` is already imported.)

**Verify:**
- `uv run pytest tests/test_conftest_hooks.py -q` → 4 pass.
- Because the SDK is currently stale, `uv run pytest -q -m "not slow"` (the gate's
  pytest) must now END with the `⚠ ring-3 OFF: prisma-browser-sdk stale (built
  c9391989, HEAD <head>) — rebuild: nox -s smoke` line, and the run must still be
  green (the banner does not fail anything). Capture the terminal tail as evidence.
- Confirm quiet-when-absent by pointing at an absent SDK is unnecessary here (the
  unit tests cover it). The reason text now has ONE source (`_stale_reason_text`),
  consumed by `_stale_sdk_reason`, the banner hook, AND both unit tests — so a
  reword can no longer silently disable the banner (the old plan left that hole).

**Commit:** `tests/conftest.py`, `tests/test_conftest_hooks.py`.

---

## Task 2 — Rec 5a: parametrize the dispatch matrices (`test_cli_dispatch_matrix.py`)

**File:** `tests/test_cli_dispatch_matrix.py`.

> **⚠ HARD GATE (applies to Tasks 2 and 3):** every test in this file is **ring-3**
> (`real_cli` → `real_sdk`), so `nox -s gate` (`-m "not slow"`, stale SDK) **SKIPS
> them** — the offline gate CANNOT verify these refactors. The commit is NOT done
> until you have captured a real run:
> `PHANTASOS_ALLOW_STALE_SDK=1 UV_PROJECT_ENVIRONMENT=$HOME/.tmp/rev uv run pytest tests/test_cli_dispatch_matrix.py -q`
> and confirmed the pass count is unchanged (Task 2: same total, now split into
> independent cases) with zero new skips. Paste that output into the commit
> evidence. Do not rely on the green offline gate for these two tasks.

`test_show_dispatch_matrix` (`:102-203`) runs Cases 1–4 sequentially in one function
with duplicated recorder/monkeypatch blocks (a Case-1 failure hides 2–4).
`test_delete_dispatch_matrix` (`:206-255`) does the same for Cases 5–6. Convert both
to `@pytest.mark.parametrize` over `(extra_args, expected_op)` so each case is an
independent test. **Assertions are unchanged** (`exit_code == 0`, `expected_op in
fired`); only the harness splits.

Hoist the per-test `_make_recorder`/`_make_client` closures to module scope (they
differ only in list-vs-single response shape for show vs None for delete). Worked
form for the show matrix:

```python
_SHOW_CASES = [
    pytest.param(["--id", "APP-1"], "get_application_by_id", id="id-only"),
    pytest.param(
        ["--id", "APP-1", "--type", "custom"],
        "get_application_by_type_and_id", id="id-and-type",
    ),
    pytest.param([], "list_applications", id="bare"),
    pytest.param(["--type", "custom"], "list_applications_by_type", id="type-only"),
]


def _show_client(fired: list[str]) -> Any:
    """Fake Client whose application._api records raw-method calls (show shapes)."""
    from prisma_browser.extras.resources import ApplicationResource

    _single = _make_app_response()
    _list_page = _make_list_response([_make_app_response()])

    class _Rec:
        def __getattr__(self, name: str) -> Any:
            def _fn(**kw: Any) -> Any:
                fired.append(name)
                return _list_page if name.startswith("list_") else _single
            return _fn

    class _FakeClient:
        def __init__(self) -> None:
            self.application = ApplicationResource(_Rec())
        api_client = None

    return _FakeClient()


@pytest.mark.parametrize("extra_args, expected_op", _SHOW_CASES)
def test_show_dispatch_matrix(
    real_cli: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    extra_args: list[str], expected_op: str,
) -> None:
    """`show application <args>` routes to the correct raw op (one case per test)."""
    import prisma_browser.extras.facade as facade
    from typer.testing import CliRunner

    monkeypatch.setenv("HOME", str(tmp_path))
    main = importlib.import_module("prisma_browser_cli.main")
    fired: list[str] = []
    monkeypatch.setattr(
        facade.Client, "from_env", classmethod(lambda cls: _show_client(fired))
    )
    res = CliRunner().invoke(
        main.app, ["show", "application", *extra_args, "--output", "json"]
    )
    assert res.exit_code == 0, f"{extra_args}: {res.output}"
    assert expected_op in fired, f"fired={fired}"
```

Mirror for delete with `_DELETE_CASES` (2 params) and a `_delete_client` recorder
that appends and returns `None`. Keep the original docstrings' intent as a comment on
`_SHOW_CASES` (most-specific binding wins: `--id --type` beats `--id`).

**Verify (pure refactor, ring-3):** against a built SDK,
`PHANTASOS_ALLOW_STALE_SDK=1 ... uv run pytest tests/test_cli_dispatch_matrix.py -q`
before = 2 dispatch functions (show+delete) selected; after = **6** independently
selectable node ids (`-k id-only`, `-k type-only`, `-k id-and-type` …), all passing.
Case count increased; each case independently selectable; no assertion changed.

**Commit:** `tests/test_cli_dispatch_matrix.py`.

---

## Task 3 — Rec 5b: kill the weak/vacuous asserts (`test_cli_dispatch_matrix.py`)

**File:** `tests/test_cli_dispatch_matrix.py`.

**(a) The `or`-assert at `:437`** (`test_dry_run_parity_show_by_id`):

```python
assert "APP-99" in out or "/applications" in out   # passes if EITHER half regresses
```

is satisfied even if the id vanishes from the URL. A by-id dry-run must print the id
*in the path*. **Replace ONLY the `or`-assert line at `:437`** — the `assert "GET"
in out` on the line ABOVE it (`:436`) already exists; do NOT duplicate it:

```python
# :436  assert "GET" in out          # <- keep the existing line, unchanged
assert "/applications/APP-99" in out  # replaces the :437 or-assert: id lands in the path
```

**Verify-first (mandatory):** the exact path string is generator-defined; capture
the real dry-run output before finalizing — temporarily print `out` under
`PHANTASOS_ALLOW_STALE_SDK=1 ... pytest -k show_by_id -s`, read the real URL, and pin
whatever it actually is as ONE strict substring (no `or`). If the real URL is, e.g.,
`/applications/APP-99` keep the above; if it differs, pin the real string.

**(b) The double-guarded history check at `:373-379`**
(`test_all_pages_walks_and_injects_sort`) passes vacuously when `entries` is empty:

```python
entries, _ = hist.read_entries(0)
if entries:                              # <- vacuous pass if history empty
    entry = entries[-1]
    assert entry["status"] == "success", ...
    if "http_uri" in entry:
        assert entry["http_uri"].endswith("/applications"), ...
```

Make the precondition explicit. The run records a history entry (status success);
`http_uri` is genuinely absent on the recorder-api path (documented at `:368-370`),
so that inner guard stays honest:

```python
entries, _ = hist.read_entries(0)
assert entries, "expected a history entry for the --all run"   # precondition, strict
entry = entries[-1]
assert entry["status"] == "success", f"history status: {entry}"
# http_uri is only captured when call_api fires; the recorder-api path bypasses it,
# so its ABSENCE is expected and documented — assert only when present.
if "http_uri" in entry:
    assert entry["http_uri"].endswith("/applications"), f"http_uri: {entry['http_uri']!r}"
```

If verify-first confirms `http_uri` is ALWAYS absent on this recorder-api path (the
documented expectation), prefer pinning that documented absence over a branch that
never executes: replace the `if` with `assert "http_uri" not in entry` (a real
assertion of the documented behavior). Keep the `if`-present form only if the verify
shows the key can actually appear.

**Verify-first (mandatory):** run against a built SDK and confirm `entries` is
non-empty. If — contrary to expectation — history is genuinely not written on this
monkeypatched-`sys.argv` path, do NOT keep a vacuous pass: replace `assert entries`
with `pytest.skip("no history recorded for the recorder-api path")` (honest, not a
fake pass). Record which branch you took as evidence.

**Verify:** `PHANTASOS_ALLOW_STALE_SDK=1 ... pytest tests/test_cli_dispatch_matrix.py -q`
green; the two asserts are now strictly stronger (or an honest skip), never vacuous.

**Commit:** `tests/test_cli_dispatch_matrix.py`.

---

## Task 4 — Rec 5 (Q4): behavioral panel test replaces the source-string assert

**File:** `tests/test_cli_emitted.py`.

`test_show_flags_grouped_into_panels` (`:433-454`) regex-matches the generated
**source** (`rich_help_panel="Filters"` etc.). Its behavioral twin
`test_show_help_renders_panels` (`:457-470`) proves panels via `--help` output — but
**only that Filters/Pagination/Options titles exist**. It does NOT prove the source
test's two *unique* facts: `--id` is NOT panelled, and `--output` joins `Common`.
`test_common_options_panel_renders_last` (`:1109-1130`) proves `--output` is under
`Common` and `--id` precedes `Common`, but NOT that `--id` is outside Filters.

⚠ **Do not simply delete the source test** — that would weaken coverage of
"`--id` not panelled". Instead, STRENGTHEN the behavioral twin to subsume all four
source facts via panel-section slicing, then delete the source test.

Add a section helper near `_panel_titles` (`test_cli_emitted.py:1099`):

```python
def _panel_section(help_output: str, title: str) -> str:
    """ANSI-stripped text of the Rich panel named `title`: from its header line to
    the next panel header (exclusive), or to EOF for the last panel."""
    lines = _strip_ansi(help_output).splitlines()
    starts = [
        (i, m.group(1).strip())
        for i, line in enumerate(lines)
        if (m := _PANEL_RE.search(line))
    ]
    for idx, (i, name) in enumerate(starts):
        if name == title:
            end = starts[idx + 1][0] if idx + 1 < len(starts) else len(lines)
            return "\n".join(lines[i:end])
    return ""
```

Extend `test_show_help_renders_panels` (keep `NO_COLOR=1`; do NOT use `TERM=dumb`
here — a dumb terminal drops the box borders `_panel_titles`/`_panel_section` rely
on):

```python
titles = _panel_titles(out)
assert "Filters" in titles and "Pagination" in titles   # (was source: rich_help_panel=)
assert "Options" in titles                              # default panel kept
# membership — behavioral, strictly subsumes the deleted source-regex asserts:
assert "--name" in _panel_section(out, "Filters")
assert "--limit" in _panel_section(out, "Pagination")
assert "--all" in _panel_section(out, "Pagination")
assert "--id" in _panel_section(out, "Options")     # --id NOT panelled -> default
assert "--id" not in _panel_section(out, "Filters") # ...and specifically not a filter
assert "--output" in _panel_section(out, "Common")  # source fact #4, now self-contained
```

**`models=None` nuance (accepted, low-risk):** the deleted source test rendered via
`build_cli_ir(inv, _FAKESDK_CLI_CONFIG)` (the un-deepened `models=None` path); the twin
runs on the `emitted` fixture (rendered WITH a model registry). Panel assignment for
path/query flags is model-independent, so no panel behavior is lost — but state this
explicitly in the commit body rather than claiming byte-for-byte coverage parity.

**Verify-first:** run `pytest -k show_help_renders_panels -q -s` on the fakesdk
`emitted` fixture (offline, no ring-3), print `out`, and confirm every membership
assert holds against the real `--help` layout BEFORE deleting the source test. Only
once the behavioral test is green and strictly ≥ the source coverage, **delete**
`test_show_flags_grouped_into_panels` (`:433-454`). If any membership fact can't be
proven behaviorally, KEEP that one source assertion rather than lose coverage — flag
it. (NOTE: `FIXTURE`/`_FAKESDK_CLI_CONFIG` stay USED after this deletion — by
`test_scalar_body_flags_use_real_types` at `test_cli_emitted.py:143` and the ruff-lint
test at `:724-726`. Do NOT remove the imports; Task 8 re-points them at conftest.)

**Verify:** file pass count unchanged minus 1 (the deleted source test) plus 0 new
functions, with the twin now strictly stronger. Net: no coverage lost.

**Commit:** `tests/test_cli_emitted.py`.

---

## Task 5 — Rec 5d: hoist `HELP_ENV` to conftest

**Files:** `tests/conftest.py`, `tests/test_cli_emitted_real.py`.

`_HELP_ENV = {"TERM": "dumb", "NO_COLOR": "1", "COLUMNS": "200"}` is defined per-file
in `test_cli_emitted_real.py:38` and passed to two `.invoke(..., env=_HELP_ENV)` calls
(`:546`, `:632`). Hoist the constant to conftest so help-output tests share one
deterministic env. Use a **shared constant** (imported), not an autouse fixture: an
autouse env override would perturb every test suite-wide and risk the color-positive
tests (e.g. `test_yaml_output_colored_on_terminal`, `test_render_error*` which assert
on `NO_COLOR`) — out of scope for a behavior-preserving refactor.

In `conftest.py` (module scope, near the other shared constants):

```python
# Deterministic terminal env for tests that substring-assert Typer/Rich `--help`
# LAYOUT (panel titles, hyphenated option names). TERM=dumb disables styling so the
# literals stay contiguous; the fixed COLUMNS keeps wrapping stable. Pass explicitly
# to the `.invoke(..., env=HELP_ENV)` calls whose output is substring-asserted.
HELP_ENV = {"TERM": "dumb", "NO_COLOR": "1", "COLUMNS": "200"}
```

In `test_cli_emitted_real.py`: delete the local `_HELP_ENV` (`:29-38` keep the
explanatory comment or drop it), add `from conftest import HELP_ENV`, and rename the
two call sites `env=_HELP_ENV` → `env=HELP_ENV`.

**Verify (pure move):** `uv run pytest tests/test_cli_emitted_real.py -q` — identical
pass/skip counts before and after (these are ring-3; the gate skips them, so also run
`PHANTASOS_ALLOW_STALE_SDK=1 ... pytest tests/test_cli_emitted_real.py -q`). The dict
value is byte-identical, so no output assertion changes.

**Follow-up note (do not do here):** `test_cli_emitted.py:1157` builds an equivalent
inline `{**os.environ, "COLUMNS":"200","TERM":"dumb","NO_COLOR":"1"}`; it could import
`HELP_ENV` later. Left as documented follow-up (different call shape — merges
`os.environ`), not swept in this PR.

**Commit:** `tests/conftest.py`, `tests/test_cli_emitted_real.py`.

---

## Task 6 — Rec 3a+3b: `isolated_home` fixture + migrate `test_cli_emitted_cache.py`

**Files:** `tests/conftest.py`, `tests/test_cli_emitted_cache.py`.

Add an `isolated_home` fixture and adopt it in the highest-density offender
(`test_cli_emitted_cache.py` does `monkeypatch.setenv("HOME", str(tmp_path))` in 21
tests). The fixture sets HOME to `tmp_path` (**the file's existing convention**, so
the `cfg.cache_dir_path() == tmp_path / ".fakesdk" / "cache"` assert at
`test_cli_emitted_cache.py:30` stays byte-identical) and adds config-cache hygiene on
entry/exit. **Decision: it does NOT purge `{{package}}` modules** — `render_and_import`
already owns that; keeping responsibilities separate avoids double-purge coupling.

In `conftest.py`:

```python
def _clear_emitted_config_cache() -> None:
    """Clear the ``load_config`` lru_cache on any *already-imported* emitted config
    module. Guarded — a no-op when no emitted CLI is resident. Defends against a test
    that imported ``<pkg>._generated.config`` OUTSIDE ``render_and_import`` leaving a
    cache bound to a stale HOME behind for the next test."""
    for name, mod in list(sys.modules.items()):
        if name.endswith("_cli._generated.config"):
            if clear := getattr(getattr(mod, "load_config", None), "cache_clear", None):
                clear()


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """HOME -> the per-test ``tmp_path``, with emitted-config cache hygiene on
    entry/exit. Yields the home dir. Isolates config/cache/history/env-file lookups
    (all keyed off HOME) without changing what any test asserts — it only replaces
    the hand-rolled ``monkeypatch.setenv("HOME", str(tmp_path))`` line and adds
    teardown hygiene."""
    monkeypatch.setenv("HOME", str(tmp_path))
    _clear_emitted_config_cache()
    try:
        yield tmp_path
    finally:
        _clear_emitted_config_cache()
```

Reference conversion — each of the 21 `test_cli_emitted_cache.py` tests: **add the
`isolated_home` fixture param and delete the `monkeypatch.setenv("HOME", str(tmp_path))`
line.** Keep every in-body `load_config.cache_clear()` unchanged — the post-env-
mutation clears (e.g. `:33`, `:37`) are load-bearing (they force a re-read after
`FAKESDK_CACHE_ENABLED`/`delenv` changes), and the leading defensive clear is harmless.
This task changes *only how the test isolates*, never what it asserts. Worked example
(`test_cache_config_defaults_and_env`, `:17-41`):

```python
def test_cache_config_defaults_and_env(
    emit_cli: Callable[..., Path],
    render_and_import: Callable[[Path, str], AbstractContextManager[ModuleType]],
    isolated_home: Path,          # <- was: monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch: pytest.MonkeyPatch,   # kept: still used for FAKESDK_CACHE_ENABLED
    tmp_path: Path,               # kept: cache_dir_path assertion references it
) -> None:
    out = emit_cli(auth=True)
    with render_and_import(out, "fakesdk_cli"):
        cfg = importlib.import_module("fakesdk_cli._generated.config")
        cfg.load_config.cache_clear()
        assert cfg.get().cache.enabled is True
        assert cfg.get().cache.dir is None
        assert cfg.cache_dir_path() == tmp_path / ".fakesdk" / "cache"   # unchanged
        monkeypatch.setenv("FAKESDK_CACHE_ENABLED", "false")
        cfg.load_config.cache_clear()                                    # load-bearing
        assert cfg.get().cache.enabled is False
        ...
```

Tests that set OTHER env (`_set_creds`, `FAKESDK_CACHE_ENABLED`, `FAKESDK_CACHE_DIR`)
keep `monkeypatch`; only the HOME line is removed. `test_unwritable_dir_fails_open`
(`:491`) keeps `blocked = tmp_path / "blocked"` — HOME is still `tmp_path`.

**Verify (pure isolation-swap):** `uv run pytest tests/test_cli_emitted_cache.py -q`
before AND after → **identical pass count** (offline; not ring-3). No assertion text
changed.

**Scope note (explicit — not silently "all swept"):** this migrates the fixture +
the one reference file (`test_cli_emitted_cache.py`, 21 sites). The remaining
~83 `monkeypatch.setenv("HOME", ...)` sites across ~11 files are a documented
follow-up (see Follow-ups) — several use the `tmp_path / "home"` convention and would
need matching assert edits, so they are out of this PR's behavior-preserving scope.

**Commit:** `tests/conftest.py`, `tests/test_cli_emitted_cache.py`.

---

## Task 7 — Rec 3c: fix the `cache_real`/`cache_live` `sys.path` leaks

**Files:** `tests/test_cli_cache_real.py`, `tests/test_cli_cache_live.py`.

Both files insert paths into `sys.path` with **no cleanup** and import the emitted CLI
/ SDK OUTSIDE the `render_and_import`/`on_sys_path` seam
(`test_cli_cache_real.py:50-52,73-75`; `test_cli_cache_live.py:22-23`). A leaked
`tmp_path` entry lets a later test import a stale `prisma_browser_cli` from a prior
render. Route through the existing seams (behavior identical; the fix is hygiene).

**`test_cli_cache_real.py`** — `test_resolver_finds_tm_on_real_facade` (`:44-66`)
imports both the real SDK (`prisma_browser.*`) and the emitted CLI
(`prisma_browser_cli._generated.auth_cache`). Nest the two seams (import
`on_sys_path` + accept the `render_and_import` fixture):

```python
def test_resolver_finds_tm_on_real_facade(
    real_sdk: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    render_and_import: Callable[[Path, str], AbstractContextManager[ModuleType]],
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    _render_pb_cli(real_sdk, tmp_path)
    with on_sys_path(real_sdk), render_and_import(tmp_path, "prisma_browser_cli"):
        try:
            facade = importlib.import_module("prisma_browser.extras.facade")
            auth = importlib.import_module("prisma_browser.extras.auth")
        except ImportError as exc:
            pytest.skip(f"prisma-browser-sdk not importable: {exc}")
        ac = importlib.import_module("prisma_browser_cli._generated.auth_cache")
        client = facade.Client(
            auth.api_client_from_credentials(client_id="x", client_secret="y", scope="z")
        )
        tm = ac.token_manager(client)
        assert tm is not None, "resolver failed on the real facade (coupling broke)"
        assert tm is client.api_client.configuration._token_manager
        assert ac.key_for(tm)
```

`test_real_tm_honors_seeded_token_without_grant` (`:69-96`) imports only the SDK — no
CLI render — so just `with on_sys_path(real_sdk):` (drop the bare
`sys.path.insert`). Add the imports at top of file:
`from contextlib import AbstractContextManager` / `from types import ModuleType` /
`from collections.abc import Callable` /
`from phantasos.generator.opmodel._pathutil import on_sys_path`. `render_and_import`
purges `prisma_browser_cli*` only; the real SDK stays resident across tests (fine —
it is stable and read-only), so no `prisma_browser.*` purge is needed.

**`test_cli_cache_live.py`** — `test_live_token_is_cached_and_reused` (`:18-36`)
imports only the SDK. Replace `if str(_REAL) not in sys.path: sys.path.insert(...)`
with `with on_sys_path(_REAL):` wrapping the body; add the
`from phantasos.generator.opmodel._pathutil import on_sys_path` import. Keep its own
`skipif` gating (it is a live-creds test, distinct from the `real_sdk` fixture — no
gating change).

**Verify (pure hygiene):**
- Offline: both files still COLLECT and their tests still skip/pass exactly as before
  (`test_cli_cache_live` skips without creds; `test_cli_cache_real` skips when SDK
  absent/stale). `uv run pytest tests/test_cli_cache_real.py tests/test_cli_cache_live.py -q`.
- With a built SDK: `PHANTASOS_ALLOW_STALE_SDK=1 ... pytest tests/test_cli_cache_real.py -q`
  passes, and `sys.path` no longer retains the `tmp_path` entry afterward (spot-check:
  run the file twice in one session, or run it alongside another emitted-CLI file, and
  confirm no cross-contamination). Assertions unchanged.

**Commit:** `tests/test_cli_cache_real.py`, `tests/test_cli_cache_live.py`.

---

## Task 8 — Rec 4a: conftest = single source for `FAKESDK_FIXTURE` + config

**Files:** `tests/conftest.py`, `tests/test_cli_emitted.py`.

`_FAKESDK_CLI_CONFIG` is defined **byte-identically** in `conftest.py:231-243` AND
`test_cli_emitted.py:18-30` (verified `diff` → IDENTICAL), plus a THIRD inline copy
inside conftest's own `emit_cli` fixture (`conftest.py:182-194`). The fakesdk fixture
path is `FIXTURE`/`FAKESDK`/`fixture` in ~17 files. **Finding to record:** the review
also cited "a variant in `test_cli_emitted_environments.py`", but that file no longer
defines its own config — it consumes the shared `emitted`/`emitted_auth` fixtures.
Note this in the commit body; nothing to delete there.

Consolidate to conftest as the single source, then import in the reference file:

1. In `conftest.py`: move `FIXTURE` (`:227`) and `_FAKESDK_CLI_CONFIG` (`:231-243`)
   up to just below the imports (so `emit_cli` can reference them without relying on
   late binding), add a public alias `FAKESDK_FIXTURE = FIXTURE`, and replace the
   inline copies inside `emit_cli` (`:181` `fixture = ...`, `:182-194` `config = ...`)
   with `fixture = FIXTURE` / `config = _FAKESDK_CLI_CONFIG`. (Verify the `emit_cli`
   inline block is byte-identical first — it is, per the read; if it had drifted,
   STOP and surface it rather than pick one.)
2. In `test_cli_emitted.py`: delete `FIXTURE` (`:14`) and `_FAKESDK_CLI_CONFIG`
   (`:18-30`); add `from conftest import FIXTURE, _FAKESDK_CLI_CONFIG`. Drop the now-
   unused `from phantasos.generator.cli.cliconfig import ... RequestMapping, VariantMap`
   parts of `:11` (functions that still need `CliConfig` import it locally at
   `:140-141`). Let the gate's ruff (F401) confirm which module-level imports are now
   dead and remove exactly those.

`from conftest import FIXTURE, _FAKESDK_CLI_CONFIG` is proven to resolve (probe test
in Tech Stack). Behavior is identical — same objects, just one definition.

**Verify (pure dedup):** `uv run pytest tests/test_cli_emitted.py -q` before/after →
identical pass count; `uv run nox -s gate` green (ruff confirms no dangling imports).
`grep -c '_FAKESDK_CLI_CONFIG = CliConfig' tests/*.py` drops from 2 to 1 (conftest;
plus conftest's `emit_cli` no longer holds a 3rd inline copy).

**Commit:** `tests/conftest.py`, `tests/test_cli_emitted.py`.

---

## Task 9 — Rec 4b: migrate the inline `del sys.modules` loops to the seam

**File:** `tests/test_cli_emitted.py`.

Five tests hand-roll a purge loop (`for n in [...]: del sys.modules[n]`) to force a
fresh re-import after setting `NO_COLOR`, instead of the `render_and_import` seam:
`:308-309`, `:343-344`, `:383-384`, `:461-462`, `:517-518`. Each of these tests
already receives the `emitted` fixture (== `tmp_path`), so nest `render_and_import`
around the (now fresh) import + assertions. Worked example
(`test_render_error_api_exception_to_stderr`, `:302-327`):

```python
def test_render_error_api_exception_to_stderr(
    emitted: Path,
    render_and_import: Callable[[Path, str], AbstractContextManager[ModuleType]],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    with render_and_import(emitted, "fakesdk_cli"):    # fresh import; purges on exit
        d = importlib.import_module("fakesdk_cli._generated.diagnostics")

        class _Exc:  # duck-typed ApiException
            status = 400
            reason = "Bad Request"
            body = (
                '{"errorResponse":{"error":"group name already exists",'
                '"message":"failed to create device group"}}'
            )
            data = None

        d.render_error(_Exc())
    err = capsys.readouterr().err
    assert "400 Bad Request" in err
    assert "group name already exists" in err
    assert "errorResponse" in err and "failed to create device group" in err
    assert "HTTPHeaderDict" not in err
    assert "response headers" not in err.lower()
```

Nesting is safe: the outer `emitted` fixture already added `tmp_path` to `sys.path`,
so the inner `render_and_import` sees the entry present (`added=False`) and leaves it
alone on exit while still giving a fresh module (purge → import → purge). Add the
`render_and_import` fixture param + the `AbstractContextManager`/`ModuleType`/`Callable`
imports (already imported in `test_cli_emitted.py`? add if missing — currently only
`Callable`, `Iterator` at `:4`; add `AbstractContextManager`, `ModuleType`). Repeat
mechanically for the other four (`:344` `test_cli_runner_api_error_is_pretty`, `:384`
`test_render_error_non_json_body`, `:462` `test_show_help_renders_panels` — coordinate
with Task 4 which also edits this test, `:518` `test_version_flag_wired`). Assertions
are unchanged; only the purge mechanism swaps.

**Verify (pure refactor):** `uv run pytest tests/test_cli_emitted.py -q` before/after
→ identical pass count. No bare `del sys.modules` remains in `test_cli_emitted.py`
(`grep -n 'del sys.modules' tests/test_cli_emitted.py` → empty).

**Commit:** `tests/test_cli_emitted.py`.

---

## Documented follow-ups (explicitly NOT in this PR)

Surfaced so nothing is silently claimed "all swept":

1. **Broad HOME sweep (Rec 3):** ~83 remaining `monkeypatch.setenv("HOME", ...)` sites
   across ~11 files (`test_cli_emitted_environments.py` 25, `test_cli_emitted_connection.py`
   7, `test_cli_emitted.py` 6, `test_cli_emitted_history.py`, `…logging.py`,
   `…config.py`, `test_cli_lazy_loading.py`, `test_cli_prisma_access_e2e.py`,
   `test_cli_dispatch_matrix.py`, …). Many use the `tmp_path / "home"` convention and
   would need matching assert edits, so `isolated_home` can't drop in without
   per-file review. Sweep in a later PR, one file per commit.
2. **`_imported` migration for the module-level ctxmanagers (Rec 4):**
   `test_cli_emitted_connection.py::_fed_cli` (`:65-93`, purge at `:83`/`:91`) and
   `test_cli_federated_runtime.py::_fed_runtime` (`:93-122`, purge at `:112`/`:120`)
   hand-roll the same insert+purge dance — but they are module-level `@contextmanager`
   helpers (can't request a fixture) AND they already clean up correctly (a `finally`
   block). Migrating means either exposing `_imported` for direct import
   (`from conftest import ...` works) or converting to fixtures (touches ~15 call
   sites). Low value (no leak today); deferred. When done: reduce each to
   `with render_and_import(out, "<pkg>_cli"), on_sys_path(FIXTURE): yield`.
   `test_cli_prisma_access_e2e.py:86,119` are the same shape.
3. **`HELP_ENV` reuse at `test_cli_emitted.py:1157`** (inline `{**os.environ, ...}`).
4. **Per-file fakesdk path constants** (`FIXTURE`/`FAKESDK` in ~15 files): all
   byte-identical one-liners; replacing with `from conftest import FAKESDK_FIXTURE`
   is churn-heavy and low-value. Sweep opportunistically.

---

## Self-Review

**Every rec maps to a task:**
- Rec 2 → **Task 1** (hook + pure helper + 4-case unit test; reuses `_stale_sdk_reason`).
- Rec 3 → **Task 6** (a: `isolated_home` fixture; b: `test_cli_emitted_cache.py`
  reference migration) + **Task 7** (c: `cache_real`/`cache_live` seam routing).
- Rec 4 → **Task 8** (a: conftest SSoT for path+config, delete dups) + **Task 9**
  (b: `_imported` migration of the five `test_cli_emitted.py` purge loops).
- Rec 5 → **Task 2** (parametrize matrices) + **Task 3** (weak/vacuous asserts) +
  **Task 4** (Q4 behavioral panel test) + **Task 5** (`HELP_ENV` hoist).

**No assertion weakened — audited per task:**
- Task 2: assertions identical; 1 function → 4 (show) / 2 (delete) independent cases —
  strictly better isolation, same checks.
- Task 3: `or`-assert → single strict substring (stronger); vacuous `if entries` →
  `assert entries` (stronger) or honest `pytest.skip` (removes a fake pass).
- Task 4: source-regex → behavioral panel-section membership that **subsumes** all
  four source facts (`--id` not panelled proven behaviorally) — equal-or-stronger.
- Task 5: byte-identical dict moved; no output assertion touched.
- Tasks 6, 7, 8, 9: pure isolation/dedup/mechanism swaps; verification is
  before/after identical pass counts; no assertion text edited.

**Spots where a "fix" could reduce coverage (guarded):**
- **Task 4 (Q4)** is the real risk: naively deleting the source test WOULD drop the
  "`--id` not panelled" and "`--output` in Common" coverage. Guard: the behavioral
  twin is strengthened to prove both BEFORE the source test is deleted; if any fact
  can't be shown behaviorally, keep that single source assert. Flagged below.
- **Task 3 history precondition:** if the run genuinely records no history on the
  recorder-api path, `assert entries` would newly FAIL — the plan's verify-first step
  catches this and falls back to an honest `pytest.skip`, never a vacuous pass.
- **Task 6 `isolated_home`:** its cache-clear is mostly defensive given
  `render_and_import` purges; it removes no load-bearing in-body `cache_clear()`.
  Net coverage unchanged; it only centralizes HOME + adds teardown hygiene.

**Conflict with "no weakened assertions" to adjudicate (controller):**
- **Rec 5 / Q4:** the review says "drop the brittle source-string assert in favor of
  the behavioral one." Taken literally, dropping `test_show_flags_grouped_into_panels`
  *loses* coverage of "`--id` is not panelled" and "`--output` joins Common" — the
  `--help` twin only proves panel *existence*. **Resolution in this plan:** do NOT
  drop-and-lose; instead STRENGTHEN the behavioral twin (panel-section membership) to
  subsume all four facts, then delete the source test — net strictly ≥ prior coverage.
  This is the one place the review's phrasing and the "no weakened assertions"
  constraint pull apart; the plan resolves in favor of the constraint. No other
  rec conflicts.

**Ring-3 verification gap (not a conflict, a caveat):** Tasks 2, 3, and the real-spec
part of Task 5 touch `real_sdk` tests that the offline gate SKIPS. The gate cannot
prove them; the plan requires an explicit `PHANTASOS_ALLOW_STALE_SDK=1` / `nox -s smoke`
run with captured output for those tasks.

## Review revisions (python-pro, folded in 2026-07-06)

- **[Fix] Rec-2 drift guard was illusory** → the staleness reason now has ONE source,
  a pure `_stale_reason_text(built, head)` that `_stale_sdk_reason`, the banner hook,
  and BOTH unit tests consume. `test_banner_fires_on_staleness_skip` feeds that real
  builder (not a copied literal), and the drift test asserts the sentinel is a
  substring of the builder's output — so a reword can't silently kill the banner.
- **[Fix] Task 4's "imports become unused" note was wrong** → `FIXTURE`/
  `_FAKESDK_CLI_CONFIG` stay used by `test_cli_emitted.py:143` + the `:724-726` lint
  test; the note is corrected to "keep the imports; Task 8 re-points them at conftest."
- **[Fix] Tasks 2 & 3 hard gate** → a prominent ⚠ block requires the captured
  `PHANTASOS_ALLOW_STALE_SDK=1` ring-3 run as commit evidence (offline gate skips them).
- **[Nit] Q4 twin** adds `assert "--output" in _panel_section(out, "Common")` so fact
  #4 is self-contained; the `models=None` path nuance is stated (accepted, low-risk).
- **[Nit] Task 3(a)** replaces ONLY the `:437` or-assert (the `:436` `GET` line stays,
  not duplicated); **3(b)** prefers `assert "http_uri" not in entry` when verify-first
  confirms the documented absence.
- **[Approved, no change]** `from conftest import` is robust here (verified: `prepend`
  import-mode, `pythonpath=["."]`, a single conftest, no `tests/__init__.py`); the Q4
  delete-after-strengthen is sound; `isolated_home` explicit-not-autouse and `HELP_ENV`
  constant-not-autouse are the correct calls (autouse would break the color-positive
  tests). Task 4 ↔ Task 9 both edit `test_show_help_renders_panels` — do as one edit.
