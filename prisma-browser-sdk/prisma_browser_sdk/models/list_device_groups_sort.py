from enum import Enum


class ListDeviceGroupsSort(str, Enum):
    DEVICEGROUP_CREATED_AT = "deviceGroup.created_at"
    DEVICEGROUP_NAME = "deviceGroup.name"
    DEVICEGROUP_PLATFORM = "deviceGroup.platform"
    DEVICEGROUP_UPDATED_AT = "deviceGroup.updated_at"

    def __str__(self) -> str:
        return str(self.value)
