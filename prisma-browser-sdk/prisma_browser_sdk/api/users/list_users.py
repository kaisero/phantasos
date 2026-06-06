import datetime
from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.api_error import ApiError
from ...models.list_users_response_200 import ListUsersResponse200
from ...models.list_users_sort import ListUsersSort
from ...models.order import Order
from ...models.user_status import UserStatus
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    limit: int | Unset = UNSET,
    include_deleted: bool | Unset = UNSET,
    user_name: str | Unset = UNSET,
    user_email: str | Unset = UNSET,
    user_first_seen_gte: datetime.datetime | Unset = UNSET,
    user_last_seen_lte: datetime.datetime | Unset = UNSET,
    user_status: UserStatus | Unset = UNSET,
    group_id: str | Unset = UNSET,
    cursor: str | Unset = UNSET,
    sort: ListUsersSort | Unset = UNSET,
    order: Order | Unset = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["limit"] = limit

    params["includeDeleted"] = include_deleted

    params["user.name"] = user_name

    params["user.email"] = user_email

    json_user_first_seen_gte: str | Unset = UNSET
    if not isinstance(user_first_seen_gte, Unset):
        json_user_first_seen_gte = user_first_seen_gte.isoformat()
    params["user.first_seen_gte"] = json_user_first_seen_gte

    json_user_last_seen_lte: str | Unset = UNSET
    if not isinstance(user_last_seen_lte, Unset):
        json_user_last_seen_lte = user_last_seen_lte.isoformat()
    params["user.last_seen_lte"] = json_user_last_seen_lte

    json_user_status: str | Unset = UNSET
    if not isinstance(user_status, Unset):
        json_user_status = user_status.value

    params["user.status"] = json_user_status

    params["groupId"] = group_id

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
        "url": "/seb-api/v1/users",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ApiError | ListUsersResponse200 | None:
    if response.status_code == 200:
        response_200 = ListUsersResponse200.from_dict(response.json())

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
) -> Response[ApiError | ListUsersResponse200]:
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
    include_deleted: bool | Unset = UNSET,
    user_name: str | Unset = UNSET,
    user_email: str | Unset = UNSET,
    user_first_seen_gte: datetime.datetime | Unset = UNSET,
    user_last_seen_lte: datetime.datetime | Unset = UNSET,
    user_status: UserStatus | Unset = UNSET,
    group_id: str | Unset = UNSET,
    cursor: str | Unset = UNSET,
    sort: ListUsersSort | Unset = UNSET,
    order: Order | Unset = UNSET,
) -> Response[ApiError | ListUsersResponse200]:
    """Returns a list of users

    Args:
        limit (int | Unset):
        include_deleted (bool | Unset):
        user_name (str | Unset):
        user_email (str | Unset):
        user_first_seen_gte (datetime.datetime | Unset):
        user_last_seen_lte (datetime.datetime | Unset):
        user_status (UserStatus | Unset): User status
        group_id (str | Unset):
        cursor (str | Unset):
        sort (ListUsersSort | Unset):
        order (Order | Unset): The sort order

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ApiError | ListUsersResponse200]
    """

    kwargs = _get_kwargs(
        limit=limit,
        include_deleted=include_deleted,
        user_name=user_name,
        user_email=user_email,
        user_first_seen_gte=user_first_seen_gte,
        user_last_seen_lte=user_last_seen_lte,
        user_status=user_status,
        group_id=group_id,
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
    include_deleted: bool | Unset = UNSET,
    user_name: str | Unset = UNSET,
    user_email: str | Unset = UNSET,
    user_first_seen_gte: datetime.datetime | Unset = UNSET,
    user_last_seen_lte: datetime.datetime | Unset = UNSET,
    user_status: UserStatus | Unset = UNSET,
    group_id: str | Unset = UNSET,
    cursor: str | Unset = UNSET,
    sort: ListUsersSort | Unset = UNSET,
    order: Order | Unset = UNSET,
) -> ApiError | ListUsersResponse200 | None:
    """Returns a list of users

    Args:
        limit (int | Unset):
        include_deleted (bool | Unset):
        user_name (str | Unset):
        user_email (str | Unset):
        user_first_seen_gte (datetime.datetime | Unset):
        user_last_seen_lte (datetime.datetime | Unset):
        user_status (UserStatus | Unset): User status
        group_id (str | Unset):
        cursor (str | Unset):
        sort (ListUsersSort | Unset):
        order (Order | Unset): The sort order

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ApiError | ListUsersResponse200
    """

    return sync_detailed(
        client=client,
        limit=limit,
        include_deleted=include_deleted,
        user_name=user_name,
        user_email=user_email,
        user_first_seen_gte=user_first_seen_gte,
        user_last_seen_lte=user_last_seen_lte,
        user_status=user_status,
        group_id=group_id,
        cursor=cursor,
        sort=sort,
        order=order,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    limit: int | Unset = UNSET,
    include_deleted: bool | Unset = UNSET,
    user_name: str | Unset = UNSET,
    user_email: str | Unset = UNSET,
    user_first_seen_gte: datetime.datetime | Unset = UNSET,
    user_last_seen_lte: datetime.datetime | Unset = UNSET,
    user_status: UserStatus | Unset = UNSET,
    group_id: str | Unset = UNSET,
    cursor: str | Unset = UNSET,
    sort: ListUsersSort | Unset = UNSET,
    order: Order | Unset = UNSET,
) -> Response[ApiError | ListUsersResponse200]:
    """Returns a list of users

    Args:
        limit (int | Unset):
        include_deleted (bool | Unset):
        user_name (str | Unset):
        user_email (str | Unset):
        user_first_seen_gte (datetime.datetime | Unset):
        user_last_seen_lte (datetime.datetime | Unset):
        user_status (UserStatus | Unset): User status
        group_id (str | Unset):
        cursor (str | Unset):
        sort (ListUsersSort | Unset):
        order (Order | Unset): The sort order

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ApiError | ListUsersResponse200]
    """

    kwargs = _get_kwargs(
        limit=limit,
        include_deleted=include_deleted,
        user_name=user_name,
        user_email=user_email,
        user_first_seen_gte=user_first_seen_gte,
        user_last_seen_lte=user_last_seen_lte,
        user_status=user_status,
        group_id=group_id,
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
    include_deleted: bool | Unset = UNSET,
    user_name: str | Unset = UNSET,
    user_email: str | Unset = UNSET,
    user_first_seen_gte: datetime.datetime | Unset = UNSET,
    user_last_seen_lte: datetime.datetime | Unset = UNSET,
    user_status: UserStatus | Unset = UNSET,
    group_id: str | Unset = UNSET,
    cursor: str | Unset = UNSET,
    sort: ListUsersSort | Unset = UNSET,
    order: Order | Unset = UNSET,
) -> ApiError | ListUsersResponse200 | None:
    """Returns a list of users

    Args:
        limit (int | Unset):
        include_deleted (bool | Unset):
        user_name (str | Unset):
        user_email (str | Unset):
        user_first_seen_gte (datetime.datetime | Unset):
        user_last_seen_lte (datetime.datetime | Unset):
        user_status (UserStatus | Unset): User status
        group_id (str | Unset):
        cursor (str | Unset):
        sort (ListUsersSort | Unset):
        order (Order | Unset): The sort order

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ApiError | ListUsersResponse200
    """

    return (
        await asyncio_detailed(
            client=client,
            limit=limit,
            include_deleted=include_deleted,
            user_name=user_name,
            user_email=user_email,
            user_first_seen_gte=user_first_seen_gte,
            user_last_seen_lte=user_last_seen_lte,
            user_status=user_status,
            group_id=group_id,
            cursor=cursor,
            sort=sort,
            order=order,
        )
    ).parsed
