#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import os
from typing import Any, Callable, Dict, Generator

import pytest
from dex import apply_dex_resources, get_dex_manifest, get_dex_service_ip
from lightkube import Client, KubeConfig
from lightkube.core.exceptions import ApiError
from lightkube.resources.apps_v1 import Deployment
from playwright.async_api import async_playwright
from playwright.async_api._generated import Browser, BrowserContext, BrowserType, Page
from playwright.async_api._generated import Playwright as AsyncPlaywright
from pytest_operator.plugin import OpsTest

logger = logging.getLogger(__name__)
KUBECONFIG = os.environ.get("TESTING_KUBECONFIG", "~/.kube/config")


@pytest.fixture(scope="session")
def client() -> Client:
    return Client(config=KubeConfig.from_file(KUBECONFIG), field_manager="dex-test")


@pytest.fixture(scope="module")
def dex(ops_test: OpsTest, client: Client) -> Generator[str, None, None]:
    # Use ops-lib-manifests?
    try:
        try:
            client.get(Deployment, "dex", namespace="dex")
        except ApiError:
            logger.info("Deploying dex resources")
            apply_dex_resources(client, restart=False)

            # We need to patch the dex service to apply the metallb ip, we don't know that before
            # the service is created
            apply_dex_resources(client)

        yield get_dex_service_ip(client)
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
def dex_user_email() -> str:
    return "admin@example.com"


@pytest.fixture()
def dex_user_password() -> str:
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
async def playwright() -> Generator[AsyncPlaywright, None, None]:
    async with async_playwright() as playwright_object:
        yield playwright_object


@pytest.fixture(scope="module")
def browser_type(playwright: AsyncPlaywright, browser_name: str) -> BrowserType:
    if browser_name == "chromium":
        return playwright.chromium
    if browser_name == "firefox":
        return playwright.firefox
    if browser_name == "webkit":
        return playwright.webkit


@pytest.fixture(scope="module")
async def browser_factory(
    launch_arguments: Dict, browser_type: BrowserType
) -> Generator[Browser, None, None]:
    browsers = []

    async def launch(**kwargs):
        browser = await browser_type.launch(**launch_arguments, **kwargs)
        browsers.append(browser)
        return browser

    yield launch
    for browser in browsers:
        await browser.close()


@pytest.fixture(scope="module")
async def browser(browser_factory: Browser) -> Generator[Browser, None, None]:
    browser = await browser_factory()
    yield browser
    await browser.close()


@pytest.fixture
async def context_factory(
    browser: Browser,
) -> Generator[Callable[..., BrowserContext], None, None]:
    contexts = []

    async def launch(**kwargs):
        context = await browser.new_context(**kwargs)
        contexts.append(context)
        return context

    yield launch
    for context in contexts:
        await context.close()


@pytest.fixture
async def context(context_factory: Callable[..., BrowserContext]) -> BrowserContext:
    context = await context_factory(ignore_https_errors=True)
    yield context
    await context.close()


@pytest.fixture
async def page(context: BrowserContext) -> Page:
    page = await context.new_page()
    yield page
    await page.close()
