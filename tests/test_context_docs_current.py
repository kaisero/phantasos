"""Freshness gate: the .agents/context/ generated blocks must match the code.

This enforces the agent-context-docs design's mechanism (c) without any
`.claude/**` change: if a documented subsystem's code changes the module map or
public API but the doc's GENERATED blocks are not regenerated, this test fails in
the offline gate. Fix with ``uv run nox -s context`` then re-run.
See docs/specs/2026-06-14-agents-context-docs-design.md.
"""

from __future__ import annotations

from tools import context_docs


def test_context_docs_generated_blocks_are_current() -> None:
    assert context_docs.main(["--check"]) == 0, "Stale .agents/context/ generated blocks — run `uv run nox -s context`."
