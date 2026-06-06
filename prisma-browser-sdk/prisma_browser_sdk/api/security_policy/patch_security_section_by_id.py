from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.patch_security_section_by_id_response_200 import PatchSecuritySectionByIDResponse200
from ...models.patch_security_section_by_id_response_400 import PatchSecuritySectionByIDResponse400
from ...models.patch_security_section_by_id_response_401 import PatchSecuritySectionByIDResponse401
from ...models.patch_security_section_by_id_response_403 import PatchSecuritySectionByIDResponse403
from ...models.patch_security_section_by_id_response_404 import PatchSecuritySectionByIDResponse404
from ...models.patch_security_section_by_id_response_500 import PatchSecuritySectionByIDResponse500
from ...models.section_patch_request import SectionPatchRequest
from ...types import Response


def _get_kwargs(
    id: str,
    *,
    body: SectionPatchRequest,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "patch",
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
) -> (
    PatchSecuritySectionByIDResponse200
    | PatchSecuritySectionByIDResponse400
    | PatchSecuritySectionByIDResponse401
    | PatchSecuritySectionByIDResponse403
    | PatchSecuritySectionByIDResponse404
    | PatchSecuritySectionByIDResponse500
    | None
):
    if response.status_code == 200:
        response_200 = PatchSecuritySectionByIDResponse200.from_dict(response.json())

        return response_200

    if response.status_code == 400:
        response_400 = PatchSecuritySectionByIDResponse400.from_dict(response.json())

        return response_400

    if response.status_code == 401:
        response_401 = PatchSecuritySectionByIDResponse401.from_dict(response.json())

        return response_401

    if response.status_code == 403:
        response_403 = PatchSecuritySectionByIDResponse403.from_dict(response.json())

        return response_403

    if response.status_code == 404:
        response_404 = PatchSecuritySectionByIDResponse404.from_dict(response.json())

        return response_404

    if response.status_code == 500:
        response_500 = PatchSecuritySectionByIDResponse500.from_dict(response.json())

        return response_500

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[
    PatchSecuritySectionByIDResponse200
    | PatchSecuritySectionByIDResponse400
    | PatchSecuritySectionByIDResponse401
    | PatchSecuritySectionByIDResponse403
    | PatchSecuritySectionByIDResponse404
    | PatchSecuritySectionByIDResponse500
]:
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
    body: SectionPatchRequest,
) -> Response[
    PatchSecuritySectionByIDResponse200
    | PatchSecuritySectionByIDResponse400
    | PatchSecuritySectionByIDResponse401
    | PatchSecuritySectionByIDResponse403
    | PatchSecuritySectionByIDResponse404
    | PatchSecuritySectionByIDResponse500
]:
    """Partially update a security policy section.

     Partially update a security policy section by its unique identifier. All fields are optional; at
    least one must be provided. Supports updating the section name and/or repositioning the section
    within the policy. Only operates on sections of type security.

    Args:
        id (str):
        body (SectionPatchRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[PatchSecuritySectionByIDResponse200 | PatchSecuritySectionByIDResponse400 | PatchSecuritySectionByIDResponse401 | PatchSecuritySectionByIDResponse403 | PatchSecuritySectionByIDResponse404 | PatchSecuritySectionByIDResponse500]
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
    body: SectionPatchRequest,
) -> (
    PatchSecuritySectionByIDResponse200
    | PatchSecuritySectionByIDResponse400
    | PatchSecuritySectionByIDResponse401
    | PatchSecuritySectionByIDResponse403
    | PatchSecuritySectionByIDResponse404
    | PatchSecuritySectionByIDResponse500
    | None
):
    """Partially update a security policy section.

     Partially update a security policy section by its unique identifier. All fields are optional; at
    least one must be provided. Supports updating the section name and/or repositioning the section
    within the policy. Only operates on sections of type security.

    Args:
        id (str):
        body (SectionPatchRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        PatchSecuritySectionByIDResponse200 | PatchSecuritySectionByIDResponse400 | PatchSecuritySectionByIDResponse401 | PatchSecuritySectionByIDResponse403 | PatchSecuritySectionByIDResponse404 | PatchSecuritySectionByIDResponse500
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
    body: SectionPatchRequest,
) -> Response[
    PatchSecuritySectionByIDResponse200
    | PatchSecuritySectionByIDResponse400
    | PatchSecuritySectionByIDResponse401
    | PatchSecuritySectionByIDResponse403
    | PatchSecuritySectionByIDResponse404
    | PatchSecuritySectionByIDResponse500
]:
    """Partially update a security policy section.

     Partially update a security policy section by its unique identifier. All fields are optional; at
    least one must be provided. Supports updating the section name and/or repositioning the section
    within the policy. Only operates on sections of type security.

    Args:
        id (str):
        body (SectionPatchRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[PatchSecuritySectionByIDResponse200 | PatchSecuritySectionByIDResponse400 | PatchSecuritySectionByIDResponse401 | PatchSecuritySectionByIDResponse403 | PatchSecuritySectionByIDResponse404 | PatchSecuritySectionByIDResponse500]
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
    body: SectionPatchRequest,
) -> (
    PatchSecuritySectionByIDResponse200
    | PatchSecuritySectionByIDResponse400
    | PatchSecuritySectionByIDResponse401
    | PatchSecuritySectionByIDResponse403
    | PatchSecuritySectionByIDResponse404
    | PatchSecuritySectionByIDResponse500
    | None
):
    """Partially update a security policy section.

     Partially update a security policy section by its unique identifier. All fields are optional; at
    least one must be provided. Supports updating the section name and/or repositioning the section
    within the policy. Only operates on sections of type security.

    Args:
        id (str):
        body (SectionPatchRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        PatchSecuritySectionByIDResponse200 | PatchSecuritySectionByIDResponse400 | PatchSecuritySectionByIDResponse401 | PatchSecuritySectionByIDResponse403 | PatchSecuritySectionByIDResponse404 | PatchSecuritySectionByIDResponse500
    """

    return (
        await asyncio_detailed(
            id=id,
            client=client,
            body=body,
        )
    ).parsed
