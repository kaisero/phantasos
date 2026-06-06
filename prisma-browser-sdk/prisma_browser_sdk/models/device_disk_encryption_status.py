from .._lenient import LenientStrEnum


class DeviceDiskEncryptionStatus(LenientStrEnum):
    DISKENCRYPTIONSTATUSDISABLED = "DiskEncryptionStatusDisabled"
    DISKENCRYPTIONSTATUSENABLED = "DiskEncryptionStatusEnabled"
    DISKENCRYPTIONSTATUSUNKNOWN = "DiskEncryptionStatusUnknown"

    def __str__(self) -> str:
        return str(self.value)
