from .._lenient import LenientStrEnum


class RequestActionAdminBypassTimeframe(LenientStrEnum):
    ONCE = "Once"
    VALUE_1 = "10m"
    VALUE_10 = "30d"
    VALUE_11 = "60d"
    VALUE_12 = "90d"
    VALUE_2 = "1h"
    VALUE_3 = "4h"
    VALUE_4 = "9h"
    VALUE_5 = "12h"
    VALUE_6 = "24h"
    VALUE_7 = "3d"
    VALUE_8 = "7d"
    VALUE_9 = "14d"

    def __str__(self) -> str:
        return str(self.value)
