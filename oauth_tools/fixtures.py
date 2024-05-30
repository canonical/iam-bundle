#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import os
from typing import Any, AsyncGenerator, Callable, Coroutine, Dict, Generator

import pytest
from lightkube import Client, KubeConfig
from playwright.async_api import async_playwright
from playwright.async_api._generated import Browser, BrowserContext, BrowserType, Page
from playwright.async_api._generated import Playwright as AsyncPlaywright
from pytest_operator.plugin import OpsTest

from oauth_tools.constants import APPS, DEX_CLIENT_ID, DEX_CLIENT_SECRET, EXTERNAL_USER_EMAIL
from oauth_tools.external_idp import DexIdpService

logger = logging.getLogger(__name__)
KUBECONFIG = os.environ.get("TESTING_KUBECONFIG", "~/.kube/config")


@pytest.fixture(scope="session")
def client() -> Client:
    return Client(config=KubeConfig.from_file(KUBECONFIG), field_manager="dex-test")


@pytest.fixture(scope="module")
def ext_idp_service(ops_test: OpsTest, client: Client) -> Generator[DexIdpService, None, None]:
    # Use ops-lib-manifests?
    ext_idp_manager = DexIdpService(client=client)
    try:
        logger.info("Deploying dex resources")

        yield ext_idp_manager
    finally:
        if ops_test.keep_model:
            return
        logger.info("Deleting dex resources")
        ext_idp_manager.remove_idp_service()


@pytest.fixture
def dex_client_id() -> str:
    return DEX_CLIENT_ID


@pytest.fixture
def dex_client_secret() -> str:
    return DEX_CLIENT_SECRET


@pytest.fixture
def user_email() -> str:
    return EXTERNAL_USER_EMAIL


@pytest.fixture
def hydra_app_name() -> str:
    return APPS.HYDRA


@pytest.fixture
def kratos_app_name() -> str:
    return APPS.KRATOS


@pytest.fixture
def kratos_external_idp_integrator_app_name() -> str:
    return APPS.KRATOS_EXTERNAL_IDP_INTEGRATOR


@pytest.fixture
def public_traefik_app_name() -> str:
    return APPS.TRAEFIK_PUBLIC


@pytest.fixture
def admin_traefik_app_name() -> str:
    return APPS.TRAEFIK_ADMIN


@pytest.fixture
def self_signed_certificates_app_name() -> str:
    return APPS.SELF_SIGNED_CERTIFICATES


# To learn more about playwright for python see https://github.com/microsoft/playwright-python.
# Fixtures are accessible from
# https://github.com/microsoft/playwright-python/blob/main/tests/async/conftest.py.
@pytest.fixture(scope="module")
def launch_arguments(pytestconfig: Any) -> Dict:
    return {
        "headless": not (pytestconfig.getoption("--headed") or os.getenv("HEADFUL", False)),
        "channel": pytestconfig.getoption("--browser-channel"),
    }


@pytest.fixture(scope="module")
async def playwright() -> AsyncGenerator[AsyncPlaywright, None]:
    async with async_playwright() as playwright_object:
        yield playwright_object


@pytest.fixture(scope="module")
def browser_type(playwright: AsyncPlaywright, browser_name: str) -> BrowserType:
    if browser_name == "firefox":
        return playwright.firefox
    if browser_name == "webkit":
        return playwright.webkit
    return playwright.chromium


@pytest.fixture(scope="module")
async def browser_factory(
    launch_arguments: Dict, browser_type: BrowserType
) -> AsyncGenerator[Callable[..., Coroutine[Any, Any, Browser]], None]:
    browsers = []

    async def launch(**kwargs: Any) -> Browser:
        browser = await browser_type.launch(**launch_arguments, **kwargs)
        browsers.append(browser)
        return browser

    yield launch
    for browser in browsers:
        await browser.close()


@pytest.fixture(scope="module")
async def browser(
    browser_factory: Callable[..., Coroutine[Any, Any, Browser]],
) -> AsyncGenerator[Browser, None]:
    browser = await browser_factory()
    yield browser
    await browser.close()


@pytest.fixture
async def context_factory(
    browser: Browser,
) -> AsyncGenerator[Callable[..., Coroutine[Any, Any, BrowserContext]], None]:
    contexts = []

    async def launch(**kwargs: Any) -> BrowserContext:
        context = await browser.new_context(**kwargs)
        contexts.append(context)
        return context

    yield launch
    for context in contexts:
        await context.close()


@pytest.fixture
async def context(
    context_factory: Callable[..., Coroutine[Any, Any, BrowserContext]],
) -> AsyncGenerator[BrowserContext, None]:
    context = await context_factory(ignore_https_errors=True)
    yield context
    await context.close()


@pytest.fixture
async def page(context: BrowserContext) -> AsyncGenerator[Page, None]:
    page = await context.new_page()
    yield page
    await page.close()
