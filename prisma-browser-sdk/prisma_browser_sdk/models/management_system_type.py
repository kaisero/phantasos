from .._lenient import LenientStrEnum


class ManagementSystemType(LenientStrEnum):
    ACTIVE_DIRECTORY = "Active Directory"
    AZURE_AD = "Azure AD"
    JAMF = "Jamf"
    MICROSOFT_INTUNE = "Microsoft Intune"

    def __str__(self) -> str:
        return str(self.value)
