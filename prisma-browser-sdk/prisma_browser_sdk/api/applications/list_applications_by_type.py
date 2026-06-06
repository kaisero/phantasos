from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.api_error import ApiError
from ...models.list_applications_by_type_response_200 import ListApplicationsByTypeResponse200
from ...models.list_applications_by_type_response_400 import ListApplicationsByTypeResponse400
from ...models.list_applications_by_type_sort import ListApplicationsByTypeSort
from ...models.list_applications_by_type_type import ListApplicationsByTypeType
from ...models.order import Order
from ...types import UNSET, Response, Unset


def _get_kwargs(
    type_: ListApplicationsByTypeType,
    *,
    name: str | Unset = UNSET,
    url_query: str | Unset = UNSET,
    configuration_version: str | Unset = "draft",
    cursor: str | Unset = UNSET,
    limit: int | Unset = UNSET,
    sort: ListApplicationsByTypeSort | Unset = UNSET,
    order: Order | Unset = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["name"] = name

    params["url"] = url_query

    params["configurationVersion"] = configuration_version

    params["cursor"] = cursor

    params["limit"] = limit

    json_sort: str | Unset = UNSET
    if not isinstance(sort, Unset):
        json_sort = sort.value

    params["sort"] = json_sort

    json_order: str | Unset = UNSET
    if not isinstance(order, Unset):
        json_order = order.value

    params["order"] = json_order

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/seb-api/v1/applications/type/{type_}".format(
            type_=quote(str(type_), safe=""),
        ),
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ApiError | ListApplicationsByTypeResponse200 | ListApplicationsByTypeResponse400 | None:
    if response.status_code == 200:
        response_200 = ListApplicationsByTypeResponse200.from_dict(response.json())

        return response_200

    if response.status_code == 400:
        response_400 = ListApplicationsByTypeResponse400.from_dict(response.json())

        return response_400

    if response.status_code == 403:
        response_403 = ApiError.from_dict(response.json())

        return response_403

    if response.status_code == 500:
        response_500 = ApiError.from_dict(response.json())

        return response_500

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ApiError | ListApplicationsByTypeResponse200 | ListApplicationsByTypeResponse400]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    type_: ListApplicationsByTypeType,
    *,
    client: AuthenticatedClient | Client,
    name: str | Unset = UNSET,
    url_query: str | Unset = UNSET,
    configuration_version: str | Unset = "draft",
    cursor: str | Unset = UNSET,
    limit: int | Unset = UNSET,
    sort: ListApplicationsByTypeSort | Unset = UNSET,
    order: Order | Unset = UNSET,
) -> Response[ApiError | ListApplicationsByTypeResponse200 | ListApplicationsByTypeResponse400]:
    """Returns a list of applications

     Fetches application objects belonging to a specific type.

    Args:
        type_ (ListApplicationsByTypeType):
        name (str | Unset):
        url_query (str | Unset):
        configuration_version (str | Unset):  Default: 'draft'.
        cursor (str | Unset):
        limit (int | Unset):
        sort (ListApplicationsByTypeSort | Unset):
        order (Order | Unset): The sort order

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ApiError | ListApplicationsByTypeResponse200 | ListApplicationsByTypeResponse400]
    """

    kwargs = _get_kwargs(
        type_=type_,
        name=name,
        url_query=url_query,
        configuration_version=configuration_version,
        cursor=cursor,
        limit=limit,
        sort=sort,
        order=order,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    type_: ListApplicationsByTypeType,
    *,
    client: AuthenticatedClient | Client,
    name: str | Unset = UNSET,
    url_query: str | Unset = UNSET,
    configuration_version: str | Unset = "draft",
    cursor: str | Unset = UNSET,
    limit: int | Unset = UNSET,
    sort: ListApplicationsByTypeSort | Unset = UNSET,
    order: Order | Unset = UNSET,
) -> ApiError | ListApplicationsByTypeResponse200 | ListApplicationsByTypeResponse400 | None:
    """Returns a list of applications

     Fetches application objects belonging to a specific type.

    Args:
        type_ (ListApplicationsByTypeType):
        name (str | Unset):
        url_query (str | Unset):
        configuration_version (str | Unset):  Default: 'draft'.
        cursor (str | Unset):
        limit (int | Unset):
        sort (ListApplicationsByTypeSort | Unset):
        order (Order | Unset): The sort order

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ApiError | ListApplicationsByTypeResponse200 | ListApplicationsByTypeResponse400
    """

    return sync_detailed(
        type_=type_,
        client=client,
        name=name,
        url_query=url_query,
        configuration_version=configuration_version,
        cursor=cursor,
        limit=limit,
        sort=sort,
        order=order,
    ).parsed


async def asyncio_detailed(
    type_: ListApplicationsByTypeType,
    *,
    client: AuthenticatedClient | Client,
    name: str | Unset = UNSET,
    url_query: str | Unset = UNSET,
    configuration_version: str | Unset = "draft",
    cursor: str | Unset = UNSET,
    limit: int | Unset = UNSET,
    sort: ListApplicationsByTypeSort | Unset = UNSET,
    order: Order | Unset = UNSET,
) -> Response[ApiError | ListApplicationsByTypeResponse200 | ListApplicationsByTypeResponse400]:
    """Returns a list of applications

     Fetches application objects belonging to a specific type.

    Args:
        type_ (ListApplicationsByTypeType):
        name (str | Unset):
        url_query (str | Unset):
        configuration_version (str | Unset):  Default: 'draft'.
        cursor (str | Unset):
        limit (int | Unset):
        sort (ListApplicationsByTypeSort | Unset):
        order (Order | Unset): The sort order

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ApiError | ListApplicationsByTypeResponse200 | ListApplicationsByTypeResponse400]
    """

    kwargs = _get_kwargs(
        type_=type_,
        name=name,
        url_query=url_query,
        configuration_version=configuration_version,
        cursor=cursor,
        limit=limit,
        sort=sort,
        order=order,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    type_: ListApplicationsByTypeType,
    *,
    client: AuthenticatedClient | Client,
    name: str | Unset = UNSET,
    url_query: str | Unset = UNSET,
    configuration_version: str | Unset = "draft",
    cursor: str | Unset = UNSET,
    limit: int | Unset = UNSET,
    sort: ListApplicationsByTypeSort | Unset = UNSET,
    order: Order | Unset = UNSET,
) -> ApiError | ListApplicationsByTypeResponse200 | ListApplicationsByTypeResponse400 | None:
    """Returns a list of applications

     Fetches application objects belonging to a specific type.

    Args:
        type_ (ListApplicationsByTypeType):
        name (str | Unset):
        url_query (str | Unset):
        configuration_version (str | Unset):  Default: 'draft'.
        cursor (str | Unset):
        limit (int | Unset):
        sort (ListApplicationsByTypeSort | Unset):
        order (Order | Unset): The sort order

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ApiError | ListApplicationsByTypeResponse200 | ListApplicationsByTypeResponse400
    """

    return (
        await asyncio_detailed(
            type_=type_,
            client=client,
            name=name,
            url_query=url_query,
            configuration_version=configuration_version,
            cursor=cursor,
            limit=limit,
            sort=sort,
            order=order,
        )
    ).parsed
