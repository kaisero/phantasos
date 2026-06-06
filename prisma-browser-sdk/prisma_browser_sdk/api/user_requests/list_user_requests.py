from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.api_error import ApiError
from ...models.list_user_requests_request_status import ListUserRequestsRequestStatus
from ...models.list_user_requests_request_type import ListUserRequestsRequestType
from ...models.list_user_requests_response_200 import ListUserRequestsResponse200
from ...models.list_user_requests_sort import ListUserRequestsSort
from ...models.order import Order
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    limit: int | Unset = UNSET,
    request_type: ListUserRequestsRequestType | Unset = UNSET,
    request_user_id: str | Unset = UNSET,
    request_device_id: str | Unset = UNSET,
    request_rule_id: str | Unset = UNSET,
    request_url: str | Unset = UNSET,
    request_responded_by: str | Unset = UNSET,
    request_status: ListUserRequestsRequestStatus | Unset = UNSET,
    cursor: str | Unset = UNSET,
    sort: ListUserRequestsSort | Unset = UNSET,
    order: Order | Unset = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["limit"] = limit

    json_request_type: str | Unset = UNSET
    if not isinstance(request_type, Unset):
        json_request_type = request_type.value

    params["request.type"] = json_request_type

    params["request.user_id"] = request_user_id

    params["request.device_id"] = request_device_id

    params["request.rule_id"] = request_rule_id

    params["request.url"] = request_url

    params["request.responded_by"] = request_responded_by

    json_request_status: str | Unset = UNSET
    if not isinstance(request_status, Unset):
        json_request_status = request_status.value

    params["request.status"] = json_request_status

    params["cursor"] = cursor

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
        "url": "/seb-api/v1/user-requests",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ApiError | ListUserRequestsResponse200 | None:
    if response.status_code == 200:
        response_200 = ListUserRequestsResponse200.from_dict(response.json())

        return response_200

    if response.status_code == 400:
        response_400 = ApiError.from_dict(response.json())

        return response_400

    if response.status_code == 500:
        response_500 = ApiError.from_dict(response.json())

        return response_500

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ApiError | ListUserRequestsResponse200]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    limit: int | Unset = UNSET,
    request_type: ListUserRequestsRequestType | Unset = UNSET,
    request_user_id: str | Unset = UNSET,
    request_device_id: str | Unset = UNSET,
    request_rule_id: str | Unset = UNSET,
    request_url: str | Unset = UNSET,
    request_responded_by: str | Unset = UNSET,
    request_status: ListUserRequestsRequestStatus | Unset = UNSET,
    cursor: str | Unset = UNSET,
    sort: ListUserRequestsSort | Unset = UNSET,
    order: Order | Unset = UNSET,
) -> Response[ApiError | ListUserRequestsResponse200]:
    """Returns a list of user requests

    Args:
        limit (int | Unset):
        request_type (ListUserRequestsRequestType | Unset):
        request_user_id (str | Unset):
        request_device_id (str | Unset):
        request_rule_id (str | Unset):
        request_url (str | Unset):
        request_responded_by (str | Unset):
        request_status (ListUserRequestsRequestStatus | Unset):
        cursor (str | Unset):
        sort (ListUserRequestsSort | Unset):
        order (Order | Unset): The sort order

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ApiError | ListUserRequestsResponse200]
    """

    kwargs = _get_kwargs(
        limit=limit,
        request_type=request_type,
        request_user_id=request_user_id,
        request_device_id=request_device_id,
        request_rule_id=request_rule_id,
        request_url=request_url,
        request_responded_by=request_responded_by,
        request_status=request_status,
        cursor=cursor,
        sort=sort,
        order=order,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    limit: int | Unset = UNSET,
    request_type: ListUserRequestsRequestType | Unset = UNSET,
    request_user_id: str | Unset = UNSET,
    request_device_id: str | Unset = UNSET,
    request_rule_id: str | Unset = UNSET,
    request_url: str | Unset = UNSET,
    request_responded_by: str | Unset = UNSET,
    request_status: ListUserRequestsRequestStatus | Unset = UNSET,
    cursor: str | Unset = UNSET,
    sort: ListUserRequestsSort | Unset = UNSET,
    order: Order | Unset = UNSET,
) -> ApiError | ListUserRequestsResponse200 | None:
    """Returns a list of user requests

    Args:
        limit (int | Unset):
        request_type (ListUserRequestsRequestType | Unset):
        request_user_id (str | Unset):
        request_device_id (str | Unset):
        request_rule_id (str | Unset):
        request_url (str | Unset):
        request_responded_by (str | Unset):
        request_status (ListUserRequestsRequestStatus | Unset):
        cursor (str | Unset):
        sort (ListUserRequestsSort | Unset):
        order (Order | Unset): The sort order

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ApiError | ListUserRequestsResponse200
    """

    return sync_detailed(
        client=client,
        limit=limit,
        request_type=request_type,
        request_user_id=request_user_id,
        request_device_id=request_device_id,
        request_rule_id=request_rule_id,
        request_url=request_url,
        request_responded_by=request_responded_by,
        request_status=request_status,
        cursor=cursor,
        sort=sort,
        order=order,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    limit: int | Unset = UNSET,
    request_type: ListUserRequestsRequestType | Unset = UNSET,
    request_user_id: str | Unset = UNSET,
    request_device_id: str | Unset = UNSET,
    request_rule_id: str | Unset = UNSET,
    request_url: str | Unset = UNSET,
    request_responded_by: str | Unset = UNSET,
    request_status: ListUserRequestsRequestStatus | Unset = UNSET,
    cursor: str | Unset = UNSET,
    sort: ListUserRequestsSort | Unset = UNSET,
    order: Order | Unset = UNSET,
) -> Response[ApiError | ListUserRequestsResponse200]:
    """Returns a list of user requests

    Args:
        limit (int | Unset):
        request_type (ListUserRequestsRequestType | Unset):
        request_user_id (str | Unset):
        request_device_id (str | Unset):
        request_rule_id (str | Unset):
        request_url (str | Unset):
        request_responded_by (str | Unset):
        request_status (ListUserRequestsRequestStatus | Unset):
        cursor (str | Unset):
        sort (ListUserRequestsSort | Unset):
        order (Order | Unset): The sort order

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ApiError | ListUserRequestsResponse200]
    """

    kwargs = _get_kwargs(
        limit=limit,
        request_type=request_type,
        request_user_id=request_user_id,
        request_device_id=request_device_id,
        request_rule_id=request_rule_id,
        request_url=request_url,
        request_responded_by=request_responded_by,
        request_status=request_status,
        cursor=cursor,
        sort=sort,
        order=order,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    limit: int | Unset = UNSET,
    request_type: ListUserRequestsRequestType | Unset = UNSET,
    request_user_id: str | Unset = UNSET,
    request_device_id: str | Unset = UNSET,
    request_rule_id: str | Unset = UNSET,
    request_url: str | Unset = UNSET,
    request_responded_by: str | Unset = UNSET,
    request_status: ListUserRequestsRequestStatus | Unset = UNSET,
    cursor: str | Unset = UNSET,
    sort: ListUserRequestsSort | Unset = UNSET,
    order: Order | Unset = UNSET,
) -> ApiError | ListUserRequestsResponse200 | None:
    """Returns a list of user requests

    Args:
        limit (int | Unset):
        request_type (ListUserRequestsRequestType | Unset):
        request_user_id (str | Unset):
        request_device_id (str | Unset):
        request_rule_id (str | Unset):
        request_url (str | Unset):
        request_responded_by (str | Unset):
        request_status (ListUserRequestsRequestStatus | Unset):
        cursor (str | Unset):
        sort (ListUserRequestsSort | Unset):
        order (Order | Unset): The sort order

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ApiError | ListUserRequestsResponse200
    """

    return (
        await asyncio_detailed(
            client=client,
            limit=limit,
            request_type=request_type,
            request_user_id=request_user_id,
            request_device_id=request_device_id,
            request_rule_id=request_rule_id,
            request_url=request_url,
            request_responded_by=request_responded_by,
            request_status=request_status,
            cursor=cursor,
            sort=sort,
            order=order,
        )
    ).parsed
