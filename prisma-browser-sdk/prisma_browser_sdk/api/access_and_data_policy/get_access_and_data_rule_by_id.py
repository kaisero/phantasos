from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.access_and_data_rule_detailed import AccessAndDataRuleDetailed
from ...models.api_error import ApiError
from ...types import UNSET, Response, Unset


def _get_kwargs(
    id: str,
    *,
    configuration_version: str | Unset = "draft",
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["configurationVersion"] = configuration_version

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/seb-api/v1/policy/access-and-data/rules/{id}".format(
            id=quote(str(id), safe=""),
        ),
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> AccessAndDataRuleDetailed | ApiError | None:
    if response.status_code == 200:
        response_200 = AccessAndDataRuleDetailed.from_dict(response.json())

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
) -> Response[AccessAndDataRuleDetailed | ApiError]:
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
    configuration_version: str | Unset = "draft",
) -> Response[AccessAndDataRuleDetailed | ApiError]:
    """Retrieve an Access and Data Rule by ID

     Fetches a single, detailed access-and-data rule object with controls sections by its unique
    identifier.

    Args:
        id (str):
        configuration_version (str | Unset):  Default: 'draft'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AccessAndDataRuleDetailed | ApiError]
    """

    kwargs = _get_kwargs(
        id=id,
        configuration_version=configuration_version,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    id: str,
    *,
    client: AuthenticatedClient | Client,
    configuration_version: str | Unset = "draft",
) -> AccessAndDataRuleDetailed | ApiError | None:
    """Retrieve an Access and Data Rule by ID

     Fetches a single, detailed access-and-data rule object with controls sections by its unique
    identifier.

    Args:
        id (str):
        configuration_version (str | Unset):  Default: 'draft'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AccessAndDataRuleDetailed | ApiError
    """

    return sync_detailed(
        id=id,
        client=client,
        configuration_version=configuration_version,
    ).parsed


async def asyncio_detailed(
    id: str,
    *,
    client: AuthenticatedClient | Client,
    configuration_version: str | Unset = "draft",
) -> Response[AccessAndDataRuleDetailed | ApiError]:
    """Retrieve an Access and Data Rule by ID

     Fetches a single, detailed access-and-data rule object with controls sections by its unique
    identifier.

    Args:
        id (str):
        configuration_version (str | Unset):  Default: 'draft'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AccessAndDataRuleDetailed | ApiError]
    """

    kwargs = _get_kwargs(
        id=id,
        configuration_version=configuration_version,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    id: str,
    *,
    client: AuthenticatedClient | Client,
    configuration_version: str | Unset = "draft",
) -> AccessAndDataRuleDetailed | ApiError | None:
    """Retrieve an Access and Data Rule by ID

     Fetches a single, detailed access-and-data rule object with controls sections by its unique
    identifier.

    Args:
        id (str):
        configuration_version (str | Unset):  Default: 'draft'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AccessAndDataRuleDetailed | ApiError
    """

    return (
        await asyncio_detailed(
            id=id,
            client=client,
            configuration_version=configuration_version,
        )
    ).parsed
