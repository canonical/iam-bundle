#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
import logging
from os.path import join
from pathlib import Path
from time import sleep
from typing import Optional

import requests
from lightkube import Client, codecs
from lightkube.core.exceptions import ApiError, ObjectDeleted
from lightkube.resources.apps_v1 import Deployment
from lightkube.resources.core_v1 import Pod, Service
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)


DEX_MANIFESTS = Path(__file__).parent.parent.parent / "manifests" / "dex.yaml"


def get_dex_manifest(**context):
    with open(DEX_MANIFESTS, "r") as file:
        return codecs.load_all_yaml(file, context=context)


def dex_is_ready(client, issuer_url=None):
    for pod in client.list(Pod, namespace="dex", labels={"app": "dex"}):
        # Some pods may be deleted, if we are restarting
        try:
            client.wait(
                Pod, pod.metadata.name, for_conditions=["Ready", "Deleted"], namespace="dex"
            )
        except ObjectDeleted:
            pass
    client.wait(Deployment, "dex", namespace="dex", for_conditions=["Available"])
    if not issuer_url:
        issuer_url = get_dex_service_ip(client)

    resp = requests.get(join(issuer_url, ".well-known/openid-configuration"))
    if resp.status_code != 200:
        raise RuntimeError("Failed to deploy dex")


def apply_dex_resources(
    client: Client,
    client_id: str = "client_id",
    client_secret: str = "client_secret",
    redirect_uri: str = "",
    issuer_url: Optional[str] = None,
    restart: Optional[bool] = True,
    wait_for_ready: Optional[bool] = True,
) -> None:
    # Get the dex IP
    if not issuer_url:
        try:
            issuer_url = get_dex_service_ip(client)
        except ApiError:
            logger.info("No service found for dex")

    objs = get_dex_manifest(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        issuer_url=issuer_url,
    )

    for obj in objs:
        client.apply(obj, force=True)

    if restart:
        logger.info("Restarting dex")
        for pod in client.list(Pod, namespace="dex", labels={"app": "dex"}):
            client.delete(Pod, pod.metadata.name, namespace="dex")

    if wait_for_ready:
        logger.info("Waiting for dex to be ready")
        try:
            dex_is_ready(client, issuer_url)
        except (RuntimeError, RequestException):
            sleep(3)
            dex_is_ready(client, issuer_url)


def get_dex_service_ip(client: Client):
    service = client.get(Service, "dex", namespace="dex")
    return f"http://{service.status.loadBalancer.ingress[0].ip}:5556/"
