from .._lenient import LenientStrEnum


class PluginEventEventType(LenientStrEnum):
    LOGINATTEMPT = "loginAttempt"
    LOGINFAIL = "loginFail"
    PASSWORDRESET = "passwordReset"
    USERREGISTRATION = "userRegistration"

    def __str__(self) -> str:
        return str(self.value)
