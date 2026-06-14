"""Isolated end-to-end smoke for a GENERATED CLI (the generate -> install -> run gate).

Renders the fakesdk CLI (with auth), installs it into a CLEAN venv that has only
the CLI's DECLARED third-party deps, and runs its entry point + the
``environment`` commands exactly the way the console script does
(``from <pkg>.main import app; app()``).

This catches what the in-repo pytest suite cannot: that suite runs in the dev
venv (which has extra packages such as a full ``click``), so it never proves the
generated CLI works against *its own* declared dependencies. In particular
``typer>=0.12`` resolves to the slim core, which does NOT install a top-level
``click`` — so any stray ``import click`` (or other undeclared dep) in the
emitted code breaks every generated CLI at import time. Run via ``nox -s cli-smoke``.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

from phantasos.config import ScmOAuth
from phantasos.generator.cli.classify import build_cli_ir
from phantasos.generator.cli.cliconfig import CliConfig
from phantasos.generator.cli.introspect import introspect
from phantasos.generator.cli.render_cli import render_cli
from phantasos.generator.cli.scaffold_context import _CLI_DEPS

_REPO = Path(__file__).resolve().parent.parent
_FIXTURE = _REPO / "tests" / "fixtures" / "fakesdk"
_PKG = "fakesdk_cli"


def _render(out: Path) -> None:
    """Generate the fakesdk CLI WITH an auth component (so the environment
    commands are emitted) into ``out``."""
    ir = build_cli_ir(introspect("fakesdk", _FIXTURE), CliConfig())[0]
    render_cli(
        ir,
        package=_PKG,
        out_dir=out,
        env_prefix="FAKESDK",
        auth=ScmOAuth(type="scm_oauth"),
    )


def _clean_venv(venv: Path) -> Path:
    """Create a fresh venv holding ONLY the CLI's declared third-party deps.

    The SDK distribution (a CLI dep in real builds) is supplied on PYTHONPATH for
    the fixture instead. ``typer`` here resolves to the slim core WITHOUT a
    top-level ``click`` — faithfully reproducing a real user's environment."""
    subprocess.run(["uv", "venv", str(venv)], check=True, capture_output=True)
    py = venv / "bin" / "python"
    deps = [d for d in _CLI_DEPS if not d.endswith("-sdk")]
    subprocess.run(
        ["uv", "pip", "install", "--python", str(py), *deps],
        check=True,
        capture_output=True,
    )
    return py


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="cli-smoke-"))
    try:
        out = tmp / "out"
        _render(out)
        py = _clean_venv(tmp / "venv")
        home = tmp / "home"
        home.mkdir()
        env = {
            **os.environ,
            "HOME": str(home),
            "PYTHONPATH": os.pathsep.join([str(out), str(_FIXTURE.parent)]),
        }
        for var in ("CLIENT_ID", "CLIENT_SECRET", "SCOPE", "BASE_URL"):
            env.pop(var, None)  # don't let ambient auth interfere

        # the exact import chain the console script runs (main -> app -> ...).
        runner = "from fakesdk_cli.main import app; app()"

        def cli(*args: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                [str(py), "-c", runner, *args],
                capture_output=True,
                text=True,
                env=env,
                cwd=str(tmp),
            )

        # The clean venv must genuinely lack a top-level click (faithful repro).
        no_click = subprocess.run(
            [str(py), "-c", "import click"], capture_output=True, text=True
        )
        assert no_click.returncode != 0, "expected NO top-level click in the clean venv"

        # 1. The import that previously failed, plus help for the whole tree.
        r = cli("--help")
        assert r.returncode == 0, f"`--help` failed:\n{r.stderr}"
        r = cli("environment", "--help")
        assert r.returncode == 0 and "create" in r.stdout, (
            f"`environment --help`:\n{r.stdout}{r.stderr}"
        )

        # 2. create (secret via flag so no prompt), auto-activate, file is 0o600.
        r = cli(
            "environment",
            "create",
            "prod",
            "--client-id",
            "abc",
            "--scope",
            "tsg_id:1",
            "--base-url",
            "https://api.example.com",
            "--client-secret",
            "s3cr3t",
        )
        assert r.returncode == 0, f"create failed:\n{r.stderr}"
        cfg = home / ".fakesdk_cli" / "config.yml"
        # Parse + assert config content in the CLEAN venv (it has pyyaml; this
        # outer process only has phantasos + stdlib).
        verify = (
            "import sys, yaml; d = yaml.safe_load(open(sys.argv[1]));"
            " assert d['environments']['prod']['client_secret'] == 's3cr3t', d;"
            " assert d['default_environment'] == 'prod', d; print('CONFIG OK')"
        )
        chk = subprocess.run(
            [str(py), "-c", verify, str(cfg)], capture_output=True, text=True
        )
        assert chk.returncode == 0 and "CONFIG OK" in chk.stdout, chk.stderr
        mode = stat.S_IMODE(cfg.stat().st_mode)
        assert mode == 0o600, oct(mode)

        # 3. list marks active and hides values; current prints the active name.
        r = cli("environment", "list")
        assert r.returncode == 0 and "prod" in r.stdout and "s3cr3t" not in r.stdout, (
            r.stdout
        )
        r = cli("environment", "current")
        assert r.returncode == 0 and "prod" in r.stdout, r.stdout

        print(
            "cli-smoke OK: generated CLI imports + runs against its declared deps "
            "(typer slim, no top-level click)"
        )
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
