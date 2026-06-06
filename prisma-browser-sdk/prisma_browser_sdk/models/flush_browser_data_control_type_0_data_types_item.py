from .._lenient import LenientStrEnum


class FlushBrowserDataControlType0DataTypesItem(LenientStrEnum):
    AUTOFILLDATA = "autofillData"
    BROWSINGHISTORY = "browsingHistory"
    CACHEDCONTENT = "cachedContent"
    COOKIESANDSITEDATA = "cookiesAndSiteData"
    DOWNLOADHISTORY = "downloadHistory"
    OPENTABS = "openTabs"
    SAVEDPASSWORDS = "savedPasswords"
    SITESETTINGS = "siteSettings"
    WEBAPPDATA = "webAppData"

    def __str__(self) -> str:
        return str(self.value)
