import prisma_browser._lenient as lenient
from prisma_browser.models.user_provider import UserProvider
from prisma_browser.models.authentication_factor_pin_code_control_pin_code_max_failed_attempts import (
    AuthenticationFactorPinCodeControlPinCodeMaxFailedAttempts as IntEnum,
)


def setup_function(_):
    lenient.UNKNOWN_ENUM_VALUES.clear()


def test_known_str_value_is_canonical():
    assert UserProvider("local") is UserProvider.LOCAL


def test_unknown_str_value_passes_through_and_records():
    v = UserProvider("scm")
    assert v.value == "scm"
    assert str(v) == "scm" or v == "scm"
    assert "scm" in lenient.UNKNOWN_ENUM_VALUES["UserProvider"]


def test_unknown_str_serializes_to_real_value():
    import json
    assert json.dumps(UserProvider("scm")) == '"scm"'


def test_unknown_int_value_passes_through():
    v = IntEnum(9999)
    assert v.value == 9999
    assert 9999 in lenient.UNKNOWN_ENUM_VALUES[IntEnum.__name__]
