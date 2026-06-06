from enum import Enum


class MobileDeviceManagementSystemName(str, Enum):
    JAMF = "Jamf"
    MICROSOFT_INTUNE = "Microsoft Intune"
    OTHER = "Other"

    def __str__(self) -> str:
        return str(self.value)
