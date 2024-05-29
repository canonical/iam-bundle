#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import abc
import logging
from os.path import join
from time import sleep
from typing import List, Optional

import requests
from lightkube import Client, KubeConfig, codecs
from lightkube.core.exceptions import ApiError, ObjectDeleted
from lightkube.resources.apps_v1 import Deployment
from lightkube.resources.core_v1 import Namespace, Pod, Service
from pytest_operator.plugin import OpsTest
from requests.exceptions import RequestException

from oauth_tools.constants import (
    DEX_CLIENT_ID,
    DEX_CLIENT_SECRET,
    DEX_MANIFESTS,
    EXTERNAL_USER_EMAIL,
    EXTERNAL_USER_PASSWORD,
    KUBECONFIG,
)

logger = logging.getLogger(__name__)


class ExternalIdpService(abc.ABC):
    """Abstract class for managing lifecycle for an external IdP."""

    @property
    @abc.abstractmethod
    def client_id(self) -> str:
        """The client_id of a registered client."""
        ...

    @property
    @abc.abstractmethod
    def client_secret(self) -> str:
        """The client_sercet of a registered client."""
        ...

    @property
    @abc.abstractmethod
    def user_email(self) -> str:
        """The test user's email."""
        ...

    @property
    @abc.abstractmethod
    def user_password(self) -> str:
        """The test user's password."""
        ...

    @property
    @abc.abstractmethod
    def issuer_url(self) -> str:
        """The provider's issuer URL."""
        ...

    @abc.abstractmethod
    def create_idp_service(self) -> None:
        """Deploy and configure the idp service."""
        ...

    @abc.abstractmethod
    def remove_idp_service(self) -> None:
        """Remove and clean up the idp service."""
        ...

    @abc.abstractmethod
    def update_redirect_uri(self, redirect_uri: str) -> None:
        """Update the registered client's redirect_uri."""
        ...


class DexIdpService(ExternalIdpService):
    """Class for managing lifecycle for an external Dex IdP."""

    client_id = DEX_CLIENT_ID
    client_secret = DEX_CLIENT_SECRET
    user_email = EXTERNAL_USER_EMAIL
    user_password = EXTERNAL_USER_PASSWORD
    _namespace = "dex"

    def __init__(self, client: Optional[Client] = None):
        if not client:
            client = Client(config=KubeConfig.from_file(KUBECONFIG), field_manager="dex-test")
        self._client = client
        self._redirect_uri = ""
        if not self._dex_namespace_exists():
            self._apply_dex_resources()

    @property
    def issuer_url(self) -> str:
        """The provider's issuer URL."""
        service = self._client.get(Service, "dex", namespace=self.namespace)
        return f"http://{service.status.loadBalancer.ingress[0].ip}:5556/"

    @property
    def namespace(self) -> str:
        """The k8s namespace in which dex is deployed."""
        return self._namespace

    def _dex_namespace_exists(self) -> bool:
        try:
            self._client.get(Namespace, self.namespace)
            return True
        except ApiError:
            return False

    def _get_dex_manifest(self) -> List[codecs.AnyResource]:
        temp_issuer_url = None
        try:
            temp_issuer_url = self.issuer_url
        except ApiError:
            logger.info("No service found for identity provider")

        temp_redirect_url = self._redirect_uri
        if not temp_redirect_url:
            temp_redirect_url = None

        with open(DEX_MANIFESTS, "r") as file:
            return codecs.load_all_yaml(
                file,
                context={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": temp_redirect_url,
                    "issuer_url": temp_issuer_url,
                    "namespace": self.namespace,
                },
            )

    def _restart_dex(self) -> None:
        for pod in self._client.list(Pod, namespace=self.namespace, labels={"app": "dex"}):
            self._client.delete(Pod, pod.metadata.name, namespace=self.namespace)

    def _apply_dex_resources(self) -> None:
        objs = self._get_dex_manifest()

        for obj in objs:
            self._client.apply(obj, force=True)

        logger.info("Restarting dex")
        self._restart_dex()

        logger.info("Waiting for dex to be ready")
        self._wait_until_is_ready()

    def __wait_until_is_ready(self) -> None:
        for pod in self._client.list(Pod, namespace=self.namespace, labels={"app": "dex"}):
            # Some pods may be deleted, if we are restarting
            try:
                self._client.wait(
                    Pod,
                    pod.metadata.name,
                    for_conditions=["Ready", "Deleted"],
                    namespace=self.namespace,
                )
            except ObjectDeleted:
                pass
        self._client.wait(
            Deployment, "dex", namespace=self.namespace, for_conditions=["Available"]
        )

        issuer_url = self.issuer_url
        resp = requests.get(join(issuer_url, ".well-known/openid-configuration"))
        if resp.status_code != 200:
            raise RuntimeError("Failed to deploy dex")

    def create_idp_service(self):
        """Deploy and configure the dex service."""
        self._apply_dex_resources()

    def update_redirect_uri(self, redirect_uri: str) -> None:
        """Update the registered client's redirect_uri."""
        if not redirect_uri:
            logger.info("Empty parameter for redirect_uri")
            return
        self._redirect_uri = redirect_uri
        self._apply_dex_resources()

    def _wait_until_is_ready(self) -> None:
        """Wait until the dex service is ready."""
        try:
            self.__wait_until_is_ready()
        except (RuntimeError, RequestException):
            sleep(3)
            self.__wait_until_is_ready()

    def remove_idp_service(self) -> None:
        """Remove and clean up the dex manifests."""
        logger.info("Deleting dex resources")
        for obj in self._get_dex_manifest():
            try:
                self._client.delete(type(obj), obj.metadata.name, namespace=obj.metadata.namespace)
            except ApiError:
                pass
