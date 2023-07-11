#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

from os.path import join
from secrets import token_urlsafe
from urllib.parse import urlencode

import requests


def get_authorization_url(hydra_url: str, client_id: str, client_secret: str) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": client_secret,
        "response_type": "code",
        "response_mode": "query",
        "scope": "openid profile email",
        "state": token_urlsafe(),
        "nonce": token_urlsafe(),
    }
    return join(hydra_url, "oauth2/auth?" + urlencode(params))


def client_credentials_grant_request(
    hydra_url: str, client_id: str, client_secret: str, scope: str = "openid profile"
) -> requests.Response:
    url = join(hydra_url, "oauth2/token")
    body = {
        "grant_type": "client_credentials",
        "scope": scope,
    }

    return requests.post(
        url,
        data=body,
        auth=(client_id, client_secret),
        verify=False,
    )


def auth_code_grant_request(
    hydra_url: str, client_id: str, client_secret: str, auth_code: str, redirect_uri: str
) -> requests.Response:
    url = join(hydra_url, "oauth2/token")
    body = {
        "code": auth_code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }

    return requests.post(
        url,
        data=body,
        auth=(client_id, client_secret),
        verify=False,
    )


def userinfo_request(hydra_url: str, access_token: str) -> requests.Response:
    url = join(hydra_url, "userinfo")

    return requests.get(
        url,
        headers={
            "Authorization": "Bearer " + access_token,
            "Content-Type": "application/json",
        },
        verify=False,
    )
