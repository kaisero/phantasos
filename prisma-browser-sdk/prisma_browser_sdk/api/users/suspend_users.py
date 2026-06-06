from http import HTTPStatus
from typing import Any, cast

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.suspend_users_response_400 import SuspendUsersResponse400
from ...models.suspend_users_response_404 import SuspendUsersResponse404
from ...models.user_status_change_request import UserStatusChangeRequest
from ...models.user_suspend_response import UserSuspendResponse
from ...types import Response


def _get_kwargs(
    *,
    body: UserStatusChangeRequest,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/seb-api/v1/users/suspend",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Any | SuspendUsersResponse400 | SuspendUsersResponse404 | UserSuspendResponse | None:
    if response.status_code == 200:
        response_200 = UserSuspendResponse.from_dict(response.json())

        return response_200

    if response.status_code == 400:
        response_400 = SuspendUsersResponse400.from_dict(response.json())

        return response_400

    if response.status_code == 403:
        response_403 = cast(Any, None)
        return response_403

    if response.status_code == 404:
        response_404 = SuspendUsersResponse404.from_dict(response.json())

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
) -> Response[Any | SuspendUsersResponse400 | SuspendUsersResponse404 | UserSuspendResponse]:
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
) -> Response[Any | SuspendUsersResponse400 | SuspendUsersResponse404 | UserSuspendResponse]:
    """Suspend users

     Suspend one or more users by changing their status to suspended. Suspended users will lose access to
    the browser from all of their known or future devices, except from their Prisma Browser Extension
    and mobile devices.

    Args:
        body (UserStatusChangeRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | SuspendUsersResponse400 | SuspendUsersResponse404 | UserSuspendResponse]
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
) -> Any | SuspendUsersResponse400 | SuspendUsersResponse404 | UserSuspendResponse | None:
    """Suspend users

     Suspend one or more users by changing their status to suspended. Suspended users will lose access to
    the browser from all of their known or future devices, except from their Prisma Browser Extension
    and mobile devices.

    Args:
        body (UserStatusChangeRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | SuspendUsersResponse400 | SuspendUsersResponse404 | UserSuspendResponse
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: UserStatusChangeRequest,
) -> Response[Any | SuspendUsersResponse400 | SuspendUsersResponse404 | UserSuspendResponse]:
    """Suspend users

     Suspend one or more users by changing their status to suspended. Suspended users will lose access to
    the browser from all of their known or future devices, except from their Prisma Browser Extension
    and mobile devices.

    Args:
        body (UserStatusChangeRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | SuspendUsersResponse400 | SuspendUsersResponse404 | UserSuspendResponse]
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
) -> Any | SuspendUsersResponse400 | SuspendUsersResponse404 | UserSuspendResponse | None:
    """Suspend users

     Suspend one or more users by changing their status to suspended. Suspended users will lose access to
    the browser from all of their known or future devices, except from their Prisma Browser Extension
    and mobile devices.

    Args:
        body (UserStatusChangeRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | SuspendUsersResponse400 | SuspendUsersResponse404 | UserSuspendResponse
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
