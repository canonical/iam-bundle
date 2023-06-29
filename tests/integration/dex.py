#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from os.path import join
from pathlib import Path
from time import sleep
from typing import List, Optional

import requests
from lightkube import Client, codecs
from lightkube.core.exceptions import ApiError, ObjectDeleted
from lightkube.resources.apps_v1 import Deployment
from lightkube.resources.core_v1 import Pod, Service
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)


DEX_MANIFESTS = Path(__file__).parent.parent.parent / "manifests" / "dex.yaml"


def get_dex_manifest(
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    redirect_uri: Optional[str] = None,
    issuer_url: Optional[str] = None,
) -> List[codecs.AnyResource]:
    with open(DEX_MANIFESTS, "r") as file:
        return codecs.load_all_yaml(
            file,
            context={
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "issuer_url": issuer_url,
            },
        )


def _restart_dex(client: Client) -> None:
    for pod in client.list(Pod, namespace="dex", labels={"app": "dex"}):
        client.delete(Pod, pod.metadata.name, namespace="dex")


def _wait_until_dex_is_ready(client: Client, issuer_url: Optional[str] = None) -> None:
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
        issuer_url = get_dex_service_url(client)

    resp = requests.get(join(issuer_url, ".well-known/openid-configuration"))
    if resp.status_code != 200:
        raise RuntimeError("Failed to deploy dex")


def wait_until_dex_is_ready(client: Client, issuer_url: Optional[str] = None) -> None:
    try:
        _wait_until_dex_is_ready(client, issuer_url)
    except (RuntimeError, RequestException):
        # It may take some time for dex to restart, so we sleep a little
        # and try again
        sleep(3)
        _wait_until_dex_is_ready(client, issuer_url)


def _apply_dex_manifests(
    client: Client,
    client_id: str = "client_id",
    client_secret: str = "client_secret",
    redirect_uri: str = "",
    issuer_url: Optional[str] = None,
):
    objs = get_dex_manifest(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        issuer_url=issuer_url,
    )

    for obj in objs:
        client.apply(obj, force=True)


def create_dex_resources(
    client: Client,
    client_id: str = "client_id",
    client_secret: str = "client_secret",
    redirect_uri: str = "",
    issuer_url: Optional[str] = None,
):
    _apply_dex_manifests(
        client,
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        issuer_url=issuer_url,
    )

    logger.info("Waiting for dex to be ready")
    wait_until_dex_is_ready(client, issuer_url)


def apply_dex_resources(
    client: Client,
    client_id: str = "client_id",
    client_secret: str = "client_secret",
    redirect_uri: str = "",
    issuer_url: Optional[str] = None,
) -> None:
    if not issuer_url:
        try:
            issuer_url = get_dex_service_url(client)
        except ApiError:
            logger.info("No service found for dex")

    _apply_dex_manifests(
        client,
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        issuer_url=issuer_url,
    )

    logger.info("Restarting dex")
    _restart_dex(client)

    logger.info("Waiting for dex to be ready")
    wait_until_dex_is_ready(client, issuer_url)


def get_dex_service_url(client: Client) -> str:
    service = client.get(Service, "dex", namespace="dex")
    return f"http://{service.status.loadBalancer.ingress[0].ip}:5556/"
