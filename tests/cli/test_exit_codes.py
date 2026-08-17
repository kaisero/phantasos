"""Guard: the Errors guide's exit-code table (0/1/2) must match the runtime.

Exit codes are inline literals in the emitted runtime (there is no ExitCode enum), so
this greps ALL CLI templates (not just _generated/ — main.py/hooks.py are hand-owned
templates outside it; docs templates are excluded as they are not runtime). If a new
code is introduced, update BOTH the runtime AND docs/guides/errors.md.jinja, then this
guard.
"""

import re
from pathlib import Path

TEMPLATES = Path(__file__).parent.parent.parent / "src" / "phantasos" / "generator" / "cli" / "templates"


def test_runtime_uses_only_documented_exit_codes() -> None:
    allowed_code = {"1", "2"}
    offenders: list[str] = []
    for tmpl in TEMPLATES.rglob("*.jinja"):
        if "/docs/" in tmpl.as_posix():
            continue  # docs templates document codes; they are not runtime
        text = tmpl.read_text()
        rel = tmpl.relative_to(TEMPLATES)
        # SystemExit/typer.Exit may legitimately carry 0 (clean exit); a `code=`
        # kwarg is always a _diag.fail() failure code, so code=0 there is a bug.
        for m in re.finditer(r"SystemExit\(\s*(\d+)\s*\)", text):
            if m.group(1) not in allowed_code | {"0"}:
                offenders.append(f"{rel}: SystemExit({m.group(1)})")
        for m in re.finditer(r"typer\.Exit\(\s*(\d+)\s*\)", text):
            if m.group(1) not in allowed_code | {"0"}:
                offenders.append(f"{rel}: typer.Exit({m.group(1)})")
        for m in re.finditer(r"\bcode\s*=\s*(\d+)\b", text):
            if m.group(1) not in allowed_code:
                offenders.append(f"{rel}: code={m.group(1)}")
    assert not offenders, (
        "Undocumented exit codes found; update docs/guides/errors.md.jinja and this guard:\n  " + "\n  ".join(offenders)
    )
