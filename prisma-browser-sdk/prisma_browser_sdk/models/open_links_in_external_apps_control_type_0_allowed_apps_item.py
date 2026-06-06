from .._lenient import LenientStrEnum


class OpenLinksInExternalAppsControlType0AllowedAppsItem(LenientStrEnum):
    GMAIL = "gmail"
    GOOGLEDOCS = "googleDocs"
    GOOGLEDRIVE = "googleDrive"
    MICROSOFT365 = "microsoft365"
    MICROSOFTONEDRIVE = "microsoftOneDrive"
    MICROSOFTTEAMS = "microsoftTeams"
    SALESFORCE = "salesforce"
    SLACK = "slack"
    ZOOM = "zoom"

    def __str__(self) -> str:
        return str(self.value)
