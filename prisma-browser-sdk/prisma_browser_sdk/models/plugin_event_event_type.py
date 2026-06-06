from enum import Enum


class PluginEventEventType(str, Enum):
    LOGINATTEMPT = "loginAttempt"
    LOGINFAIL = "loginFail"
    PASSWORDRESET = "passwordReset"
    USERREGISTRATION = "userRegistration"

    def __str__(self) -> str:
        return str(self.value)
