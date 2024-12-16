#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import asyncio
from secrets import token_urlsafe
from typing import AsyncGenerator, Awaitable, Callable, Optional
from urllib.parse import urlencode

import httpx
import lightkube
import pytest
import pytest_asyncio
from httpx import AsyncClient, Response
from lightkube.generic_resource import create_namespaced_resource
from lightkube.models.meta_v1 import ObjectMeta
from pytest import FixtureRequest
from pytest_operator.plugin import OpsTest

pytest_plugins = ["oauth_tools.fixtures"]


AuthorizationPolicy = create_namespaced_resource(
    "security.istio.io",
    "v1",
    "AuthorizationPolicy",
    "authorizationpolicies",
)


def pytest_addoption(parser: pytest.Parser):
    parser.addoption(
        "--enable-service-mesh",
        action="store_true",
        default=False,
        help="Enable service mesh for the integration tests",
    )


@pytest.fixture
def enable_service_mesh(request: FixtureRequest):
    return request.config.getoption("--enable-service-mesh")


@pytest_asyncio.fixture(scope="module")
async def k8s_client() -> lightkube.AsyncClient:
    return lightkube.AsyncClient()


@pytest_asyncio.fixture
async def deploy_istio_service_mesh(
    ops_test: OpsTest, enable_service_mesh: bool, k8s_client: lightkube.AsyncClient
) -> None:
    # Deploy the istio control plane charm
    await ops_test.track_model(
        alias="istio-system",
        model_name="istio-system",
        destroy_storage=True,
    )
    istio_system = ops_test.models.get("istio-system")

    await istio_system.model.deploy(
        application_name="istio-k8s",
        entity_url="istio-k8s",
        channel="latest/edge",
        trust=True,
    )
    await istio_system.model.wait_for_idle(
        ["istio-k8s"],
        status="active",
        timeout=5 * 60,
    )

    if not enable_service_mesh:
        return

    # Deploy the istio beacon charm to add every application into the service mesh
    await ops_test.model.deploy(
        application_name="istio-beacon-k8s",
        entity_url="istio-beacon-k8s",
        channel="latest/edge",
        config={"model-on-mesh": True},
        trust=True,
    )
    await ops_test.model.wait_for_idle(
        ["istio-beacon-k8s"],
        status="active",
        timeout=5 * 60,
    )

    # TODO: remove the AuthorizationPolicy when https://github.com/canonical/istio-ingress-k8s-operator/issues/30 is fixed
    # Manually add an AuthorizationPolicy to allow all traffic
    allow_all_policy = AuthorizationPolicy(
        metadata=ObjectMeta(
            name="allow-all",
            namespace=ops_test.model_name,
        ),
        spec={
            "rules": [{}],
        },
    )

    await k8s_client.apply(allow_all_policy, field_manager="test-auth-policy")


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
