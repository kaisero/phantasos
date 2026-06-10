class OpenApiException(Exception):  # noqa: N818
    """Base SDK exception (mirrors the real SDK)."""


class ApiException(OpenApiException):
    """HTTP API exception (mirrors the real SDK's ApiException with status/body)."""

    def __init__(self, status=None, reason=None, body=None, data=None):
        self.status = status
        self.reason = reason
        self.body = body
        self.data = data
        super().__init__(str(status))
