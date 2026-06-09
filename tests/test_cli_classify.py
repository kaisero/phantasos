import pytest

from phantasos.generator.cli.classify import classify_name


@pytest.mark.parametrize(
    "method,verb,obj",
    [
        ("create_application", "set", "application"),
        ("patch_application_by_type_and_id", "set", "application"),
        ("update_device_group", "set", "device-group"),
        ("delete_application_by_id", "del", "application"),
        ("bulk_delete_applications", "del", "application"),
        ("get_application_by_id", "show", "application"),
        ("list_applications", "show", "application"),
        ("list_device_groups", "show", "device-group"),
        ("bulk_create_applications", "set", "application"),
        ("create_access_and_data_rule", "set", "access-and-data-rule"),
    ],
)
def test_classify_verb_and_noun(method, verb, obj):
    c = classify_name(method)
    assert c is not None
    assert (c.verb, c.object) == (verb, obj)


@pytest.mark.parametrize(
    "method",
    [
        "update_access_and_data_positions",  # reorder, not a "position" object
        "force_reauth_devices",
        "suspend_users",
        "revoke_user_request",
        "publish_draft_configuration",
        "action_user_request",
    ],
)
def test_unmapped_returns_none(method):
    assert classify_name(method) is None


# tests/test_cli_classify.py  (append)
from phantasos.generator.cli.classify import detect_id_param
from phantasos.generator.cli.inventory import ParamInfo


def _p(name, location, required=True, enum_values=None):
    return ParamInfo(name=name, annotation="str", location=location,
                     required=required, enum_values=enum_values)


def test_detect_id_literal():
    params = [_p("id", "path")]
    assert detect_id_param(params).name == "id"


def test_detect_id_nonliteral_name():
    params = [_p("thing_id", "path")]
    assert detect_id_param(params).name == "thing_id"


def test_detect_id_ignores_discriminator_enum():
    # type is a path enum (discriminator), id is the real id
    params = [_p("type", "path", enum_values=["simple", "complex"]), _p("id", "path")]
    assert detect_id_param(params).name == "id"


def test_detect_id_none_when_no_path_id():
    params = [_p("name", "query", required=False)]
    assert detect_id_param(params) is None
