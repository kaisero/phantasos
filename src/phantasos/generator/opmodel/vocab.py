"""Classification vocabulary shared by opmodel, sdk, and cli (the base layer).

Lives here (not cli.ir) so the base opmodel layer never imports UP into cli,
restoring an acyclic ``opmodel -> {sdk, cli}`` layering.

``cli.ir`` keeps a BYTE-IDENTICAL copy of these three aliases rather than
importing them from here, because ``cli.ir``'s source is copied verbatim into
each generated CLI as ``_generated/spec.py`` (see ``cli.render_cli``) — a
standalone package with no ``opmodel`` to import from. The two definitions MUST
stay in sync: their values serialize into the frozen ir.json/spec.py contract.
"""

from __future__ import annotations

from typing import Literal

FlagKind = Literal["scalar", "enum", "json", "file", "id"]
Verb = Literal["create", "update", "delete", "show", "request", "load", "backup"]
SubVerb = Literal[
    "create",
    "patch",
    "put",
    "update",
    "get",
    "list",
    "delete",
    "bulk_create",
    "bulk_delete",
    "action",
]
