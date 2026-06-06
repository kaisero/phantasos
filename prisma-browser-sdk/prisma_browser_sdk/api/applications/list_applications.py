from http import HTTPStatus
from typing import Any, cast

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.list_applications_response_200 import ListApplicationsResponse200
from ...models.list_applications_response_400 import ListApplicationsResponse400
from ...models.list_applications_sort import ListApplicationsSort
from ...models.list_applications_type import ListApplicationsType
from ...models.order import Order
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    type_: ListApplicationsType | Unset = UNSET,
    name: str | Unset = UNSET,
    url_query: str | Unset = UNSET,
    limit: int | Unset = UNSET,
    cursor: str | Unset = UNSET,
    sort: ListApplicationsSort | Unset = UNSET,
    order: Order | Unset = UNSET,
    configuration_version: str | Unset = "draft",
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_type_: str | Unset = UNSET
    if not isinstance(type_, Unset):
        json_type_ = type_.value

    params["type"] = json_type_

    params["name"] = name

    params["url"] = url_query

    params["limit"] = limit

    params["cursor"] = cursor

    json_sort: str | Unset = UNSET
    if not isinstance(sort, Unset):
        json_sort = sort.value

    params["sort"] = json_sort

    json_order: str | Unset = UNSET
    if not isinstance(order, Unset):
        json_order = order.value

    params["order"] = json_order

    params["configurationVersion"] = configuration_version

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/seb-api/v1/applications",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Any | ListApplicationsResponse200 | ListApplicationsResponse400 | None:
    if response.status_code == 200:
        response_200 = ListApplicationsResponse200.from_dict(response.json())

        return response_200

    if response.status_code == 400:
        response_400 = ListApplicationsResponse400.from_dict(response.json())

        return response_400

    if response.status_code == 403:
        response_403 = cast(Any, None)
        return response_403

    if response.status_code == 404:
        response_404 = cast(Any, None)
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
) -> Response[Any | ListApplicationsResponse200 | ListApplicationsResponse400]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    type_: ListApplicationsType | Unset = UNSET,
    name: str | Unset = UNSET,
    url_query: str | Unset = UNSET,
    limit: int | Unset = UNSET,
    cursor: str | Unset = UNSET,
    sort: ListApplicationsSort | Unset = UNSET,
    order: Order | Unset = UNSET,
    configuration_version: str | Unset = "draft",
) -> Response[Any | ListApplicationsResponse200 | ListApplicationsResponse400]:
    """Returns a list of applications

     Fetches all application objects, with support for filtering and pagination.

    Args:
        type_ (ListApplicationsType | Unset):
        name (str | Unset):
        url_query (str | Unset):
        limit (int | Unset):
        cursor (str | Unset):
        sort (ListApplicationsSort | Unset):
        order (Order | Unset): The sort order
        configuration_version (str | Unset):  Default: 'draft'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | ListApplicationsResponse200 | ListApplicationsResponse400]
    """

    kwargs = _get_kwargs(
        type_=type_,
        name=name,
        url_query=url_query,
        limit=limit,
        cursor=cursor,
        sort=sort,
        order=order,
        configuration_version=configuration_version,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    type_: ListApplicationsType | Unset = UNSET,
    name: str | Unset = UNSET,
    url_query: str | Unset = UNSET,
    limit: int | Unset = UNSET,
    cursor: str | Unset = UNSET,
    sort: ListApplicationsSort | Unset = UNSET,
    order: Order | Unset = UNSET,
    configuration_version: str | Unset = "draft",
) -> Any | ListApplicationsResponse200 | ListApplicationsResponse400 | None:
    """Returns a list of applications

     Fetches all application objects, with support for filtering and pagination.

    Args:
        type_ (ListApplicationsType | Unset):
        name (str | Unset):
        url_query (str | Unset):
        limit (int | Unset):
        cursor (str | Unset):
        sort (ListApplicationsSort | Unset):
        order (Order | Unset): The sort order
        configuration_version (str | Unset):  Default: 'draft'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | ListApplicationsResponse200 | ListApplicationsResponse400
    """

    return sync_detailed(
        client=client,
        type_=type_,
        name=name,
        url_query=url_query,
        limit=limit,
        cursor=cursor,
        sort=sort,
        order=order,
        configuration_version=configuration_version,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    type_: ListApplicationsType | Unset = UNSET,
    name: str | Unset = UNSET,
    url_query: str | Unset = UNSET,
    limit: int | Unset = UNSET,
    cursor: str | Unset = UNSET,
    sort: ListApplicationsSort | Unset = UNSET,
    order: Order | Unset = UNSET,
    configuration_version: str | Unset = "draft",
) -> Response[Any | ListApplicationsResponse200 | ListApplicationsResponse400]:
    """Returns a list of applications

     Fetches all application objects, with support for filtering and pagination.

    Args:
        type_ (ListApplicationsType | Unset):
        name (str | Unset):
        url_query (str | Unset):
        limit (int | Unset):
        cursor (str | Unset):
        sort (ListApplicationsSort | Unset):
        order (Order | Unset): The sort order
        configuration_version (str | Unset):  Default: 'draft'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | ListApplicationsResponse200 | ListApplicationsResponse400]
    """

    kwargs = _get_kwargs(
        type_=type_,
        name=name,
        url_query=url_query,
        limit=limit,
        cursor=cursor,
        sort=sort,
        order=order,
        configuration_version=configuration_version,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    type_: ListApplicationsType | Unset = UNSET,
    name: str | Unset = UNSET,
    url_query: str | Unset = UNSET,
    limit: int | Unset = UNSET,
    cursor: str | Unset = UNSET,
    sort: ListApplicationsSort | Unset = UNSET,
    order: Order | Unset = UNSET,
    configuration_version: str | Unset = "draft",
) -> Any | ListApplicationsResponse200 | ListApplicationsResponse400 | None:
    """Returns a list of applications

     Fetches all application objects, with support for filtering and pagination.

    Args:
        type_ (ListApplicationsType | Unset):
        name (str | Unset):
        url_query (str | Unset):
        limit (int | Unset):
        cursor (str | Unset):
        sort (ListApplicationsSort | Unset):
        order (Order | Unset): The sort order
        configuration_version (str | Unset):  Default: 'draft'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | ListApplicationsResponse200 | ListApplicationsResponse400
    """

    return (
        await asyncio_detailed(
            client=client,
            type_=type_,
            name=name,
            url_query=url_query,
            limit=limit,
            cursor=cursor,
            sort=sort,
            order=order,
            configuration_version=configuration_version,
        )
    ).parsed
