"""PR1 tests: AuthComponent base class + enforced credential_fields; scm_oauth rename.

PR2 tests: CliIR carries credential_fields; render_cli threads auth component through.
D1 tests: ConnectionField IR descriptor; render_cli threads default_headers through.
"""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from phantasos.config import BUILTIN_AUTH, AuthComponent, ScmOAuth
from phantasos.generator.cli.classify import build_cli_ir
from phantasos.generator.cli.cliconfig import CliConfig
from phantasos.generator.cli.introspect import introspect
from phantasos.generator.cli.ir import ConnectionField, CredentialField
from phantasos.generator.cli.render_cli import render_cli
from phantasos.productconfig import HeaderSpec

_FIXTURE = Path(__file__).parent / "fixtures" / "fakesdk"


def test_scm_oauth_registered_and_bakes_token_url() -> None:
    assert BUILTIN_AUTH["scm_oauth"] is ScmOAuth
    assert ScmOAuth(type="scm_oauth").token_url == "https://auth.apps.paloaltonetworks.com/oauth2/access_token"


@pytest.mark.parametrize("model", BUILTIN_AUTH.values())
def test_every_auth_component_declares_credential_fields(
    model: type[AuthComponent],
) -> None:
    fields = model(type="x").credential_fields()
    assert fields and all(isinstance(f, CredentialField) for f in fields)


def test_contract_enforced_at_definition() -> None:
    with pytest.raises(TypeError, match="must override credential_fields"):

        class BadAuth(AuthComponent):
            pass


# ---------------------------------------------------------------------------
# PR2: generic auth-component carrier on CliIR
# ---------------------------------------------------------------------------


def test_arbitrary_auth_component_drives_credential_fields(tmp_path: Path) -> None:
    """A stub auth component (not ScmOAuth) drives credential_fields in ir.json."""

    class StubAuth(AuthComponent):
        type: str = "stub"

        def credential_fields(self) -> list[CredentialField]:
            return [
                CredentialField(name="api_key_id", env_var="API_KEY_ID"),
                CredentialField(name="api_key", env_var="API_KEY", secret=True),
                CredentialField(name="base_url", env_var="BASE_URL", client_kwarg="host"),
            ]

    ir = build_cli_ir(introspect("fakesdk", _FIXTURE), CliConfig())[0]
    render_cli(
        ir,
        package="fakesdk_cli",
        out_dir=tmp_path,
        env_prefix="FAKESDK",
        auth=StubAuth(),
    )

    emitted = json.loads((tmp_path / "fakesdk_cli" / "_generated" / "ir.json").read_text())
    names = [f["name"] for f in emitted["credential_fields"]]
    assert names == ["api_key_id", "api_key", "base_url"]
    assert "client_id" not in names  # no SCM bleed-through
    secret = {f["name"]: f["secret"] for f in emitted["credential_fields"]}
    assert secret["api_key"] is True


def test_no_auth_gives_empty_credential_fields(tmp_path: Path) -> None:
    """No auth kwarg -> ir.json has an empty credential_fields list."""

    ir = build_cli_ir(introspect("fakesdk", _FIXTURE), CliConfig())[0]
    render_cli(ir, package="fakesdk_cli", out_dir=tmp_path, env_prefix="FAKESDK")

    emitted = json.loads((tmp_path / "fakesdk_cli" / "_generated" / "ir.json").read_text())
    assert emitted["credential_fields"] == []


# ---------------------------------------------------------------------------
# D1: ConnectionField IR descriptor from default_headers
# ---------------------------------------------------------------------------


def test_connection_fields_enriched_from_default_headers(tmp_path: Path) -> None:
    """render_cli with default_headers -> ir.json carries connection_fields."""
    default_headers = {
        "X-PANW-Region": HeaderSpec(env="PANW_REGION", required_for=["incidents"]),
        "prisma-tenant": HeaderSpec(env="PRISMA_TENANT", required=True),
    }
    ir = build_cli_ir(introspect("fakesdk", _FIXTURE), CliConfig())[0]
    render_cli(
        ir,
        package="fakesdk_cli",
        out_dir=tmp_path,
        env_prefix="FAKESDK",
        default_headers=default_headers,
    )

    emitted = json.loads((tmp_path / "fakesdk_cli" / "_generated" / "ir.json").read_text())
    cf = emitted["connection_fields"]
    assert len(cf) == 2
    by_name = {f["name"]: f for f in cf}
    assert by_name["X-PANW-Region"]["env"] == "PANW_REGION"
    assert by_name["X-PANW-Region"]["required_for"] == ["incidents"]
    assert by_name["X-PANW-Region"]["required"] is False
    assert by_name["prisma-tenant"]["env"] == "PRISMA_TENANT"
    assert by_name["prisma-tenant"]["required"] is True
    assert by_name["prisma-tenant"]["required_for"] == []


def test_no_default_headers_gives_empty_connection_fields(tmp_path: Path) -> None:
    """No default_headers -> ir.json has empty connection_fields."""
    ir = build_cli_ir(introspect("fakesdk", _FIXTURE), CliConfig())[0]
    render_cli(ir, package="fakesdk_cli", out_dir=tmp_path, env_prefix="FAKESDK")

    emitted = json.loads((tmp_path / "fakesdk_cli" / "_generated" / "ir.json").read_text())
    assert emitted["connection_fields"] == []


def test_connection_field_model() -> None:
    """ConnectionField is a frozen pydantic descriptor."""
    cf = ConnectionField(name="X-Foo", env="FOO_VAR", required_for=["bar"])
    assert cf.name == "X-Foo"
    assert cf.env == "FOO_VAR"
    assert cf.required is False
    assert cf.required_for == ["bar"]
    # frozen — pydantic raises ValidationError on attribute assignment
    with pytest.raises(ValidationError):
        cf.name = "mutate"
