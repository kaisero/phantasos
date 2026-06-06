from .._lenient import LenientStrEnum


class LocationMethod(LenientStrEnum):
    GEOIP = "GeoIp"
    LOCATION_SERVICES = "Location services"
    UNKNOWN = "Unknown"

    def __str__(self) -> str:
        return str(self.value)
