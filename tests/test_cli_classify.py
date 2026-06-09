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
