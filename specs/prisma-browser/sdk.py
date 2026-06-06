"""Prisma Browser SDK — spec config for sdkgen.

Build with:  sdkgen build specs/prisma-browser/sdk.py
"""
from pathlib import Path

from sdkgen import CursorPagination, Facade, NestedError, OAuthClientCredentials, SdkConfig

_REPO_ROOT = Path(__file__).resolve().parents[2]

CONFIG = SdkConfig(
    spec=str(_REPO_ROOT / "prismaBrowserAPIspecWithSecurityPolicy.yaml"),
    package="prisma_browser",
    base_url="https://api.sase.paloaltonetworks.com",
    project_dir=".",
    auth=OAuthClientCredentials(
        token_url="https://auth.apps.paloaltonetworks.com/oauth2/access_token",
        scope_env="SCOPE",
        base_url_env="PRISMA_SASE_BASE_URL",
        config_class_name="PrismaSaseConfiguration",
    ),
    pagination=CursorPagination(),   # data / page_info.cursor / has_next_page
    errors=NestedError(),            # {error: {code, message}}
    facade=Facade(),
)

# --- spec-specific quirks (formerly hard-coded in preprocess_spec.py) ---
_HOISTS = [
    ("AllowedOrBlockedExtensionsControl", "extensions", "AllowedOrBlockedExtensionEntry"),
    ("LaunchingExternalApplicationsControl", "exceptions", "ExternalApplicationLaunchException"),
    ("TrustedCertificateAuthoritiesControl", "additionalCertificates", "TrustedCertificateEntry"),
    ("InternetExplorerCompatibilityModeControl", "sites", "InternetExplorerCompatibilitySite"),
]
_TAG_OPS = [
    ("/seb-api/v1/user-requests", "get", "ListUserRequests", "User Requests"),
    ("/seb-api/v1/user-requests/{id}", "get", "GetUserRequestByID", "User Requests"),
    ("/seb-api/v1/user-requests/{id}/action", "post", "ActionUserRequest", "User Requests"),
    ("/seb-api/v1/user-requests/{id}/revoke", "post", "RevokeUserRequest", "User Requests"),
]


def preprocess(spec):
    from sdkgen.preprocess import hoist_items, tag_operations
    hoist_items(spec, _HOISTS)
    tag_operations(spec, _TAG_OPS)
