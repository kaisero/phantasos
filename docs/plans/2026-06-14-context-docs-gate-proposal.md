# Context-docs freshness gate — human-apply proposal

The agent-context-docs work (`feature/agents-context-docs`, PR #21) builds the
`.agents/context/` set. Its freshness design has three mechanisms; two are already
done on the branch, one needs a **human-applied change to frozen `.claude/**`**
(the freeze hook denies agent writes there, and the Stop-gate blocks on a dirty
protected path — by design). This document is that change, ready to apply.

## Already enforced on the branch (no action needed)

1. **CLAUDE.md instruction** — the "Agent context docs" section tells agents to
   read the relevant deep-dive before working a subsystem and run `nox -s context`
   after. (Committed.)
2. **Generated blocks can't rot** — `tests/test_context_docs_current.py` asserts
   `context_docs.main(["--check"]) == 0`, so a code change that shifts a doc's
   module-map/API without `nox -s context` **fails the offline gate** already.
   No `.claude/**` change was required for this. (Committed.)

## Needs human application — the narrative co-change gate

This is the only piece touching frozen paths: warn (or block) when a documented
subsystem's **code** changes but its **deep-dive** is not touched in the same
change. Apply via a CODEOWNERS-reviewed PR (or temporarily set
`fast_gate_enabled = false` / lift the freeze, apply, restore).

### 1. `.claude/harness.toml` — add the mapping + toggle

```toml
# Narrative freshness gate for .agents/context/ (see the agent-context-docs spec).
# "warn" = print a reminder on Stop; "block" = also block the stop; "off" = disable.
context_docs_gate = "warn"

# code glob -> owning .agents/context/ doc. Most-specific globs FIRST (the hook
# uses the first match). Generated-block freshness is handled by a test, not here;
# this only nudges the hand-written narrative to keep pace with code.
[context_docs_map]
"src/phantasos/generator/sdk/components/**" = "components.md"
"src/phantasos/generator/sdk/**" = "sdk-generator.md"
"src/phantasos/generator/cli/**" = "cli-generator.md"
"src/phantasos/scaffold.py" = "scaffold.md"
"src/phantasos/scaffold/**" = "scaffold.md"
"src/phantasos/productconfig.py" = "product-config.md"
"src/phantasos/config.py" = "components.md"
"src/phantasos/cli.py" = "phantasos-cli.md"
".claude/hooks/**" = "harness-and-testing.md"
"noxfile.py" = "harness-and-testing.md"
".github/workflows/release.yml" = "release-workflow.md"
```

### 2. `.claude/hooks/fast_gate.py` — add the check

Add this helper (it reuses the existing `_git_lines`):

```python
def _stale_context_docs(root: Path, mapping: dict[str, str]) -> list[str]:
    """Code changed without its owning .agents/context/ doc being touched too."""
    changed = set(_git_lines(root, "diff", "--name-only", "HEAD")) | set(
        _git_lines(root, "ls-files", "--others", "--exclude-standard")
    )
    # most-specific globs first (longest pattern wins)
    patterns = sorted(mapping.items(), key=lambda kv: len(kv[0]), reverse=True)
    needed: set[str] = set()
    for f in changed:
        for glob, doc in patterns:
            if fnmatch.fnmatch(f, glob):
                needed.add(doc)
                break
    touched = {Path(f).name for f in changed if f.startswith(".agents/context/")}
    return sorted(d for d in needed if d not in touched)
```

Then inside `main()`, after the offline-gate block computes `failures` (just
before `if not failures:`), add:

```python
        gate_mode = cfg.get("context_docs_gate", "off")
        if gate_mode in ("warn", "block"):
            stale_docs = _stale_context_docs(root, cfg.get("context_docs_map", {}))
            if stale_docs:
                msg = (
                    "context docs may be stale — code changed without its "
                    ".agents/context/ deep-dive: " + ", ".join(stale_docs)
                    + " (update the narrative; run `nox -s context` for blocks)."
                )
                if gate_mode == "block":
                    failures.append(msg)
                else:
                    print(f"WARNING: {msg}", file=sys.stderr)
```

`"warn"` is the recommended default: the deep-research validation found agent-doc
*benefit* unproven and excess context harmful, so a hard block on narrative is
not justified yet — nudge, don't wedge. Escalate to `"block"` later if drift
proves a problem. The loop guard already protects against a wedged session.

### 3. Add a hook unit test (in the offline suite, not frozen)

`tests/test_harness_hooks.py` is frozen-adjacent (it's under `tests/`, not
`.claude/`, so it's editable) — add a `_stale_context_docs` case: a fake repo
where a mapped code file is changed without its doc → returns that doc; with the
doc also changed → returns empty.

## Separate finding for human review — fast_gate loop-guard state (a real bug)

While building these docs, the harness's own `tests/test_harness_hooks.py::TestFastGate`
proved **flaky in long-lived environments**. Root cause (in frozen
`.claude/hooks/fast_gate.py`): the loop-guard counter is stored at
`/tmp/phantasos-fast-gate-<sha256(root)[:12]>.json`, **one shared file per repo
path across all runs and sessions**. Accumulated `blocks` from prior real gate
runs (and other sessions) leak into the tests, eventually tripping the
allow-with-warning path so a block-expecting test sees an empty stdout and fails.
`rm -f /tmp/phantasos-fast-gate-*.json` makes it green again.

Fresh CI is unaffected (clean `/tmp` per run), so PR #21's CI should be green —
but the state-file keying is brittle. Suggested fix (human, frozen path): key the
state file by `session_id` too (or store it under a per-run dir), and have the
tests point `PHANTASOS_*` at a tmp path so they never touch the shared file.

## Apply order

1. Land PR #21 (the docs + the freshness test) — its CI is independent of this.
2. In a CODEOWNERS-reviewed PR touching `.claude/**`: apply §1 + §2 (+ §3 test),
   and optionally the loop-guard fix.
