from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.api_error import ApiError
from ...models.create_sign_in_rule_body import CreateSignInRuleBody
from ...models.create_sign_in_rule_response_201 import CreateSignInRuleResponse201
from ...types import Response


def _get_kwargs(
    *,
    body: CreateSignInRuleBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/seb-api/v1/policy/sign-in/rules",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ApiError | CreateSignInRuleResponse201 | None:
    if response.status_code == 201:
        response_201 = CreateSignInRuleResponse201.from_dict(response.json())

        return response_201

    if response.status_code == 400:
        response_400 = ApiError.from_dict(response.json())

        return response_400

    if response.status_code == 401:
        response_401 = ApiError.from_dict(response.json())

        return response_401

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
) -> Response[ApiError | CreateSignInRuleResponse201]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: CreateSignInRuleBody,
) -> Response[ApiError | CreateSignInRuleResponse201]:
    """Creates a new sign-in rule in the policy.

     Creates a new sign-in rule in the policy. The rule is created in the draft configuration and must be
    published to become active.

    Args:
        body (CreateSignInRuleBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ApiError | CreateSignInRuleResponse201]
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
    body: CreateSignInRuleBody,
) -> ApiError | CreateSignInRuleResponse201 | None:
    """Creates a new sign-in rule in the policy.

     Creates a new sign-in rule in the policy. The rule is created in the draft configuration and must be
    published to become active.

    Args:
        body (CreateSignInRuleBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ApiError | CreateSignInRuleResponse201
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: CreateSignInRuleBody,
) -> Response[ApiError | CreateSignInRuleResponse201]:
    """Creates a new sign-in rule in the policy.

     Creates a new sign-in rule in the policy. The rule is created in the draft configuration and must be
    published to become active.

    Args:
        body (CreateSignInRuleBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ApiError | CreateSignInRuleResponse201]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: CreateSignInRuleBody,
) -> ApiError | CreateSignInRuleResponse201 | None:
    """Creates a new sign-in rule in the policy.

     Creates a new sign-in rule in the policy. The rule is created in the draft configuration and must be
    published to become active.

    Args:
        body (CreateSignInRuleBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ApiError | CreateSignInRuleResponse201
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
