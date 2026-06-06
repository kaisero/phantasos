from enum import Enum


class FlushBrowserDataControlType0DataTypesItem(str, Enum):
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
