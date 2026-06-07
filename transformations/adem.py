"""ADEM data API SDK — spec config for phantasos.

ADEM (Autonomous Digital Experience Management) is a timeseries data API on Strata
Cloud Manager / SASE. Build with:  phantasos build transformations/adem.py

Shape notes (vs. prisma-browser, which exercises all components):
- auth: HTTP bearer JWT obtained via the same SASE client-credentials flow -> reuse
  OAuthClientCredentials unchanged.
- pagination: request-side page/limit/sortBy params; responses are aggregates with no
  uniform items array, so no cursor-follower is vendored (pagination=None).
- errors: responses use bare status codes (no {error:{message}} body) -> errors=None.
"""

from pathlib import Path

from phantasos import Facade, OAuthClientCredentials, SdkConfig

_REPO_ROOT = Path(__file__).resolve().parent.parent  # transformations/ -> repo root
_OUTPUT_DIR = _REPO_ROOT.parent / "adem-sdk"

CONFIG = SdkConfig(
    spec=str(_REPO_ROOT / "specs" / "adem.yml"),
    package="adem",
    base_url="https://api.sase.paloaltonetworks.com",
    project_dir=str(_OUTPUT_DIR),
    auth=OAuthClientCredentials(
        token_url="https://auth.apps.paloaltonetworks.com/oauth2/access_token",  # noqa: S106  OAuth token endpoint URL, not a secret
        scope_env="SCOPE",
        base_url_env="ADEM_BASE_URL",
        config_class_name="AdemConfiguration",
    ),
    pagination=None,
    errors=None,
    facade=Facade(),
)


def preprocess(spec):
    # The spec carries a stray top-level `ExternalTags: {}` key (not valid OpenAPI root
    # field), which fails OAG spec validation. Drop it.
    spec.pop("ExternalTags", None)
