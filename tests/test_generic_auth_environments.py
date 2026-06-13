"""PR1 tests: AuthComponent base class + enforced credential_fields; scm_oauth rename."""

import pytest
from phantasos.config import ScmOAuth, AuthComponent, BUILTIN_AUTH
from phantasos.generator.cli.ir import CredentialField


def test_scm_oauth_registered_and_bakes_token_url():
    assert BUILTIN_AUTH["scm_oauth"] is ScmOAuth
    assert ScmOAuth(type="scm_oauth").token_url == \
        "https://auth.apps.paloaltonetworks.com/oauth2/access_token"


@pytest.mark.parametrize("model", BUILTIN_AUTH.values())
def test_every_auth_component_declares_credential_fields(model):
    fields = model(type="x").credential_fields()
    assert fields and all(isinstance(f, CredentialField) for f in fields)


def test_contract_enforced_at_definition():
    with pytest.raises(TypeError, match="must override credential_fields"):
        class BadAuth(AuthComponent):
            pass
