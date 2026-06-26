"""Task runner for phantasos.

One source of truth for the checks run both locally and in CI. Run everything
with ``uv run nox`` or a single session with ``uv run nox -s tests``.

Sessions use uv to provision their virtualenvs (and to install the locked
dependency groups) for fast, reproducible runs.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

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

# Product enrollment for the product-parametrized sessions (smoke/live/sdk-docs)
# lives in nox.toml, NOT hardcoded here — see that file's header. Add a product
# to a stage there once it is ready to be gated.
_NOX_CONFIG = Path(__file__).parent / "nox.toml"
_PRODUCTS_DIR = Path(__file__).parent / "products"


def _pipeline() -> dict[str, Any]:
    """Load nox.toml — the per-stage product enrollment + sdk-docs assertions."""
    if not _NOX_CONFIG.exists():
        raise FileNotFoundError(
            f"{_NOX_CONFIG.name} is missing; it declares the products for each "
            "product-parametrized session (smoke/live/sdk-docs)."
        )
    with _NOX_CONFIG.open("rb") as fh:
        return tomllib.load(fh)


def _stage_products(stage: str) -> list[str]:
    """Products enrolled in ``stage``, validated against ``products/``."""
    cfg = _pipeline().get(stage)
    if not cfg or "products" not in cfg:
        raise KeyError(f"nox.toml has no [{stage}] products list")
    products: list[str] = cfg["products"]
    for name in products:
        if not (_PRODUCTS_DIR / name).is_dir():
            raise ValueError(
                f"nox.toml [{stage}] enrolls unknown product {name!r} "
                f"(no products/{name}/)"
            )
    return products


def _stage_asserts(stage: str, product: str) -> list[dict[str, str]]:
    """Per-product post-build content assertions declared for ``stage``."""
    return [
        a
        for a in _pipeline().get(stage, {}).get("assert", [])
        if a.get("product") == product
    ]


def _run_content_asserts(
    session: nox.Session, stage: str, product: str, site: Path
) -> None:
    """Run the nox.toml per-product content guards for ``stage`` against ``site/``."""
    for check in _stage_asserts(stage, product):
        target = site / check["file"]
        text = target.read_text() if target.exists() else ""
        if "contains" in check and check["contains"] not in text:
            session.error(
                f"{product}: {check['file']} is missing {check['contains']!r}"
            )
        if "not_contains" in check and check["not_contains"] in text:
            session.error(
                f"{product}: {check['file']} unexpectedly contains "
                f"{check['not_contains']!r}"
            )


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
    from phantasos.productconfig import sdk_runtime_deps

    _sync(session, "test")
    # Tests that build a `facade:` SDK introspect the emitted package, whose
    # vendored facade imports the SDK's runtime deps (urllib3 via retry, etc.).
    # Pre-install them so the build's wrapper-vendoring import works — mirrors
    # the `smoke` session.
    session.install(*sdk_runtime_deps())
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
    from phantasos.productconfig import sdk_runtime_deps

    _sync(session)
    # `phantasos sdk build` of a docs:-enabled product (prisma-browser) introspects
    # the freshly generated package in-process (build_docs_context), which imports the
    # SDK's runtime deps (e.g. python-dateutil). Pre-install them so the build's
    # introspect step can import the package. Mirrors the `live`/`sdk-docs` sessions.
    session.install(*sdk_runtime_deps())
    for product in _stage_products("smoke"):
        session.run("phantasos", "sdk", "build", product)


@nox.session
def live(session: nox.Session) -> None:
    """Generate each enrolled SDK (nox.toml [live]) and run its live CRUD suite.

    Phase-boundary + CI gate (live.yml). Needs CLIENT_ID/CLIENT_SECRET/SCOPE
    in the environment (a local ``.env`` is read as a convenience); the suite
    SKIPS without them, so running this credential-less is safe and green.
    Needs network + Java (auto-provisioned, like ``smoke``).
    """
    _sync(session, "test")
    # `sdk build` now introspects the freshly-generated package in-process (to
    # vendor the typed resource wrappers), which import-walks the SDK — so its
    # base runtime deps must be importable in THIS venv before the build, not
    # only after `session.install(out_dir)` below.
    from phantasos.productconfig import _BASE_DEPS

    session.install(*_BASE_DEPS)
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
    for product in _stage_products("live"):
        session.run("phantasos", "sdk", "build", product, "--no-smoke")
        out_dir = load_product(product).output_dir
        session.install(str(out_dir))
        # Run every emitted live suite (`test_*_live.py`): single-spec products ship
        # the frozen `test_sdk_crud_live.py` oracle; the federated prisma-access ships
        # `test_first_light_live.py` (per-sub base-path read). All skip without creds.
        live_tests = sorted(out_dir.glob("tests/test_*_live.py"))
        if not live_tests:
            session.error(f"{product}: no live test (tests/test_*_live.py) emitted")
        session.run("pytest", "-v", *(str(p) for p in live_tests))


@nox.session(name="sdk-docs", venv_backend="uv")
def sdk_docs(session: nox.Session) -> None:
    """Build each enrolled SDK + its docs and run ``mkdocs build --strict``.

    Products (and per-product fidelity assertions) are declared in nox.toml
    ``[sdk-docs]`` — no product is hardcoded here. Integration gate (opt-in; needs
    the OAG JRE + network, self-provisioned like ``smoke``). NOT in
    nox.options.sessions, so the default ``nox``/CI run is unaffected and
    phantasos's own ``docs`` session stays intact.
    """
    import shutil

    from phantasos.productconfig import load_product, sdk_runtime_deps

    _sync(session)
    # Pre-install the SDK's known stable runtime deps so the in-process introspect
    # step (docs context build during `sdk build`) can import the package. Installed
    # directly (not via the SDK's pyproject) so this is robust to partially-built SDK
    # state; the dep set is stable across products/regenerations, and introspect()
    # adds the SDK dir to sys.path itself.
    session.install(*sdk_runtime_deps())
    root = Path.cwd()
    for product in _stage_products("sdk-docs"):
        out = load_product(product).output_dir
        # Wipe any stale mkdocs site/ tree — setuptools flat-layout discovery would
        # otherwise see both site/ and the SDK package as top-level packages.
        if (out / "site").exists():
            shutil.rmtree(out / "site")
        session.run("phantasos", "sdk", "build", product, "--no-smoke")
        # Isolate this `uv run` to a DEDICATED per-product project env so it does not
        # editable-install the generated SDK into the shared/gate venv (which would
        # make the package resolvable to mypy and break the gate's real-SDK tests).
        build_env = f"{session.virtualenv.location}-build-{product}"
        docs_env = {**os.environ, "UV_PROJECT_ENVIRONMENT": build_env}
        session.chdir(str(out))
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
        session.chdir(str(root))
        # Generic guard for every enrolled product: the reference rendered.
        site = out / "site"
        if not (site / "reference").exists():
            session.error(f"{product}: reference pages were not generated")
        # Product-specific content guards declared in nox.toml [[sdk-docs.assert]].
        _run_content_asserts(session, "sdk-docs", product, site)


@nox.session(name="cli-docs", venv_backend="uv")
def cli_docs(session: nox.Session) -> None:
    """Build each enrolled CLI + its docs and run ``mkdocs build --strict``.

    Products are declared in nox.toml ``[cli-docs]``. Opt-in integration gate (NOT in
    nox.options.sessions, like ``sdk-docs``). The CLI docs markdown is rendered at
    ``phantasos cli build`` time, so the mkdocs build needs only ``mkdocs-material``
    (the emitted CLI's ``docs`` dependency group). The CLI output dir is derived the
    same way the build computes it (via ``build_cli_scaffold_context``), NOT by
    string-munging the SDK output dir name.
    """
    import shutil

    from phantasos.generator.cli.cliconfig import load_cli_config
    from phantasos.generator.cli.scaffold_context import build_cli_scaffold_context
    from phantasos.productconfig import load_product, sdk_runtime_deps

    _sync(session)
    # `phantasos cli build` introspects the built SDK, so it must be importable.
    session.install(*sdk_runtime_deps())
    root = Path.cwd()
    for product in _stage_products("cli-docs"):
        loaded = load_product(product)
        cli_cfg = load_cli_config(Path(loaded.base_dir) / "cli.yml")
        # Derive the CLI out dir exactly as `cli build` does. build_cli_scaffold_context
        # ignores its `ir` arg (only loaded + cli_cfg determine `distribution`), so
        # ir=None is safe here; we consume ONLY ctx["distribution"].
        ctx = build_cli_scaffold_context(loaded, ir=None, cli_cfg=cli_cfg)
        cli_out = Path(loaded.output_dir).parent / str(ctx["distribution"])
        if (cli_out / "site").exists():
            shutil.rmtree(cli_out / "site")
        session.run("phantasos", "sdk", "build", product, "--no-smoke")
        session.run("phantasos", "cli", "build", product)
        if not cli_out.is_dir():
            session.error(f"{product}: CLI was not emitted at {cli_out}")
        build_env = f"{session.virtualenv.location}-clibuild-{product}"
        docs_env = {**os.environ, "UV_PROJECT_ENVIRONMENT": build_env}
        session.chdir(str(cli_out))
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
        session.chdir(str(root))
        site = cli_out / "site"
        if not (site / "reference").exists():
            session.error(f"{product}: CLI command reference was not generated")
        _run_content_asserts(session, "cli-docs", product, site)
