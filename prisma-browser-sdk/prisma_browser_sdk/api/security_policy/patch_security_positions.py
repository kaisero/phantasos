from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.api_error import ApiError
from ...models.patch_positions_request import PatchPositionsRequest
from ...models.positions_success_response import PositionsSuccessResponse
from ...types import Response


def _get_kwargs(
    *,
    body: PatchPositionsRequest,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "patch",
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
    body: PatchPositionsRequest,
) -> Response[ApiError | PositionsSuccessResponse]:
    """Apply partial positional changes (moves) to the security policy

     Submits an ordered list of moves. Each move repositions one rule or section into an
    explicit container (target.sectionId) using a position keyword (top/bottom/before/after)
    plus an optional anchor. Section subjects auto-carry their child rules in the same relative
    order. Default (baseline) rules are pinned at the bottom and cannot be moved or anchored on.
    All moves apply atomically; if any move fails, no DB changes or audit events are produced.
    The failing move's index is in the error details.

    Args:
        body (PatchPositionsRequest): Request body for PATCH positions — an ordered list of moves
            to apply atomically. Example: {'moves': [{'subject': {'type': 'Rule', 'id':
            '0RU00000000000000000000000001'}, 'target': {'position': 'after', 'anchor': {'type':
            'Section', 'id': '0RS00000000000000000000000001'}, 'sectionId': None}}, {'subject':
            {'type': 'Section', 'id': '0RS00000000000000000000000002'}, 'target': {'position':
            'top'}}]}.

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
    body: PatchPositionsRequest,
) -> ApiError | PositionsSuccessResponse | None:
    """Apply partial positional changes (moves) to the security policy

     Submits an ordered list of moves. Each move repositions one rule or section into an
    explicit container (target.sectionId) using a position keyword (top/bottom/before/after)
    plus an optional anchor. Section subjects auto-carry their child rules in the same relative
    order. Default (baseline) rules are pinned at the bottom and cannot be moved or anchored on.
    All moves apply atomically; if any move fails, no DB changes or audit events are produced.
    The failing move's index is in the error details.

    Args:
        body (PatchPositionsRequest): Request body for PATCH positions — an ordered list of moves
            to apply atomically. Example: {'moves': [{'subject': {'type': 'Rule', 'id':
            '0RU00000000000000000000000001'}, 'target': {'position': 'after', 'anchor': {'type':
            'Section', 'id': '0RS00000000000000000000000001'}, 'sectionId': None}}, {'subject':
            {'type': 'Section', 'id': '0RS00000000000000000000000002'}, 'target': {'position':
            'top'}}]}.

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
    body: PatchPositionsRequest,
) -> Response[ApiError | PositionsSuccessResponse]:
    """Apply partial positional changes (moves) to the security policy

     Submits an ordered list of moves. Each move repositions one rule or section into an
    explicit container (target.sectionId) using a position keyword (top/bottom/before/after)
    plus an optional anchor. Section subjects auto-carry their child rules in the same relative
    order. Default (baseline) rules are pinned at the bottom and cannot be moved or anchored on.
    All moves apply atomically; if any move fails, no DB changes or audit events are produced.
    The failing move's index is in the error details.

    Args:
        body (PatchPositionsRequest): Request body for PATCH positions — an ordered list of moves
            to apply atomically. Example: {'moves': [{'subject': {'type': 'Rule', 'id':
            '0RU00000000000000000000000001'}, 'target': {'position': 'after', 'anchor': {'type':
            'Section', 'id': '0RS00000000000000000000000001'}, 'sectionId': None}}, {'subject':
            {'type': 'Section', 'id': '0RS00000000000000000000000002'}, 'target': {'position':
            'top'}}]}.

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
    body: PatchPositionsRequest,
) -> ApiError | PositionsSuccessResponse | None:
    """Apply partial positional changes (moves) to the security policy

     Submits an ordered list of moves. Each move repositions one rule or section into an
    explicit container (target.sectionId) using a position keyword (top/bottom/before/after)
    plus an optional anchor. Section subjects auto-carry their child rules in the same relative
    order. Default (baseline) rules are pinned at the bottom and cannot be moved or anchored on.
    All moves apply atomically; if any move fails, no DB changes or audit events are produced.
    The failing move's index is in the error details.

    Args:
        body (PatchPositionsRequest): Request body for PATCH positions — an ordered list of moves
            to apply atomically. Example: {'moves': [{'subject': {'type': 'Rule', 'id':
            '0RU00000000000000000000000001'}, 'target': {'position': 'after', 'anchor': {'type':
            'Section', 'id': '0RS00000000000000000000000001'}, 'sectionId': None}}, {'subject':
            {'type': 'Section', 'id': '0RS00000000000000000000000002'}, 'target': {'position':
            'top'}}]}.

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
