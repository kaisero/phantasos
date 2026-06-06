from prisma_browser.extras import error_message, is_rate_limited
from prisma_browser.extras.errors import ApiException


def _exc(status, body):
    e = ApiException(status=status); e.body = body; e.reason = "X"; return e


def test_error_message_nested():
    assert error_message(_exc(400, '{"error":{"code":"VALIDATION_ERROR","message":"bad"}}')) == "VALIDATION_ERROR: bad"


def test_error_message_falls_back_to_reason():
    assert error_message(_exc(404, "")) == "X"


def test_is_rate_limited():
    assert is_rate_limited(_exc(429, "")) and not is_rate_limited(_exc(404, ""))
