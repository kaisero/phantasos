# Agent-Context Docs — Thin Slice + A/B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the *thin slice* of the `.agents/context/` agent-facing doc set — the `index.md`, ONE subsystem deep-dive (`sdk-generator.md`), the mechanical-section generator with `--check`, and the plain-path entry pointers — then run an A/B evaluation that decides whether (and how) to scale to the remaining docs and the freshness gate.

**Architecture:** File-based markdown under `.agents/context/`, loaded on demand (plain-path references from CLAUDE.md/AGENTS.md — never `@`-imports). A Python tool (`tools/context_docs.py`) regenerates terse mechanical blocks (module map, public API signatures) into `<!-- GENERATED:* -->` markers from the live code via AST, with a `--check` mode wired to `nox -s context` so the blocks cannot rot. The freshness **gate is explicitly deferred** to the next increment (after the A/B proves the docs' worth). Minimalism is enforced (size caps); benefit is measured, not assumed.

**Tech Stack:** Python 3.11+ (stdlib `ast`/`argparse`), nox, pytest, ruff, mypy, Typer (host CLI introspection — later increment), `gh`. Spec: `docs/specs/2026-06-14-agents-context-docs-design.md`.

**Harness note:** the quality harness is live on `develop` — the **freeze hook denies writes to `.claude/**` and the oracle template**, and the **Stop hook runs `uv run nox -s gate`** every turn. Keep the tree green (the TDD steps + commits do this); never edit protected paths. On sshfs, prefix uv with `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-ctx`.

---

## File structure

| File | Responsibility |
|---|---|
| `.agents/context/index.md` | Read-first map: overarching system technical design + curated links to deep-dives (llms.txt-shaped). |
| `.agents/context/sdk-generator.md` | The single slice deep-dive: SDK build pipeline; carries the two `<!-- GENERATED:* -->` blocks. |
| `tools/context_docs.py` | Generator: renders module-map + public-API blocks from live code into doc markers; `--check` mode for the gate. |
| `tools/ab_eval/tasks.md` | The 3 fixed SDK-generator questions for the A/B. |
| `tools/ab_eval/run.py` | A/B runner: invokes `claude -p --output-format json` with/without the doc, logs turns + tokens. |
| `tools/ab_eval/RESULTS.md` | A/B results table + the scale/no-scale decision. |
| `tests/test_context_docs.py` | Tests for the generator (module_map, public_api, inject, --check). |
| `AGENTS.md` (root) | Thin cross-tool pointer → `.agents/context/index.md`. |
| `CLAUDE.md` | EDIT: add the plain-path read-before/update-after instruction. |
| `noxfile.py` | EDIT: add `context` session (`--check`). |
| `CHANGELOG.md` | EDIT: `## [Unreleased]` entry. |

**Out of this slice (next increment, post-A/B):** the other 9 deep-dives, `decisions.md`, `goals-non-goals.md`, and the harness **gate extension** (`[context_docs]` mapping + `fast_gate.py` check).

---

## Task 1: Branch + scaffolding

**Files:**
- Create: `.agents/context/` (dir)

- [ ] **Step 1: Create the feature branch off develop**

```bash
git fetch origin
git switch -c feature/agents-context-docs origin/develop
```

- [ ] **Step 2: Create the context dir with a placeholder so git tracks it**

```bash
mkdir -p .agents/context tools/ab_eval
```

- [ ] **Step 3: Commit the scaffold**

```bash
git add -A
git commit -m "chore(docs): scaffold .agents/context/ + tools/ for agent-context docs"
```

---

## Task 2: Mechanical-section generator (`tools/context_docs.py`)

**Files:**
- Create: `tools/context_docs.py`
- Test: `tests/test_context_docs.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_context_docs.py
from pathlib import Path

import pytest

from tools import context_docs as cd


def _pkg(tmp_path: Path) -> Path:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "alpha.py").write_text(
        '"""Alpha module does A.\n\nmore.\n"""\n'
        "def public_fn(x, y):\n"
        '    """Run the thing."""\n'
        "    return x\n\n"
        "def _private():\n"
        "    return 1\n"
    )
    (pkg / "beta.py").write_text(
        '"""Beta module."""\n'
        "class Widget:\n"
        '    """A widget."""\n'
        "    pass\n"
    )
    return pkg


def test_module_map_lists_modules_with_first_docline(tmp_path):
    out = cd.module_map(_pkg(tmp_path))
    assert "- `alpha.py` — Alpha module does A." in out
    assert "- `beta.py` — Beta module." in out
    assert "__init__.py" not in out


def test_public_api_extracts_public_only(tmp_path):
    out = cd.public_api(_pkg(tmp_path))
    assert "`public_fn(x, y)` — Run the thing." in out
    assert "class `Widget` — A widget." in out
    assert "_private" not in out


def test_inject_replaces_between_markers_idempotently():
    text = "head\n<!-- GENERATED:api -->\nOLD\n<!-- /GENERATED:api -->\ntail\n"
    once = cd.inject(text, "api", "NEW")
    twice = cd.inject(once, "api", "NEW")
    assert "NEW" in once and "OLD" not in once
    assert once == twice
    assert once.startswith("head") and once.rstrip().endswith("tail")


def test_inject_missing_markers_raises():
    with pytest.raises(ValueError):
        cd.inject("no markers here", "api", "x")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-ctx uv run pytest tests/test_context_docs.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.context_docs'` (and missing `tools/__init__.py`).

- [ ] **Step 3: Make `tools` a package**

```bash
touch tools/__init__.py
```

- [ ] **Step 4: Write the generator**

```python
# tools/context_docs.py
"""Generate the mechanical sections of .agents/context/ docs.

Each registered block is rendered from the live code (AST) into marker-delimited
regions of a doc, so it cannot rot. ``--check`` regenerates to a buffer and exits
1 if any doc is out of date — the freshness gate runs this. See
docs/specs/2026-06-14-agents-context-docs-design.md.
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CONTEXT = REPO / ".agents" / "context"

# (doc filename, block kind, package dir relative to repo root).
BLOCKS: list[tuple[str, str, str]] = [
    ("sdk-generator.md", "module-map", "src/phantasos/generator/sdk"),
    ("sdk-generator.md", "api", "src/phantasos/generator/sdk"),
]


def _first_doc_line(node: ast.AST) -> str:
    doc = ast.get_docstring(node) if isinstance(
        node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    ) else None
    return doc.splitlines()[0].strip() if doc else ""


def module_map(pkg_dir: Path) -> str:
    rows = []
    for path in sorted(pkg_dir.glob("*.py")):
        if path.name == "__init__.py":
            continue
        tree = ast.parse(path.read_text())
        rows.append(f"- `{path.name}` — {_first_doc_line(tree)}")
    return "\n".join(rows)


def _signature(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args = [a.arg for a in fn.args.args]
    return f"{fn.name}({', '.join(args)})"


def public_api(pkg_dir: Path) -> str:
    out: list[str] = []
    for path in sorted(pkg_dir.glob("*.py")):
        if path.name == "__init__.py":
            continue
        tree = ast.parse(path.read_text())
        items: list[str] = []
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                items.append(f"  - class `{node.name}` — {_first_doc_line(node)}")
            elif isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef)
            ) and not node.name.startswith("_"):
                items.append(f"  - `{_signature(node)}` — {_first_doc_line(node)}")
        if items:
            out.append(f"- `{path.name}`")
            out.extend(items)
    return "\n".join(out)


RENDERERS = {"module-map": module_map, "api": public_api}


def render(kind: str, pkg_dir: Path) -> str:
    return RENDERERS[kind](pkg_dir)


def inject(text: str, kind: str, content: str) -> str:
    start, end = f"<!-- GENERATED:{kind} -->", f"<!-- /GENERATED:{kind} -->"
    i, j = text.find(start), text.find(end)
    if i == -1 or j == -1:
        raise ValueError(f"markers for {kind!r} not found")
    return text[: i + len(start)] + "\n" + content + "\n" + text[j:]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="fail if any block is stale")
    ns = ap.parse_args(argv)
    stale: list[str] = []
    for doc_name, kind, pkg in BLOCKS:
        doc = CONTEXT / doc_name
        text = doc.read_text()
        updated = inject(text, kind, render(kind, REPO / pkg))
        if ns.check:
            if updated != text:
                stale.append(f"{doc_name}:{kind}")
        else:
            doc.write_text(updated)
    if ns.check and stale:
        print("stale generated blocks: " + ", ".join(stale), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-ctx uv run pytest tests/test_context_docs.py -q`
Expected: PASS (4 passed).

- [ ] **Step 6: Lint + type-check the new code**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-ctx uv run ruff check tools/ tests/test_context_docs.py && UV_PROJECT_ENVIRONMENT=/tmp/phantasos-ctx uv run mypy tools/context_docs.py`
Expected: clean. (If mypy complains about `tools` not being in scope, add `tools` to `[tool.ruff] src` / `mypy` paths in `pyproject.toml` — mirror how `transformations` is already listed in `pyproject.toml:90`.)

- [ ] **Step 7: Commit**

```bash
git add tools/__init__.py tools/context_docs.py tests/test_context_docs.py pyproject.toml
git commit -m "feat(context-docs): AST generator for module-map + public-api blocks with --check"
```

---

## Task 3: `nox -s context` session

**Files:**
- Modify: `noxfile.py` (add a session after `gate`)

- [ ] **Step 1: Add the session**

Add to `noxfile.py` (single-env, no venv — like `gate`):

```python
@nox.session(venv_backend="none")
def context(session: nox.Session) -> None:
    """Regenerate (or --check) the .agents/context/ mechanical blocks.

    `nox -s context` rewrites the GENERATED markers from live code;
    `nox -s context -- --check` fails if any block is stale (the freshness
    gate runs this). Pure stdlib, no install needed.
    """
    session.run("python", "tools/context_docs.py", *session.posargs, external=True)
```

- [ ] **Step 2: Verify check-mode runs (will fail until the doc + markers exist — that's Task 5)**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-ctx uv run nox -s context -- --check`
Expected: nonzero exit with `FileNotFoundError` / markers-not-found (because `sdk-generator.md` doesn't exist yet). This is expected; Task 5 creates the doc, after which `--check` passes.

- [ ] **Step 3: Commit**

```bash
git add noxfile.py
git commit -m "build(context-docs): add nox -s context session (generate / --check)"
```

---

## Task 4: `index.md` (authored, llms.txt-shaped)

**Files:**
- Create: `.agents/context/index.md`

**Authoring is the work here** (prose written from the code, not pre-canned). Read these before writing: `README.md`, `docs/ARCHITECTURE.md` (for the *intended* model — but VALIDATE against code, it's stale), `src/phantasos/cli.py`, `src/phantasos/generator/{sdk,cli}/__init__.py`, `src/phantasos/productconfig.py`, `noxfile.py`.

- [ ] **Step 1: Write `index.md` to this exact skeleton, filling the prose**

```markdown
# phantasos

> Generate native, self-contained Python SDKs and CLIs from OpenAPI specs. This
> is the read-first map for coding agents working in-repo: the system model and
> where each subsystem is documented. Load only the deep-dive you need.

## System technical design

<!-- Substantive, ≤ ~1 screen. Cover, validated against code:
  - the two-stage pipeline: spec → (sdk build) → SDK → (cli build) → CLI
  - the three layers: framework code (src/phantasos/) vs generated artifact
    (the emitted SDK/CLI, a pure build artifact — never hand-edit) vs product
    config (products/<name>/: openapi.yml, sdk.yml, cli.yml, overrides/, hooks.py)
  - end-to-end control/data flow (name the entry points: phantasos.cli, 
    generator.sdk.build.build, generator.cli render path)
  - the repo map (one line per top-level src/ package)
  - hard invariants (generated artifact is disposable; products/ + src/scaffold/
    are the only version-controlled customization surfaces) -->

## Subsystem deep-dives

- [sdk-generator](sdk-generator.md): the SDK build pipeline (preprocess → provision → OAG → patches → vendor → scaffold → smoke).
<!-- remaining links added in the scale increment: product-config, components,
     cli-generator, scaffold, phantasos-cli, harness-and-testing, release-workflow -->

## Cross-cutting

<!-- links added in the scale increment: decisions, goals-non-goals -->

## Rules

The binding rules (test policy, branching/release, the config-adding recipe) live
in `CLAUDE.md` at the repo root — this set explains mechanism and rationale, not rules.
```

- [ ] **Step 2: Enforce the size cap**

Run: `wc -l .agents/context/index.md`
Expected: ≤ ~120 lines. If over, cut — minimalism is a hard constraint (spec decision 13).

- [ ] **Step 3: Validate the claims against code**

For each concrete claim (entry-point names, pipeline order, layer boundaries), confirm by reading the named file/symbol. Where a claim is only confirmable by running (e.g. a live build), mark it or omit it. Evidence-before-assertions.

- [ ] **Step 4: Commit**

```bash
git add .agents/context/index.md
git commit -m "docs(context): index.md — system model + curated deep-dive links"
```

---

## Task 5: `sdk-generator.md` deep-dive (template + generated blocks)

**Files:**
- Create: `.agents/context/sdk-generator.md`

Read before writing: `src/phantasos/generator/sdk/{build,generate,preprocess,patches,render,smoke,provision}.py` and the spec `docs/specs/2026-06-09-cli-generator-design.md` + `docs/specs/2026-06-12-sdk-generator-package-and-cli-restructure-design.md` for provenance.

- [ ] **Step 1: Write the doc to this exact skeleton (markers MUST match the generator)**

```markdown
# sdk-generator

Validated against <git-sha> on 2026-06-14 · Purpose: how `phantasos sdk build` turns a product's spec into a vendored, scaffolded Python SDK.

## Purpose & responsibilities

<!-- terse: what generator/sdk owns end-to-end -->

## How it works

<!-- pipeline call chain with NAVIGATION anchors (class/function + file), no line
  numbers: build.build() orchestrates → preprocess → provision (JRE/jar) → generate
  (OAG) → patches → render (vendor components + scaffold) → smoke. Name the function
  in each module; say which file to open. Navigate, don't enumerate. -->

## Build / run pointers

- Build the example SDKs: `uv run nox -s smoke` (auto-provisions JRE; needs network).
- One product: `phantasos sdk build <name>` (`--no-smoke` to skip the import-check).
- Unit tests: `uv run nox -s gate` (offline) or `pytest tests/test_generate.py …`.

## Module map

<!-- GENERATED:module-map -->
<!-- /GENERATED:module-map -->

## Public API

<!-- GENERATED:api -->
<!-- /GENERATED:api -->

## Gotchas / invariants

<!-- e.g. OAG's setup.py/requirements/tox/CI suppressed via .openapi-generator-ignore;
  the generated SDK is never hand-edited; jar/JRE pinned under ~/.cache/phantasos -->

## See also

- Specs: `docs/specs/2026-06-12-sdk-generator-package-and-cli-restructure-design.md`
- Decisions: (added in the scale increment) `decisions.md`
- Rules: `CLAUDE.md`
```

- [ ] **Step 2: Populate the generated blocks**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-ctx uv run nox -s context`
Expected: exit 0; the two GENERATED blocks in `sdk-generator.md` now contain the module map + public API. Inspect with `git diff`.

- [ ] **Step 3: Verify `--check` is now green (the gate's signal)**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-ctx uv run nox -s context -- --check`
Expected: exit 0 (no stale blocks).

- [ ] **Step 4: Enforce the size cap**

Run: `wc -l .agents/context/sdk-generator.md`
Expected: ≤ ~400 lines incl. generated blocks. Trim narrative if over.

- [ ] **Step 5: Commit**

```bash
git add .agents/context/sdk-generator.md
git commit -m "docs(context): sdk-generator deep-dive + generated module-map/api blocks"
```

---

## Task 6: Entry pointers (`AGENTS.md` + `CLAUDE.md`)

**Files:**
- Create: `AGENTS.md`
- Modify: `CLAUDE.md` (append a section)

- [ ] **Step 1: Create the thin root `AGENTS.md`**

```markdown
# AGENTS.md

Agent-facing technical docs for phantasos live in `.agents/context/` — start at
[`.agents/context/index.md`](.agents/context/index.md), then open the relevant
subsystem deep-dive on demand. The binding rules (test policy, branching, the
config-adding recipe) are in [`CLAUDE.md`](CLAUDE.md).
```

- [ ] **Step 2: Append the read/update instruction to `CLAUDE.md`**

Add this section (plain-path reference — NOT an `@`-import, which would load at launch):

```markdown
## Agent context docs (`.agents/context/`)

Deep technical docs for this repo live in `.agents/context/` (start at
`.agents/context/index.md`). They are loaded **on demand** — do NOT `@`-import them.

- **Before** working in a subsystem, read its deep-dive (e.g. `.agents/context/sdk-generator.md`).
- **After** a change that alters a subsystem, update its deep-dive's narrative and
  run `uv run nox -s context` to refresh its generated blocks (`-- --check` must pass).
```

- [ ] **Step 3: Verify the gate stays green (CLAUDE.md is not protected; editing it is allowed)**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-ctx uv run nox -s gate`
Expected: PASS (ruff/mypy/pytest green; the new tool + tests included).

- [ ] **Step 4: Commit**

```bash
git add AGENTS.md CLAUDE.md
git commit -m "docs(context): plain-path pointers from AGENTS.md + CLAUDE.md"
```

---

## Task 7: A/B evaluation (does the doc reduce re-derivation without hurting?)

**Files:**
- Create: `tools/ab_eval/tasks.md`, `tools/ab_eval/run.py`, `tools/ab_eval/RESULTS.md`

This answers the spec's validation gate (decision 14) with data before scaling. Metric: turns + tokens to correctly answer a fixed SDK-generator question, **with** the doc available vs **without**.

- [ ] **Step 1: Write the fixed task set**

```markdown
<!-- tools/ab_eval/tasks.md -->
# A/B tasks (SDK-generator subsystem)

1. In which function and file does `phantasos sdk build` decide whether to run the smoke import-check, and what flag disables it?
2. List, in order, the pipeline stages `build()` runs from spec to emitted SDK, naming the module for each.
3. Where are OpenAPI Generator's own setup.py/requirements/tox/CI suppressed, and by what mechanism?
```

(Each has a known correct answer an evaluator can grade pass/fail.)

- [ ] **Step 2: Write the runner**

```python
# tools/ab_eval/run.py
"""Run the A/B: each task answered by `claude -p`, WITH vs WITHOUT the context doc.

WITHOUT temporarily renames .agents/context/sdk-generator.md aside so the agent
must derive from code. Captures num_turns + token usage from --output-format json.
Run from the repo root. Requires `claude` on PATH and a clean working tree.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DOC = REPO / ".agents" / "context" / "sdk-generator.md"
TASKS = [
    "In which function and file does `phantasos sdk build` decide whether to run "
    "the smoke import-check, and what flag disables it?",
    "List, in order, the pipeline stages build() runs from spec to emitted SDK, "
    "naming the module for each.",
    "Where are OpenAPI Generator's own setup.py/requirements/tox/CI suppressed, "
    "and by what mechanism?",
]


def ask(prompt: str) -> dict:
    out = subprocess.run(
        ["claude", "-p", prompt, "--output-format", "json"],
        cwd=REPO, capture_output=True, text=True, check=True,
    )
    data = json.loads(out.stdout)
    usage = data.get("usage", {})
    return {
        "turns": data.get("num_turns"),
        "out_tokens": usage.get("output_tokens"),
        "in_tokens": usage.get("input_tokens"),
        "answer": data.get("result", ""),
    }


def run_condition(label: str) -> list[dict]:
    return [{"task": i + 1, "label": label, **ask(t)} for i, t in enumerate(TASKS)]


def main() -> None:
    with_doc = run_condition("with")
    moved = DOC.with_suffix(".md.hidden")
    DOC.rename(moved)
    try:
        without_doc = run_condition("without")
    finally:
        moved.rename(DOC)
    print(json.dumps({"with": with_doc, "without": without_doc}, indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run the A/B and capture output**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-ctx uv run python tools/ab_eval/run.py > /tmp/ab_raw.json`
Expected: JSON with `with`/`without` arrays (turns + tokens per task). If `claude` isn't available in this environment, record that and run it where it is — do NOT fabricate numbers.

- [ ] **Step 4: Record results + the decision**

Write `tools/ab_eval/RESULTS.md`: a table (task · with-turns · without-turns · with-tokens · without-tokens · both-correct?) plus the verdict against this **pass criterion**:

> **Scale** if WITH-doc answers are correct and use **fewer or equal re-derivation turns** than WITHOUT, **and** total tokens do not rise (the doc's load cost is repaid). **Do not scale as-is** if WITH-doc raises tokens without cutting turns (the excess-context harm the research flagged) — then narrow the doc / drop generated blocks and re-test.

- [ ] **Step 5: Commit**

```bash
git add tools/ab_eval/
git commit -m "test(context-docs): A/B harness + results for the sdk-generator deep-dive"
```

---

## Task 8: PR to develop

- [ ] **Step 1: Add a CHANGELOG entry under `## [Unreleased]`**

```markdown
### Added

- Agent-facing context docs (`.agents/context/`) — thin slice: system index +
  sdk-generator deep-dive, with an AST generator (`nox -s context`) for the
  mechanical sections and an A/B evaluation harness.
```

- [ ] **Step 2: Final gate + check**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-ctx uv run nox -s gate && UV_PROJECT_ENVIRONMENT=/tmp/phantasos-ctx uv run nox -s context -- --check`
Expected: both exit 0.

- [ ] **Step 3: Push + open the PR (base develop, squash)**

```bash
git add CHANGELOG.md && git commit -m "docs(changelog): agent-context docs thin slice"
git push -u origin feature/agents-context-docs
gh pr create --base develop --title "Agent-context docs: thin slice + A/B (index + sdk-generator)" \
  --body "Thin slice of .agents/context/ per docs/specs/2026-06-14-agents-context-docs-design.md. Generator + A/B included; gate deferred to the next increment pending the A/B result. No version bump."
```

- [ ] **Step 4: Confirm CI green, then squash-merge**

Run: `gh pr checks --watch` then `gh pr merge --squash` (only after the A/B verdict is reviewed).

---

## Deferred to the next increment (post-A/B)

Planned separately once Task 7's verdict is in:
1. **Scale** — the remaining deep-dives (`product-config`, `components`, `cli-generator`, `scaffold`, `phantasos-cli`, `harness-and-testing`, `release-workflow`) + `decisions.md` + `goals-non-goals.md`, each under the size cap, each with its generated blocks (extend `BLOCKS` in `tools/context_docs.py`). Includes the **targeted WHY-interview** for `decisions.md`.
2. **Gate** — extend `.claude/harness.toml` with the `[context_docs]` code-glob→doc mapping and add the check to `.claude/hooks/fast_gate.py` (warn-then-escalate; `context_docs_enabled` toggle). **Note:** `.claude/**` is freeze-protected — this increment requires a human-reviewed PR touching protected paths (CODEOWNERS), not an agent edit.

---

## Self-review

- **Spec coverage:** index.md (decision 2,5,7), sdk-generator deep-dive at navigation-anchor altitude + build/run pointers (decision 8), file-based `.agents/context/` (decision 6), plain-path pointers not @-import (decision 7), terse generated blocks + `--check` (decision 10c, 13), anti-bloat size caps (decision 13), A/B measurement (decision 14), gate deferred to satisfy "gate-last" sequencing (item 2). WHY docs + remaining subsystems + gate are explicitly deferred (staged build). ✓
- **Placeholders:** doc *prose* is authored during execution (inherent to a docs task) but every authoring step ships the exact skeleton, the files to read, the required coverage, the size cap, and the validation command — no "TBD". Tool/test/runner code is complete. ✓
- **Type consistency:** `module_map`/`public_api`/`inject`/`render`/`main` names match across `tools/context_docs.py`, `tests/test_context_docs.py`, and the `nox -s context` invocation; marker strings `<!-- GENERATED:module-map -->` / `:api` match between the generator's `BLOCKS` and `sdk-generator.md`. ✓
