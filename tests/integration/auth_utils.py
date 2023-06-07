from base64 import b64encode
from os.path import join
from secrets import token_urlsafe
from urllib.parse import urlencode

import requests
from pytest_operator.plugin import OpsTest


def construct_authorization_url(hydra_url, client_id, client_secret):
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


def get_basic_http_auth_header(username, password):
    token = b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def token_request(hydra_url, client_id, client_secret, auth_code, redirect_uri):
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
