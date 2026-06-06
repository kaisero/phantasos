from .._lenient import LenientStrEnum


class BlockExtensionsByPermissionsControlType0Action(LenientStrEnum):
    BLOCKBYPERMISSION = "blockByPermission"
    GRANTALL = "grantAll"

    def __str__(self) -> str:
        return str(self.value)
