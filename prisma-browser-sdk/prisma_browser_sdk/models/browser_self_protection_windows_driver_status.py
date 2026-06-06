from .._lenient import LenientStrEnum


class BrowserSelfProtectionWindowsDriverStatus(LenientStrEnum):
    INACTIVE = "Inactive"
    PROTECTED = "Protected"
    UNKNOWN = "Unknown"
    UNPROTECTED = "Unprotected"
    UNPROTECTEDARMINCOMPATIBLE = "UnprotectedArmIncompatible"
    UNPROTECTEDUSERINSTALL = "UnprotectedUserInstall"

    def __str__(self) -> str:
        return str(self.value)
