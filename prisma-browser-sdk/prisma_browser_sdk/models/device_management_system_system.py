from .._lenient import LenientStrEnum


class DeviceManagementSystemSystem(LenientStrEnum):
    AD = "ad"
    AZUREAD = "azureAd"
    INTUNE = "intune"
    JAMF = "jamf"

    def __str__(self) -> str:
        return str(self.value)
