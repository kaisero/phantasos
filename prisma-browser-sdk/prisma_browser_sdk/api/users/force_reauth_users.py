from http import HTTPStatus
from typing import Any, cast

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.force_reauth_users_response_400 import ForceReauthUsersResponse400
from ...models.force_reauth_users_response_404 import ForceReauthUsersResponse404
from ...models.user_force_reauth_response import UserForceReauthResponse
from ...models.user_status_change_request import UserStatusChangeRequest
from ...types import Response


def _get_kwargs(
    *,
    body: UserStatusChangeRequest,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/seb-api/v1/users/force-reauth",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Any | ForceReauthUsersResponse400 | ForceReauthUsersResponse404 | UserForceReauthResponse | None:
    if response.status_code == 200:
        response_200 = UserForceReauthResponse.from_dict(response.json())

        return response_200

    if response.status_code == 400:
        response_400 = ForceReauthUsersResponse400.from_dict(response.json())

        return response_400

    if response.status_code == 403:
        response_403 = cast(Any, None)
        return response_403

    if response.status_code == 404:
        response_404 = ForceReauthUsersResponse404.from_dict(response.json())

        return response_404

    if response.status_code == 500:
        response_500 = cast(Any, None)
        return response_500

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[Any | ForceReauthUsersResponse400 | ForceReauthUsersResponse404 | UserForceReauthResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: UserStatusChangeRequest,
) -> Response[Any | ForceReauthUsersResponse400 | ForceReauthUsersResponse404 | UserForceReauthResponse]:
    """Force re-authentication for users

     Force re-authentication on all active devices for one or more users. Upon execution, targeted users
    will be required to re-authenticate to the browser on all of their devices.

    Args:
        body (UserStatusChangeRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | ForceReauthUsersResponse400 | ForceReauthUsersResponse404 | UserForceReauthResponse]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    body: UserStatusChangeRequest,
) -> Any | ForceReauthUsersResponse400 | ForceReauthUsersResponse404 | UserForceReauthResponse | None:
    """Force re-authentication for users

     Force re-authentication on all active devices for one or more users. Upon execution, targeted users
    will be required to re-authenticate to the browser on all of their devices.

    Args:
        body (UserStatusChangeRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | ForceReauthUsersResponse400 | ForceReauthUsersResponse404 | UserForceReauthResponse
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: UserStatusChangeRequest,
) -> Response[Any | ForceReauthUsersResponse400 | ForceReauthUsersResponse404 | UserForceReauthResponse]:
    """Force re-authentication for users

     Force re-authentication on all active devices for one or more users. Upon execution, targeted users
    will be required to re-authenticate to the browser on all of their devices.

    Args:
        body (UserStatusChangeRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | ForceReauthUsersResponse400 | ForceReauthUsersResponse404 | UserForceReauthResponse]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: UserStatusChangeRequest,
) -> Any | ForceReauthUsersResponse400 | ForceReauthUsersResponse404 | UserForceReauthResponse | None:
    """Force re-authentication for users

     Force re-authentication on all active devices for one or more users. Upon execution, targeted users
    will be required to re-authenticate to the browser on all of their devices.

    Args:
        body (UserStatusChangeRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | ForceReauthUsersResponse400 | ForceReauthUsersResponse404 | UserForceReauthResponse
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
