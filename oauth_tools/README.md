# Oauth Tools

## Overview

`oauth_tools` is a python module that provides a bunch of helper functions for deploying the `identity-platform bundle` and performing authn flows. This module is being used both internally in the identity-platform bundle and on other charms that integrate with the identity platform.

## Installation

`oauth_tools` is not published to pypi, you can install it from github by including the following URL on your requirements.txt:
```
git+https://github.com/canonical/iam-bundle@<version>#egg=oauth_tools
```

`oauth_tools` depends on [playwright](https://playwright.dev/) to perform the browser tests. For this reason you will need to install the pytest [playwright plugin](https://playwright.dev/python/docs/intro). A typical `tox.ini` test section will look like this:
```
[testenv:integration]
description = Run integration tests
deps =
    ...
    git+https://github.com/canonical/iam-bundle@IAM-877#egg=oauth_tools
commands =
    playwright install
    pytest ...
```

## Usage

`oauth_tools` provides a bunch of [helper functions](./oauth_helpers.py) as well as [pytest fixtures](./fixtures.py) that can be used to deploy the identity bundle and it's dependencies.

To enable the `oauth_tools` fixtures, add this to your test file:
```python
pytest_plugins = ["oauth_tools.fixtures"]
```

An example of an oauth_tools test case looks like this:

```python
from playwright.async_api._generated import Page, BrowserContext
from oauth_tools import (
  deploy_identity_bundle,
  DexIdpService,
)

pytest_plugins = ["oauth_tools.fixtures"]


async def test_build_and_deploy(
    ops_test: OpsTest,
    hydra_app_name: str,
    public_traefik_app_name: str,
    self_signed_certificates_app_name: str,
    ext_idp_service: DexIdpService,
):
    # `ext_idp_service` will deploy an external idp to use for loggining in and manage it's lifecycle

    # Deploy the identity bundle
    await deploy_identity_bundle(
        ops_test=ops_test, bundle_channel="0.1/edge", ext_idp_service=ext_idp_service
    )

    # Deploy your charm
    ...

    # Integrate your charm with the bundle
    await ops_test.model.integrate("<your-charm>:oauth", hydra_app_name)
    # Trust the certificate that is used by hydra
    await ops_test.model.integrate("<your-charm>:receive-ca-cert", self_signed_certificates_app_name)

    await ops_test.model.wait_for_idle(
        status="active",
        raise_on_blocked=False,
        raise_on_error=False,
        timeout=1000,
    )

async def test_oauth_login_with_identity_bundle(
    ops_test: OpsTest,
    page: Page,
    context: BrowserContext,
    public_traefik_app_name: str,
    external_user_email: str,
    ext_idp_service: DexIdpService,
) -> None:
    # Access your application's login page
    await access_application_login_page(
        page=page, url=<some_url>, redirect_login_url=redirect_login
    )

    # Click your application's login button
    await click_on_sign_in_button_by_text(
        page=page, text="some-text"
    )

    # The user is redirected to the identity-bundle. Complete the login flow.
    await complete_auth_code_login(
        page=page, ops_test=ops_test, ext_idp_service=ext_idp_service
    )

    # Verify that the user is logged in
    ...
```

### Debugging Playwright tests

To debug your playwright tests, you can run your tests using `PWDEBUG=1`.

```shell
PWDEBUG=1 PYTHONPATH=. pytest ...
```

## Contributing

Please see [CONTRIBUTING.md](./CONTRIBUTING.md) for developer guidance.
