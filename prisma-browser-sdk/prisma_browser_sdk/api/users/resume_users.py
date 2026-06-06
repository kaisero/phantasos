from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.api_error import ApiError
from ...models.resume_users_response_400 import ResumeUsersResponse400
from ...models.resume_users_response_404 import ResumeUsersResponse404
from ...models.user_resume_response import UserResumeResponse
from ...models.user_status_change_request import UserStatusChangeRequest
from ...types import Response


def _get_kwargs(
    *,
    body: UserStatusChangeRequest,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/seb-api/v1/users/resume",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ApiError | ResumeUsersResponse400 | ResumeUsersResponse404 | UserResumeResponse | None:
    if response.status_code == 200:
        response_200 = UserResumeResponse.from_dict(response.json())

        return response_200

    if response.status_code == 400:
        response_400 = ResumeUsersResponse400.from_dict(response.json())

        return response_400

    if response.status_code == 403:
        response_403 = ApiError.from_dict(response.json())

        return response_403

    if response.status_code == 404:
        response_404 = ResumeUsersResponse404.from_dict(response.json())

        return response_404

    if response.status_code == 500:
        response_500 = ApiError.from_dict(response.json())

        return response_500

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ApiError | ResumeUsersResponse400 | ResumeUsersResponse404 | UserResumeResponse]:
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
) -> Response[ApiError | ResumeUsersResponse400 | ResumeUsersResponse404 | UserResumeResponse]:
    """Resume suspended users

     Resume one or more suspended users by changing their status to active. Resumed users will regain
    access to the browser from all of their known or future devices.

    Args:
        body (UserStatusChangeRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ApiError | ResumeUsersResponse400 | ResumeUsersResponse404 | UserResumeResponse]
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
) -> ApiError | ResumeUsersResponse400 | ResumeUsersResponse404 | UserResumeResponse | None:
    """Resume suspended users

     Resume one or more suspended users by changing their status to active. Resumed users will regain
    access to the browser from all of their known or future devices.

    Args:
        body (UserStatusChangeRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ApiError | ResumeUsersResponse400 | ResumeUsersResponse404 | UserResumeResponse
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: UserStatusChangeRequest,
) -> Response[ApiError | ResumeUsersResponse400 | ResumeUsersResponse404 | UserResumeResponse]:
    """Resume suspended users

     Resume one or more suspended users by changing their status to active. Resumed users will regain
    access to the browser from all of their known or future devices.

    Args:
        body (UserStatusChangeRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ApiError | ResumeUsersResponse400 | ResumeUsersResponse404 | UserResumeResponse]
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
) -> ApiError | ResumeUsersResponse400 | ResumeUsersResponse404 | UserResumeResponse | None:
    """Resume suspended users

     Resume one or more suspended users by changing their status to active. Resumed users will regain
    access to the browser from all of their known or future devices.

    Args:
        body (UserStatusChangeRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ApiError | ResumeUsersResponse400 | ResumeUsersResponse404 | UserResumeResponse
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
