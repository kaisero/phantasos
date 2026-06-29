"""G2: the real prisma-access CLI — offline smoke + live CRUD round-trip.

End-to-end proof of the whole federated-CLI branch against the REAL, on-disk SDK
(`phantasos sdk build prisma-access`) and G1's `cli.yml` (objects + incidents only):

* the lazy composer is in the artifact — building the top-level ``Client`` with
  ``PANW_REGION`` unset must NOT raise, ``.objects`` works region-unset, and
  ``.incidents`` raises only when accessed (its ``required_for`` header);
* the federated CLI builds with ZERO unmapped non-CRUD ops (B3 fail-loud is happy);
* the built CLI imports and ``--help`` / ``which`` / ``discover`` / ``show objects
  … --help`` / federated ``request … --help`` resolve offline;
* an objects ``--dry-run`` serializes the flattened SCM body WITHOUT a region (objects
  ∉ ``X-PANW-Region.required_for``), needing no network and no credentials;
* (live, creds-gated) an ``objects address`` create → get → list → update → delete
  round-trip dispatches through ``client.objects.address.*`` and the tenant accepts it.

The whole module SKIPS cleanly when the SDK is not built (or its runtime deps are
unavailable); the live test additionally SKIPS without credentials — mirroring the
frozen SDK live oracle's guard. NOTHING here mocks the SDK/tenant boundary: the
offline checks drive the real generated CLI, and the live check hits the real tenant.
"""

from __future__ import annotations

import importlib
import json
import os
import re
import sys
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from phantasos.generator.cli.classify import build_ir
from phantasos.generator.cli.cliconfig import load_cli_config
from phantasos.generator.cli.discover import render_table
from phantasos.generator.cli.render_cli import render_cli
from phantasos.productconfig import load_product

_REQUIRED_ENV = ("CLIENT_ID", "CLIENT_SECRET", "SCOPE")
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def _parse_json(output: str) -> Any:
    """Parse the (Rich-printed) JSON a ``--output json`` command emits."""
    return json.loads(_strip_ansi(output).strip())


@pytest.fixture(scope="module")
def built_cli(tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[str, Any]]:
    """Build the federated prisma-access CLI from the ON-DISK SDK and import it.

    Skips when the SDK isn't built or its runtime deps can't be imported (so the
    offline gate stays green on a checkout that hasn't run ``sdk build``). Keeps the
    SDK + the rendered CLI on ``sys.path`` for the module so every test can drive it.
    """
    loaded = load_product("prisma-access")
    sdk = Path(loaded.output_dir)
    pkg = loaded.config.package
    if not (sdk / Path(*pkg.split("."))).joinpath("__init__.py").exists():
        pytest.skip(
            "prisma-access SDK not built (run `phantasos sdk build prisma-access`)"
        )

    cfg = load_cli_config(Path(loaded.base_dir) / "cli.yml")
    out = tmp_path_factory.mktemp("prisma_access_cli_out")

    added = [p for p in (str(out), str(sdk)) if p not in sys.path]
    for p in added:
        sys.path.insert(0, p)

    def _purge() -> None:
        for m in [
            n
            for n in sys.modules
            if n == "prisma_access_cli" or n.startswith("prisma_access_cli.")
        ]:
            del sys.modules[m]

    try:
        try:
            ir, unmapped = build_ir(pkg, sdk, cfg)
        except ImportError as exc:  # SDK present but runtime deps unavailable
            pytest.skip(f"prisma-access SDK runtime deps unavailable: {exc}")
        render_cli(
            ir,
            package="prisma_access_cli",
            out_dir=out,
            distribution="prisma-access-cli",
            auth=loaded.auth,
            errors=loaded.errors,
            default_headers=getattr(loaded.config, "default_headers", None) or None,
        )
        _purge()
        app_mod = importlib.import_module("prisma_access_cli._generated.app")
        yield {
            "app": app_mod.build_generated_app(),
            "ir": ir,
            "unmapped": unmapped,
        }
    finally:
        _purge()
        for p in added:
            if p in sys.path:
                sys.path.remove(p)


# --- the federated build is fully mapped (B3 fail-loud) ---------------------


def test_build_has_no_unmapped_ops(built_cli: dict[str, Any]) -> None:
    """G1's cli.yml maps every non-CRUD op on the enrolled subs — B3 stays loud."""
    assert built_cli["unmapped"] == []


# --- lazy composer is in the rebuilt artifact (region-unset construction) ----


def test_lazy_composer_region_unset(
    built_cli: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The composing ``Client`` builds region-unset; ``.objects`` works; only
    ``.incidents`` (its ``required_for`` header) raises, and only on access."""
    monkeypatch.delenv("PANW_REGION", raising=False)
    import prisma_access
    from prisma_access._auth import configuration_from_credentials

    cfg = configuration_from_credentials(
        client_id="x", client_secret="y", scope="tsg_id:1"
    )
    client = prisma_access.Client(cfg)  # must NOT raise region-unset (lazy)
    assert client.objects is not None  # objects needs no region
    with pytest.raises(RuntimeError, match="X-PANW-Region"):
        _ = client.incidents  # raises only here, only because region is unset


# --- offline CLI smoke (no network, no credentials) -------------------------


def test_offline_help_lists_verbs(built_cli: dict[str, Any]) -> None:
    res = CliRunner().invoke(built_cli["app"], ["--help"])
    assert res.exit_code == 0, res.output
    out = _strip_ansi(res.output)
    for verb in ("create", "show", "update", "delete", "request"):
        assert verb in out


def test_offline_which_address_resolves_to_objects(built_cli: dict[str, Any]) -> None:
    res = CliRunner().invoke(built_cli["app"], ["which", "address"])
    assert res.exit_code == 0, res.output
    out = _strip_ansi(res.output)
    assert "address" in out and "objects" in out


def test_offline_show_objects_address_help(built_cli: dict[str, Any]) -> None:
    res = CliRunner().invoke(built_cli["app"], ["show", "objects", "address", "--help"])
    assert res.exit_code == 0, res.output
    assert "--id" in _strip_ansi(res.output)


def test_offline_request_incidents_help(built_cli: dict[str, Any]) -> None:
    """The one federated non-CRUD op surfaces under `request incidents incident`."""
    res = CliRunner().invoke(built_cli["app"], ["request", "incidents", "--help"])
    assert res.exit_code == 0, res.output
    assert "incident" in _strip_ansi(res.output)


def test_offline_discover_groups_subpackages(built_cli: dict[str, Any]) -> None:
    """`cli discover` renders the federated classification table, grouped per sub."""
    table = render_table(built_cli["ir"], built_cli["unmapped"])
    assert "## objects" in table
    assert "## incidents" in table
    assert "create address" in table


def test_offline_objects_dry_run_without_region_or_creds(
    built_cli: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """An objects --dry-run serializes the flattened SCM body with NO region and NO
    credentials — proving objects ∉ region.required_for and the credential-free
    serialize seam."""
    for var in ("PANW_REGION", *_REQUIRED_ENV):
        monkeypatch.delenv(var, raising=False)
    res = CliRunner().invoke(
        built_cli["app"],
        [
            "create",
            "objects",
            "address",
            "--name",
            "phx-smoke",
            "--folder",
            "Shared",
            "--ip-netmask",
            "10.0.0.0/24",
            "--dry-run",
        ],
    )
    assert res.exit_code == 0, res.output
    out = _strip_ansi(res.output)
    assert "DRY RUN" in out
    # the lifted SCM value field (`ip_netmask`) actually serializes onto the wire
    assert "phx-smoke" in out and "10.0.0.0/24" in out
    # a clean dry-run, never a raw region/credential traceback
    assert "Traceback" not in out and "RuntimeError" not in out


# --- live CRUD round-trip (skips cleanly without credentials) ---------------


@pytest.mark.skipif(
    any(not os.environ.get(var) for var in _REQUIRED_ENV),
    reason="live tenant credentials not set: " + ", ".join(_REQUIRED_ENV),
)
def test_live_objects_address_crud_round_trip(
    built_cli: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """create → get → list → update → delete an ``objects address`` through the CLI.

    Region-unset throughout (objects need none — lazy composer): the CLI dispatches
    every step through ``client.objects.address.*`` and the real tenant accepts it.
    """
    app = built_cli["app"]
    runner = CliRunner()
    # Isolate HOME so no real ~/.prisma_access_cli env is selected; rely on the
    # ambient CLIENT_ID/CLIENT_SECRET/SCOPE (the live creds) for auth.
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("PRISMA_ACCESS_ENVIRONMENT", raising=False)
    monkeypatch.delenv("PANW_REGION", raising=False)  # objects need no region

    name = f"phx-cli-{uuid.uuid4().hex[:12]}"

    created = runner.invoke(
        app,
        [
            "create",
            "objects",
            "address",
            "--name",
            name,
            "--folder",
            "Shared",
            "--ip-netmask",
            "10.0.0.0/24",
            "--output",
            "json",
        ],
    )
    assert created.exit_code == 0, created.output
    addr = _parse_json(created.output)
    addr_id = addr["id"]

    try:
        assert addr["name"] == name
        got = runner.invoke(
            app,
            ["show", "objects", "address", "--id", addr_id, "--output", "json"],
        )
        assert got.exit_code == 0, got.output
        fetched = _parse_json(got.output)
        assert fetched["name"] == name
        assert fetched["ip_netmask"] == "10.0.0.0/24"

        listed = runner.invoke(
            app,
            ["show", "objects", "address", "--folder", "Shared", "--output", "json"],
        )
        assert listed.exit_code == 0, listed.output
        assert name in _strip_ansi(listed.output)

        updated = runner.invoke(
            app,
            [
                "update",
                "objects",
                "address",
                "--id",
                addr_id,
                "--name",
                name,
                "--folder",
                "Shared",
                "--ip-netmask",
                "10.0.0.0/25",
                "--output",
                "json",
            ],
        )
        assert updated.exit_code == 0, updated.output
        assert _parse_json(updated.output)["ip_netmask"] == "10.0.0.0/25"
    finally:
        deleted = runner.invoke(app, ["delete", "objects", "address", "--id", addr_id])
        assert deleted.exit_code == 0, deleted.output
