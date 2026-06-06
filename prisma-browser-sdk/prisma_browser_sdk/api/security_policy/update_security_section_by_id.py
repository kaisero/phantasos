from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.api_error import ApiError
from ...models.section_update_request import SectionUpdateRequest
from ...models.update_security_section_by_id_response_200 import UpdateSecuritySectionByIDResponse200
from ...types import Response


def _get_kwargs(
    id: str,
    *,
    body: SectionUpdateRequest,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "put",
        "url": "/seb-api/v1/policy/security/sections/{id}".format(
            id=quote(str(id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ApiError | UpdateSecuritySectionByIDResponse200 | None:
    if response.status_code == 200:
        response_200 = UpdateSecuritySectionByIDResponse200.from_dict(response.json())

        return response_200

    if response.status_code == 400:
        response_400 = ApiError.from_dict(response.json())

        return response_400

    if response.status_code == 401:
        response_401 = ApiError.from_dict(response.json())

        return response_401

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
) -> Response[ApiError | UpdateSecuritySectionByIDResponse200]:
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
    body: SectionUpdateRequest,
) -> Response[ApiError | UpdateSecuritySectionByIDResponse200]:
    """Updates a security rule section.

     Updates a security rule section by its unique identifier. Only operates on sections of type
    security.

    Args:
        id (str):
        body (SectionUpdateRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ApiError | UpdateSecuritySectionByIDResponse200]
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
    body: SectionUpdateRequest,
) -> ApiError | UpdateSecuritySectionByIDResponse200 | None:
    """Updates a security rule section.

     Updates a security rule section by its unique identifier. Only operates on sections of type
    security.

    Args:
        id (str):
        body (SectionUpdateRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ApiError | UpdateSecuritySectionByIDResponse200
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
    body: SectionUpdateRequest,
) -> Response[ApiError | UpdateSecuritySectionByIDResponse200]:
    """Updates a security rule section.

     Updates a security rule section by its unique identifier. Only operates on sections of type
    security.

    Args:
        id (str):
        body (SectionUpdateRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ApiError | UpdateSecuritySectionByIDResponse200]
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
    body: SectionUpdateRequest,
) -> ApiError | UpdateSecuritySectionByIDResponse200 | None:
    """Updates a security rule section.

     Updates a security rule section by its unique identifier. Only operates on sections of type
    security.

    Args:
        id (str):
        body (SectionUpdateRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ApiError | UpdateSecuritySectionByIDResponse200
    """

    return (
        await asyncio_detailed(
            id=id,
            client=client,
            body=body,
        )
    ).parsed
