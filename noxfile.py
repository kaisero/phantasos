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
# sshfs quirk: some dev checkouts cannot hold symlinks, so session venvs under
# ./.nox fail to create. NOX_ENVDIR relocates them (e.g. /tmp/phantasos-nox);
# CI leaves it unset and uses the default ./.nox.
if os.environ.get("NOX_ENVDIR"):
    nox.options.envdir = os.environ["NOX_ENVDIR"]
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


@nox.session(venv_backend="none")
def gate(session: nox.Session) -> None:
    """Fast offline quality gate — single environment, no venv creation.

    Run by the Stop hook on every agent turn (see .claude/harness.toml), so it
    must stay fast: ruff + mypy + the offline pytest suite, no coverage, no
    multi-Python matrix. Runs in the invoking environment (``uv run nox``).
    """
    session.run("ruff", "check", ".")
    session.run("ruff", "format", "--check", ".")
    session.run("mypy")
    session.run("pytest", "-q")


@nox.session(venv_backend="none")
def context(session: nox.Session) -> None:
    """Regenerate (or --check) the .agents/context/ mechanical blocks.

    `nox -s context` rewrites the GENERATED markers from live code;
    `nox -s context -- --check` fails if any block is stale (the freshness
    gate runs this). Pure stdlib, no install needed.
    """
    session.run("python", "tools/context_docs.py", *session.posargs, external=True)


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


@nox.session
def live(session: nox.Session) -> None:
    """Generate the prisma-browser SDK and run its live CRUD suite (real tenant).

    Phase-boundary + CI gate (live.yml). Needs CLIENT_ID/CLIENT_SECRET/SCOPE
    in the environment (a local ``.env`` is read as a convenience); the suite
    SKIPS without them, so running this credential-less is safe and green.
    Needs network + Java (auto-provisioned, like ``smoke``).
    """
    _sync(session, "test")
    env_file = Path(".env")
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key, _, value = stripped.partition("=")
                session.env.setdefault(key.strip(), value.strip().strip('"'))
    from phantasos.productconfig import load_product, sdk_runtime_deps

    # Pre-install the SDK's stable runtime deps so the in-process introspect step
    # (triggered by docs context build during sdk build) can import the SDK package.
    # introspect() adds the SDK dir to sys.path; we only need the deps in the venv.
    session.install(*sdk_runtime_deps())
    session.run("phantasos", "sdk", "build", "prisma-browser", "--no-smoke")
    out_dir = load_product("prisma-browser").output_dir
    session.install(str(out_dir))
    session.run("pytest", "-v", str(out_dir / "tests" / "test_sdk_crud_live.py"))


@nox.session(name="sdk-docs", venv_backend="uv")
def sdk_docs(session: nox.Session) -> None:
    """Build the prisma-browser SDK + its docs and run ``mkdocs build --strict``.

    Integration gate (opt-in; needs the OAG JRE + network, self-provisioned like
    ``smoke``). NOT added to nox.options.sessions, so the default ``nox``/CI run is
    unaffected and phantasos's own ``docs`` session stays intact.
    """
    from phantasos.productconfig import load_product, sdk_runtime_deps

    _sync(session)
    out = load_product("prisma-browser").output_dir
    # Wipe any stale mkdocs site/ tree left by a previous run — setuptools's flat
    # layout discovery would otherwise see both `site/` and the SDK package as
    # top-level packages and refuse to build.
    stale_site = out / "site"
    if stale_site.exists():
        import shutil

        shutil.rmtree(stale_site)
    # Pre-install the SDK's known stable runtime deps.  We install them directly
    # (rather than via the SDK's own pyproject.toml) so this step is robust to
    # partially-built SDK state — e.g. when the OAG-generated pyproject.toml is
    # present instead of the phantasos-scaffolded one, installing the whole project
    # would fail (wrong build backend / flat-layout discovery collision with
    # site/).  The dep set is stable across regenerations; introspect() adds the
    # SDK dir to sys.path itself, so the package is importable without pip install.
    session.install(*sdk_runtime_deps())
    session.run("phantasos", "sdk", "build", "prisma-browser", "--no-smoke")
    session.chdir(str(out))
    # Isolate this `uv run` to a DEDICATED project env. It would otherwise inherit
    # UV_PROJECT_ENVIRONMENT (commonly the offline-gate venv, per CLAUDE.md) and
    # editable-install the generated SDK there — which makes prisma_browser
    # resolvable to mypy and breaks the gate's real-SDK tests. A separate env dir
    # keeps the shared gate env clean.
    # Dedicated build env dir (the session venv path + "-build"), kept off the
    # shared/gate env so the SDK is not editable-installed there.
    build_env = session.virtualenv.location + "-build"
    docs_env = {**os.environ, "UV_PROJECT_ENVIRONMENT": build_env}
    session.run(
        "uv",
        "run",
        "--group",
        "docs",
        "mkdocs",
        "build",
        "--strict",
        external=True,
        env=docs_env,
    )
    site = out / "site"
    if not (site / "reference").exists():
        session.error("reference pages were not generated")
    # (A) griffe-pydantic surfaces field descriptions on a leaf model page
    leaf = site / "reference/models/custom_application_input/index.html"
    if not (leaf.exists() and "Name of the application" in leaf.read_text()):
        session.error("model field descriptions did not render (griffe-pydantic)")
    # (B) oneOf wrapper page links its variant models
    wrapper = site / "reference/models/create_or_replace_app_input/index.html"
    if not (wrapper.exists() and "CustomApplicationInput" in wrapper.read_text()):
        session.error("oneOf wrapper page is missing variant links")
    # (C) the curated CRUD example rendered (not the opaque placeholder)
    crud = site / "guides/crud/index.html"
    txt = crud.read_text() if crud.exists() else ""
    if "Acme Wiki" not in txt or "CreateOrReplaceAppInput(...)" in txt:
        session.error("CRUD create example did not render the curated body")
