from pathlib import Path
from typing import cast

import pytest

from phantasos.generator.cli.cliconfig import CliDocsConfig
from phantasos.generator.cli.docs import CONTEXT_KEYS, build_cli_docs_context
from phantasos.generator.cli.ir import CliIR, Command, CredentialField, Flag, FlagKind

# _command_view is private but imported deliberately: the drift guard (D2) must compare
# the docs flag set against the REAL emitted-CLI grouping. Update this if it's renamed.
from phantasos.generator.cli.render_cli import _command_view


def _flag(
    name: str,
    *,
    py_type: str = "str",
    kind: FlagKind = "scalar",
    required: bool = True,
    choices: list[str] | None = None,
) -> Flag:
    return Flag(
        name=name,
        param=name.lstrip("-").replace("-", "_"),
        py_type=py_type,
        kind=kind,
        required=required,
        choices=choices,
    )


def _ir() -> CliIR:
    return CliIR(
        sdk_package="acme",
        sdk_version="1",
        credential_fields=[CredentialField(name="token", env_var="ACME_TOKEN")],
        commands=[
            Command(
                verb="create",
                object="widget",
                key="create:widget",
                sdk_resource="widgets",
                summary="Create a widget.",
                body_flags=[_flag("--name")],
            ),
            Command(
                verb="show",
                object="widget",
                key="show:widget",
                sdk_resource="widgets",
                summary="List widgets.",
                paginated=True,
                query_flags=[
                    _flag("--limit", py_type="int", required=False),
                    _flag("--name", required=False),
                ],
            ),
        ],
    )


def _objects(ctx: dict[str, object]) -> list[dict[str, object]]:
    return cast("list[dict[str, object]]", ctx["objects"])


def _commands(obj: dict[str, object]) -> list[dict[str, object]]:
    return cast("list[dict[str, object]]", obj["commands"])


def _flag_names(flags: object) -> set[object]:
    return {cast("dict[str, object]", f)["name"] for f in cast("list[object]", flags)}


def test_context_groups_by_object_and_gates_guides() -> None:
    ctx = build_cli_docs_context(
        _ir(),
        CliDocsConfig(showcase_object="widget"),
        distribution="acmecli",
        site_name="Acme CLI",
    )
    assert ctx["site_name"] == "Acme CLI"
    assert [o["object"] for o in _objects(ctx)] == ["widget"]
    assert ctx["has_auth"] is True
    assert ctx["show_pagination_guide"] is True
    create = _commands(_objects(ctx)[0])[0]
    assert create["usage"] == "create widget"  # lean heading: no dist, no [OPTIONS]
    assert (
        create["example"] == 'acmecli create widget --name "example"'
    )  # full runnable
    showcase = cast("dict[str, object]", ctx["showcase"])
    assert showcase["object"] == "widget"
    assert showcase["has_create"] is True
    assert showcase["variant"] is None  # not configured -> None


def test_showcase_variant_threaded() -> None:
    ir = CliIR(
        sdk_package="acme",
        sdk_version="1",
        commands=[
            Command(
                verb="create",
                object="gizmo",
                variant="simple",
                key="create:gizmo:simple",
                sdk_resource="gizmos",
                body_flags=[_flag("--name")],
            )
        ],
    )
    ctx = build_cli_docs_context(
        ir,
        CliDocsConfig(showcase_object="gizmo", showcase_variant="simple"),
        distribution="acmecli",
        site_name="x",
    )
    showcase = cast("dict[str, object]", ctx["showcase"])
    assert showcase["variant"] == "simple"


def test_context_key_set_is_the_documented_contract() -> None:
    ctx = build_cli_docs_context(
        _ir(),
        CliDocsConfig(showcase_object="widget"),
        distribution="acmecli",
        site_name="x",
    )
    assert set(ctx) == CONTEXT_KEYS


def test_docs_flags_match_emitted_help() -> None:
    """D2 guard: the reference flag set per command equals the emitted CLI's."""
    ir = _ir()
    variant_groups: set[tuple[str, str]] = {
        (c.verb, c.object) for c in ir.commands if c.variant or c.action
    }
    ctx = build_cli_docs_context(
        ir,
        CliDocsConfig(showcase_object="widget"),
        distribution="acmecli",
        site_name="x",
    )
    docs_by_key = {
        cast("str", cmd["key"]): cmd for o in _objects(ctx) for cmd in _commands(o)
    }
    for c in ir.commands:
        emitted = _flag_names(_command_view(c, variant_groups)["all_flags"])
        d = docs_by_key[c.key]
        rendered: set[object] = set()
        for grp in ("path_flags", "body_flags", "filter_flags", "pagination_flags"):
            rendered |= _flag_names(d[grp])
        assert rendered == emitted, c.key


def test_query_flags_split_filters_vs_pagination() -> None:
    """D16/D9 guard: the Filters/Pagination split (not just membership) is correct."""
    ctx = build_cli_docs_context(
        _ir(),
        CliDocsConfig(showcase_object="widget"),
        distribution="acmecli",
        site_name="x",
    )
    show = next(
        c for o in _objects(ctx) for c in _commands(o) if c["key"] == "show:widget"
    )
    assert _flag_names(show["pagination_flags"]) == {"--limit"}
    assert _flag_names(show["filter_flags"]) == {"--name"}


def test_show_pagination_guide_false_without_paginated_command() -> None:
    ir = CliIR(
        sdk_package="acme",
        sdk_version="1",
        commands=[
            Command(
                verb="create",
                object="widget",
                key="create:widget",
                sdk_resource="widgets",
                body_flags=[_flag("--name")],
            )
        ],
    )
    ctx = build_cli_docs_context(
        ir,
        CliDocsConfig(showcase_object="widget"),
        distribution="acmecli",
        site_name="x",
    )
    assert ctx["show_pagination_guide"] is False


def test_command_description_strips_sphinx_block() -> None:
    # openapi-generator appends a :param:/:type:/:return: block; keep only the prose.
    ir = CliIR(
        sdk_package="acme",
        sdk_version="1",
        commands=[
            Command(
                verb="show",
                object="widget",
                key="show:widget",
                sdk_resource="widgets",
                summary="Get a widget.",
                description=(
                    "Returns a specific widget by id.\n\n"
                    ":param id: The widget ID. (required)\n"
                    ":type id: str\n"
                    ":param _request_timeout: timeout setting for this request.\n"
                    ":return: Returns the result object."
                ),
            )
        ],
    )
    ctx = build_cli_docs_context(
        ir,
        CliDocsConfig(showcase_object="widget"),
        distribution="acmecli",
        site_name="x",
    )
    cmd = _commands(_objects(ctx)[0])[0]
    # Exact equality proves the entire :param/:type/:return block — including the
    # SDK-internal _request_timeout noise — was stripped, keeping only the prose.
    assert cmd["description"] == "Returns a specific widget by id."


def test_unknown_example_key_raises() -> None:
    with pytest.raises(ValueError, match="matching no command"):
        build_cli_docs_context(
            _ir(),
            CliDocsConfig(showcase_object="widget", examples={"create:nope": "x"}),
            distribution="acmecli",
            site_name="x",
        )


def test_example_override_applied_for_valid_key() -> None:
    ctx = build_cli_docs_context(
        _ir(),
        CliDocsConfig(
            showcase_object="widget",
            examples={"create:widget": "acmecli create widget --name Engineering"},
        ),
        distribution="acmecli",
        site_name="x",
    )
    create = next(
        c for o in _objects(ctx) for c in _commands(o) if c["key"] == "create:widget"
    )
    assert create["example"] == "acmecli create widget --name Engineering"


def test_showcase_variant_must_be_a_create_variant() -> None:
    # A variant that exists only on a non-create verb must NOT pass validation: the
    # Quickstart shows the create example, so it would otherwise go silently missing.
    ir = CliIR(
        sdk_package="acme",
        sdk_version="1",
        commands=[
            Command(
                verb="update",
                object="gizmo",
                variant="simple",
                key="update:gizmo:simple",
                sdk_resource="gizmos",
                path_params=[_flag("--id")],
            )
        ],
    )
    with pytest.raises(ValueError, match="not a create variant"):
        build_cli_docs_context(
            ir,
            CliDocsConfig(showcase_object="gizmo", showcase_variant="simple"),
            distribution="acmecli",
            site_name="x",
        )


def test_common_flags_match_emitted_template() -> None:
    """Guard: the static _COMMON_FLAGS set matches the Common help-panel flags emitted
    in commands.py.jinja, so the reference 'Common options' section can't drift."""
    from phantasos.generator.cli.docs import _COMMON_FLAGS

    tmpl = (
        Path(__file__).parent.parent.parent
        / "src/phantasos/generator/cli/templates/_generated/commands.py.jinja"
    ).read_text()
    assert tmpl.count('rich_help_panel="Common"') == len(_COMMON_FLAGS)
    for f in _COMMON_FLAGS:
        assert f'"{f["name"]}' in tmpl, f["name"]


def test_flag_help_pipe_escaped_for_markdown_table() -> None:
    flag = Flag(
        name="--mode",
        param="mode",
        py_type="str",
        kind="scalar",
        required=False,
        help="pick a | b\nor c",
    )
    ir = CliIR(
        sdk_package="acme",
        sdk_version="1",
        commands=[
            Command(
                verb="create",
                object="widget",
                key="create:widget",
                sdk_resource="widgets",
                body_flags=[flag],
            )
        ],
    )
    ctx = build_cli_docs_context(
        ir,
        CliDocsConfig(showcase_object="widget"),
        distribution="acmecli",
        site_name="x",
    )
    row = cast("list[dict[str, object]]", _commands(_objects(ctx)[0])[0]["body_flags"])[
        0
    ]
    assert row["help"] == "pick a \\| b or c"  # pipe escaped, newline -> space


def test_unknown_showcase_object_raises() -> None:
    with pytest.raises(ValueError, match="not a CLI object"):
        build_cli_docs_context(
            _ir(),
            CliDocsConfig(showcase_object="nope"),
            distribution="acmecli",
            site_name="x",
        )


def test_unknown_showcase_variant_raises() -> None:
    ir = CliIR(
        sdk_package="acme",
        sdk_version="1",
        commands=[
            Command(
                verb="create",
                object="gizmo",
                variant="simple",
                key="create:gizmo:simple",
                sdk_resource="gizmos",
                body_flags=[_flag("--name")],
            )
        ],
    )
    with pytest.raises(ValueError, match="not a create variant"):
        build_cli_docs_context(
            ir,
            CliDocsConfig(showcase_object="gizmo", showcase_variant="nope"),
            distribution="acmecli",
            site_name="x",
        )
