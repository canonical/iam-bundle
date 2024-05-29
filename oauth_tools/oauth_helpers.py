#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import re
from os.path import join
from typing import Dict, List, Optional

from playwright.async_api import expect
from playwright.async_api._generated import BrowserContext, Page
from pytest_operator.plugin import OpsTest

from oauth_tools.constants import APPS
from oauth_tools.external_idp import DexIdpService, ExternalIdpService

logger = logging.getLogger(__name__)


async def get_reverse_proxy_app_url(
    ops_test: OpsTest, ingress_app_name: str, app_name: str
) -> str:
    """Get the address of a proxied application."""
    status = await ops_test.model.get_status()  # noqa: F821
    address = status["applications"][ingress_app_name]["public-address"]
    return f"https://{address}/{ops_test.model.name}-{app_name}/"


async def deploy_identity_bundle(
    ops_test: OpsTest,
    bundle_url: str = "identity-platform",
    bundle_channel: Optional[str] = None,
    ext_idp_service: Optional[ExternalIdpService] = None,
):
    """Helper function for deploying and configuring the identity bundle and its dependencies."""
    if ext_idp_service and not isinstance(ext_idp_service, ExternalIdpService):
        raise ValueError(
            f"Invalid ext_idp_service type: {type(ext_idp_service)}, MUST be ExternalIdpManager or None"
        )

    deploy_cmd = ["juju", "deploy", bundle_url, "--trust"]
    if bundle_channel:
        deploy_cmd.extend(["--channel", bundle_channel])
    await ops_test.run(*deploy_cmd)

    # Wait for apps to go active, kratos_external_idp_integrator needs config to unblock
    await ops_test.model.wait_for_idle(
        [getattr(APPS, k) for k in APPS._fields if k != "KRATOS_EXTERNAL_IDP_INTEGRATOR"],
        raise_on_blocked=False,
        status="active",
        timeout=2000,
    )

    if not ext_idp_service:
        return

    await ops_test.model.applications[APPS.KRATOS_EXTERNAL_IDP_INTEGRATOR].set_config({
        "client_id": ext_idp_service.client_id,
        "client_secret": ext_idp_service.client_secret,
        "provider": "generic",
        "issuer_url": ext_idp_service.issuer_url,
        "scope": "profile email",
        "provider_id": "Dex",
    })
    await ops_test.model.wait_for_idle(
        raise_on_blocked=False,
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

    ext_idp_service.update_redirect_uri(redirect_uri=action_output.results["redirect-uri"])


async def clean_up_identity_bundle(
    ops_test: OpsTest,
    ext_idp_service: Optional[ExternalIdpService] = None,
):
    """Helper function for cleaning up the identity bundle and its dependencies."""
    for app in APPS.keys():
        await ops_test.model.remove_application(app, destroy_storage=True, no_wait=True)
    if ext_idp_service:
        ext_idp_service.remove_idp_service()


async def access_application_login_page(page: Page, url: str, redirect_login_url: str = ""):
    """Convenience function for navigating the browser to the login page.

    Usage:
        If the url of the application redirects to a login page, pass the application's url as url,
        and a pattern string for the login page as redirect_login_url.

        Otherwise pass the url of the application's login page as url, and leave redirect_login_url
        empty.
    """
    await page.goto(url)
    if redirect_login_url:
        await expect(page).to_have_url(re.compile(rf"{redirect_login_url}*"))


async def click_on_sign_in_button_by_text(page: Page, text: str):
    """Convenience function for retrieving the Oauth Sign In button by its displayed text."""
    async with page.expect_navigation():
        await page.get_by_text(text).click()


async def click_on_sign_in_button_by_alt_text(page: Page, alt_text: str):
    """Convenience function for retrieving the Oauth Sign In button by the alt text."""
    async with page.expect_navigation():
        await page.get_by_alt_text(alt_text).click()


async def complete_auth_code_login(
    page: Page, ops_test: OpsTest, ext_idp_service: Optional[ExternalIdpService] = None
) -> None:
    """Convenience function for navigating the external identity provider's user interface."""
    if not ext_idp_service:
        ext_idp_service = DexIdpService(ops_test=ops_test)
    elif not isinstance(ext_idp_service, ExternalIdpService):
        raise ValueError(
            f"Invalid ext_idp_service type: {type(ext_idp_service)}, MUST be ExternalIdpManager or None"
        )

    expected_url = join(
        await get_reverse_proxy_app_url(
            ops_test, APPS.TRAEFIK_PUBLIC, APPS.IDENTITY_PLATFORM_LOGIN_UI_OPERATOR
        ),
        "ui/login",
    )
    await expect(page).to_have_url(re.compile(rf"{expected_url}*"))
    async with page.expect_navigation():
        await page.get_by_role("button", name="Dex").click()

    await expect(page).to_have_url(re.compile(rf"{ext_idp_service.issuer_url}*"))
    await page.get_by_placeholder("email address").click()
    await page.get_by_placeholder("email address").fill(ext_idp_service.user_email)
    await page.get_by_placeholder("password").click()
    await page.get_by_placeholder("password").fill(ext_idp_service.user_password)
    await page.get_by_role("button", name="Login").click()


async def complete_device_login(
    page: Page,
    ops_test: OpsTest,
    verification_uri_complete: str,
    ext_idp_service: Optional[ExternalIdpService] = None,
) -> None:
    # Go to verification URL
    await page.goto(verification_uri_complete)
    expected_url = join(
        await get_reverse_proxy_app_url(
            ops_test, APPS.TRAEFIK_PUBLIC, "identity-platform-login-ui-operator"
        ),
        "ui/device_code",
    )
    await expect(page).to_have_url(re.compile(rf"{expected_url}*"))

    async with page.expect_navigation():
        await page.get_by_role("button", name="Next").click()

    await complete_auth_code_login(page, ops_test, ext_idp_service=ext_idp_service)

    expected_url = join(
        await get_reverse_proxy_app_url(
            ops_test, APPS.TRAEFIK_PUBLIC, "identity-platform-login-ui-operator"
        ),
        "ui/device_complete",
    )
    await page.wait_for_url(expected_url + "?*")


async def verify_page_loads(page: Page, url: str):
    """Convenience function for verifying that the correct url has been loaded."""
    await page.wait_for_url(url)


async def get_cookie_from_browser_by_name(
    browser_context: BrowserContext, name: str
) -> Optional[str]:
    """Convenience function for retrieving a cookie."""
    cookies = await browser_context.cookies()
    for cookie in cookies:
        if cookie["name"] == name:
            return cookie["value"]
    return None


async def get_cookies_from_browser_by_url(browser_context: BrowserContext, url: str) -> List[Dict]:
    """Convenience function for retrieving cookies belonging to a domain."""
    # see structure of returned dictionaries at
    # https://playwright.dev/docs/api/class-browsercontext#browser-context-cookies
    cookies = await browser_context.cookies(url)
    return cookies


__all__ = [
    "get_reverse_proxy_app_url",
    "deploy_identity_bundle",
    "clean_up_identity_bundle",
    "access_application_login_page",
    "click_on_sign_in_button_by_text",
    "click_on_sign_in_button_by_alt_text",
    "complete_auth_code_login",
    "complete_device_login",
    "verify_page_loads",
    "get_cookie_from_browser_by_name",
    "get_cookies_from_browser_by_url",
]
