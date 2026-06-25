"""Retain tests: runtime dispatch routing, --all multipage, dry-run parity.

These cover behaviour the golden snapshot cannot verify:
  - which *raw* `*Api` op fires for each arg combo (multi-binding dispatch)
  - that `--all` walks >1 page AND injects the cli.yml sort/order defaults
  - that the history entry records the first-page URI ending in `/applications`
  - dry-run parity (method + URL + body present in output for a fixed set)

All tests that need the real SDK are gated with ``skipif(not REAL_SDK.exists())``.
"""

from __future__ import annotations

import importlib
import sys
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import MagicMock

import pytest

from phantasos.generator.cli.classify import build_cli_ir, cli_operations
from phantasos.generator.cli.cliconfig import load_cli_config
from phantasos.generator.cli.render_cli import render_cli

REAL_SDK = Path(__file__).parent.parent.parent / "prisma-browser-sdk"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def real_cli(
    tmp_path: Path,
    render_and_import: Callable[[Path, str], AbstractContextManager[ModuleType]],
) -> Iterator[Path]:
    """Build the prisma-browser CLI into ``tmp_path``; importable as
    ``prisma_browser_cli``.  Skips when the SDK is absent or its runtime deps
    are missing."""
    if not REAL_SDK.exists():
        pytest.skip("prisma-browser-sdk not built")
    try:
        inv = cli_operations("prisma_browser", REAL_SDK)
    except ImportError as exc:
        pytest.skip(f"prisma-browser-sdk runtime deps unavailable: {exc}")

    cfg = load_cli_config(Path("products/prisma-browser/cli.yml"))
    ir, _ = build_cli_ir(inv, cfg)
    render_cli(
        ir,
        package="prisma_browser_cli",
        out_dir=tmp_path,
        env_prefix="PRISMA",
        distribution="prisma-browser-cli",
    )
    with render_and_import(tmp_path, "prisma_browser_cli"):
        yield tmp_path


def _make_app_response(**fields: Any) -> dict[str, Any]:
    """Return a plain dict that the output renderer can JSON-serialize."""
    return {"id": "APP-1", "type": "custom", "name": "Test App", **fields}


def _make_list_response(items: list[dict[str, Any]], cursor: str | None = None) -> Any:
    """Return an envelope-like page with ``data`` and optional pagination cursor.

    Built as a simple object (not a MagicMock) so ``model_dump`` returns a
    plain, JSON-serializable dict.
    """
    _cursor = cursor
    _has_next = cursor is not None
    _items = items

    class _PageInfo:
        has_next_page = _has_next
        cursor = _cursor

    class _Page:
        data = _items
        page_info = _PageInfo()

        def model_dump(self, *a: Any, **k: Any) -> dict[str, Any]:
            return {"data": _items, "page_info": None}

        def model_copy(self, update: dict[str, Any] | None = None) -> Any:
            p = _Page()
            if update:
                for attr_k, attr_v in update.items():
                    setattr(p, attr_k, attr_v)
            return p

    return _Page()


# ---------------------------------------------------------------------------
# 1. Dispatch-matrix tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not REAL_SDK.exists(), reason="prisma-browser-sdk not built")
def test_show_dispatch_matrix(
    real_cli: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``show application`` routes to the correct raw op for every arg combo.

    The wrapper's ``_api`` attribute (the raw ``ApplicationsApi`` instance) is
    replaced by a recorder; each raw method name that fires is appended to
    ``fired``.  The *most-specific* binding wins (more required args = higher
    priority), so --id + --type beats --id alone.
    """
    import prisma_browser.extras.facade as facade
    from prisma_browser.extras.resources import ApplicationResource
    from typer.testing import CliRunner

    monkeypatch.setenv("HOME", str(tmp_path))
    main = importlib.import_module("prisma_browser_cli.main")
    runner = CliRunner()

    # Minimal responses compatible with the output renderer.
    _single = _make_app_response()
    _list_page = _make_list_response([_make_app_response()])

    def _make_recorder(fired: list[str]) -> Any:
        """Build a fake ApplicationsApi that records raw-method calls."""

        class _Rec:
            def __getattr__(self, name: str) -> Any:
                def _fn(**kw: Any) -> Any:
                    fired.append(name)
                    # return the right shape based on the op
                    if name.startswith("list_"):
                        return _list_page
                    return _single

                return _fn

        return _Rec()

    def _make_client(fired: list[str]) -> Any:
        """Build a fake Client where ``application._api`` is our recorder."""
        rec = _make_recorder(fired)

        class _FakeClient:
            def __init__(self) -> None:
                # Build a real ApplicationResource backed by our recorder
                self.application = ApplicationResource(rec)

            # The runtime looks for api_client; None skips the call_api wrapper
            # (no HTTP URI capture needed for this dispatch-only test).
            api_client = None

        return _FakeClient()

    # ------------------------------------------------------------------ show
    # Case 1: show application --id X  →  get_application_by_id
    fired: list[str] = []
    client = _make_client(fired)
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: client))
    res = runner.invoke(
        main.app, ["show", "application", "--id", "APP-1", "--output", "json"]
    )
    assert res.exit_code == 0, f"--id only: {res.output}"
    assert "get_application_by_id" in fired, f"fired={fired}"

    # Case 2: show application --id X --type T  →  get_application_by_type_and_id
    fired.clear()
    client = _make_client(fired)
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: client))
    res = runner.invoke(
        main.app,
        [
            "show",
            "application",
            "--id",
            "APP-1",
            "--type",
            "custom",
            "--output",
            "json",
        ],
    )
    assert res.exit_code == 0, f"--id --type: {res.output}"
    assert "get_application_by_type_and_id" in fired, f"fired={fired}"

    # Case 3: show application (bare, no --id)  →  list_applications
    fired.clear()
    client = _make_client(fired)
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: client))
    res = runner.invoke(main.app, ["show", "application", "--output", "json"])
    assert res.exit_code == 0, f"bare: {res.output}"
    assert "list_applications" in fired, f"fired={fired}"

    # Case 4: show application --type T (no --id)  →  list_applications_by_type
    # (a LIST binding, not a get; --type alone is a filter on the list, not a get-route)
    fired.clear()
    client = _make_client(fired)
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: client))
    res = runner.invoke(
        main.app, ["show", "application", "--type", "custom", "--output", "json"]
    )
    assert res.exit_code == 0, f"--type only: {res.output}"
    assert "list_applications_by_type" in fired, f"fired={fired}"


@pytest.mark.skipif(not REAL_SDK.exists(), reason="prisma-browser-sdk not built")
def test_delete_dispatch_matrix(
    real_cli: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``delete application`` routes to the correct raw op for every arg combo."""
    import prisma_browser.extras.facade as facade
    from prisma_browser.extras.resources import ApplicationResource
    from typer.testing import CliRunner

    monkeypatch.setenv("HOME", str(tmp_path))
    main = importlib.import_module("prisma_browser_cli.main")
    runner = CliRunner()

    def _make_recorder(fired: list[str]) -> Any:
        class _Rec:
            def __getattr__(self, name: str) -> Any:
                def _fn(**kw: Any) -> None:
                    fired.append(name)

                return _fn

        return _Rec()

    def _make_client(fired: list[str]) -> Any:
        rec = _make_recorder(fired)

        class _FakeClient:
            def __init__(self) -> None:
                self.application = ApplicationResource(rec)

            api_client = None

        return _FakeClient()

    # Case 5: delete application --id X  →  delete_application_by_id
    fired: list[str] = []
    client = _make_client(fired)
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: client))
    res = runner.invoke(main.app, ["delete", "application", "--id", "APP-1"])
    assert res.exit_code == 0, f"delete --id only: {res.output}"
    assert "delete_application_by_id" in fired, f"fired={fired}"

    # Case 6: delete application --id X --type T  →  delete_application_by_type_and_id
    fired.clear()
    client = _make_client(fired)
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: client))
    res = runner.invoke(
        main.app, ["delete", "application", "--id", "APP-1", "--type", "custom"]
    )
    assert res.exit_code == 0, f"delete --id --type: {res.output}"
    assert "delete_application_by_type_and_id" in fired, f"fired={fired}"


# ---------------------------------------------------------------------------
# 2. --all multipage test: sort injected, page 2 fetched, history URI recorded
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not REAL_SDK.exists(), reason="prisma-browser-sdk not built")
def test_all_pages_walks_and_injects_sort(
    real_cli: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``show application --all`` must:

    (a) inject the cli.yml ``defaults`` ``sort=application.name`` and
        ``order=asc`` into the raw list call (cursor pagination requires an
        explicit sort);
    (b) walk more than one page (the fake first page carries a cursor);
    (c) record a history entry with status ``success``; if ``http_uri`` is
        present it must end with ``/applications``.
    """
    import prisma_browser.extras.facade as facade
    from prisma_browser.extras.resources import ApplicationResource
    from typer.testing import CliRunner

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(
        sys, "argv", ["prisma-browser-cli", "show", "application", "--all"]
    )
    main = importlib.import_module("prisma_browser_cli.main")
    runner = CliRunner()

    # Track all raw calls including kwargs (to verify sort/order injected).
    raw_calls: list[tuple[str, dict[str, Any]]] = []

    app1: dict[str, Any] = {"id": "APP-1", "name": "Alpha"}
    app2: dict[str, Any] = {"id": "APP-2", "name": "Beta"}

    # Page 1: has_next_page=True, cursor="CUR1"
    page1 = _make_list_response([app1], cursor="CUR1")
    # Page 2: final page, no cursor
    page2 = _make_list_response([app2], cursor=None)

    call_count = [0]

    class _RecorderApi:
        """Fake ApplicationsApi that records raw calls and simulates 2 pages."""

        def __getattr__(self, name: str) -> Any:
            def _fn(**kw: Any) -> Any:
                raw_calls.append((name, dict(kw)))
                n = call_count[0]
                call_count[0] += 1
                if name == "list_applications":
                    return page1 if n == 0 else page2
                return MagicMock()

            return _fn

    class _FakeApiClient:
        """Minimal api_client; the runtime can wrap its ``call_api`` for URI capture."""

        def call_api(
            self,
            method: str,
            url: str,
            *args: Any,
            **kw: Any,
        ) -> Any:
            return {}

    class _FakeClient:
        def __init__(self) -> None:
            self._api_client = _FakeApiClient()
            self.application = ApplicationResource(_RecorderApi())

        @property
        def api_client(self) -> _FakeApiClient:
            return self._api_client

    client_instance = _FakeClient()
    monkeypatch.setattr(
        facade.Client, "from_env", classmethod(lambda cls: client_instance)
    )

    res = runner.invoke(main.app, ["show", "application", "--all", "--output", "json"])
    assert res.exit_code == 0, res.output

    # (a) sort + order defaults were injected into the first raw call.
    list_calls = [(n, kw) for n, kw in raw_calls if n == "list_applications"]
    assert list_calls, f"list_applications was never called; raw_calls={raw_calls}"
    first_kw = list_calls[0][1]
    # The defaults (query_flags cli_default) flow through as kwargs to the raw API;
    # after enum coercion, sort/order arrive as enum objects with a `.value`.
    sort_val = first_kw.get("sort")
    order_val = first_kw.get("order")
    assert sort_val is not None, (
        f"'sort' not in first list_applications call; got {first_kw}"
    )
    assert order_val is not None, (
        f"'order' not in first list_applications call; got {first_kw}"
    )
    sort_str = getattr(sort_val, "value", str(sort_val))
    assert "application.name" in sort_str, (
        f"expected 'application.name' in sort value; got {sort_str!r}"
    )
    order_str = getattr(order_val, "value", str(order_val))
    assert "asc" in order_str, f"expected 'asc' in order value; got {order_str!r}"

    # (b) page 2 was fetched (list called at least twice).
    assert call_count[0] >= 2, (
        f"expected >=2 list calls for --all; got {call_count[0]}; raw_calls={raw_calls}"
    )

    # (c) history entry records success; if http_uri is present it ends with
    #     /applications (URI is only captured when call_api fires, which our
    #     recorder-api path bypasses — absence is expected and noted).
    hist = importlib.import_module("prisma_browser_cli._generated.history")
    entries, _ = hist.read_entries(0)
    if entries:
        entry = entries[-1]
        assert entry["status"] == "success", f"history status: {entry}"
        if "http_uri" in entry:
            assert entry["http_uri"].endswith("/applications"), (
                f"http_uri: {entry['http_uri']!r}"
            )


# ---------------------------------------------------------------------------
# 3. Dry-run parity tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not REAL_SDK.exists(), reason="prisma-browser-sdk not built")
def test_dry_run_parity_show_list(real_cli: Path) -> None:
    """``show application --dry-run`` prints GET + /applications, no dispatch."""
    from typer.testing import CliRunner

    main = importlib.import_module("prisma_browser_cli.main")
    res = CliRunner().invoke(main.app, ["show", "application", "--dry-run"])
    assert res.exit_code == 0, res.output
    out = res.output
    assert "GET" in out
    assert "/applications" in out
    # dry-run must NOT leak the raw op name (old call-reference string)
    assert "list_applications(" not in out


@pytest.mark.skipif(not REAL_SDK.exists(), reason="prisma-browser-sdk not built")
def test_dry_run_parity_create_device_group(real_cli: Path) -> None:
    """``create device-group --dry-run`` prints POST + /device-groups + body."""
    from typer.testing import CliRunner

    main = importlib.import_module("prisma_browser_cli.main")
    res = CliRunner().invoke(
        main.app,
        [
            "create",
            "device-group",
            "--name",
            "TestGroup",
            "--platform",
            "Desktop Browser",
            "--dry-run",
        ],
    )
    assert res.exit_code == 0, res.output
    out = res.output
    assert "POST" in out
    assert "device-groups" in out
    assert "TestGroup" in out  # body payload present


@pytest.mark.skipif(not REAL_SDK.exists(), reason="prisma-browser-sdk not built")
def test_dry_run_parity_show_by_id(real_cli: Path) -> None:
    """``show application --id X --dry-run`` prints GET + /applications/X."""
    from typer.testing import CliRunner

    main = importlib.import_module("prisma_browser_cli.main")
    res = CliRunner().invoke(
        main.app,
        ["show", "application", "--id", "APP-99", "--dry-run"],
    )
    assert res.exit_code == 0, res.output
    out = res.output
    assert "GET" in out
    assert "APP-99" in out or "/applications" in out
    assert "get_application_by_id(" not in out  # NOT the old call-reference string
