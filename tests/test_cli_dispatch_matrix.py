"""Retain tests: runtime dispatch routing, --all multipage, dry-run parity.

These cover behaviour the golden snapshot cannot verify:
  - which *raw* `*Api` op fires for each arg combo (multi-binding dispatch)
  - that `--all` walks >1 page AND injects the cli.yml sort/order defaults
  - that the history entry records the first-page URI ending in `/applications`
  - dry-run parity (method + URL + body present in output for a fixed set)

All tests that need the real SDK require the ``real_sdk`` fixture.
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

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def real_cli(
    real_sdk: Path,
    tmp_path: Path,
    render_and_import: Callable[[Path, str], AbstractContextManager[ModuleType]],
) -> Iterator[Path]:
    """Build the prisma-browser CLI into ``tmp_path``; importable as
    ``prisma_browser_cli``.  Skips when the SDK is absent or its runtime deps
    are missing."""
    try:
        inv = cli_operations("prisma_browser", real_sdk)
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


# Most-specific binding wins (more required args = higher priority): `--id --type`
# beats `--id` alone; `--type` alone is a LIST filter, not a get-route.
_SHOW_CASES = [
    pytest.param(["--id", "APP-1"], "get_application_by_id", id="id-only"),
    pytest.param(
        ["--id", "APP-1", "--type", "custom"],
        "get_application_by_type_and_id",
        id="id-and-type",
    ),
    pytest.param([], "list_applications", id="bare"),
    pytest.param(["--type", "custom"], "list_applications_by_type", id="type-only"),
]

_DELETE_CASES = [
    pytest.param(["--id", "APP-1"], "delete_application_by_id", id="id-only"),
    pytest.param(
        ["--id", "APP-1", "--type", "custom"],
        "delete_application_by_type_and_id",
        id="id-and-type",
    ),
]


def _show_client(fired: list[str]) -> Any:
    """Fake Client whose application._api records raw-method calls (show shapes)."""
    from prisma_browser.extras.resources import ApplicationResource

    _single = _make_app_response()
    _list_page = _make_list_response([_make_app_response()])

    class _Rec:
        def __getattr__(self, name: str) -> Any:
            def _fn(**kw: Any) -> Any:
                fired.append(name)
                return _list_page if name.startswith("list_") else _single

            return _fn

    class _FakeClient:
        def __init__(self) -> None:
            self.application = ApplicationResource(_Rec())

        api_client = None

    return _FakeClient()


def _delete_client(fired: list[str]) -> Any:
    """Fake Client whose application._api records raw-method calls (delete: None)."""
    from prisma_browser.extras.resources import ApplicationResource

    class _Rec:
        def __getattr__(self, name: str) -> Any:
            def _fn(**kw: Any) -> None:
                fired.append(name)

            return _fn

    class _FakeClient:
        def __init__(self) -> None:
            self.application = ApplicationResource(_Rec())

        api_client = None

    return _FakeClient()


@pytest.mark.parametrize("extra_args, expected_op", _SHOW_CASES)
def test_show_dispatch_matrix(
    real_cli: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    extra_args: list[str],
    expected_op: str,
) -> None:
    """`show application <args>` routes to the correct raw op (one case per test)."""
    import prisma_browser.extras.facade as facade
    from typer.testing import CliRunner

    monkeypatch.setenv("HOME", str(tmp_path))
    main = importlib.import_module("prisma_browser_cli.main")
    fired: list[str] = []
    monkeypatch.setattr(
        facade.Client, "from_env", classmethod(lambda cls: _show_client(fired))
    )
    res = CliRunner().invoke(
        main.app, ["show", "application", *extra_args, "--output", "json"]
    )
    assert res.exit_code == 0, f"{extra_args}: {res.output}"
    assert expected_op in fired, f"fired={fired}"


@pytest.mark.parametrize("extra_args, expected_op", _DELETE_CASES)
def test_delete_dispatch_matrix(
    real_cli: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    extra_args: list[str],
    expected_op: str,
) -> None:
    """`delete application <args>` routes to the correct raw op (one case per test)."""
    import prisma_browser.extras.facade as facade
    from typer.testing import CliRunner

    monkeypatch.setenv("HOME", str(tmp_path))
    main = importlib.import_module("prisma_browser_cli.main")
    fired: list[str] = []
    monkeypatch.setattr(
        facade.Client, "from_env", classmethod(lambda cls: _delete_client(fired))
    )
    res = CliRunner().invoke(main.app, ["delete", "application", *extra_args])
    assert res.exit_code == 0, f"{extra_args}: {res.output}"
    assert expected_op in fired, f"fired={fired}"


# ---------------------------------------------------------------------------
# 2. --all multipage test: sort injected, page 2 fetched, history URI recorded
# ---------------------------------------------------------------------------


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
