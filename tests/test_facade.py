from prisma_browser.extras import Client
from prisma_browser.api.users_api import UsersApi
from prisma_browser.api.security_policy_api import SecurityPolicyApi


def test_facade_wires_resources_without_network():
    # client-credentials build is lazy (no token fetch until a call)
    client = Client.from_credentials(client_id="x", client_secret="y", scope="tsg_id:1")
    assert isinstance(client.users, UsersApi)
    assert isinstance(client.security_policy, SecurityPolicyApi)
    assert sum(1 for r in (
        "users", "user_groups", "user_requests", "devices", "device_groups",
        "applications", "application_groups", "plugins", "security_policy",
        "sign_in_policy", "access_and_data_policy", "customization_policy",
        "configuration_management") if hasattr(client, r)) == 13
