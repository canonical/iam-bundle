#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import os
from typing import Any, AsyncGenerator, Callable, Coroutine, Dict, Generator

import pytest
from lightkube import Client, KubeConfig
from lightkube.core.exceptions import ApiError
from playwright.async_api import async_playwright
from playwright.async_api._generated import Browser, BrowserContext, BrowserType, Page
from playwright.async_api._generated import Playwright as AsyncPlaywright
from pytest_operator.plugin import OpsTest

from integration.dex import (
    apply_dex_resources,
    create_dex_resources,
    get_dex_manifest,
    get_dex_service_url,
)

logger = logging.getLogger(__name__)
KUBECONFIG = os.environ.get("TESTING_KUBECONFIG", "~/.kube/config")


@pytest.fixture(scope="session")
def client() -> Client:
    return Client(config=KubeConfig.from_file(KUBECONFIG), field_manager="dex-test")


@pytest.fixture(scope="module")
def ext_idp_service(ops_test: OpsTest, client: Client) -> Generator[str, None, None]:
    # Use ops-lib-manifests?
    try:
        logger.info("Deploying dex resources")
        create_dex_resources(client)

        # We need to set the dex issuer_url to be the IP that was assigned to
        # the dex service by metallb. We can't know that before hand, so we
        # reapply the dex manifests.
        apply_dex_resources(client)

        yield get_dex_service_url(client)
    finally:
        if ops_test.keep_model:
            return
        logger.info("Deleting dex resources")
        for obj in get_dex_manifest():
            try:
                client.delete(type(obj), obj.metadata.name, namespace=obj.metadata.namespace)
            except ApiError:
                pass


@pytest.fixture()
def external_user_email() -> str:
    return "admin@example.com"


@pytest.fixture()
def external_user_password() -> str:
    return "password"


# The playwright fixtures are taken from:
# https://github.com/microsoft/playwright-python/blob/main/tests/async/conftest.py
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
    elif browser_name == "webkit":
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
    browser_factory: Callable[..., Coroutine[Any, Any, Browser]]
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
    context_factory: Callable[..., Coroutine[Any, Any, BrowserContext]]
) -> AsyncGenerator[BrowserContext, None]:
    context = await context_factory(ignore_https_errors=True)
    yield context
    await context.close()


@pytest.fixture
async def page(context: BrowserContext) -> AsyncGenerator[Page, None]:
    page = await context.new_page()
    yield page
    await page.close()
