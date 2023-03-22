#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import inspect
import logging
import os
from pathlib import Path

import pytest
import requests
from pytest_operator.plugin import OpsTest

logger = logging.getLogger(__name__)

TRAEFIK_ADMIN_APP = "traefik-admin"
TRAEFIK_PUBLIC_APP = "traefik-public"


def get_this_script_dir() -> Path:
    filename = inspect.getframeinfo(inspect.currentframe()).filename  # type: ignore[arg-type]
    path = os.path.dirname(os.path.abspath(filename))
    return Path(path)


async def get_unit_address(ops_test: OpsTest, app_name: str, unit_num: int) -> str:
    """Get private address of a unit."""
    status = await ops_test.model.get_status()  # noqa: F821
    return status["applications"][app_name]["units"][f"{app_name}/{unit_num}"]["address"]


@pytest.mark.skip_if_deployed
@pytest.mark.abort_on_fail
async def test_render_and_deploy_bundle(ops_test: OpsTest):
    """Render the bundle from template and deploy using ops_test."""
    await ops_test.model.set_config({"logging-config": "<root>=WARNING; unit=DEBUG"})

    # logger.info("Rendering bundle %s", get_this_script_dir() / ".." / ".." / "bundle.yaml.j2")
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
            "client_id": os.environ["KRATOS_EXTERNAL_IDP_CLIENT_ID"],
            "microsoft_tenant_id": os.environ["KRATOS_EXTERNAL_IDP_TENANT_ID"],
            "client_secret": os.environ["KRATOS_EXTERNAL_IDP_CLIENT_SECRET"],
            "provider": "microsoft",
        }
    )

    async with ops_test.fast_forward():
        await ops_test.model.wait_for_idle(
            raise_on_blocked=False,
            raise_on_error=False,
            status="active",
            timeout=1000,
        )


@pytest.mark.abort_on_fail
async def test_hydra_is_up(ops_test: OpsTest):
    """Check that hydra and its environment dependencies (e.g. the database) are responsive."""
    app_name = "hydra"
    admin_address = await get_unit_address(ops_test, TRAEFIK_ADMIN_APP, 0)

    health_check_url = f"http://{admin_address}/{ops_test.model.name}-{app_name}/health/ready"
    logger.info(f"Hydra admin health check address: {health_check_url}")

    resp = requests.get(health_check_url)
    assert resp.status_code == 200


@pytest.mark.abort_on_fail
async def test_kratos_is_up(ops_test: OpsTest):
    """Check that kratos and its environment dependencies (e.g. the database) are responsive."""
    app_name = "kratos"
    admin_address = await get_unit_address(ops_test, TRAEFIK_ADMIN_APP, 0)

    health_check_url = (
        f"http://{admin_address}/{ops_test.model.name}-{app_name}/admin/health/ready"
    )
    logger.info(f"Kratos admin health check address: {health_check_url}")

    resp = requests.get(health_check_url)
    assert resp.status_code == 200
