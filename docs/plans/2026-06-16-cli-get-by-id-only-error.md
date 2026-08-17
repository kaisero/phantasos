# Generated-CLI "no list operation" error Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a generated CLI's `show <object>` is backed *only* by a get-by-id operation (no list endpoint exists), emit a clear, house-style diagnostic — `'show <object>' has no list operation` + a `--id` hint — instead of the generic, misleading `no operation for '…' matches the given arguments`.

**Architecture:** A build-time fact (`Command.get_by_id_only`) is computed once in `classify.build_cli_ir`, serialized into the IR (and copied verbatim into the emitted `spec.py`), and read by the emitted `runtime._pick_binding` to choose the tailored message. The classifier stays the single source of structural truth; the runtime stays dumb (reads a flag, formats a message). Scope is deliberately narrow: only the `show` + no-list + by-id case is special-cased; every other no-match case keeps the existing generic fallback.

**Tech Stack:** Python 3.12+, pydantic (frozen IR models), Jinja2 (emitted CLI templates), Typer + Rich (emitted CLI), pytest, nox, ruff, mypy.

---

## Background / why

`phantasos cli discover prisma-browser` shows that `access-and-data-rule` (and `-section`) only expose a get-by-id read — the API has **no** `List…Rules` endpoint; rules are enumerated through `show access-and-data-policy` (the policy doc embeds them). The classifier correctly wires `show:access-and-data-rule` to `get_access_and_data_rule_by_id`, which requires `--id`. Running `show access-and-data-rule` with no `--id` therefore matches no binding and the runtime prints the generic `no operation for 'show:access-and-data-rule' matches the given arguments` — which reads like a wiring bug. This plan replaces that with a precise message.

Decisions locked in the design grill:
- **Runtime diagnostic** via the existing `_diag` pipeline (not a build-time required `--id`).
- **Narrow scope** — only `show` + no-list + by-id; generic fallback untouched for everything else.
- **Build-time IR flag** named **`get_by_id_only`** (prescriptive), computed in `build_cli_ir`.
- **Generic hint** (no smart sibling-command suggestion).
- **Both test layers** — a fast classify unit test + an emitted behavioral test, written first (TDD).

The fixture already contains the exact shape: `tests/fixtures/fakesdk` has a `thing` resource with only `get_thing(thing_id)` + `delete_thing(thing_id)` — a `show:thing` with one get-by-id binding and no list. No fixture changes needed.

## File Structure

- **Modify** `src/phantasos/generator/cli/ir.py` — add `get_by_id_only: bool = False` to the `Command` model. (`spec.py` is copied verbatim from this file at render time, so the field propagates to emitted CLIs automatically.)
- **Modify** `src/phantasos/generator/cli/classify.py` — compute `get_by_id_only` for each command in `build_cli_ir`.
- **Modify** `src/phantasos/generator/cli/templates/_generated/runtime.py.jinja` — in `_pick_binding`, branch on `cmd.get_by_id_only` when no binding matches.
- **Modify** `tests/test_cli_classify.py` — unit test pinning the flag.
- **Modify** `tests/test_cli_emitted.py` — behavioral test pinning the user-facing error.
- **Modify** `CHANGELOG.md` — a `### Fixed` bullet under `## [Unreleased]`.
- **Modify** `.agents/context/cli-generator.md` — narrative + gotcha note for the new flag.

---

## Task 0: Branch off develop

**Files:** none (git only)

- [ ] **Step 1: Create the working branch**

We are on `develop`. Feature/bugfix work must not be committed to `develop` directly. This is a user-facing behavior change → bugfix branch, PR back into `develop` (squash), recorded under `## [Unreleased]`, **no** version bump.

Run:
```bash
git checkout develop
git checkout -b bugfix/cli-show-id-only-error
git branch --show-current
```
Expected: `bugfix/cli-show-id-only-error`

---

## Task 1: Build-time `get_by_id_only` flag (IR + classifier)

**Files:**
- Modify: `src/phantasos/generator/cli/ir.py:118` (the `Command` model)
- Modify: `src/phantasos/generator/cli/classify.py:404` (end of the classification loop in `build_cli_ir`)
- Test: `tests/test_cli_classify.py`

- [ ] **Step 1: Write the failing classify unit test**

Add this new test function to `tests/test_cli_classify.py` (it reuses the same imports already at the top of the file: `build_cli_ir`, `introspect`, `CliConfig`, and `FIXTURE`):

```python
def test_get_by_id_only_flag() -> None:
    """`thing` exposes only get_thing(thing_id) (no list) -> get_by_id_only;
    `widget` has list_widgets -> not id-only."""
    inv = introspect("fakesdk", FIXTURE)
    ir, _ = build_cli_ir(inv, CliConfig())
    by_key = {c.key: c for c in ir.commands}
    assert by_key["show:thing"].get_by_id_only is True
    assert by_key["show:widget"].get_by_id_only is False
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-gate-venv-1cfe88f2b77a uv run pytest tests/test_cli_classify.py::test_get_by_id_only_flag -q`
Expected: FAIL — `AttributeError: 'Command' object has no attribute 'get_by_id_only'` (the field does not exist yet).

- [ ] **Step 3: Add the field to the `Command` model**

In `src/phantasos/generator/cli/ir.py`, inside `class Command(BaseModel)`, insert the new field immediately after `paginated: bool = False` (line 118):

```python
    paginated: bool = False
    # True ONLY for a `show` command whose every binding is the SAME single
    # get-by-id operation and there is NO list binding — i.e. the object can only
    # be fetched one-at-a-time by id (the API exposes no list endpoint). Drives the
    # runtime "has no list operation" diagnostic in _pick_binding.
    get_by_id_only: bool = False
```

- [ ] **Step 4: Run the test to verify it still fails (now on the assertion)**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-gate-venv-1cfe88f2b77a uv run pytest tests/test_cli_classify.py::test_get_by_id_only_flag -q`
Expected: FAIL — `assert False is True` for `show:thing` (the field defaults to `False`; nothing computes it yet).

- [ ] **Step 5: Compute the flag in `build_cli_ir`**

In `src/phantasos/generator/cli/classify.py`, in `build_cli_ir`, add this block immediately **after** the main classification loop (`for op in inv.operations:` … ending at line 404) and **before** the `# ---- Table columns.` comment (line 406):

```python
    # ---- get-by-id-only show commands.
    # A `show` with a single get-by-id binding and NO list operation can only
    # fetch one object by id; flag it so the runtime emits a precise "no list
    # operation" diagnostic instead of the generic no-match message. The strict
    # `requires == [id]` check keeps the flag (and message) accurate: a show whose
    # get also needs a discriminator (e.g. by_type_and_id) is NOT flagged.
    for cmd in groups.values():
        id_flag = next((f for f in cmd.path_params if f.kind == "id"), None)
        cmd.get_by_id_only = (
            cmd.verb == "show"
            and id_flag is not None
            and not any(b.sub_verb == "list" for b in cmd.bindings)
            and all(b.requires == [id_flag.param] for b in cmd.bindings)
        )
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-gate-venv-1cfe88f2b77a uv run pytest tests/test_cli_classify.py::test_get_by_id_only_flag -q`
Expected: PASS.

- [ ] **Step 7: Lint/type-check the changed source**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-gate-venv-1cfe88f2b77a uv run nox -s gate`
Expected: PASS (ruff check, ruff format --check, mypy, full pytest). If `ruff format --check` flags the new lines, run `uv run ruff format src/phantasos/generator/cli/ir.py src/phantasos/generator/cli/classify.py tests/test_cli_classify.py` and re-run.

- [ ] **Step 8: Commit**

```bash
git add src/phantasos/generator/cli/ir.py src/phantasos/generator/cli/classify.py tests/test_cli_classify.py
git commit -m "feat(cli): flag get-by-id-only show commands in the IR"
```

---

## Task 2: Runtime diagnostic (`_pick_binding`)

**Files:**
- Modify: `src/phantasos/generator/cli/templates/_generated/runtime.py.jinja:233-239` (`_pick_binding`)
- Test: `tests/test_cli_emitted.py`

> Depends on Task 1: the emitted `spec.py` (copied from `ir.py`) and `ir.json` must already carry `get_by_id_only` for the runtime to read it.

- [ ] **Step 1: Write the failing behavioral test**

Add this test to `tests/test_cli_emitted.py` (it uses the existing `emitted` fixture and the already-imported `importlib` / `pytest`):

```python
def test_show_id_only_reports_no_list_operation(
    emitted: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`show thing` (backed only by get_thing-by-id, no list) reports a clear
    'no list operation' error with an --id hint, not the generic no-match.
    Fails before any client is constructed, so no fake facade is needed."""
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    with pytest.raises(SystemExit) as exc:
        rt.run(
            "show:thing",
            path={},
            body={},
            query={},
            output="json",
            paginate_all=False,
            dry_run=False,
            verbose=False,
        )
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "has no list operation" in err
    assert "--id" in err


def test_show_id_only_with_id_still_dispatches_get(
    emitted: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Positive control: the get-by-id path is unaffected — `show thing --id t1`
    still dispatches get_thing(thing_id="t1"). (No existing test covered this.)"""
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    calls: list[Any] = []
    facade, fake_cls = _fake_client(calls)
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: fake_cls()))
    rt.run(
        "show:thing",
        path={"thing_id": "t1"},
        body={},
        query={},
        output="json",
        paginate_all=False,
        dry_run=False,
        verbose=False,
    )
    assert calls and calls[0][0] == "get_thing"
    assert calls[0][1].get("thing_id") == "t1"
```

> The positive-control test reuses the existing `_fake_client` helper + `from_env`
> monkeypatch pattern (see `test_runtime_create_vs_patch`). It dispatches a real
> binding, so it DOES need the fake facade — unlike the error test, which fails at
> `_pick_binding` before any client is built.

- [ ] **Step 2: Run the tests to verify the error test fails (and the positive control passes)**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-gate-venv-1cfe88f2b77a uv run pytest "tests/test_cli_emitted.py::test_show_id_only_reports_no_list_operation" "tests/test_cli_emitted.py::test_show_id_only_with_id_still_dispatches_get" -q`
Expected: the error test FAILS — exit code is `2` (matches) but stderr still contains the generic `no operation for 'show:thing' matches the given arguments`, so `assert "has no list operation" in err` fails. The positive-control test PASSES already (the get-by-id happy path is structurally unchanged by this work).

- [ ] **Step 3: Add the tailored branch in `_pick_binding`**

In `src/phantasos/generator/cli/templates/_generated/runtime.py.jinja`, replace the body of `_pick_binding` (lines 233-239):

```python
def _pick_binding(cmd: Command, present: set[str]) -> MethodBinding:
    candidates = [b for b in cmd.bindings if set(b.requires) <= present]
    if not candidates:
        _diag.fail(f"no operation for '{cmd.key}' matches the given arguments", code=2)
    best_len = max(len(b.requires) for b in candidates)
    top = [b for b in candidates if len(b.requires) == best_len]
    return min(top, key=lambda b: (_SUBVERB_PRIORITY.get(b.sub_verb, 99), b.sdk_method))
```

with:

```python
def _pick_binding(cmd: Command, present: set[str]) -> MethodBinding:
    candidates = [b for b in cmd.bindings if set(b.requires) <= present]
    if not candidates:
        if cmd.get_by_id_only:
            # A `show` backed only by get-by-id (no list endpoint exists).
            # Reaching here means --id was omitted; say so precisely instead of
            # the generic no-match message.
            _diag.fail(
                f"'{cmd.verb} {cmd.object}' has no list operation",
                code=2,
                hint=(
                    f"fetch a single {cmd.object} by id, "
                    f"e.g. '{cmd.verb} {cmd.object} --id <id>'"
                ),
            )
        _diag.fail(f"no operation for '{cmd.key}' matches the given arguments", code=2)
    best_len = max(len(b.requires) for b in candidates)
    top = [b for b in candidates if len(b.requires) == best_len]
    return min(top, key=lambda b: (_SUBVERB_PRIORITY.get(b.sub_verb, 99), b.sdk_method))
```

(`_diag.fail` is `NoReturn`, so the generic fallback runs only when `get_by_id_only` is false — and `best_len = max(...)` stays unreachable when `candidates` is empty, exactly as before.)

- [ ] **Step 4: Run both tests to verify they pass**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-gate-venv-1cfe88f2b77a uv run pytest "tests/test_cli_emitted.py::test_show_id_only_reports_no_list_operation" "tests/test_cli_emitted.py::test_show_id_only_with_id_still_dispatches_get" -q`
Expected: PASS (both).

- [ ] **Step 5: Run the broader CLI test set to confirm no regression**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-gate-venv-1cfe88f2b77a uv run pytest tests/test_cli_emitted.py tests/test_cli_render.py -q`
Expected: PASS (the generic no-match path is unchanged; render still emits valid, importable runtime).

- [ ] **Step 6: Commit**

```bash
git add src/phantasos/generator/cli/templates/_generated/runtime.py.jinja tests/test_cli_emitted.py
git commit -m "feat(cli): clear 'no list operation' error for get-by-id-only show commands"
```

---

## Task 3: Docs — CHANGELOG + deep-dive

**Files:**
- Modify: `CHANGELOG.md` (the `### Fixed` block under `## [Unreleased]`)
- Modify: `.agents/context/cli-generator.md`

- [ ] **Step 1: Add the CHANGELOG entry**

In `CHANGELOG.md`, under `## [Unreleased]` → `### Fixed`, append this bullet (after the existing credential-pre-flight bullet):

```markdown
- Generated CLIs now report a clear error when a `show <object>` is backed only by a get-by-id operation and the API exposes no list endpoint (e.g. `show access-and-data-rule`, `show access-and-data-section`): instead of the generic `no operation for '…' matches the given arguments`, the CLI prints `'show <object>' has no list operation` with a hint to fetch a single object by `--id` (exit code `2`). Detected at build time via a new `Command.get_by_id_only` IR flag.
```

- [ ] **Step 2: Update the cli-generator deep-dive narrative**

In `.agents/context/cli-generator.md`:

In the **Classify** bullet (the numbered list under "How it works", item 2), append a sentence:

```markdown
   It also flags `Command.get_by_id_only` — a `show` whose only binding is a single
   get-by-id (no list endpoint) — so the runtime can emit a precise "no list
   operation" error instead of the generic no-match message.
```

And under **Gotchas / invariants**, add a bullet:

```markdown
- **`get_by_id_only`** marks a `show` command backed solely by a get-by-id
  operation (no list binding; the get requires exactly the id). `runtime._pick_binding`
  uses it to print `'show <object>' has no list operation` + an `--id` hint when no
  binding matches, rather than the generic no-match diagnostic. Computed strictly
  (`requires == [id]`), so a `show` whose get also needs a discriminator is not flagged.
```

- [ ] **Step 3: Refresh the generated context blocks and verify**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-gate-venv-1cfe88f2b77a NOX_ENVDIR=/tmp/phantasos-nox uv run nox -s context`
Then verify the check passes: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-gate-venv-1cfe88f2b77a NOX_ENVDIR=/tmp/phantasos-nox uv run nox -s context -- --check`
Expected: PASS. (Adding a model *field* doesn't change the generated module-map/API blocks, which list classes and functions — so this should be a no-op refresh, but run it to satisfy the deep-dive update policy.)

- [ ] **Step 4: Commit**

```bash
git add CHANGELOG.md .agents/context/cli-generator.md
git commit -m "docs(cli): note get_by_id_only error in CHANGELOG + cli-generator deep-dive"
```

---

## Task 4: Full verification

**Files:** none

- [ ] **Step 1: Run the offline gate (the Stop-hook gate)**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-gate-venv-1cfe88f2b77a NOX_ENVDIR=/tmp/phantasos-nox uv run nox -s gate`
Expected: PASS — `ruff check`, `ruff format --check`, `mypy`, and the full `pytest -q` suite (including the two new tests) all green.

- [ ] **Step 2: Run the live CRUD gate (skips without credentials)**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-gate-venv-1cfe88f2b77a NOX_ENVDIR=/tmp/phantasos-nox uv run nox -s live`
Expected: PASS or SKIP — this change touches only CLI error wiring (no SDK/CRUD behavior), so live adds no new coverage here; it must not regress.

- [ ] **Step 3: (Optional) Real-CLI sanity check against the built prisma-browser CLI**

If the prisma-browser SDK + CLI are rebuilt from this branch, confirm the real message:
```bash
prisma-browser-cli show access-and-data-rule --output table   # expect: 'show access-and-data-rule' has no list operation
prisma-browser-cli show access-and-data-policy --output table  # expect: the rules+sections listing (unchanged)
```

---

## Self-review notes

- **Spec coverage:** runtime diagnostic (Task 2), narrow scope (strict `requires == [id]` predicate; generic fallback retained — Task 1/2), build-time `get_by_id_only` flag (Task 1), generic hint (Task 2), both test layers (Tasks 1 & 2), plus a positive-control test for the get-by-id happy path (Task 2 — added after review found it was NOT already covered: no existing test invokes `rt.run("show:thing", …)`). All grill decisions covered.
- **Review evidence (probed on the real fixture before coding):** the predicate yields `True` for `show:thing` (`requires=[['thing_id']]`, id_param `'thing_id'`) and `False` for `show:widget`/`show:gizmo` (both carry a `list` binding); `build_cli_ir(inv, CliConfig())` builds with no error; `_pick_binding` (`runtime.py.jinja:452`) runs before the client is constructed (`:499`), and `_diag.fail` is `NoReturn` (`diagnostics.py.jinja:109`); no existing test pins the old generic message.
- **Type consistency:** field name `get_by_id_only` is identical in `ir.py`, `classify.py`, `runtime.py.jinja`, and both tests. `_diag.fail(..., hint=…)` matches the existing `diagnostics.emit` signature (`expected`/`example`/`got`/`hint`). `rt.run(key, *, path, body, query, output, paginate_all, dry_run, verbose)` matches the existing emitted-runtime signature used elsewhere in `test_cli_emitted.py`.
- **No placeholders:** every code/command step is concrete.
- **Env note:** the `UV_PROJECT_ENVIRONMENT` / `NOX_ENVDIR` prefixes keep uv/nox venvs off the sshfs `.venv` and on the larger root fs per `CLAUDE.md`; the gate-venv hash path matches the Stop hook's.
