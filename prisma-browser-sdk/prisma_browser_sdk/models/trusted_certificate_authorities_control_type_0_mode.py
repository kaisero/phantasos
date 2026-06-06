from .._lenient import LenientStrEnum


class TrustedCertificateAuthoritiesControlType0Mode(LenientStrEnum):
    DEVICETRUSTSTORE = "deviceTrustStore"
    NONE = "none"
    PRISMABROWSERTRUSTSTORE = "prismaBrowserTrustStore"

    def __str__(self) -> str:
        return str(self.value)
