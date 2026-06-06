from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.api_error import ApiError
from ...types import UNSET, Response, Unset


def _get_kwargs(
    id: str,
    *,
    delete_rules: bool | Unset = False,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["deleteRules"] = delete_rules

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "delete",
        "url": "/seb-api/v1/policy/customization/sections/{id}".format(
            id=quote(str(id), safe=""),
        ),
        "params": params,
    }

    return _kwargs


def _parse_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Any | ApiError | None:
    if response.status_code == 204:
        response_204 = cast(Any, None)
        return response_204

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


def _build_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Response[Any | ApiError]:
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
    delete_rules: bool | Unset = False,
) -> Response[Any | ApiError]:
    """Delete a customization rule section.

     Delete a customization rule section by its unique identifier.

    Args:
        id (str):
        delete_rules (bool | Unset):  Default: False.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | ApiError]
    """

    kwargs = _get_kwargs(
        id=id,
        delete_rules=delete_rules,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    id: str,
    *,
    client: AuthenticatedClient | Client,
    delete_rules: bool | Unset = False,
) -> Any | ApiError | None:
    """Delete a customization rule section.

     Delete a customization rule section by its unique identifier.

    Args:
        id (str):
        delete_rules (bool | Unset):  Default: False.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | ApiError
    """

    return sync_detailed(
        id=id,
        client=client,
        delete_rules=delete_rules,
    ).parsed


async def asyncio_detailed(
    id: str,
    *,
    client: AuthenticatedClient | Client,
    delete_rules: bool | Unset = False,
) -> Response[Any | ApiError]:
    """Delete a customization rule section.

     Delete a customization rule section by its unique identifier.

    Args:
        id (str):
        delete_rules (bool | Unset):  Default: False.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | ApiError]
    """

    kwargs = _get_kwargs(
        id=id,
        delete_rules=delete_rules,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    id: str,
    *,
    client: AuthenticatedClient | Client,
    delete_rules: bool | Unset = False,
) -> Any | ApiError | None:
    """Delete a customization rule section.

     Delete a customization rule section by its unique identifier.

    Args:
        id (str):
        delete_rules (bool | Unset):  Default: False.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | ApiError
    """

    return (
        await asyncio_detailed(
            id=id,
            client=client,
            delete_rules=delete_rules,
        )
    ).parsed
