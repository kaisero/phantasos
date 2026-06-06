from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.custom_patch_application_input import CustomPatchApplicationInput
from ...models.local_desktop_patch_application_input import LocalDesktopPatchApplicationInput
from ...models.non_web_patch_application_input import NonWebPatchApplicationInput
from ...models.patch_application_by_type_and_id_response_200 import PatchApplicationByTypeAndIDResponse200
from ...models.patch_application_by_type_and_id_response_400 import PatchApplicationByTypeAndIDResponse400
from ...models.patch_application_by_type_and_id_response_409 import PatchApplicationByTypeAndIDResponse409
from ...models.patch_application_by_type_and_id_type import PatchApplicationByTypeAndIDType
from ...models.private_patch_application_input import PrivatePatchApplicationInput
from ...types import Response


def _get_kwargs(
    type_: PatchApplicationByTypeAndIDType,
    id: str,
    *,
    body: CustomPatchApplicationInput
    | LocalDesktopPatchApplicationInput
    | NonWebPatchApplicationInput
    | PrivatePatchApplicationInput,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/seb-api/v1/applications/type/{type_}/{id}".format(
            type_=quote(str(type_), safe=""),
            id=quote(str(id), safe=""),
        ),
    }

    if isinstance(body, CustomPatchApplicationInput):
        _kwargs["json"] = body.to_dict()
    elif isinstance(body, PrivatePatchApplicationInput):
        _kwargs["json"] = body.to_dict()
    elif isinstance(body, NonWebPatchApplicationInput):
        _kwargs["json"] = body.to_dict()
    else:
        _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    Any
    | PatchApplicationByTypeAndIDResponse200
    | PatchApplicationByTypeAndIDResponse400
    | PatchApplicationByTypeAndIDResponse409
    | None
):
    if response.status_code == 200:
        response_200 = PatchApplicationByTypeAndIDResponse200.from_dict(response.json())

        return response_200

    if response.status_code == 400:
        response_400 = PatchApplicationByTypeAndIDResponse400.from_dict(response.json())

        return response_400

    if response.status_code == 403:
        response_403 = cast(Any, None)
        return response_403

    if response.status_code == 404:
        response_404 = cast(Any, None)
        return response_404

    if response.status_code == 409:
        response_409 = PatchApplicationByTypeAndIDResponse409.from_dict(response.json())

        return response_409

    if response.status_code == 500:
        response_500 = cast(Any, None)
        return response_500

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[
    Any
    | PatchApplicationByTypeAndIDResponse200
    | PatchApplicationByTypeAndIDResponse400
    | PatchApplicationByTypeAndIDResponse409
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    type_: PatchApplicationByTypeAndIDType,
    id: str,
    *,
    client: AuthenticatedClient | Client,
    body: CustomPatchApplicationInput
    | LocalDesktopPatchApplicationInput
    | NonWebPatchApplicationInput
    | PrivatePatchApplicationInput,
) -> Response[
    Any
    | PatchApplicationByTypeAndIDResponse200
    | PatchApplicationByTypeAndIDResponse400
    | PatchApplicationByTypeAndIDResponse409
]:
    """Updates an application

     Partially updates an application - provided attributes are set as specified, others remain
    unchanged.

    **URL Limit:** For custom, private, and non-web applications, there is a tenant-wide limit of 15,000
    URLs combined. Exceeding this limit returns a 400 Bad Request error.

    Args:
        type_ (PatchApplicationByTypeAndIDType):
        id (str):
        body (CustomPatchApplicationInput | LocalDesktopPatchApplicationInput |
            NonWebPatchApplicationInput | PrivatePatchApplicationInput):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | PatchApplicationByTypeAndIDResponse200 | PatchApplicationByTypeAndIDResponse400 | PatchApplicationByTypeAndIDResponse409]
    """

    kwargs = _get_kwargs(
        type_=type_,
        id=id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    type_: PatchApplicationByTypeAndIDType,
    id: str,
    *,
    client: AuthenticatedClient | Client,
    body: CustomPatchApplicationInput
    | LocalDesktopPatchApplicationInput
    | NonWebPatchApplicationInput
    | PrivatePatchApplicationInput,
) -> (
    Any
    | PatchApplicationByTypeAndIDResponse200
    | PatchApplicationByTypeAndIDResponse400
    | PatchApplicationByTypeAndIDResponse409
    | None
):
    """Updates an application

     Partially updates an application - provided attributes are set as specified, others remain
    unchanged.

    **URL Limit:** For custom, private, and non-web applications, there is a tenant-wide limit of 15,000
    URLs combined. Exceeding this limit returns a 400 Bad Request error.

    Args:
        type_ (PatchApplicationByTypeAndIDType):
        id (str):
        body (CustomPatchApplicationInput | LocalDesktopPatchApplicationInput |
            NonWebPatchApplicationInput | PrivatePatchApplicationInput):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | PatchApplicationByTypeAndIDResponse200 | PatchApplicationByTypeAndIDResponse400 | PatchApplicationByTypeAndIDResponse409
    """

    return sync_detailed(
        type_=type_,
        id=id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    type_: PatchApplicationByTypeAndIDType,
    id: str,
    *,
    client: AuthenticatedClient | Client,
    body: CustomPatchApplicationInput
    | LocalDesktopPatchApplicationInput
    | NonWebPatchApplicationInput
    | PrivatePatchApplicationInput,
) -> Response[
    Any
    | PatchApplicationByTypeAndIDResponse200
    | PatchApplicationByTypeAndIDResponse400
    | PatchApplicationByTypeAndIDResponse409
]:
    """Updates an application

     Partially updates an application - provided attributes are set as specified, others remain
    unchanged.

    **URL Limit:** For custom, private, and non-web applications, there is a tenant-wide limit of 15,000
    URLs combined. Exceeding this limit returns a 400 Bad Request error.

    Args:
        type_ (PatchApplicationByTypeAndIDType):
        id (str):
        body (CustomPatchApplicationInput | LocalDesktopPatchApplicationInput |
            NonWebPatchApplicationInput | PrivatePatchApplicationInput):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | PatchApplicationByTypeAndIDResponse200 | PatchApplicationByTypeAndIDResponse400 | PatchApplicationByTypeAndIDResponse409]
    """

    kwargs = _get_kwargs(
        type_=type_,
        id=id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    type_: PatchApplicationByTypeAndIDType,
    id: str,
    *,
    client: AuthenticatedClient | Client,
    body: CustomPatchApplicationInput
    | LocalDesktopPatchApplicationInput
    | NonWebPatchApplicationInput
    | PrivatePatchApplicationInput,
) -> (
    Any
    | PatchApplicationByTypeAndIDResponse200
    | PatchApplicationByTypeAndIDResponse400
    | PatchApplicationByTypeAndIDResponse409
    | None
):
    """Updates an application

     Partially updates an application - provided attributes are set as specified, others remain
    unchanged.

    **URL Limit:** For custom, private, and non-web applications, there is a tenant-wide limit of 15,000
    URLs combined. Exceeding this limit returns a 400 Bad Request error.

    Args:
        type_ (PatchApplicationByTypeAndIDType):
        id (str):
        body (CustomPatchApplicationInput | LocalDesktopPatchApplicationInput |
            NonWebPatchApplicationInput | PrivatePatchApplicationInput):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | PatchApplicationByTypeAndIDResponse200 | PatchApplicationByTypeAndIDResponse400 | PatchApplicationByTypeAndIDResponse409
    """

    return (
        await asyncio_detailed(
            type_=type_,
            id=id,
            client=client,
            body=body,
        )
    ).parsed
