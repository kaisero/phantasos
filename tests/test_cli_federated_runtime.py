"""C2: federation-aware runtime — the emitted CLI actually RUNS a federated SDK.

Renders the federated `fedsdk` CLI (subs alpha/beta) and drives its emitted
`runtime.py` through `CliRunner`/`rt.run`, asserting each per-sub seam resolves:

- dispatch navigates two levels: `client.<sub>.<object>.<verb>(...)`;
- the request body is built from the SUB's `models` module (`fedsdk.alpha.models`,
  not a nonexistent `fedsdk.models`);
- `--dry-run` serializes via the sub wrapper's `_serialize` seam (no dispatch);
- a raised SDK error is caught/funnelled (no `ModuleNotFoundError` leaking from a
  guessed top-level `fedsdk.exceptions`);
- `_sdk_exc` points at the federated `_runtime.exceptions` (the real layout), while
  a single-package command still resolves the bare `<pkg>.exceptions` path.

The SDK is stubbed at the `Client.from_env` seam (no network), mirroring the
single-spec emitted-CLI runtime tests in `test_cli_emitted_runtime.py`.
"""

from __future__ import annotations

import importlib
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from phantasos.generator.cli.classify import build_ir
from phantasos.generator.cli.cliconfig import CliConfig, RequestMapping
from phantasos.generator.cli.ir import Command
from phantasos.generator.cli.render_cli import render_cli
from phantasos.generator.opmodel._pathutil import on_sys_path

FEDSDK = Path(__file__).parent / "fixtures" / "fedsdk"


def _fed_cfg() -> CliConfig:
    """Map beta's non-CRUD `compute` (else the federated build fails loud)."""
    return CliConfig(
        subpackages={
            "alpha": CliConfig(),  # G1: enroll alpha (allowlist needs it listed)
            "beta": CliConfig(
                request={
                    "gadgets.compute_gadget": RequestMapping(
                        object="gadget", action="compute"
                    )
                }
            ),
        }
    )


class _ListResult:
    """Envelope-shaped list result (mirrors a real List*200Response)."""

    def __init__(self, data: list[Any]) -> None:
        self.data = data
        self.page_info = None

    def model_dump(self, *a: Any, **k: Any) -> dict[str, Any]:
        return {"data": self.data, "page_info": self.page_info}


def _fake_fed_client(recorder: list[Any]) -> type:
    """A stand-in for the COMPOSING client: `client.<sub>.<object>` is a recorder
    exposing clean verb methods. Records `(clean_method, kwargs)` — proving the
    runtime navigates two levels (sub then object)."""

    class _Rec:
        def __getattr__(self, name: str) -> Any:
            def _call(*, all_pages: bool = False, **kw: Any) -> Any:
                recorder.append((name, kw))
                if name == "list":
                    return _ListResult([{"id": "1"}])
                return {"id": kw.get("id", "new")}

            return _call

    class _Sub:
        def __init__(self) -> None:
            self.widget = _Rec()  # alpha's object
            self.gadget = _Rec()  # beta's object

    class _FedClient:
        def __init__(self) -> None:
            self.alpha = _Sub()
            self.beta = _Sub()

    return _FedClient


@contextmanager
def _fed_runtime(tmp_path: Path) -> Iterator[Any]:
    """Render the fedsdk CLI, keep the SDK on sys.path, yield its runtime module."""
    ir, _ = build_ir("fedsdk", FEDSDK, _fed_cfg())
    render_cli(
        ir,
        package="fedsdk_cli",
        out_dir=tmp_path,
        env_prefix="FEDSDK",
        distribution="fedsdk",
    )
    import sys

    entry = str(tmp_path)
    added = entry not in sys.path
    if added:
        sys.path.insert(0, entry)
    purge = [m for m in sys.modules if m == "fedsdk_cli" or m.startswith("fedsdk_cli.")]
    for m in purge:
        del sys.modules[m]
    try:
        with on_sys_path(FEDSDK):  # the SDK is "installed" for the runtime's imports
            yield importlib.import_module("fedsdk_cli._generated.runtime")
    finally:
        for m in [
            n for n in sys.modules if n == "fedsdk_cli" or n.startswith("fedsdk_cli.")
        ]:
            del sys.modules[m]
        if added and entry in sys.path:
            sys.path.remove(entry)


def test_federated_dispatch_navigates_sub_then_object(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _fed_runtime(tmp_path) as rt:
        import fedsdk
        import fedsdk.alpha.models as alpha_models

        calls: list[Any] = []
        monkeypatch.setattr(
            fedsdk.Client,
            "from_env",
            classmethod(lambda cls, **kw: _fake_fed_client(calls)()),
        )
        rt.run(
            "create:widget",
            path={},
            body={"name": "w1", "size": 3},
            query={},
            output="json",
            paginate_all=False,
            dry_run=False,
            verbose=False,
        )
        # dispatched on alpha.widget via clean verb, body built from the SUB models
        assert calls and calls[0][0] == "create"
        body = calls[0][1]["body"]
        assert isinstance(body, alpha_models.WidgetInput)
        assert body.name == "w1" and body.size == 3


def test_federated_list_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _fed_runtime(tmp_path) as rt:
        import fedsdk

        calls: list[Any] = []
        monkeypatch.setattr(
            fedsdk.Client,
            "from_env",
            classmethod(lambda cls, **kw: _fake_fed_client(calls)()),
        )
        rt.run(
            "show:widget",
            path={},
            body={},
            query={"limit": "5"},
            output="json",
            paginate_all=False,
            dry_run=False,
            verbose=False,
        )
        assert any(n == "list" for n, _ in calls)
        _, kw = next((n, k) for n, k in calls if n == "list")
        assert kw.get("limit") == 5  # coerced + accepted by the sub wrapper


def test_accepted_params_resolves_per_sub_facade(tmp_path: Path) -> None:
    """`_accepted_params` resolves the SUB's facade `_WRAPPERS` (not a fail-open
    None), so a cli.yml-injected default for an unaccepted param would actually be
    dropped. A wrong/missing federated path returns None and silently drops nothing —
    this pins the per-sub resolution that `test_federated_list_dispatch` can't (its
    `limit` is user-supplied, so the drop branch never fires)."""
    with _fed_runtime(tmp_path) as rt:
        cmd = Command(
            verb="show",
            object="widget",
            key="show:widget",
            sdk_resource="widget",
            subpackage="alpha",
        )
        # WidgetResource.list(self, limit=None) -> {"limit"} via fedsdk.alpha's facade.
        # If _accepted_params resolved the wrong (top-level) facade it would be None.
        assert rt._accepted_params(cmd, "list") == {"limit"}


def test_federated_dry_run_serializes_via_sub_wrapper(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with _fed_runtime(tmp_path) as rt:
        import fedsdk

        calls: list[Any] = []
        monkeypatch.setattr(
            fedsdk.Client,
            "from_env",
            classmethod(lambda cls, **kw: _fake_fed_client(calls)()),
        )
        rt.run(
            "create:widget",
            path={},
            body={"name": "w1", "size": 3},
            query={},
            output="json",
            paginate_all=False,
            dry_run=True,
            verbose=False,
        )
        out = capsys.readouterr().out
        assert calls == []  # dry-run never dispatches
        # rich serialize path (sub wrapper `_serialize`) — not the bare fallback
        assert "DRY RUN" in out
        assert "create_widget" in out  # the sub wrapper's serialized request line


def test_federated_sdk_error_is_funnelled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with _fed_runtime(tmp_path) as rt:
        import fedsdk
        import fedsdk._runtime.exceptions as exc_mod

        class _Boom:
            def __init__(self) -> None:
                class _W:
                    def create(self, **kw: Any) -> Any:
                        raise exc_mod.OpenApiException("boom")

                class _Sub:
                    widget = _W()

                self.alpha = _Sub()

        monkeypatch.setattr(
            fedsdk.Client, "from_env", classmethod(lambda cls, **kw: _Boom())
        )
        with pytest.raises(SystemExit) as ei:
            rt.run(
                "create:widget",
                path={},
                body={"name": "w1", "size": 3},
                query={},
                output="json",
                paginate_all=False,
                dry_run=False,
                verbose=False,
            )
        assert ei.value.code == 1
        assert "error:" in capsys.readouterr().err


def test_sdk_exc_resolves_runtime_exceptions_per_sub(tmp_path: Path) -> None:
    """`_sdk_exc` points at the federated `_runtime.exceptions` for a sub command,
    and falls back to the bare `<pkg>.exceptions` (here absent -> Exception) for a
    single-package command."""
    with _fed_runtime(tmp_path) as rt:
        import fedsdk._runtime.exceptions as exc_mod

        fed_cmd = Command(
            verb="create",
            object="widget",
            key="create:widget",
            sdk_resource="widget",
            subpackage="alpha",
        )
        assert rt._sdk_exc(fed_cmd) is exc_mod.OpenApiException
        single_cmd = Command(
            verb="create",
            object="widget",
            key="create:widget",
            sdk_resource="widget",
            subpackage=None,
        )
        # no `fedsdk.exceptions` module -> graceful Exception fallback (unchanged)
        assert rt._sdk_exc(single_cmd) is Exception
