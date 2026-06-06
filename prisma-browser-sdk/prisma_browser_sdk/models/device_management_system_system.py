from enum import Enum


class DeviceManagementSystemSystem(str, Enum):
    AD = "ad"
    AZUREAD = "azureAd"
    INTUNE = "intune"
    JAMF = "jamf"

    def __str__(self) -> str:
        return str(self.value)
