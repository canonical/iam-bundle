#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import collections
import inspect
import logging
import os
import re
from os.path import join
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
import requests
from lightkube import Client
from playwright.async_api import expect
from playwright.async_api._generated import Page
from pytest_operator.plugin import OpsTest

from integration.auth_utils import (
    auth_code_grant_request,
    client_credentials_grant_request,
    get_authorization_url,
    userinfo_request,
)
from integration.dex import apply_dex_resources

logger = logging.getLogger(__name__)

APPS = collections.namedtuple(
    "Apps",
    ["TRAEFIK_ADMIN", "TRAEFIK_PUBLIC", "HYDRA", "KRATOS", "KRATOS_EXTERNAL_IDP_INTEGRATOR"],
)(
    TRAEFIK_ADMIN="traefik-admin",
    TRAEFIK_PUBLIC="traefik-public",
    HYDRA="hydra",
    KRATOS="kratos",
    KRATOS_EXTERNAL_IDP_INTEGRATOR="kratos-external-idp-integrator",
)


DEX_CLIENT_ID = "client_id"
DEX_CLIENT_SECRET = "client_secret"


def get_this_script_dir() -> Path:
    filename = inspect.getframeinfo(inspect.currentframe()).filename  # type: ignore[arg-type]
    path = os.path.dirname(os.path.abspath(filename))
    return Path(path)


def get_bundle_template() -> Path:
    return get_this_script_dir() / ".." / ".." / "bundle.yaml.j2"


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
async def test_render_and_deploy_bundle(ops_test: OpsTest, ext_idp_service: str) -> None:
    """Render the bundle from template and deploy using ops_test."""
    await ops_test.model.set_config({"logging-config": "<root>=WARNING; unit=DEBUG"})

    logger.info(f"Rendering bundle {get_bundle_template()}")

    # set the "testing" template variable so the template renders for testing
    context = {"testing": "true", "channel": "edge"}

    logger.debug(f"Using context {context}")

    rendered_bundle = ops_test.render_bundle(get_bundle_template(), context=context)

    logger.info(f"Rendered bundle {str(rendered_bundle)}")

    await ops_test.run("juju", "deploy", rendered_bundle, "--trust")

    await ops_test.model.applications[APPS.KRATOS_EXTERNAL_IDP_INTEGRATOR].set_config(
        {
            "client_id": DEX_CLIENT_ID,
            "client_secret": DEX_CLIENT_SECRET,
            "provider": "generic",
            "issuer_url": "https://path/to/dex",
            "scope": "profile email",
        }
    )

    await ops_test.model.wait_for_idle(
        raise_on_blocked=False,
        status="active",
        timeout=2000,
    )


@pytest.mark.abort_on_fail
async def test_hydra_is_up(ops_test: OpsTest) -> None:
    """Check that hydra and its environment dependencies (e.g. the database) are responsive."""
    hydra_url = await get_reverse_proxy_app_url(ops_test, APPS.TRAEFIK_ADMIN, APPS.HYDRA)

    health_check_url = join(hydra_url, "health/ready")

    resp = requests.get(health_check_url, verify=False)
    assert resp.status_code == 200


@pytest.mark.abort_on_fail
async def test_kratos_is_up(ops_test: OpsTest) -> None:
    """Check that kratos and its environment dependencies (e.g. the database) are responsive."""
    kratos_url = await get_reverse_proxy_app_url(ops_test, APPS.TRAEFIK_ADMIN, APPS.KRATOS)

    health_check_url = join(kratos_url, "admin/health/ready")

    resp = requests.get(health_check_url, verify=False)
    assert resp.status_code == 200


@pytest.mark.abort_on_fail
async def test_kratos_external_idp_redirect_url(
    ops_test: OpsTest, client: Client, ext_idp_service: str
) -> None:
    await ops_test.model.applications[APPS.KRATOS_EXTERNAL_IDP_INTEGRATOR].set_config(
        {"issuer_url": ext_idp_service, "provider_id": "Dex"}
    )

    await ops_test.model.wait_for_idle(
        raise_on_blocked=False,
        raise_on_error=False,
        status="active",
        timeout=2000,
    )

    get_redirect_uri_action = (
        await ops_test.model.applications[APPS.KRATOS_EXTERNAL_IDP_INTEGRATOR]
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
async def test_multiple_kratos_external_idp_integrators(ops_test: OpsTest) -> None:
    """Deploy an additional external idp integrator charm and test the action.

    The purpose of this test is to check that kratos allows for integration
    with multiple IdPs.
    """
    additional_idp_name = "generic-external-idp"

    config = {
        "client_id": "client_id",
        "client_secret": "client_secret",
        "provider": "generic",
        "issuer_url": "http://path/to/dex",
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
    await ops_test.model.integrate(
        "generic-external-idp:kratos-external-idp", "kratos:kratos-external-idp"
    )

    await ops_test.model.wait_for_idle(
        raise_on_blocked=False,
        status="active",
        timeout=360,
    )
    assert ops_test.model.applications[additional_idp_name].units[0].workload_status == "active"
    assert ops_test.model.applications[APPS.KRATOS].units[0].workload_status == "active"

    # Check that the redirect_uri is returned by the action
    get_redirect_uri_action = (
        await ops_test.model.applications[additional_idp_name]
        .units[0]
        .run_action("get-redirect-uri")
    )

    action_output = await get_redirect_uri_action.wait()
    assert "redirect-uri" in action_output.results


async def test_kratos_scale_up(ops_test: OpsTest) -> None:
    """Check that kratos works after it is scaled up."""
    app = ops_test.model.applications[APPS.KRATOS]

    await app.scale(3)

    await ops_test.model.wait_for_idle(
        apps=[APPS.KRATOS],
        raise_on_blocked=True,
        status="active",
        timeout=2000,
        wait_for_exact_units=3,
    )


async def test_hydra_scale_up(ops_test: OpsTest) -> None:
    """Check that hydra works after it is scaled up."""
    app = ops_test.model.applications[APPS.HYDRA]

    await app.scale(3)

    await ops_test.model.wait_for_idle(
        apps=[APPS.HYDRA],
        raise_on_blocked=True,
        status="active",
        timeout=2000,
        wait_for_exact_units=3,
    )


async def test_create_hydra_client(ops_test: OpsTest, ext_idp_service: str) -> None:
    """Register a client on hydra."""
    app = ops_test.model.applications[APPS.HYDRA]
    action = await app.units[0].run_action(
        "create-oauth-client",
        **{
            "grant-types": ["authorization_code", "client_credentials"],
        },
    )

    res = (await action.wait()).results

    assert res["client-id"]
    assert res["client-secret"]


async def test_authorization_code_flow(
    ops_test: OpsTest,
    ext_idp_service: str,
    external_user_email: str,
    external_user_password: str,
    page: Page,
) -> None:
    # This is a hack, we just need a server to be running on the redirect_uri
    # so that when we get redirected there we don't get a connection_refused
    # error.
    redirect_uri = await get_reverse_proxy_app_url(ops_test, APPS.TRAEFIK_PUBLIC, "dummy")
    app = ops_test.model.applications[APPS.HYDRA]
    action = await app.units[0].run_action(
        "create-oauth-client",
        **{
            "redirect-uris": [redirect_uri],
            "grant-types": ["authorization_code"],
        },
    )
    res = (await action.wait()).results
    client_id = res["client-id"]
    client_secret = res["client-secret"]

    hydra_url = await get_reverse_proxy_app_url(ops_test, APPS.TRAEFIK_PUBLIC, APPS.HYDRA)

    # Go to hydra authorization endpoint
    await page.goto(get_authorization_url(hydra_url, client_id, redirect_uri))

    expected_url = join(
        await get_reverse_proxy_app_url(
            ops_test, APPS.TRAEFIK_PUBLIC, "identity-platform-login-ui-operator"
        ),
        "ui/login",
    )
    await expect(page).to_have_url(re.compile(rf"{expected_url}*"))

    # Choose provider
    async with page.expect_navigation():
        await page.get_by_role("button", name="Dex").click()

    await expect(page).to_have_url(re.compile(rf"{ext_idp_service}*"))

    # Login
    await page.get_by_placeholder("email address").click()
    await page.get_by_placeholder("email address").fill(external_user_email)
    await page.get_by_placeholder("password").click()
    await page.get_by_placeholder("password").fill(external_user_password)
    await page.get_by_role("button", name="Login").click()

    await page.wait_for_url(redirect_uri + "?*")

    parsed_url = urlparse(page.url)
    query_params = parse_qs(parsed_url.query)

    assert "code" in query_params

    # Exchange code for tokens
    resp = auth_code_grant_request(
        hydra_url, client_id, client_secret, query_params["code"][0], redirect_uri
    )
    json_resp = resp.json()

    assert "id_token" in json_resp
    assert "access_token" in json_resp

    # Try to use the access token
    resp = userinfo_request(hydra_url, json_resp["access_token"])
    json_resp = resp.json()

    assert resp.status_code == 200
    assert json_resp["email"] == external_user_email


async def test_client_credentials_flow(
    ops_test: OpsTest,
) -> None:
    app = ops_test.model.applications[APPS.HYDRA]
    action = await app.units[0].run_action(
        "create-oauth-client",
        **{
            "grant-types": ["client_credentials"],
        },
    )
    res = (await action.wait()).results
    client_id = res["client-id"]
    client_secret = res["client-secret"]

    hydra_url = await get_reverse_proxy_app_url(ops_test, APPS.TRAEFIK_PUBLIC, APPS.HYDRA)

    resp = client_credentials_grant_request(hydra_url, client_id, client_secret)

    assert "access_token" in resp.json()
