from enum import Enum


class ManagementSystemType(str, Enum):
    ACTIVE_DIRECTORY = "Active Directory"
    AZURE_AD = "Azure AD"
    JAMF = "Jamf"
    MICROSOFT_INTUNE = "Microsoft Intune"

    def __str__(self) -> str:
        return str(self.value)
