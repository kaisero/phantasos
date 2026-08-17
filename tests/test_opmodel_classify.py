"""Tests for opmodel.classify: pure helpers + OBJECT_OF."""

from phantasos.generator.opmodel.classify import OBJECT_OF, classify_name


def test_classify_unchanged() -> None:
    c = classify_name("create_applications")
    assert c is not None
    assert (c.verb, c.object) == ("create", "application")
    assert classify_name("suspend_devices") is None


def test_object_of_crud_only() -> None:
    assert OBJECT_OF("get_application_by_type_and_id") == "application"
    assert OBJECT_OF("delete_access_and_data_rule_by_id") == "access-and-data-rule"
    assert OBJECT_OF("suspend_devices") is None  # non-CRUD -> derived in wrapper-gen
    assert OBJECT_OF("update_device_group") is None  # PUT -> handled in wrapper-gen
    # _SKIP_FRAGMENTS guard: a `*_positions` op must NOT launder a junk object even
    # though it begins with a verb prefix (`patch_`).
    assert OBJECT_OF("patch_security_positions") is None
    assert OBJECT_OF("update_security_positions") is None
