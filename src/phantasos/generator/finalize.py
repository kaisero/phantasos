"""Post-generation finalize: static-analysis cleanup, lockfile, and CI gate.

Runs LAST — after the scaffold has written the project's ``pyproject.toml`` (so the
project's own ruff/mypy config, line-length, and per-file-ignores apply) — and is
shared by both the SDK and CLI build paths. It turns raw generated code into a
project that passes its own CI:

1. ``ruff check --fix`` + ``ruff format`` over the whole tree (clears the autofixable
   bulk deterministically and formats to the project's line-length).
2. ``uv lock`` so ``uv.lock`` ships with the project (CI runs ``uv lock --check``).
3. (gate, on by default) ``uv run nox -s lint type_check`` — the exact checks CI runs.
   Raises :class:`FinalizeError` on failure so a project that can't pass its own CI is
   never emitted silently. Pass ``verify=False`` (``--no-verify``) to skip the gate.

Missing tooling degrades gracefully: if ``ruff``/``uv`` aren't on PATH (e.g. a
pip-only phantasos install) the corresponding step is skipped with a visible note
rather than hard-failing the build.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


class FinalizeError(RuntimeError):
    """The post-generation CI gate (ruff/mypy via nox) failed."""


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=False)


def ruff_pin() -> str:
    """The pip requirement pinning the generated project to *our* ruff.

    The finalize pass below formats the tree with whichever ``ruff`` is on PATH,
    while the generated project's own ``nox -s lint`` re-checks that formatting.
    If the two resolve different ruff versions the project can never pass its own
    gate — a formatting rule added between them (e.g. 0.16's markdown code-block
    formatting) reformats a file our pass left alone. Pinning the emitted noxfile
    to the exact version we format with keeps them in lockstep. Falls back to the
    unpinned name when ruff isn't installed (the format step is skipped anyway).
    """
    ruff = shutil.which("ruff")
    if not ruff:
        return "ruff"
    out = subprocess.run([ruff, "--version"], capture_output=True, text=True, check=False)
    if out.returncode != 0:
        return "ruff"
    parts = out.stdout.split()  # "ruff 0.15.16"
    return f"ruff=={parts[1]}" if len(parts) >= 2 else "ruff"


def finalize(project_dir: Path, *, verify: bool = True) -> dict[str, str]:
    """Clean, lock, and (optionally) gate a freshly generated project.

    Returns a small status map (per step) for the build summary. Raises
    :class:`FinalizeError` only when the gate runs and fails.
    """
    # Escape hatch for phantasos's own test suite, which builds many stub/fake
    # projects where a real ruff/uv/nox pass is meaningless (and slow).
    if os.environ.get("PHANTASOS_SKIP_FINALIZE"):
        return {"skipped": "PHANTASOS_SKIP_FINALIZE"}
    # Nothing to finalize without a scaffolded project (e.g. tests that stub out
    # the scaffold step and write no pyproject.toml).
    if not (project_dir / "pyproject.toml").is_file():
        return {"skipped": "no pyproject.toml"}

    result: dict[str, str] = {}

    ruff = shutil.which("ruff")
    if ruff:
        # Use the PROJECT config (no --isolated): line-length, select, and the
        # generated-code per-file-ignores must apply.
        _run([ruff, "check", "--fix", "."], project_dir)
        _run([ruff, "format", "."], project_dir)
        result["ruff"] = "ok"
    else:
        result["ruff"] = "skipped (ruff not found)"

    uv = shutil.which("uv")
    if not uv:
        result["uv_lock"] = "skipped (uv not found)"
        result["verify"] = "skipped (uv not found)"
        return result

    lock = _run([uv, "lock"], project_dir)
    if lock.returncode != 0:
        raise FinalizeError(f"`uv lock` failed:\n{lock.stdout}\n{lock.stderr}")
    result["uv_lock"] = "ok"

    if not verify:
        result["verify"] = "skipped (--no-verify)"
        return result

    gate = _run([uv, "run", "nox", "-s", "lint", "type_check"], project_dir)
    if gate.returncode != 0:
        raise FinalizeError(
            "post-generation CI gate failed (nox -s lint type_check).\n"
            "Re-run with --no-verify to emit anyway.\n\n"
            f"{gate.stdout}\n{gate.stderr}"
        )
    result["verify"] = "ok"
    return result
