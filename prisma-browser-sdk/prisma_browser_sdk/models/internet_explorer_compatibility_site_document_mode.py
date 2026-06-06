from enum import Enum


class InternetExplorerCompatibilitySiteDocumentMode(str, Enum):
    IE10 = "IE10"
    IE10_EDGE = "IE10 Edge"
    IE11 = "IE11"
    IE11_EDGE = "IE11 Edge"
    IE7 = "IE7"
    IE7_EDGE = "IE7 Edge"
    IE8 = "IE8"
    IE8_EDGE = "IE8 Edge"
    IE9 = "IE9"
    IE9_EDGE = "IE9 Edge"

    def __str__(self) -> str:
        return str(self.value)
