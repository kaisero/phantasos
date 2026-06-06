from enum import Enum


class BlockExtensionsByPermissionsControlType0Action(str, Enum):
    BLOCKBYPERMISSION = "blockByPermission"
    GRANTALL = "grantAll"

    def __str__(self) -> str:
        return str(self.value)
