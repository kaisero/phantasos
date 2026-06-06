from enum import Enum


class TrustedCertificateAuthoritiesControlType0Mode(str, Enum):
    DEVICETRUSTSTORE = "deviceTrustStore"
    NONE = "none"
    PRISMABROWSERTRUSTSTORE = "prismaBrowserTrustStore"

    def __str__(self) -> str:
        return str(self.value)
