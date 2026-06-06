from .._lenient import LenientStrEnum


class NativeMessagingHostsControlType0Action(LenientStrEnum):
    ALLOW = "allow"
    ALLOWADMININSTALLEDONLY = "allowAdminInstalledOnly"
    BLOCK = "block"

    def __str__(self) -> str:
        return str(self.value)
