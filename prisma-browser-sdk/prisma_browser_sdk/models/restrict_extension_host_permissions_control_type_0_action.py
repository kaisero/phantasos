from enum import Enum


class RestrictExtensionHostPermissionsControlType0Action(str, Enum):
    DISABLE = "disable"
    ENABLE = "enable"
    ENABLEFORSPECIFICDOMAINS = "enableForSpecificDomains"

    def __str__(self) -> str:
        return str(self.value)
