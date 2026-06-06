from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.api_error import ApiError
from ...models.get_access_and_data_policy_response_200 import GetAccessAndDataPolicyResponse200
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    configuration_version: str | Unset = "draft",
    limit: int | Unset = 100,
    cursor: str | Unset = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["configurationVersion"] = configuration_version

    params["limit"] = limit

    params["cursor"] = cursor

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/seb-api/v1/policy/access-and-data",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ApiError | GetAccessAndDataPolicyResponse200 | None:
    if response.status_code == 200:
        response_200 = GetAccessAndDataPolicyResponse200.from_dict(response.json())

        return response_200

    if response.status_code == 400:
        response_400 = ApiError.from_dict(response.json())

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
) -> Response[ApiError | GetAccessAndDataPolicyResponse200]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    configuration_version: str | Unset = "draft",
    limit: int | Unset = 100,
    cursor: str | Unset = UNSET,
) -> Response[ApiError | GetAccessAndDataPolicyResponse200]:
    """Retrieve the Access and Data Policy

     Fetches the complete access and data policy, which is an ordered list of rules and sections.

    Args:
        configuration_version (str | Unset):  Default: 'draft'.
        limit (int | Unset):  Default: 100.
        cursor (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ApiError | GetAccessAndDataPolicyResponse200]
    """

    kwargs = _get_kwargs(
        configuration_version=configuration_version,
        limit=limit,
        cursor=cursor,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    configuration_version: str | Unset = "draft",
    limit: int | Unset = 100,
    cursor: str | Unset = UNSET,
) -> ApiError | GetAccessAndDataPolicyResponse200 | None:
    """Retrieve the Access and Data Policy

     Fetches the complete access and data policy, which is an ordered list of rules and sections.

    Args:
        configuration_version (str | Unset):  Default: 'draft'.
        limit (int | Unset):  Default: 100.
        cursor (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ApiError | GetAccessAndDataPolicyResponse200
    """

    return sync_detailed(
        client=client,
        configuration_version=configuration_version,
        limit=limit,
        cursor=cursor,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    configuration_version: str | Unset = "draft",
    limit: int | Unset = 100,
    cursor: str | Unset = UNSET,
) -> Response[ApiError | GetAccessAndDataPolicyResponse200]:
    """Retrieve the Access and Data Policy

     Fetches the complete access and data policy, which is an ordered list of rules and sections.

    Args:
        configuration_version (str | Unset):  Default: 'draft'.
        limit (int | Unset):  Default: 100.
        cursor (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ApiError | GetAccessAndDataPolicyResponse200]
    """

    kwargs = _get_kwargs(
        configuration_version=configuration_version,
        limit=limit,
        cursor=cursor,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    configuration_version: str | Unset = "draft",
    limit: int | Unset = 100,
    cursor: str | Unset = UNSET,
) -> ApiError | GetAccessAndDataPolicyResponse200 | None:
    """Retrieve the Access and Data Policy

     Fetches the complete access and data policy, which is an ordered list of rules and sections.

    Args:
        configuration_version (str | Unset):  Default: 'draft'.
        limit (int | Unset):  Default: 100.
        cursor (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ApiError | GetAccessAndDataPolicyResponse200
    """

    return (
        await asyncio_detailed(
            client=client,
            configuration_version=configuration_version,
            limit=limit,
            cursor=cursor,
        )
    ).parsed
