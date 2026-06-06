"""Native, resource-oriented facade over the OpenAPI-Generator SDK.

Instead of `UsersApi(api_client).list_users(...)`, use:

    from prisma_browser.extras import Client
    client = Client.from_env()                       # OAuth2 from CLIENT_ID/SECRET/SCOPE
    for user in client.paginate(client.users.list_users, limit=100):
        ...
    user = client.users.get_user_by_id(some_id)

`client.<resource>` is the corresponding generated `*Api` instance (so all operations
are available under their generated names); `client.paginate(...)` follows cursors.

Hand-maintained — copied into `prisma_browser/extras/` by the build.
"""

from __future__ import annotations

from typing import Any, Callable, Iterator

from ..api.access_and_data_policy_api import AccessAndDataPolicyApi
from ..api.application_groups_api import ApplicationGroupsApi
from ..api.applications_api import ApplicationsApi
from ..api.configuration_management_api import ConfigurationManagementApi
from ..api.customization_policy_api import CustomizationPolicyApi
from ..api.device_groups_api import DeviceGroupsApi
from ..api.devices_api import DevicesApi
from ..api.plugins_api import PluginsApi
from ..api.security_policy_api import SecurityPolicyApi
from ..api.sign_in_policy_api import SignInPolicyApi
from ..api.user_groups_api import UserGroupsApi
from ..api.user_requests_api import UserRequestsApi
from ..api.users_api import UsersApi
from .auth import api_client_from_credentials, api_client_from_env
from .pagination import paginate

__all__ = ["Client"]

# attribute name on Client -> generated Api class
_RESOURCES = {
    "users": UsersApi,
    "user_groups": UserGroupsApi,
    "user_requests": UserRequestsApi,
    "devices": DevicesApi,
    "device_groups": DeviceGroupsApi,
    "applications": ApplicationsApi,
    "application_groups": ApplicationGroupsApi,
    "plugins": PluginsApi,
    "security_policy": SecurityPolicyApi,
    "sign_in_policy": SignInPolicyApi,
    "access_and_data_policy": AccessAndDataPolicyApi,
    "customization_policy": CustomizationPolicyApi,
    "configuration_management": ConfigurationManagementApi,
}


class Client:
    """Resource-oriented entry point. Each resource attribute is a generated *Api."""

    def __init__(self, api_client):
        self._api_client = api_client
        for name, api_cls in _RESOURCES.items():
            setattr(self, name, api_cls(api_client))

    # type hints for editors/users (set dynamically above)
    users: UsersApi
    user_groups: UserGroupsApi
    user_requests: UserRequestsApi
    devices: DevicesApi
    device_groups: DeviceGroupsApi
    applications: ApplicationsApi
    application_groups: ApplicationGroupsApi
    plugins: PluginsApi
    security_policy: SecurityPolicyApi
    sign_in_policy: SignInPolicyApi
    access_and_data_policy: AccessAndDataPolicyApi
    customization_policy: CustomizationPolicyApi
    configuration_management: ConfigurationManagementApi

    @classmethod
    def from_env(cls, **kwargs) -> "Client":
        return cls(api_client_from_env(**kwargs))

    @classmethod
    def from_credentials(cls, **kwargs) -> "Client":
        return cls(api_client_from_credentials(**kwargs))

    def paginate(self, list_method: Callable[..., Any], **filters: Any) -> Iterator[Any]:
        """Yield every item across all pages of a list endpoint (cursor-following)."""
        return paginate(list_method, **filters)

    @property
    def api_client(self):
        return self._api_client

    def close(self) -> None:
        # OAG's ApiClient is a context manager (no public close()); release its pool.
        self._api_client.__exit__(None, None, None)

    def __enter__(self) -> "Client":
        return self

    def __exit__(self, exc_type=None, exc_value=None, traceback=None) -> None:
        self._api_client.__exit__(exc_type, exc_value, traceback)
