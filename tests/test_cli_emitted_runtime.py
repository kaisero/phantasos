import importlib
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest


def test_runtime_create_vs_patch(
    fake_client: Callable[[list[Any]], tuple[Any, type]],
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    calls: list[Any] = []
    facade, fake_cls = fake_client(calls)
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: fake_cls()))

    rt.run(
        "create:widget",
        path={},
        body={"name": "foo", "priority": 1},
        query={},
        output="json",
        paginate_all=False,
        dry_run=False,
        verbose=False,
    )
    rt.run(
        "update:widget",
        path={"id": "w9"},
        body={"name": "bar"},
        query={},
        output="json",
        paginate_all=False,
        dry_run=False,
        verbose=False,
    )
    # Wrapper surface: clean verb on the `widget` object; PATCH backs `update`.
    assert calls[0][0] == "create"
    assert calls[1][0] == "update" and calls[1][1].get("id") == "w9"


def test_runtime_variant_wraps_body_and_fills_type(
    fake_client: Callable[[list[Any]], tuple[Any, type]],
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    import fakesdk.models as models

    calls: list[Any] = []
    facade, fake_cls = fake_client(calls)
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: fake_cls()))

    rt.run(
        "create:gizmo:simple",
        path={},
        body={"name": "x"},
        query={},
        output="json",
        paginate_all=False,
        dry_run=False,
        verbose=False,
    )
    name, kw = calls[0]
    assert name == "create"  # wrapper clean verb
    assert kw["type"] == "simple"  # H4: variant fills the path param
    wrapped = kw["body"]  # wrapper takes the request body under `body`
    assert isinstance(wrapped, models.CreateGizmoInput)  # H3: oneOf wrapper
    assert isinstance(wrapped.actual_instance, models.SimpleGizmoInput)
    assert wrapped.actual_instance.name == "x"


def test_runtime_dry_run_does_not_call(
    fake_client: Callable[[list[Any]], tuple[Any, type]],
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    calls: list[Any] = []
    facade, fake_cls = fake_client(calls)
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: fake_cls()))
    rt.run(
        "create:widget",
        path={},
        body={"name": "x", "priority": 1},
        query={},
        output="json",
        paginate_all=False,
        dry_run=True,
        verbose=False,
    )
    assert calls == []
    assert "create:widget" in capsys.readouterr().out


def test_runtime_friendly_error_on_sdk_exception(
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    import fakesdk.exceptions as exc_mod
    import fakesdk.extras.facade as facade

    class _Boom:
        widget = None

        def __init__(self) -> None:
            class _W:
                def create(self, **kw: Any) -> Any:
                    raise exc_mod.OpenApiException("boom")

            self.widget = _W()

    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: _Boom()))
    import pytest as _pytest

    with _pytest.raises(SystemExit) as ei:
        rt.run(
            "create:widget",
            path={},
            body={"name": "x", "priority": 1},
            query={},
            output="json",
            paginate_all=False,
            dry_run=False,
            verbose=False,
        )
    assert ei.value.code == 1
    assert "error:" in capsys.readouterr().err


def test_update_uses_patch(
    fake_client: Callable[[list[Any]], tuple[Any, type]],
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # `update X --id` dispatches to the PATCH binding (PUT update_* is deferred).
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    calls: list[Any] = []
    facade, fake_cls = fake_client(calls)
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: fake_cls()))
    rt.run(
        "update:widget",
        path={"id": "w1"},
        body={"name": "n"},
        query={},
        output="json",
        paginate_all=False,
        dry_run=False,
        verbose=False,
    )
    assert calls[0][0] == "update"  # PATCH backs `update` (PUT replace deferred)


def test_create_without_id_creates(
    fake_client: Callable[[list[Any]], tuple[Any, type]],
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    calls: list[Any] = []
    facade, fake_cls = fake_client(calls)
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: fake_cls()))
    rt.run(
        "create:widget",
        path={},
        body={"name": "n", "priority": 1},
        query={},
        output="json",
        paginate_all=False,
        dry_run=False,
        verbose=False,
    )
    assert calls[0][0] == "create"


def test_cli_runner_show_create_delete(
    fake_client: Callable[[list[Any]], tuple[Any, type]],
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    calls: list[Any] = []
    _, fake_client_cls = fake_client(calls)
    import fakesdk.extras.facade as facade

    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: fake_client_cls()))

    r = CliRunner()
    res1 = r.invoke(main.app, ["show", "widget", "--output", "json"])
    assert res1.exit_code == 0
    res2 = r.invoke(main.app, ["show", "widget", "--id", "w1", "--output", "json"])
    assert res2.exit_code == 0
    res3 = r.invoke(
        main.app,
        ["create", "widget", "--name", "foo", "--priority", "1", "--output", "json"],
    )
    assert res3.exit_code == 0
    res4 = r.invoke(main.app, ["delete", "widget", "--id", "w1", "--output", "json"])
    assert res4.exit_code == 0

    # All four commands dispatch on the `widget` wrapper via its clean verbs.
    kinds = [c[0] for c in calls]
    assert "list" in kinds and "get" in kinds
    assert "create" in kinds and "delete" in kinds


def test_cli_runner_variant_and_nonvariant_under_object(
    fake_client: Callable[[list[Any]], tuple[Any, type]],
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade
    import fakesdk.models as models

    calls: list[Any] = []
    _, fake_client_cls = fake_client(calls)
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: fake_client_cls()))

    r = CliRunner()
    # variant create: create gizmo simple (create_gizmo is variant-mapped)
    res = r.invoke(main.app, ["create", "gizmo", "simple", "--name", "g1", "--output", "json"])
    assert res.exit_code == 0, res.output
    # non-variant patch under the update verb: update gizmo (patch_gizmo, no variant)
    res2 = r.invoke(
        main.app,
        ["update", "gizmo", "--id", "z9", "--name", "g2", "--output", "json"],
    )
    assert res2.exit_code == 0, res2.output

    # Both commands dispatch on the `gizmo` wrapper; PATCH backs `update`.
    names = [c[0] for c in calls]
    assert "create" in names  # from `create gizmo simple`
    assert "update" in names  # from `update gizmo` (PATCH)
    create_call = next(kw for n, kw in calls if n == "create")
    assert create_call["type"] == "simple"
    assert isinstance(create_call["body"], models.CreateGizmoInput)


def test_runtime_coerces_int_query(
    fake_client: Callable[[list[Any]], tuple[Any, type]],
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    calls: list[Any] = []
    _, fake_client_cls = fake_client(calls)
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: fake_client_cls()))
    res = CliRunner().invoke(main.app, ["show", "widget", "--limit", "50", "--output", "json"])
    assert res.exit_code == 0, res.output
    _, kw = next((n, k) for n, k in calls if n == "list")
    assert kw.get("limit") == 50 and isinstance(kw["limit"], int)  # coerced str->int


def test_bool_body_flag_accepts_value_and_coerces(
    fake_client: Callable[[list[Any]], tuple[Any, type]],
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A settable bool field takes a VALUE (--enabled true|false), like every other
    # field — NOT a Typer on/off flag. The string is coerced to a real bool before
    # the model is built. (Regression: native `bool` made Typer reject the value as
    # an unexpected extra argument.)
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    calls: list[Any] = []
    _, fake_client_cls = fake_client(calls)
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: fake_client_cls()))
    r = CliRunner()
    for raw, expected in [("true", True), ("false", False)]:
        calls.clear()
        res = r.invoke(
            main.app,
            [
                "create",
                "widget",
                "--name",
                "w",
                "--priority",
                "1",
                "--enabled",
                raw,
                "--output",
                "json",
            ],
        )
        assert res.exit_code == 0, res.output
        _, kw = next((n, k) for n, k in calls if n == "create")
        body = kw["body"]
        assert body.enabled is expected  # coerced str -> real bool


def test_bool_body_flag_rejects_non_bool_value(
    fake_client: Callable[[list[Any]], tuple[Any, type]],
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # An unparseable bool errors cleanly (named flag, nonzero exit) — it must NOT be
    # silently coerced to False, nor escape as a raw traceback.
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    _, fake_client_cls = fake_client([])
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: fake_client_cls()))
    res = CliRunner().invoke(
        main.app,
        ["create", "widget", "--name", "w", "--priority", "1", "--enabled", "maybe"],
    )
    assert res.exit_code != 0
    # no traceback
    assert res.exception is None or isinstance(res.exception, SystemExit)
    assert "enabled" in res.stderr


def test_invalid_json_flag_reports_clean_error(
    fake_client: Callable[[list[Any]], tuple[Any, type]],
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Invalid JSON to a JSON-string flag (e.g. --spec / --urls) reports a clean,
    # flag-named error instead of dumping a raw JSONDecodeError traceback.
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    _, fake_client_cls = fake_client([])
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: fake_client_cls()))
    res = CliRunner().invoke(
        main.app,
        ["create", "widget", "--name", "w", "--priority", "1", "--spec", "notjson"],
    )
    assert res.exit_code != 0
    # no traceback
    assert res.exception is None or isinstance(res.exception, SystemExit)
    assert "spec" in res.stderr


def test_runtime_json_error_example_minimal_and_debug_full(
    fake_client: Callable[[list[Any]], tuple[Any, type]],
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    _, fake_client_cls = fake_client([])
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: fake_client_cls()))
    argv = [
        "create",
        "widget",
        "--name",
        "w",
        "--priority",
        "1",
        "--profile",
        "notjson",
    ]

    # default level → MINIMAL non-empty skeleton: first member (contact) + its
    # required field; the OPTIONAL `tags` is omitted.
    res = CliRunner().invoke(main.app, argv)
    assert res.exit_code != 0
    assert res.exception is None or isinstance(res.exception, SystemExit)
    assert "contact" in res.stderr  # registry skeleton, not {}
    assert "'{}'" not in res.stderr  # never the broken empty fallback
    assert "tags" not in res.stderr  # optional field absent at minimal

    # debug level → FULL skeleton includes optional fields (e.g. tags). Config is
    # cached at import; set env THEN clear the cache before re-invoking (CLAUDE.md).
    monkeypatch.setenv("FAKESDK_LOGGING_LEVEL", "debug")
    cfg = importlib.import_module("fakesdk_cli._generated.config")
    cfg.load_config.cache_clear()
    res2 = CliRunner().invoke(main.app, argv)
    assert "tags" in res2.stderr  # optional field => full skeleton only


def test_runtime_anonymous_json_error_keeps_keyvalue_example(
    fake_client: Callable[[list[Any]], tuple[Any, type]],
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # D11: a json flag with NO model_ref (--spec: Optional[dict]) keeps the live
    # `{"key": "value"}` fallback — it must NOT regress to an empty/missing example.
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    _, fake_client_cls = fake_client([])
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: fake_client_cls()))
    res = CliRunner().invoke(
        main.app,
        ["create", "widget", "--name", "w", "--priority", "1", "--spec", "notjson"],
    )
    assert res.exit_code != 0
    assert "key" in res.stderr and "value" in res.stderr


def test_cli_runner_request_actions(
    fake_client: Callable[[list[Any]], tuple[Any, type]],
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    calls: list[Any] = []
    _, fake_client_cls = fake_client(calls)
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: fake_client_cls()))

    r = CliRunner()
    # request is a verb group
    assert "request" in r.invoke(main.app, ["--help"]).output
    res = r.invoke(
        main.app,
        [
            "request",
            "widget",
            "suspend",
            "--name",
            "W",
            "--priority",
            "1",
            "--output",
            "json",
        ],
    )
    assert res.exit_code == 0, res.output
    res2 = r.invoke(
        main.app,
        [
            "request",
            "widget",
            "revoke",
            "--id",
            "W9",
            "--name",
            "X",
            "--priority",
            "1",
            "--output",
            "json",
        ],
    )
    assert res2.exit_code == 0, res2.output

    # request actions dispatch on the `widget` wrapper via their clean verbs.
    names = [c[0] for c in calls]
    assert "suspend" in names
    assert "revoke" in names
    revoke_call = next(kw for n, kw in calls if n == "revoke")
    assert revoke_call.get("id") == "W9"


def test_cli_runner_show_defaults_to_json(
    fake_client: Callable[[list[Any]], tuple[Any, type]],
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import fakesdk.extras.facade as facade
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")

    calls: list[Any] = []
    _, fake_client_cls = fake_client(calls)
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: fake_client_cls()))

    res = CliRunner().invoke(main.app, ["show", "widget", "--id", "w1"])  # NO --output
    assert res.exit_code == 0, res.output
    assert '"id"' in res.output  # default JSON output
    assert "WidgetsApi" not in res.output and "object at 0x" not in res.output


def test_create_missing_required_errors_cleanly(emitted: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: object()))
    res = CliRunner().invoke(main.app, ["create", "widget"])  # missing required --name
    assert res.exit_code != 0 and ("Missing option" in res.output or "required" in res.output.lower())


def test_update_requires_id(emitted: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: object()))
    res = CliRunner().invoke(main.app, ["update", "widget", "--name", "x"])  # no --id
    assert res.exit_code != 0
    assert "--id" in res.output or "id" in res.output.lower()


def test_update_body_fields_optional(
    fake_client: Callable[[list[Any]], tuple[Any, type]],
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    calls: list[Any] = []
    _, fake_client_cls = fake_client(calls)
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: fake_client_cls()))
    res = CliRunner().invoke(main.app, ["update", "widget", "--id", "w1", "--output", "json"])
    assert res.exit_code == 0, res.output  # no required body flags
    assert any(n == "update" for n, _ in calls)  # PATCH backs `update`


def test_delete_requires_id(emitted: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: object()))
    res = CliRunner().invoke(main.app, ["delete", "widget"])  # no --id
    assert res.exit_code != 0


def test_injected_defaults_not_sent_to_get_binding(emitted: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from typer.testing import CliRunner

    app_mod = importlib.import_module("fakesdk_cli._generated.app")
    rt = importlib.import_module("fakesdk_cli._generated.runtime")

    calls: list[Any] = []

    class _W:  # STRICT get signature, like the real SDK's wrapper methods
        def get(self, id: str, configuration_version: Any = None) -> dict[str, Any]:
            calls.append({"id": id, "configuration_version": configuration_version})
            return {"id": id, "name": "x"}

        def list(self, *, all_pages: bool = False, **kw: Any) -> list[Any]:
            calls.append(kw)
            return []

    class _Client:
        widget = _W()

    monkeypatch.setattr(rt, "_client", lambda **kw: _Client())
    runner = CliRunner()

    # get binding: the injected name/limit defaults must NOT reach the call
    res = runner.invoke(app_mod.build_generated_app(), ["show", "widget", "--id", "w1"])
    assert res.exit_code == 0, res.output
    assert calls[-1] == {"id": "w1", "configuration_version": None}

    # list binding still receives the defaults
    res = runner.invoke(app_mod.build_generated_app(), ["show", "widget"])
    assert res.exit_code == 0, res.output
    assert calls[-1] == {"name": "gadget", "limit": 50}


def test_show_id_only_reports_no_list_operation(emitted: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A show command backed only by get-by-id (no list) reports a clear
    'no list operation' error with an --id hint, not the generic no-match.
    Fails at _pick_binding before any client is constructed -> no fake facade."""
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    with pytest.raises(SystemExit) as exc:
        rt.run(
            "show:thing",
            path={},
            body={},
            query={},
            output="json",
            paginate_all=False,
            dry_run=False,
            verbose=False,
        )
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "has no list operation" in err
    assert "--id" in err


def test_show_id_only_with_id_still_dispatches_get(
    fake_client: Callable[[list[Any]], tuple[Any, type]],
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Positive control: the get-by-id path is unaffected — `show thing --id t1`
    still dispatches get_thing(thing_id="t1")."""
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    calls: list[Any] = []
    facade, fake_cls = fake_client(calls)
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: fake_cls()))
    rt.run(
        "show:thing",
        path={"thing_id": "t1"},
        body={},
        query={},
        output="json",
        paginate_all=False,
        dry_run=False,
        verbose=False,
    )
    assert calls and calls[0][0] == "get"  # wrapper clean verb
    assert calls[0][1].get("thing_id") == "t1"
