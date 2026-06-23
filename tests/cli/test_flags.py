from phantasos.generator.cli.flags import dedupe_flags, leaf, query_panel
from phantasos.generator.cli.ir import Command, Flag


def _f(name: str, *, required: bool = True) -> Flag:
    return Flag(
        name=f"--{name}", param=name, py_type="str", kind="scalar", required=required
    )


def test_query_panel_splits_pagination_from_filters() -> None:
    assert query_panel(_f("limit")) == "Pagination"
    assert query_panel(_f("name")) == "Filters"


def test_leaf_prefers_variant_then_action() -> None:
    assert (
        leaf(
            Command(
                verb="create", object="g", variant="simple", key="k", sdk_resource="g"
            )
        )
        == "simple"
    )
    assert (
        leaf(
            Command(
                verb="request", object="w", action="suspend", key="k", sdk_resource="w"
            )
        )
        == "suspend"
    )
    assert leaf(Command(verb="show", object="w", key="k", sdk_resource="w")) is None


def test_dedupe_flags_path_then_body_wins() -> None:
    c = Command(
        verb="update",
        object="w",
        key="k",
        sdk_resource="w",
        path_params=[_f("id"), _f("type")],
        body_flags=[_f("type"), _f("name")],  # 'type' shadows the path param
        query_flags=[_f("name"), _f("limit")],  # 'name' shadows the body flag
    )
    body, query = dedupe_flags(c)
    assert [f.param for f in body] == ["name"]
    assert [f.param for f in query] == ["limit"]
