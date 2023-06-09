#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import inspect
import logging
import os
from os.path import join
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
import requests
from lightkube import Client
from playwright.async_api._generated import Page
from pytest_operator.plugin import OpsTest

from tests.integration.auth_utils import (
    auth_code_grant_request,
    client_credentials_grant_request,
    construct_authorization_url,
)
from tests.integration.conftest import apply_dex_resources

logger = logging.getLogger(__name__)

TRAEFIK_ADMIN_APP = "traefik-admin"
TRAEFIK_PUBLIC_APP = "traefik-public"
DEX_CLIENT_ID = "client_id"
DEX_CLIENT_SECRET = "client_secret"


def get_this_script_dir() -> Path:
    filename = inspect.getframeinfo(inspect.currentframe()).filename  # type: ignore[arg-type]
    path = os.path.dirname(os.path.abspath(filename))
    return Path(path)


class State:
    """Object used to hold the (incremental) test state."""

    client_id: str
    client_secret: str
    redirect_uri: str


@pytest.fixture(scope="module")
def state() -> State:
    return State


async def get_unit_address(ops_test: OpsTest, app_name: str, unit_num: int) -> str:
    """Get private address of a unit."""
    status = await ops_test.model.get_status()  # noqa: F821
    return status["applications"][app_name]["units"][f"{app_name}/{unit_num}"]["address"]


async def get_app_address(ops_test: OpsTest, app_name: str) -> str:
    """Get address of an app."""
    status = await ops_test.model.get_status()  # noqa: F821
    return status["applications"][app_name]["public-address"]


async def get_reverse_proxy_app_url(
    ops_test: OpsTest, ingress_app_name: str, app_name: str
) -> str:
    address = await get_app_address(ops_test, ingress_app_name)
    return f"https://{address}/{ops_test.model.name}-{app_name}/"


@pytest.mark.skip_if_deployed
@pytest.mark.abort_on_fail
async def test_render_and_deploy_bundle(ops_test: OpsTest, dex: None):
    """Render the bundle from template and deploy using ops_test."""
    await ops_test.model.set_config({"logging-config": "<root>=WARNING; unit=DEBUG"})

    logger.info(f"Rendering bundle {get_this_script_dir() / '.. '/ '..' / 'bundle.yaml.j2'}")

    # set the "testing" template variable so the template renders for testing
    context = {"testing": "true", "channel": "edge"}

    logger.debug(f"Using context {context}")

    rendered_bundle = ops_test.render_bundle(
        get_this_script_dir() / ".." / ".." / "bundle.yaml.j2", context=context
    )

    logger.info(f"Rendered bundle {str(rendered_bundle)}")

    await ops_test.model.deploy(rendered_bundle, trust=True)

    await ops_test.model.applications["kratos-external-idp-integrator"].set_config(
        {
            "client_id": DEX_CLIENT_ID,
            "client_secret": DEX_CLIENT_SECRET,
            "provider": "generic",
            "issuer_url": dex,
            "scope": "profile email",
        }
    )

    await ops_test.model.wait_for_idle(
        raise_on_blocked=False,
        raise_on_error=False,
        status="active",
        timeout=2000,
    )


@pytest.mark.abort_on_fail
async def test_hydra_is_up(ops_test: OpsTest):
    """Check that hydra and its environment dependencies (e.g. the database) are responsive."""
    app_name = "hydra"
    admin_address = await get_app_address(ops_test, TRAEFIK_ADMIN_APP)

    health_check_url = f"https://{admin_address}/{ops_test.model.name}-{app_name}/health/ready"
    logger.info(f"Hydra admin health check address: {health_check_url}")

    resp = requests.get(health_check_url, verify=False)
    assert resp.status_code == 200


@pytest.mark.abort_on_fail
async def test_kratos_is_up(ops_test: OpsTest):
    """Check that kratos and its environment dependencies (e.g. the database) are responsive."""
    app_name = "kratos"
    admin_address = await get_app_address(ops_test, TRAEFIK_ADMIN_APP)

    health_check_url = (
        f"https://{admin_address}/{ops_test.model.name}-{app_name}/admin/health/ready"
    )
    logger.info(f"Kratos admin health check address: {health_check_url}")

    resp = requests.get(health_check_url, verify=False)
    assert resp.status_code == 200


@pytest.mark.abort_on_fail
async def test_kratos_external_idp_redirect_url(ops_test: OpsTest, client: Client):
    get_redirect_uri_action = (
        await ops_test.model.applications["kratos-external-idp-integrator"]
        .units[0]
        .run_action("get-redirect-uri")
    )

    action_output = await get_redirect_uri_action.wait()
    assert "redirect-uri" in action_output.results

    apply_dex_resources(
        client,
        client_id=DEX_CLIENT_ID,
        client_secret=DEX_CLIENT_SECRET,
        redirect_uri=action_output.results["redirect-uri"],
    )


@pytest.mark.skip_if_deployed
async def test_multiple_kratos_external_idp_integrators(
    ops_test: OpsTest, client: Client, dex: None
):
    """Deploy an additional external idp integrator charm and test the action.

    The purpose of this test is to check that kratos allows for integration
    with multiple IdPs.
    """
    additional_idp_name = "generic-external-idp"

    config = {
        "client_id": "id",
        "client_secret": "a12345",
        "provider": "generic",
        "issuer_url": dex,
        "scope": "profile email",
        "provider_id": "Other",
    }

    await ops_test.model.deploy(
        entity_url="kratos-external-idp-integrator",
        application_name=additional_idp_name,
        channel="edge",
        config=config,
        series="jammy",
    )
    await ops_test.model.add_relation(
        "generic-external-idp:kratos-external-idp", "kratos:kratos-external-idp"
    )

    await ops_test.model.wait_for_idle(
        raise_on_blocked=False,
        status="active",
        timeout=360,
    )
    assert ops_test.model.applications[additional_idp_name].units[0].workload_status == "active"
    assert ops_test.model.applications["kratos"].units[0].workload_status == "active"

    # Check that the redirect_uri is returned by the action
    get_redirect_uri_action = (
        await ops_test.model.applications[additional_idp_name]
        .units[0]
        .run_action("get-redirect-uri")
    )

    action_output = await get_redirect_uri_action.wait()
    assert "redirect-uri" in action_output.results


# async def test_kratos_scale_up(ops_test: OpsTest):
#     """Check that kratos works after it is scaled up."""
#     app_name = "kratos"

#     app = ops_test.model.applications[app_name]

#     await app.scale(3)

#     await ops_test.model.wait_for_idle(
#         raise_on_blocked=False,
#         raise_on_error=False,
#         status="active",
#         timeout=2000,
#     )

#     admin_address = await get_app_address(ops_test, TRAEFIK_ADMIN_APP)
#     health_check_url = (
#         f"https://{admin_address}/{ops_test.model.name}-{app_name}/admin/health/ready"
#     )
#     resp = requests.get(health_check_url, verify=False)

#     assert resp.status_code == 200


# async def test_hydra_scale_up(ops_test: OpsTest):
#     """Check that hydra works after it is scaled up."""
#     app_name = "hydra"

#     app = ops_test.model.applications[app_name]

#     await app.scale(3)

#     await ops_test.model.wait_for_idle(
#         raise_on_blocked=False,
#         raise_on_error=False,
#         status="active",
#         timeout=2000,
#     )

#     admin_address = await get_app_address(ops_test, TRAEFIK_ADMIN_APP)
#     health_check_url = f"https://{admin_address}/{ops_test.model.name}-{app_name}/health/ready"
#     resp = requests.get(health_check_url, verify=False)

#     assert resp.status_code == 200


async def test_create_hydra_client(ops_test: OpsTest, state: State, dex: str) -> None:
    """Register a client on hydra."""
    # This is a hack, we just need a server to be running on the redirect_uri
    # so that when we get redirected there we don't get an connection_refused
    # error.
    redirect_uri = join(dex, "some", "path")
    app = ops_test.model.applications["hydra"]
    action = await app.units[0].run_action(
        "create-oauth-client",
        **{
            "redirect-uris": [redirect_uri],
            "grant-types": ["authorization_code", "client_credentials"],
        },
    )

    res = (await action.wait()).results

    assert res["client-id"]
    assert res["client-secret"]
    assert res["redirect-uris"] == redirect_uri

    state.client_id = res["client-id"]
    state.client_secret = res["client-secret"]
    state.redirect_uri = res["redirect-uris"]


async def test_authorization_code_flow(
    ops_test: OpsTest,
    state: State,
    dex: str,
    dex_user_email: str,
    dex_user_password: str,
    page: Page,
) -> None:
    hydra_url = await get_reverse_proxy_app_url(ops_test, TRAEFIK_PUBLIC_APP, "hydra")

    # Go to hydra authorization endpoint
    await page.goto(construct_authorization_url(hydra_url, state.client_id, state.redirect_uri))

    expected_url = join(
        await get_reverse_proxy_app_url(
            ops_test, TRAEFIK_PUBLIC_APP, "identity-platform-login-ui-operator"
        ),
        "login",
    )
    assert page.url.startswith(expected_url + "?")

    # Choose provider
    async with page.expect_navigation():
        await page.get_by_role("button", name="Generic").click()

    assert page.url.startswith(dex)

    # Login
    await page.get_by_placeholder("email address").click()
    await page.get_by_placeholder("email address").fill(dex_user_email)
    await page.get_by_placeholder("password").click()
    await page.get_by_placeholder("password").fill(dex_user_password)
    await page.get_by_role("button", name="Login").click()

    await page.wait_for_url(state.redirect_uri + "?*")

    parsed = urlparse(page.url)
    q = parse_qs(parsed.query)

    assert "code" in q

    resp = auth_code_grant_request(
        hydra_url, state.client_id, state.client_secret, q["code"], state.redirect_uri
    )

    assert "id_token" in resp.json()
    assert "access_token" in resp.json()


async def test_client_credentials_flow(
    ops_test: OpsTest,
    state: State,
) -> None:
    hydra_url = await get_reverse_proxy_app_url(ops_test, TRAEFIK_PUBLIC_APP, "hydra")

    resp = client_credentials_grant_request(hydra_url, state.client_id, state.client_secret)

    assert "access_token" in resp.json()
