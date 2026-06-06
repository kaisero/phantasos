from enum import Enum


class BrowserSelfProtectionWindowsDriverStatus(str, Enum):
    INACTIVE = "Inactive"
    PROTECTED = "Protected"
    UNKNOWN = "Unknown"
    UNPROTECTED = "Unprotected"
    UNPROTECTEDARMINCOMPATIBLE = "UnprotectedArmIncompatible"
    UNPROTECTEDUSERINSTALL = "UnprotectedUserInstall"

    def __str__(self) -> str:
        return str(self.value)
