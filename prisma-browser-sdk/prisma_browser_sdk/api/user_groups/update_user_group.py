from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.api_error import ApiError
from ...models.update_user_group_body import UpdateUserGroupBody
from ...models.update_user_group_response_200 import UpdateUserGroupResponse200
from ...models.update_user_group_response_400 import UpdateUserGroupResponse400
from ...types import Response


def _get_kwargs(
    id: str,
    *,
    body: UpdateUserGroupBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "put",
        "url": "/seb-api/v1/user-groups/{id}".format(
            id=quote(str(id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ApiError | UpdateUserGroupResponse200 | UpdateUserGroupResponse400 | None:
    if response.status_code == 200:
        response_200 = UpdateUserGroupResponse200.from_dict(response.json())

        return response_200

    if response.status_code == 400:
        response_400 = UpdateUserGroupResponse400.from_dict(response.json())

        return response_400

    if response.status_code == 403:
        response_403 = ApiError.from_dict(response.json())

        return response_403

    if response.status_code == 404:
        response_404 = ApiError.from_dict(response.json())

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
) -> Response[ApiError | UpdateUserGroupResponse200 | UpdateUserGroupResponse400]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    id: str,
    *,
    client: AuthenticatedClient | Client,
    body: UpdateUserGroupBody,
) -> Response[ApiError | UpdateUserGroupResponse200 | UpdateUserGroupResponse400]:
    """Updates a user group

    Args:
        id (str):
        body (UpdateUserGroupBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ApiError | UpdateUserGroupResponse200 | UpdateUserGroupResponse400]
    """

    kwargs = _get_kwargs(
        id=id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    id: str,
    *,
    client: AuthenticatedClient | Client,
    body: UpdateUserGroupBody,
) -> ApiError | UpdateUserGroupResponse200 | UpdateUserGroupResponse400 | None:
    """Updates a user group

    Args:
        id (str):
        body (UpdateUserGroupBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ApiError | UpdateUserGroupResponse200 | UpdateUserGroupResponse400
    """

    return sync_detailed(
        id=id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    id: str,
    *,
    client: AuthenticatedClient | Client,
    body: UpdateUserGroupBody,
) -> Response[ApiError | UpdateUserGroupResponse200 | UpdateUserGroupResponse400]:
    """Updates a user group

    Args:
        id (str):
        body (UpdateUserGroupBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ApiError | UpdateUserGroupResponse200 | UpdateUserGroupResponse400]
    """

    kwargs = _get_kwargs(
        id=id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    id: str,
    *,
    client: AuthenticatedClient | Client,
    body: UpdateUserGroupBody,
) -> ApiError | UpdateUserGroupResponse200 | UpdateUserGroupResponse400 | None:
    """Updates a user group

    Args:
        id (str):
        body (UpdateUserGroupBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ApiError | UpdateUserGroupResponse200 | UpdateUserGroupResponse400
    """

    return (
        await asyncio_detailed(
            id=id,
            client=client,
            body=body,
        )
    ).parsed
