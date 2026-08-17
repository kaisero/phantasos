"""Run the A/B: each task answered by `claude -p`, WITH vs WITHOUT the context doc.

WITHOUT temporarily renames .agents/context/sdk-generator.md aside so the agent
must derive from code. Captures num_turns + token usage from --output-format json.
Run from the repo root. Requires `claude` on PATH and a clean working tree.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import cast

REPO = Path(__file__).resolve().parents[2]
DOC = REPO / ".agents" / "context" / "sdk-generator.md"
TASKS = [
    "In which function and file does `phantasos sdk build` decide whether to run "
    "the smoke import-check, and what flag disables it?",
    "List, in order, the pipeline stages build() runs from spec to emitted SDK, naming the module for each.",
    "Where are OpenAPI Generator's own setup.py/requirements/tox/CI suppressed, and by what mechanism?",
]


def ask(prompt: str) -> dict[str, object]:
    out = subprocess.run(
        ["claude", "-p", prompt, "--output-format", "json"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    data: dict[str, object] = json.loads(out.stdout)
    raw_usage = data.get("usage") or {}
    usage: dict[str, object] = cast("dict[str, object]", raw_usage)
    return {
        "turns": data.get("num_turns"),
        "out_tokens": usage.get("output_tokens"),
        "in_tokens": usage.get("input_tokens"),
        "answer": data.get("result", ""),
    }


def run_condition(label: str) -> list[dict[str, object]]:
    return [{"task": i + 1, "label": label, **ask(t)} for i, t in enumerate(TASKS)]


def main() -> int:
    if shutil.which("claude") is None:
        print("SKIP: `claude` not on PATH — run this in an environment with the CLI.")
        return 2
    with_doc = run_condition("with")
    moved = DOC.with_suffix(".md.hidden")
    DOC.rename(moved)
    try:
        without_doc = run_condition("without")
    finally:
        moved.rename(DOC)
    print(json.dumps({"with": with_doc, "without": without_doc}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
