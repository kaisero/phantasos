"""Pytest config for the phantasos framework engine tests.

Ensures the `phantasos` package (under src/) is importable even without an editable
install. SDK-specific tests live with each generated SDK, not here.
"""

from __future__ import annotations

import importlib
import sys
from collections.abc import Callable, Iterator
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
        for name in [
            m for m in sys.modules if m == package or m.startswith(package + ".")
        ]:
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


@pytest.fixture
def emit_cli(tmp_path: Path) -> Callable[..., Path]:
    """Emit the fakesdk CLI into tmp_path for CLI-docs tests (tests/cli/).

    `auth=True` renders WITH an auth component so the IR carries credential_fields
    (exercises the credential-gated guides). Lives here rather than in
    tests/cli/conftest.py so there is a single `conftest` module name for mypy.
    """
    from phantasos.config import ScmOAuth
    from phantasos.generator.cli.classify import build_cli_ir, cli_operations
    from phantasos.generator.cli.cliconfig import (
        CliConfig,
        CliDocsConfig,
        RequestMapping,
        VariantMap,
    )
    from phantasos.generator.cli.render_cli import render_cli

    fixture = Path(__file__).parent / "fixtures" / "fakesdk"
    config = CliConfig(
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

    calls = {"n": 0}

    def _emit(*, docs: CliDocsConfig | None = None, auth: bool = False) -> Path:
        # Render each call into its own subdir so a test can compare two emits
        # (e.g. auth-on vs auth-off) without one clobbering the other.
        calls["n"] += 1
        out = tmp_path / f"emit{calls['n']}"
        from phantasos.generator.cli.modelschema import build_model_registry

        inv = cli_operations("fakesdk", fixture)
        ir = build_cli_ir(
            inv, config, models=build_model_registry("fakesdk", fixture, inv)
        )[0]
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
# seam modules) ---

FIXTURE = Path(__file__).parent / "fixtures" / "fakesdk"

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
    """Emit the fakesdk CLI into tmp_path, importable as `fakesdk_cli` (env_prefix FAKESDK)."""  # noqa: E501
    from phantasos.generator.cli.classify import build_cli_ir, cli_operations
    from phantasos.generator.cli.modelschema import build_model_registry
    from phantasos.generator.cli.render_cli import render_cli

    inv = cli_operations("fakesdk", FIXTURE)
    ir = build_cli_ir(
        inv, _FAKESDK_CLI_CONFIG, models=build_model_registry("fakesdk", FIXTURE, inv)
    )[0]
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
    ir = build_cli_ir(
        inv, _FAKESDK_CLI_CONFIG, models=build_model_registry("fakesdk", FIXTURE, inv)
    )[0]
    render_cli(
        ir,
        package="fakesdk_cli",
        out_dir=tmp_path,
        env_prefix="FAKESDK",
        auth=ScmOAuth(type="scm_oauth"),
    )
    with _imported(tmp_path, "fakesdk_cli"):
        yield tmp_path
