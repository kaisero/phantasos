from enum import Enum


class DeviceDiskEncryptionStatus(str, Enum):
    DISKENCRYPTIONSTATUSDISABLED = "DiskEncryptionStatusDisabled"
    DISKENCRYPTIONSTATUSENABLED = "DiskEncryptionStatusEnabled"
    DISKENCRYPTIONSTATUSUNKNOWN = "DiskEncryptionStatusUnknown"

    def __str__(self) -> str:
        return str(self.value)
