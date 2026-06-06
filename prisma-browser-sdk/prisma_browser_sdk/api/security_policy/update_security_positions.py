from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.api_error import ApiError
from ...models.positions_success_response import PositionsSuccessResponse
from ...models.update_security_positions_body import UpdateSecurityPositionsBody
from ...types import Response


def _get_kwargs(
    *,
    body: UpdateSecurityPositionsBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "put",
        "url": "/seb-api/v1/policy/security/positions",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ApiError | PositionsSuccessResponse | None:
    if response.status_code == 200:
        response_200 = PositionsSuccessResponse.from_dict(response.json())

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
) -> Response[ApiError | PositionsSuccessResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: UpdateSecurityPositionsBody,
) -> Response[ApiError | PositionsSuccessResponse]:
    """Update rule and section positions in the security policy

     Submits the full ordered list of rules and sections for the security policy. Array index determines
    position (index 0 = highest priority, evaluated first). All existing rules and sections must be
    included. Rules in a section must be contiguous.

    Args:
        body (UpdateSecurityPositionsBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ApiError | PositionsSuccessResponse]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    body: UpdateSecurityPositionsBody,
) -> ApiError | PositionsSuccessResponse | None:
    """Update rule and section positions in the security policy

     Submits the full ordered list of rules and sections for the security policy. Array index determines
    position (index 0 = highest priority, evaluated first). All existing rules and sections must be
    included. Rules in a section must be contiguous.

    Args:
        body (UpdateSecurityPositionsBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ApiError | PositionsSuccessResponse
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: UpdateSecurityPositionsBody,
) -> Response[ApiError | PositionsSuccessResponse]:
    """Update rule and section positions in the security policy

     Submits the full ordered list of rules and sections for the security policy. Array index determines
    position (index 0 = highest priority, evaluated first). All existing rules and sections must be
    included. Rules in a section must be contiguous.

    Args:
        body (UpdateSecurityPositionsBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ApiError | PositionsSuccessResponse]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: UpdateSecurityPositionsBody,
) -> ApiError | PositionsSuccessResponse | None:
    """Update rule and section positions in the security policy

     Submits the full ordered list of rules and sections for the security policy. Array index determines
    position (index 0 = highest priority, evaluated first). All existing rules and sections must be
    included. Rules in a section must be contiguous.

    Args:
        body (UpdateSecurityPositionsBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ApiError | PositionsSuccessResponse
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
