#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import http
import inspect
import logging
import os
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, urlparse

import pytest
from httpx import AsyncClient
from playwright.async_api import Page
from pytest_operator.plugin import OpsTest

from oauth_tools.external_idp import ExternalIdpService
from oauth_tools.oauth_helpers import (
    complete_auth_code_login,
    complete_device_login,
    deploy_identity_bundle,
)

logger = logging.getLogger(__name__)


def get_this_script_dir() -> Path:
    filename = inspect.getframeinfo(inspect.currentframe()).filename  # type: ignore[arg-type]
    path = os.path.dirname(os.path.abspath(filename))
    return Path(path)


def get_bundle_template() -> Path:
    return get_this_script_dir() / ".." / ".." / "bundle.yaml.j2"


@pytest.mark.skip_if_deployed
@pytest.mark.abort_on_fail
async def test_deploy_istio_control_plane(ops_test: OpsTest) -> None:
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


@pytest.mark.skip_if_deployed
@pytest.mark.abort_on_fail
async def test_render_and_deploy_bundle(
    ops_test: OpsTest, ext_idp_service: ExternalIdpService
) -> None:
    """Render the bundle from template and deploy using ops_test."""
    await ops_test.model.set_config({"logging-config": "<root>=WARNING; unit=DEBUG"})

    logger.info(f"Rendering bundle {get_bundle_template()}")

    # set the "testing" template variable so the template renders for testing
    context = {"testing": "true", "channel": "edge"}

    logger.debug(f"Using context {context}")

    rendered_bundle = ops_test.render_bundle(get_bundle_template(), context=context)

    logger.info(f"Rendered bundle {str(rendered_bundle)}")

    await deploy_identity_bundle(
        ops_test, bundle_url=str(rendered_bundle), ext_idp_service=ext_idp_service
    )


@pytest.mark.abort_on_fail
async def test_hydra_is_up(
    ops_test: OpsTest,
    public_ingress_address: str,
    hydra_app_name: str,
    http_client: AsyncClient,
) -> None:
    """Check that hydra and its environment dependencies (e.g. the database) are responsive."""
    health_check_endpoint = (
        f"https://{public_ingress_address}/{ops_test.model_name}-{hydra_app_name}/health/ready"
    )

    resp = await http_client.get(health_check_endpoint)
    assert resp.status_code == http.HTTPStatus.OK, (
        f"Expected HTTP {http.HTTPStatus.OK} for {health_check_endpoint}, got {resp.status_code}."
    )


@pytest.mark.skip
@pytest.mark.abort_on_fail
async def test_kratos_is_up(
    ops_test: OpsTest,
    admin_ingress_address: str,
    kratos_app_name: str,
    http_client: AsyncClient,
) -> None:
    """Check that kratos and its environment dependencies (e.g. the database) are responsive."""
    health_check_endpoint = f"https://{admin_ingress_address}/{ops_test.model_name}-{kratos_app_name}/admin/health/ready"

    resp = await http_client.get(health_check_endpoint)
    assert resp.status_code == http.HTTPStatus.OK, (
        f"Expected HTTP {http.HTTPStatus.OK} for {health_check_endpoint}, got {resp.status_code}."
    )


@pytest.mark.skip
@pytest.mark.abort_on_fail
async def test_kratos_external_idp_redirect_url(
    ops_test: OpsTest,
    ext_idp_service: ExternalIdpService,
    kratos_external_idp_integrator_app_name: str,
) -> None:
    await ops_test.model.applications[kratos_external_idp_integrator_app_name].set_config({
        "issuer_url": ext_idp_service.issuer_url,
        "provider_id": "Dex",
    })

    await ops_test.model.wait_for_idle(
        raise_on_blocked=False,
        raise_on_error=False,
        status="active",
        timeout=10 * 60,
    )

    get_redirect_uri_action = (
        await ops_test.model.applications[kratos_external_idp_integrator_app_name]
        .units[0]
        .run_action("get-redirect-uri")
    )

    action_output = await get_redirect_uri_action.wait()
    assert "redirect-uri" in action_output.results

    ext_idp_service.update_redirect_uri(action_output.results["redirect-uri"])


@pytest.mark.skip
@pytest.mark.skip_if_deployed
async def test_multiple_kratos_external_idp_integrators(
    ops_test: OpsTest, kratos_app_name: str
) -> None:
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
        [kratos_app_name, additional_idp_name],
        raise_on_blocked=False,
        status="active",
        timeout=6 * 60,
    )

    # Check that the redirect_uri is returned by the action
    get_redirect_uri_action = (
        await ops_test.model.applications[additional_idp_name]
        .units[0]
        .run_action("get-redirect-uri")
    )

    action_output = await get_redirect_uri_action.wait()
    assert "redirect-uri" in action_output.results


@pytest.mark.skip
async def test_kratos_scale_up(ops_test: OpsTest, kratos_app_name: str) -> None:
    """Check that kratos works after it is scaled up."""
    app = ops_test.model.applications[kratos_app_name]

    await app.scale(3)

    await ops_test.model.wait_for_idle(
        apps=[kratos_app_name],
        raise_on_blocked=True,
        status="active",
        timeout=10 * 60,
        wait_for_exact_units=3,
    )


@pytest.mark.skip
async def test_hydra_scale_up(ops_test: OpsTest, hydra_app_name: str) -> None:
    """Check that hydra works after it is scaled up."""
    app = ops_test.model.applications[hydra_app_name]

    await app.scale(3)

    await ops_test.model.wait_for_idle(
        apps=[hydra_app_name],
        raise_on_blocked=True,
        status="active",
        timeout=10 * 60,
        wait_for_exact_units=3,
    )


@pytest.mark.skip
async def test_create_hydra_client(ops_test: OpsTest, hydra_app_name: str) -> None:
    """Register a client on hydra."""
    app = ops_test.model.applications[hydra_app_name]
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
    page: Page,
    ext_idp_service: ExternalIdpService,
    user_email: str,
    hydra_app_name: str,
    public_ingress_address: str,
    authorization_url: Callable,
    auth_code_grant_request: Callable,
    userinfo_request: Callable,
    refresh_token_request: Callable,
) -> None:
    # This is a hack, we just need a server to be running on the redirect_uri
    # so that when we get redirected there we don't get a connection_refused
    # error.
    scopes = ["openid", "profile", "email", "offline_access"]
    redirect_uri = f"https://{public_ingress_address}/{ops_test.model_name}-dummy/"
    app = ops_test.model.applications[hydra_app_name]
    action = await app.units[0].run_action(
        "create-oauth-client",
        **{
            "redirect-uris": [redirect_uri],
            "grant-types": ["authorization_code", "refresh_token"],
            "scope": scopes,
        },
    )
    res = (await action.wait()).results
    client_id = res["client-id"]
    client_secret = res["client-secret"]

    # Go to hydra authorization endpoint
    await page.goto(
        await authorization_url(
            client_id,
            redirect_uri,
            scope=" ".join(scopes),
        )
    )

    await complete_auth_code_login(page, ops_test, ext_idp_service=ext_idp_service)

    await page.wait_for_url(redirect_uri + "?*")

    parsed_url = urlparse(page.url)
    query_params = parse_qs(parsed_url.query)

    assert "code" in query_params

    # Exchange code for tokens
    resp = await auth_code_grant_request(
        client_id, client_secret, query_params["code"][0], redirect_uri
    )
    token_resp = resp.json()

    assert resp.status_code == 200
    assert "id_token" in token_resp
    assert "access_token" in token_resp
    assert "refresh_token" in token_resp

    # Try to use the access token
    resp = await userinfo_request(token_resp["access_token"])
    userinfo_resp = resp.json()

    assert resp.status_code == 200
    assert userinfo_resp["email"] == user_email

    # Try the refresh token
    resp = await refresh_token_request(client_id, client_secret, token_resp["refresh_token"])
    refresh_resp = resp.json()

    assert resp.status_code == 200
    assert "id_token" in refresh_resp
    assert "access_token" in refresh_resp
    assert "refresh_token" in refresh_resp

    # Try to use the new access token
    resp = await userinfo_request(refresh_resp["access_token"])
    userinfo_resp = resp.json()

    assert resp.status_code == 200
    assert userinfo_resp["email"] == user_email


async def test_client_credentials_flow(
    ops_test: OpsTest,
    hydra_app_name: str,
    client_credentials_grant_request: Callable,
) -> None:
    app = ops_test.model.applications[hydra_app_name]
    action = await app.units[0].run_action(
        "create-oauth-client",
        **{
            "grant-types": ["client_credentials"],
        },
    )
    res = (await action.wait()).results
    client_id = res["client-id"]
    client_secret = res["client-secret"]

    resp = await client_credentials_grant_request(client_id, client_secret)
    assert "access_token" in resp.json()


async def test_device_flow(
    ops_test: OpsTest,
    page: Page,
    ext_idp_service: ExternalIdpService,
    user_email: str,
    hydra_app_name: str,
    device_auth_request: Callable,
    device_token_request: Callable,
    userinfo_request: Callable,
    refresh_token_request: Callable,
) -> None:
    scopes = ["openid", "profile", "email", "offline_access"]
    app = ops_test.model.applications[hydra_app_name]
    action = await app.units[0].run_action(
        "create-oauth-client",
        **{
            "grant-types": ["urn:ietf:params:oauth:grant-type:device_code", "refresh_token"],
            "scope": scopes,
        },
    )
    res = (await action.wait()).results
    client_id = res["client-id"]
    client_secret = res["client-secret"]

    # Make the device auth request
    resp = await device_auth_request(client_id, client_secret, scope=" ".join(scopes))
    device_auth_resp = resp.json()

    assert "user_code" in device_auth_resp
    assert "device_code" in device_auth_resp
    assert "verification_uri" in device_auth_resp
    assert "verification_uri_complete" in device_auth_resp

    # Polling with the device code
    resp = await device_token_request(client_id, client_secret, device_auth_resp["device_code"])
    assert resp.status_code == 400
    assert resp.json()["error"] == "authorization_pending"

    # Complete browser flow
    await complete_device_login(
        page,
        ops_test,
        device_auth_resp["verification_uri_complete"],
        ext_idp_service=ext_idp_service,
    )

    # Exchange device code for tokens
    resp = await device_token_request(client_id, client_secret, device_auth_resp["device_code"])
    token_resp = resp.json()

    assert resp.status_code == 200
    assert "id_token" in token_resp
    assert "access_token" in token_resp
    assert "refresh_token" in token_resp

    # Try to use the access token
    resp = await userinfo_request(token_resp["access_token"])
    userinfo_resp = resp.json()

    assert resp.status_code == 200
    assert userinfo_resp["email"] == user_email

    # Try the refresh token
    resp = refresh_token_request(client_id, client_secret, token_resp["refresh_token"])
    refresh_resp = resp.json()

    assert resp.status_code == 200
    assert "id_token" in refresh_resp
    assert "access_token" in refresh_resp
    assert "refresh_token" in refresh_resp

    # Try to use the new access token
    resp = userinfo_request(refresh_resp["access_token"])
    userinfo_resp = resp.json()

    assert resp.status_code == 200
    assert userinfo_resp["email"] == user_email
