from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.catalog_application import CatalogApplication
from ...models.custom_application import CustomApplication
from ...models.get_application_by_id_response_400 import GetApplicationByIDResponse400
from ...models.local_desktop_application import LocalDesktopApplication
from ...models.non_web_application import NonWebApplication
from ...models.private_application import PrivateApplication
from ...types import UNSET, Response, Unset


def _get_kwargs(
    id: str,
    *,
    configuration_version: str | Unset = "draft",
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["configurationVersion"] = configuration_version

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/seb-api/v1/applications/{id}".format(
            id=quote(str(id), safe=""),
        ),
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    Any
    | CatalogApplication
    | CustomApplication
    | LocalDesktopApplication
    | NonWebApplication
    | PrivateApplication
    | GetApplicationByIDResponse400
    | None
):
    if response.status_code == 200:

        def _parse_response_200(
            data: object,
        ) -> CatalogApplication | CustomApplication | LocalDesktopApplication | NonWebApplication | PrivateApplication:
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_application_item_type_0 = CustomApplication.from_dict(data)

                return componentsschemas_application_item_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_application_item_type_1 = PrivateApplication.from_dict(data)

                return componentsschemas_application_item_type_1
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_application_item_type_2 = NonWebApplication.from_dict(data)

                return componentsschemas_application_item_type_2
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_application_item_type_3 = CatalogApplication.from_dict(data)

                return componentsschemas_application_item_type_3
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            if not isinstance(data, dict):
                raise TypeError()
            componentsschemas_application_item_type_4 = LocalDesktopApplication.from_dict(data)

            return componentsschemas_application_item_type_4

        response_200 = _parse_response_200(response.json())

        return response_200

    if response.status_code == 400:
        response_400 = GetApplicationByIDResponse400.from_dict(response.json())

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
) -> Response[
    Any
    | CatalogApplication
    | CustomApplication
    | LocalDesktopApplication
    | NonWebApplication
    | PrivateApplication
    | GetApplicationByIDResponse400
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
    configuration_version: str | Unset = "draft",
) -> Response[
    Any
    | CatalogApplication
    | CustomApplication
    | LocalDesktopApplication
    | NonWebApplication
    | PrivateApplication
    | GetApplicationByIDResponse400
]:
    """Returns an application

     Fetches a specific application object identified by its unique ID.

    Args:
        id (str):
        configuration_version (str | Unset):  Default: 'draft'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | CatalogApplication | CustomApplication | LocalDesktopApplication | NonWebApplication | PrivateApplication | GetApplicationByIDResponse400]
    """

    kwargs = _get_kwargs(
        id=id,
        configuration_version=configuration_version,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    id: str,
    *,
    client: AuthenticatedClient | Client,
    configuration_version: str | Unset = "draft",
) -> (
    Any
    | CatalogApplication
    | CustomApplication
    | LocalDesktopApplication
    | NonWebApplication
    | PrivateApplication
    | GetApplicationByIDResponse400
    | None
):
    """Returns an application

     Fetches a specific application object identified by its unique ID.

    Args:
        id (str):
        configuration_version (str | Unset):  Default: 'draft'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | CatalogApplication | CustomApplication | LocalDesktopApplication | NonWebApplication | PrivateApplication | GetApplicationByIDResponse400
    """

    return sync_detailed(
        id=id,
        client=client,
        configuration_version=configuration_version,
    ).parsed


async def asyncio_detailed(
    id: str,
    *,
    client: AuthenticatedClient | Client,
    configuration_version: str | Unset = "draft",
) -> Response[
    Any
    | CatalogApplication
    | CustomApplication
    | LocalDesktopApplication
    | NonWebApplication
    | PrivateApplication
    | GetApplicationByIDResponse400
]:
    """Returns an application

     Fetches a specific application object identified by its unique ID.

    Args:
        id (str):
        configuration_version (str | Unset):  Default: 'draft'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | CatalogApplication | CustomApplication | LocalDesktopApplication | NonWebApplication | PrivateApplication | GetApplicationByIDResponse400]
    """

    kwargs = _get_kwargs(
        id=id,
        configuration_version=configuration_version,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    id: str,
    *,
    client: AuthenticatedClient | Client,
    configuration_version: str | Unset = "draft",
) -> (
    Any
    | CatalogApplication
    | CustomApplication
    | LocalDesktopApplication
    | NonWebApplication
    | PrivateApplication
    | GetApplicationByIDResponse400
    | None
):
    """Returns an application

     Fetches a specific application object identified by its unique ID.

    Args:
        id (str):
        configuration_version (str | Unset):  Default: 'draft'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | CatalogApplication | CustomApplication | LocalDesktopApplication | NonWebApplication | PrivateApplication | GetApplicationByIDResponse400
    """

    return (
        await asyncio_detailed(
            id=id,
            client=client,
            configuration_version=configuration_version,
        )
    ).parsed
