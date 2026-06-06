from enum import Enum


class NativeMessagingHostsControlType0Action(str, Enum):
    ALLOW = "allow"
    ALLOWADMININSTALLEDONLY = "allowAdminInstalledOnly"
    BLOCK = "block"

    def __str__(self) -> str:
        return str(self.value)
