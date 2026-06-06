from enum import Enum


class FlushBrowserDataControlType0Trigger(str, Enum):
    BROWSERCLOSE = "browserClose"
    TIMEPERIOD = "timePeriod"

    def __str__(self) -> str:
        return str(self.value)
