"""Task runner for phantasos.

One source of truth for the checks run both locally and in CI. Run everything
with ``uv run nox`` or a single session with ``uv run nox -s tests``.

Sessions use uv to provision their virtualenvs (and to install the locked
dependency groups) for fast, reproducible runs.
"""

from __future__ import annotations

import os
from pathlib import Path

import nox

nox.options.default_venv_backend = "uv"
nox.options.reuse_existing_virtualenvs = True
nox.options.sessions = [
    "lint",
    "type_check",
    "tests",
    "cli-smoke",
    "docs",
]

PYTHON_VERSIONS = ["3.11", "3.12", "3.13", "3.14"]


def _sync(session: nox.Session, *groups: str) -> None:
    """Install the project plus the given dependency groups into the session.

    ``--no-default-groups`` keeps the umbrella ``dev`` group (uv's default) out
    of the session, so each session installs only the project plus the group(s)
    it asks for. In CI (where ``$CI`` is set — GitHub Actions and most providers
    set it) we also pass ``--frozen`` so the session uses the committed
    ``uv.lock`` verbatim and fails if it is missing or stale, instead of
    silently re-resolving. Locally we omit ``--frozen`` so the first
    ``uv run nox`` works before a lock has been written.
    """
    args = ["uv", "sync", "--no-default-groups"]
    if os.environ.get("CI"):
        args.append("--frozen")
    for group in groups:
        args += ["--group", group]
    session.run_install(
        *args,
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )


@nox.session
def lint(session: nox.Session) -> None:
    """Lint and check formatting with ruff."""
    _sync(session, "lint")
    session.run("ruff", "check", ".")
    session.run("ruff", "format", "--check", ".")


@nox.session
def type_check(session: nox.Session) -> None:
    """Static type checking with mypy."""
    _sync(session, "typecheck")
    session.run("mypy")


@nox.session(python=PYTHON_VERSIONS)
def tests(session: nox.Session) -> None:
    """Run the test suite with coverage on each supported Python.

    ``--cov`` activates pytest-cov, which reads ``[tool.coverage]`` from
    pyproject.toml and enforces ``fail_under``. Kept here (not in pytest
    ``addopts``) so ad-hoc ``pytest`` runs stay fast and matrix runs don't
    contend over a shared ``.coverage`` file.
    """
    _sync(session, "test")
    session.run("pytest", "--cov", "--cov-report=term-missing", *session.posargs)


@nox.session
def audit(session: nox.Session) -> None:
    """Scan installed dependencies for known vulnerabilities (pip-audit).

    Not in the default session list because it queries online advisory
    databases; run explicitly with ``uv run nox -s audit`` or via CI.
    """
    _sync(session, "audit")
    session.run("pip-audit")


@nox.session
def docs(session: nox.Session) -> None:
    """Build the documentation site (strict)."""
    _sync(session, "docs")
    session.run("mkdocs", "build", "--strict")


@nox.session(name="docs-serve")
def docs_serve(session: nox.Session) -> None:
    """Serve the docs locally with live reload."""
    _sync(session, "docs")
    session.run("mkdocs", "serve")


@nox.session(name="cli-smoke")
def cli_smoke(session: nox.Session) -> None:
    """Generate a CLI, install it into a CLEAN venv (its declared deps only —
    typer resolves to the slim core, no top-level ``click``), and run its entry
    point + ``config environment`` commands the way the console script does.

    This is the generate -> install-in-its-own-venv -> run gate: offline, no
    Java. It catches undeclared-dependency / import / run regressions that the
    pytest suite (which runs in the dev venv) cannot.
    """
    _sync(session)
    session.run(
        "python", str(Path(__file__).parent / "tests" / "cli_isolated_smoke.py")
    )


@nox.session
def smoke(session: nox.Session) -> None:
    """Build the example SDKs end-to-end.

    phantasos auto-provisions a pinned Temurin JRE 17 on first run (cached under
    ~/.cache/phantasos), so no system Java is required; set PHANTASOS_JAVA to use
    your own JVM. Needs network for the one-time JRE + OAG jar download. Not in
    the default session list. Each SDK is written to a sibling dir of its product dir.
    """
    _sync(session)
    session.run("phantasos", "sdk", "build", "prisma-browser")
    session.run("phantasos", "sdk", "build", "adem")
