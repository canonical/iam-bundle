#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import asyncio
import inspect
import logging
import os
from pathlib import Path

import pytest
from pytest_operator.plugin import OpsTest


def get_this_script_dir() -> Path:
    filename = inspect.getframeinfo(inspect.currentframe()).filename  # type: ignore[arg-type]
    path = os.path.dirname(os.path.abspath(filename))
    return Path(path)


@pytest.mark.abort_on_fail
async def render_bundle(ops_test: OpsTest):
    """Render the bundle from template using ops_test"""
    await ops_test.model.set_config({"logging-config": "<root>=WARNING; unit=DEBUG"})

    logger.info("Rendering bundle %s", get_this_script_dir() / ".." / ".." / "bundle.yaml.j2")

    # set the "testing" template variable so the template renders for testing
    context["testing"] = "true"
    # test in edge channel
    context["channel"] = "edge"

    logger.debug("context: %s", context)

    rendered_bundle = ops_test.render_bundle(
        get_this_script_dir() / ".." / ".." / "bundle.yaml.j2", context=context
    )

    assert rendered_bundle
