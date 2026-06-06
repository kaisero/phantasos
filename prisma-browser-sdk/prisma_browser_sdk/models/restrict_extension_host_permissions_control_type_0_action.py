from .._lenient import LenientStrEnum


class RestrictExtensionHostPermissionsControlType0Action(LenientStrEnum):
    DISABLE = "disable"
    ENABLE = "enable"
    ENABLEFORSPECIFICDOMAINS = "enableForSpecificDomains"

    def __str__(self) -> str:
        return str(self.value)
