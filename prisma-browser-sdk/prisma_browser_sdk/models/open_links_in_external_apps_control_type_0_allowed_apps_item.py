from enum import Enum


class OpenLinksInExternalAppsControlType0AllowedAppsItem(str, Enum):
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
