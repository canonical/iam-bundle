# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import os
from pathlib import Path

DEX_MANIFESTS = Path(__file__).parent / "dex.yaml"
KUBECONFIG = os.environ.get("TESTING_KUBECONFIG", "~/.kube/config")

DEX_CLIENT_ID = "client_id"
DEX_CLIENT_SECRET = "client_secret"

EXTERNAL_USER_EMAIL = "admin@example.com"
EXTERNAL_USER_PASSWORD = "password"

ADMIN_INGRESS = "admin-ingress"
PUBLIC_INGRESS = "public-ingress"
HYDRA = "hydra"
KRATOS = "kratos"
KRATOS_EXTERNAL_IDP_INTEGRATOR = "kratos-external-idp-integrator"
IDENTITY_PLATFORM_LOGIN_UI_OPERATOR = "identity-platform-login-ui-operator"
SELF_SIGNED_CERTIFICATES = "self-signed-certificates"
BUNDLE_APPS = [
    ADMIN_INGRESS,
    PUBLIC_INGRESS,
    HYDRA,
    KRATOS,
    KRATOS_EXTERNAL_IDP_INTEGRATOR,
    IDENTITY_PLATFORM_LOGIN_UI_OPERATOR,
    SELF_SIGNED_CERTIFICATES,
]

PUBLIC_LOAD_BALANCER = f"{PUBLIC_INGRESS}-istio"
ADMIN_LOAD_BALANCER = f"{ADMIN_INGRESS}"
