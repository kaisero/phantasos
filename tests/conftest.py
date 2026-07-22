"""Pytest config for the phantasos framework engine tests.

Ensures the `phantasos` package (under src/) is importable even without an editable
install. SDK-specific tests live with each generated SDK, not here.
"""

from __future__ import annotations

import functools
import importlib
import os
import sys
from collections.abc import Callable, Iterable, Iterator
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from phantasos.generator.cli.cliconfig import (
    CliConfig,
    RequestMapping,
    VariantMap,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# --- Shared fakesdk fixture path + CLI config (single source; consumed by emit_cli,
# the emitted/emitted_auth fixtures, and imported by test_cli_emitted.py) ---
FIXTURE = Path(__file__).parent / "fixtures" / "fakesdk"
FAKESDK_FIXTURE = FIXTURE  # public alias

# Variant config so the fixture produces `create:gizmo:simple` /
# `create:gizmo:complex` plus the request actions.
_FAKESDK_CLI_CONFIG = CliConfig(
    variants={
        "gizmos.create_gizmo": VariantMap(
            path_param="type",
            map={"simple": "SimpleGizmoInput", "complex": "ComplexGizmoInput"},
        )
    },
    request={
        "widgets.suspend_widget": RequestMapping(object="widget", action="suspend"),
        "widgets.revoke_widget": RequestMapping(object="widget", action="revoke"),
    },
    defaults={"widgets.list_widgets": {"name": "gadget", "limit": 50}},
)

# --- Ring-3 "real artifact" tests -------------------------------------------
# The single source of truth for the locally-built prisma-browser SDK, a sibling
# of the repo (products/prisma-browser/sdk.yml `output: ../../../prisma-browser-sdk`).
# No ring-3 test file redefines this path; they request the `real_sdk` fixture.
REAL_SDK = Path(__file__).resolve().parent.parent.parent / "prisma-browser-sdk"


@functools.cache
def _stale_sdk_reason() -> str | None:
    """Skip reason if the built SDK is stale vs the generator, else ``None``.

    The SDK's ``.build-stamp`` records the generator SHA at build time. The SDK is
    stale only if the generator source (``src/phantasos`` + the product's own
    ``products/prisma-browser``) actually changed since — a diff of the *working
    tree* against that commit, so it catches both later commits AND uncommitted
    generator edits, while ignoring unrelated commits (docs, other products). A
    missing stamp (older builds / pip-installed generator) or an unresolvable
    stamp commit means "can't tell" → don't skip. Set ``PHANTASOS_ALLOW_STALE_SDK=1``
    to force-run against a stale artifact.
    """
    if os.environ.get("PHANTASOS_ALLOW_STALE_SDK"):
        return None
    stamp = REAL_SDK / ".build-stamp"
    if not stamp.exists():
        return None
    built = stamp.read_text().strip()
    if not built:
        return None
    import subprocess

    repo = Path(__file__).resolve().parent.parent
    try:
        # --quiet exits 1 when the paths differ between `built` and the worktree,
        # 0 when identical, 128 when `built` is unknown to this checkout.
        rc = subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "diff",
                "--quiet",
                built,
                "--",
                "src/phantasos",
                "products/prisma-browser",
            ],
            capture_output=True,
            timeout=5,
        ).returncode
    except (OSError, subprocess.SubprocessError):
        return None
    if rc != 1:  # 0 = generator unchanged since build; 128 = unknown SHA → can't tell
        return None
    try:
        head = (
            subprocess.run(
                ["git", "-C", str(repo), "rev-parse", "--short=8", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
            ).stdout.strip()
            or "unknown"
        )
    except (OSError, subprocess.SubprocessError):
        head = "unknown"
    return _stale_reason_text(built[:8], head)


_STALE_SENTINEL = "prisma-browser-sdk is stale"


def _stale_reason_text(built_sha8: str, head_sha8: str) -> str:
    """The one place the staleness reason string is built (composed FROM the
    sentinel, so _STALE_SENTINEL is a substring by construction)."""
    return (
        f"{_STALE_SENTINEL}: the generator (src/phantasos or products/prisma-browser)"
        f" changed since it was built at {built_sha8} (HEAD {head_sha8}) — rebuild: "
        f"nox -s smoke (or set PHANTASOS_ALLOW_STALE_SDK=1)"
    )


def _ring3_stale_summary(skip_reasons: Iterable[str]) -> str | None:
    """One loud terminal-summary line when a ring-3 test skipped for SDK *staleness*.

    Returns ``None`` when no skip was a staleness skip (SDK absent, or the ring
    actually ran), so a fresh checkout and CI's SDK-less ``tests`` job stay quiet.
    Reuses the per-test staleness reason verbatim — it already carries the built +
    HEAD short shas and the ``rebuild: nox -s smoke`` hint — behind a ⚠ marker.
    """
    for reason in skip_reasons:
        if _STALE_SENTINEL in reason:
            return f"⚠ ring-3 OFF: {reason.removeprefix('Skipped: ')}"
    return None


def pytest_terminal_summary(terminalreporter: Any, exitstatus: int, config: pytest.Config) -> None:
    """Print the ring-3 staleness banner (stderr/summary only; never fails a run)."""
    reasons = [
        rep.longrepr[2] if isinstance(rep.longrepr, tuple) else str(rep.longrepr)
        for rep in terminalreporter.stats.get("skipped", [])
    ]
    if line := _ring3_stale_summary(reasons):
        terminalreporter.write_line(line, red=True, bold=True)


@pytest.fixture
def real_sdk() -> Path:
    """Path to the locally-built prisma-browser SDK for ring-3 real-artifact tests.

    Skips (never fails) when the SDK isn't built, so the ring is a no-op on a
    fresh checkout and in the CI matrix `tests` job, while running in the `smoke`
    session (which builds it) and on a provisioned dev machine. Requesting this
    fixture auto-tags the test with the ``real_sdk`` marker (see
    ``pytest_collection_modifyitems``), so the whole ring is selectable with
    ``-m real_sdk`` by construction — a real-artifact test cannot forget the tag.
    """
    if not REAL_SDK.exists():
        pytest.skip("prisma-browser-sdk not built (run: nox -s smoke)")
    if reason := _stale_sdk_reason():
        pytest.skip(reason)
    return REAL_SDK


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Auto-apply the ``real_sdk`` marker to every test requesting that fixture."""
    for item in items:
        if "real_sdk" in getattr(item, "fixturenames", ()):
            item.add_marker("real_sdk")


# Tests assert colour behaviour explicitly: CliRunner invokes run non-TTY (Rich emits
# plain text), and the few colour-positive tests force their own terminal. An ambient
# FORCE_COLOR (some CI/agent shells set it) overrides Rich's auto-detection and leaks
# ANSI into the "plain output" assertions. Drop it so emitted-CLI output is
# deterministic regardless of the caller's environment.
os.environ.pop("FORCE_COLOR", None)

# The post-generation finalize stage (ruff/uv lock/nox gate) is meaningless and slow
# on the stub/fake projects these tests build; skip it suite-wide. The dedicated
# finalize test and real end-to-end generation exercise it explicitly.
os.environ.setdefault("PHANTASOS_SKIP_FINALIZE", "1")


@contextmanager
def _imported(out_dir: Path, package: str) -> Iterator[ModuleType]:
    """Import an emitted package from ``out_dir`` with a clean module namespace.

    Consolidates the render/import/cleanup dance the emitted-CLI test suites
    hand-rolled inline: put ``out_dir`` on ``sys.path``, purge any already-imported
    ``package`` / ``package.*`` from ``sys.modules``, import & yield the package,
    then on exit re-purge and restore ``sys.path``. The membership test matches the
    inline purges' ``startswith(package)`` (no sibling package shares the prefix)
    while being stricter at the dot boundary. The ``sys.path`` insert/remove is
    guarded so a path already present (never the case for a unique tmp_path) is
    left untouched.
    """

    def _purge() -> None:
        for name in [m for m in sys.modules if m == package or m.startswith(package + ".")]:
            del sys.modules[name]

    entry = str(out_dir)
    added = entry not in sys.path
    if added:
        sys.path.insert(0, entry)
    _purge()
    try:
        yield importlib.import_module(package)
    finally:
        _purge()
        if added and entry in sys.path:
            sys.path.remove(entry)


@pytest.fixture
def render_and_import() -> Callable[[Path, str], AbstractContextManager[ModuleType]]:
    """Expose the :func:`_imported` ``(out_dir, package)`` context manager to tests."""
    return _imported


def _clear_emitted_config_cache() -> None:
    """Clear the ``load_config`` lru_cache on any *already-imported* emitted config
    module. Guarded — a no-op when no emitted CLI is resident. Defends against a test
    that imported ``<pkg>._generated.config`` OUTSIDE ``render_and_import`` leaving a
    cache bound to a stale HOME behind for the next test."""
    for name, mod in list(sys.modules.items()):
        if name.endswith("_cli._generated.config") and (
            clear := getattr(getattr(mod, "load_config", None), "cache_clear", None)
        ):
            clear()


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """HOME -> the per-test ``tmp_path``, with emitted-config cache hygiene on
    entry/exit. Yields the home dir. Isolates config/cache/history/env-file lookups
    (all keyed off HOME) without changing what any test asserts — it only replaces
    the hand-rolled ``monkeypatch.setenv("HOME", str(tmp_path))`` line and adds
    teardown hygiene."""
    monkeypatch.setenv("HOME", str(tmp_path))
    _clear_emitted_config_cache()
    try:
        yield tmp_path
    finally:
        _clear_emitted_config_cache()


@pytest.fixture
def emit_cli(tmp_path: Path) -> Callable[..., Path]:
    """Emit the fakesdk CLI into tmp_path for CLI-docs tests (tests/cli/).

    `auth=True` renders WITH an auth component so the IR carries credential_fields
    (exercises the credential-gated guides). Lives here rather than in
    tests/cli/conftest.py so there is a single `conftest` module name for mypy.
    """
    from phantasos.config import ScmOAuth
    from phantasos.generator.cli.classify import build_cli_ir, cli_operations
    from phantasos.generator.cli.cliconfig import CliDocsConfig
    from phantasos.generator.cli.render_cli import render_cli

    fixture = FIXTURE
    config = _FAKESDK_CLI_CONFIG

    calls = {"n": 0}

    def _emit(*, docs: CliDocsConfig | None = None, auth: bool = False) -> Path:
        # Render each call into its own subdir so a test can compare two emits
        # (e.g. auth-on vs auth-off) without one clobbering the other.
        calls["n"] += 1
        out = tmp_path / f"emit{calls['n']}"
        from phantasos.generator.cli.modelschema import build_model_registry

        inv = cli_operations("fakesdk", fixture)
        ir = build_cli_ir(inv, config, models=build_model_registry("fakesdk", fixture, inv))[0]
        render_cli(
            ir,
            package="fakesdk_cli",
            out_dir=out,
            env_prefix="FAKESDK",
            distribution="fakesdk",
            auth=ScmOAuth(type="scm_oauth") if auth else None,
            docs=docs,
            docs_site_name="Fakesdk CLI",
        )
        return out

    return _emit


# --- Shared emitted-CLI fixtures/helpers (used across the test_cli_emitted*
# seam modules) --- FIXTURE / _FAKESDK_CLI_CONFIG are defined near the top (single
# source, so emit_cli can reference them without late binding).

# Deterministic terminal env for tests that substring-assert Typer/Rich `--help`
# LAYOUT (panel titles, hyphenated option names). TERM=dumb disables styling so the
# literals stay contiguous; the fixed COLUMNS keeps wrapping stable. Pass explicitly
# to the `.invoke(..., env=HELP_ENV)` calls whose output is substring-asserted.
HELP_ENV = {"TERM": "dumb", "NO_COLOR": "1", "COLUMNS": "200"}


class _ListResult:
    """Envelope-shaped list result so the runtime's --all unwrap (result.data)
    and table rendering (items_field) both work against the fake. Carries a
    `model_dump` so the JSON/YAML renderer serializes it cleanly (mirrors a real
    pydantic List*200Response)."""

    def __init__(self, data: list[Any]) -> None:
        self.data = data
        self.page_info = None

    def model_dump(self, *a: Any, **k: Any) -> dict[str, Any]:
        return {"data": self.data, "page_info": self.page_info}


def _fake_client(recorder: list[Any]) -> tuple[Any, type]:
    """A stand-in matching the WRAPPER facade shape (post-4.2 dispatch): each
    object attr (`widget`/`gizmo`/`thing`, singular) is a recorder exposing clean
    verb methods (`create`/`get`/`list`/`update`/`delete`/`suspend`/`revoke`).
    Records `(clean_method, kwargs)` into `recorder` — the body arrives under the
    `body=` kwarg, mirroring the typed wrapper surface."""
    import fakesdk.extras.facade as facade

    class _Rec:
        def __getattr__(self, name: str) -> Any:
            def _call(*, all_pages: bool = False, **kw: Any) -> Any:
                recorder.append((name, kw))
                if name == "list":
                    return _ListResult([{"id": "1"}])
                return {"id": kw.get("id", "new")}

            return _call

    class _FakeClientCls:
        widget = _Rec()
        gizmo = _Rec()
        thing = _Rec()

        def paginate(self, method: Any, **kw: Any) -> Iterator[Any]:
            return iter(method(**kw) or [])

    return facade, _FakeClientCls


@pytest.fixture
def fake_client() -> Callable[[list[Any]], tuple[Any, type]]:
    """The shared `_fake_client` factory, exposed as a fixture for the emitted-CLI
    seam test modules (runtime/history/logging/environments/output)."""
    return _fake_client


@pytest.fixture
def emitted(tmp_path: Path) -> Iterator[Path]:
    """Emit the fakesdk CLI into tmp_path, importable as `fakesdk_cli` (env_prefix FAKESDK)."""
    from phantasos.generator.cli.classify import build_cli_ir, cli_operations
    from phantasos.generator.cli.modelschema import build_model_registry
    from phantasos.generator.cli.render_cli import render_cli

    inv = cli_operations("fakesdk", FIXTURE)
    ir = build_cli_ir(inv, _FAKESDK_CLI_CONFIG, models=build_model_registry("fakesdk", FIXTURE, inv))[0]
    render_cli(ir, package="fakesdk_cli", out_dir=tmp_path, env_prefix="FAKESDK")
    with _imported(tmp_path, "fakesdk_cli"):
        yield tmp_path


@pytest.fixture
def emitted_auth(tmp_path: Path) -> Iterator[Path]:
    """Like `emitted`, but rendered WITH an auth component so the IR carries
    credential_fields (client_id/client_secret/scope/base_url). Importable as
    `fakesdk_cli` (env_prefix FAKESDK)."""
    from phantasos.config import ScmOAuth
    from phantasos.generator.cli.classify import build_cli_ir, cli_operations
    from phantasos.generator.cli.modelschema import build_model_registry
    from phantasos.generator.cli.render_cli import render_cli

    inv = cli_operations("fakesdk", FIXTURE)
    ir = build_cli_ir(inv, _FAKESDK_CLI_CONFIG, models=build_model_registry("fakesdk", FIXTURE, inv))[0]
    render_cli(
        ir,
        package="fakesdk_cli",
        out_dir=tmp_path,
        env_prefix="FAKESDK",
        auth=ScmOAuth(type="scm_oauth"),
    )
    with _imported(tmp_path, "fakesdk_cli"):
        yield tmp_path
