from .._lenient import LenientStrEnum


class MobileDeviceManagementSystemName(LenientStrEnum):
    JAMF = "Jamf"
    MICROSOFT_INTUNE = "Microsoft Intune"
    OTHER = "Other"

    def __str__(self) -> str:
        return str(self.value)
