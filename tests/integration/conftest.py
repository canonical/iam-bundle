#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import asyncio
from secrets import token_urlsafe
from typing import AsyncGenerator, Awaitable, Callable, Optional
from urllib.parse import urlencode

import httpx
import pytest_asyncio
from httpx import AsyncClient, Response
from pytest_operator.plugin import OpsTest

pytest_plugins = ["oauth_tools.fixtures"]


async def get_k8s_service_address(namespace: str, service_name: str) -> str:
    cmd = [
        "kubectl",
        "-n",
        namespace,
        "get",
        f"service/{service_name}",
        "-o=jsonpath={.status.loadBalancer.ingress[0].ip}",
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await process.communicate()

    return stdout.decode().strip() if not process.returncode else ""


@pytest_asyncio.fixture
async def public_ingress_address(ops_test: OpsTest, public_load_balancer: str) -> str:
    return await get_k8s_service_address(ops_test.model_name, public_load_balancer)


@pytest_asyncio.fixture
async def admin_ingress_address(ops_test: OpsTest, admin_load_balancer: str) -> str:
    return await get_k8s_service_address(ops_test.model_name, admin_load_balancer)


@pytest_asyncio.fixture
async def http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(verify=False) as client:
        yield client


@pytest_asyncio.fixture
async def hydra_url(ops_test: OpsTest, public_ingress_address: str, hydra_app_name: str) -> str:
    return f"https://{public_ingress_address}/{ops_test.model_name}-{hydra_app_name}"


@pytest_asyncio.fixture
async def authorization_url(hydra_url: str) -> Callable[[str, str, Optional[str]], Awaitable[str]]:
    async def wrapper(
        client_id: str, redirect_uri: str, scope: Optional[str] = "openid profile email"
    ) -> str:
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "response_mode": "query",
            "scope": scope,
            "state": token_urlsafe(),
            "nonce": token_urlsafe(),
        }
        return f"{hydra_url}/oauth2/auth?{urlencode(params)}"

    return wrapper


@pytest_asyncio.fixture
async def client_credentials_grant_request(
    hydra_url: str, http_client: AsyncClient
) -> Callable[[str, str, Optional[str]], Awaitable[Response]]:
    async def wrapper(
        client_id: str, client_secret: str, scope: Optional[str] = "openid profile email"
    ) -> Response:
        body = {
            "grant_type": "client_credentials",
            "scope": scope,
        }

        return await http_client.post(
            url=f"{hydra_url}/oauth2/token",
            data=body,
            auth=(client_id, client_secret),
        )

    return wrapper


@pytest_asyncio.fixture
async def auth_code_grant_request(
    hydra_url: str, http_client: AsyncClient
) -> Callable[[str, str, str, str], Awaitable[Response]]:
    async def wrapper(
        client_id: str,
        client_secret: str,
        auth_code: str,
        redirect_uri: str,
    ) -> Response:
        body = {
            "code": auth_code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }

        return await http_client.post(
            url=f"{hydra_url}/oauth2/token",
            data=body,
            auth=(client_id, client_secret),
        )

    return wrapper


@pytest_asyncio.fixture
async def refresh_token_request(
    hydra_url: str,
    http_client: AsyncClient,
) -> Callable[[str, str, str], Awaitable[Response]]:
    async def wrapper(client_id: str, client_secret: str, refresh_token: str) -> Response:
        body = {
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }

        return await http_client.post(
            url=f"{hydra_url}/oauth2/token",
            data=body,
            auth=(client_id, client_secret),
        )

    return wrapper


@pytest_asyncio.fixture
async def userinfo_request(
    hydra_url: str, http_client: AsyncClient
) -> Callable[[str], Awaitable[Response]]:
    async def wrapper(access_token: str) -> Response:
        return await http_client.get(
            url=f"{hydra_url}/userinfo",
            headers={
                "Authorization": "Bearer " + access_token,
                "Content-Type": "application/json",
            },
        )

    return wrapper


@pytest_asyncio.fixture
async def device_auth_request(
    hydra_url: str,
    http_client: AsyncClient,
) -> Callable[[str, str, Optional[str]], Awaitable[Response]]:
    async def wrapper(
        client_id: str, client_secret: str, scope: Optional[str] = "openid email offline_access"
    ) -> Response:
        body = {
            "scope": scope,
            "client_id": client_id,
        }

        return await http_client.post(
            url=f"{hydra_url}/oauth2/device/auth",
            data=body,
            auth=(client_id, client_secret),
        )

    return wrapper


@pytest_asyncio.fixture
async def device_token_request(
    hydra_url: str,
    http_client: AsyncClient,
) -> Callable[[str, str, str], Awaitable[Response]]:
    async def wrapper(client_id: str, client_secret: str, device_code: str) -> Response:
        body = {
            "device_code": device_code,
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "client_id": client_id,
        }

        return await http_client.post(
            url=f"{hydra_url}/oauth2/token",
            data=body,
            auth=(client_id, client_secret),
        )

    return wrapper
