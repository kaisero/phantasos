from enum import Enum


class LocationMethod(str, Enum):
    GEOIP = "GeoIp"
    LOCATION_SERVICES = "Location services"
    UNKNOWN = "Unknown"

    def __str__(self) -> str:
        return str(self.value)
