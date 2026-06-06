from .._lenient import LenientStrEnum


class FlushBrowserDataControlType0Trigger(LenientStrEnum):
    BROWSERCLOSE = "browserClose"
    TIMEPERIOD = "timePeriod"

    def __str__(self) -> str:
        return str(self.value)
