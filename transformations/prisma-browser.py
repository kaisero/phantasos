"""Prisma Browser SDK — spec config for phantasos.

Build with:  phantasos build transformations/prisma-browser.py
"""

from pathlib import Path

from phantasos import (
    CursorPagination,
    Facade,
    NestedError,
    OAuthClientCredentials,
    SdkConfig,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent  # transformations/ -> repo root
# Generated SDK is written to a sibling dir of the generator repo, never inside it.
_OUTPUT_DIR = _REPO_ROOT.parent / "prisma-browser-sdk"

CONFIG = SdkConfig(
    spec=str(_REPO_ROOT / "specs" / "prisma-browser.yml"),
    package="prisma_browser",
    base_url="https://api.sase.paloaltonetworks.com",
    project_dir=str(_OUTPUT_DIR),
    auth=OAuthClientCredentials(
        token_url="https://auth.apps.paloaltonetworks.com/oauth2/access_token",  # noqa: S106  OAuth token endpoint URL, not a secret
        scope_env="SCOPE",
        base_url_env="PRISMA_SASE_BASE_URL",
        config_class_name="PrismaSaseConfiguration",
    ),
    pagination=CursorPagination(),  # data / page_info.cursor / has_next_page
    errors=NestedError(),  # {error: {code, message}}
    facade=Facade(),
)

# --- spec-specific quirks (formerly hard-coded in preprocess_spec.py) ---
_HOISTS = [
    (
        "AllowedOrBlockedExtensionsControl",
        "extensions",
        "AllowedOrBlockedExtensionEntry",
    ),
    (
        "LaunchingExternalApplicationsControl",
        "exceptions",
        "ExternalApplicationLaunchException",
    ),
    (
        "TrustedCertificateAuthoritiesControl",
        "additionalCertificates",
        "TrustedCertificateEntry",
    ),
    (
        "InternetExplorerCompatibilityModeControl",
        "sites",
        "InternetExplorerCompatibilitySite",
    ),
]
_TAG_OPS = [
    ("/seb-api/v1/user-requests", "get", "ListUserRequests", "User Requests"),
    ("/seb-api/v1/user-requests/{id}", "get", "GetUserRequestByID", "User Requests"),
    (
        "/seb-api/v1/user-requests/{id}/action",
        "post",
        "ActionUserRequest",
        "User Requests",
    ),
    (
        "/seb-api/v1/user-requests/{id}/revoke",
        "post",
        "RevokeUserRequest",
        "User Requests",
    ),
]


def preprocess(spec):
    from phantasos.preprocess import hoist_items, tag_operations

    hoist_items(spec, _HOISTS)
    tag_operations(spec, _TAG_OPS)
