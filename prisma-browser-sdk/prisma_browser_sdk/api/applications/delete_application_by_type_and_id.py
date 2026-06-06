from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.delete_application_by_type_and_id_response_400 import DeleteApplicationByTypeAndIDResponse400
from ...models.delete_application_by_type_and_id_type import DeleteApplicationByTypeAndIDType
from ...types import Response


def _get_kwargs(
    type_: DeleteApplicationByTypeAndIDType,
    id: str,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "delete",
        "url": "/seb-api/v1/applications/type/{type_}/{id}".format(
            type_=quote(str(type_), safe=""),
            id=quote(str(id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Any | DeleteApplicationByTypeAndIDResponse400 | None:
    if response.status_code == 204:
        response_204 = cast(Any, None)
        return response_204

    if response.status_code == 400:
        response_400 = DeleteApplicationByTypeAndIDResponse400.from_dict(response.json())

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
) -> Response[Any | DeleteApplicationByTypeAndIDResponse400]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    type_: DeleteApplicationByTypeAndIDType,
    id: str,
    *,
    client: AuthenticatedClient | Client,
) -> Response[Any | DeleteApplicationByTypeAndIDResponse400]:
    """Deletes an application

     Removes an application of the specified type from the system.

    Args:
        type_ (DeleteApplicationByTypeAndIDType):
        id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | DeleteApplicationByTypeAndIDResponse400]
    """

    kwargs = _get_kwargs(
        type_=type_,
        id=id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    type_: DeleteApplicationByTypeAndIDType,
    id: str,
    *,
    client: AuthenticatedClient | Client,
) -> Any | DeleteApplicationByTypeAndIDResponse400 | None:
    """Deletes an application

     Removes an application of the specified type from the system.

    Args:
        type_ (DeleteApplicationByTypeAndIDType):
        id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | DeleteApplicationByTypeAndIDResponse400
    """

    return sync_detailed(
        type_=type_,
        id=id,
        client=client,
    ).parsed


async def asyncio_detailed(
    type_: DeleteApplicationByTypeAndIDType,
    id: str,
    *,
    client: AuthenticatedClient | Client,
) -> Response[Any | DeleteApplicationByTypeAndIDResponse400]:
    """Deletes an application

     Removes an application of the specified type from the system.

    Args:
        type_ (DeleteApplicationByTypeAndIDType):
        id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | DeleteApplicationByTypeAndIDResponse400]
    """

    kwargs = _get_kwargs(
        type_=type_,
        id=id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    type_: DeleteApplicationByTypeAndIDType,
    id: str,
    *,
    client: AuthenticatedClient | Client,
) -> Any | DeleteApplicationByTypeAndIDResponse400 | None:
    """Deletes an application

     Removes an application of the specified type from the system.

    Args:
        type_ (DeleteApplicationByTypeAndIDType):
        id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | DeleteApplicationByTypeAndIDResponse400
    """

    return (
        await asyncio_detailed(
            type_=type_,
            id=id,
            client=client,
        )
    ).parsed
