# Changelog

## 1.0.0 (2024-06-06)


### Features

* add pytest fixtures to oauth_tools ([960172f](https://github.com/canonical/iam-bundle/commit/960172f39f485cffa7389fd943feb421eb145265))
* add setup for pypi package ([01c5217](https://github.com/canonical/iam-bundle/commit/01c5217674b9cef6ad8b009144a48d0302dbe7a0))
* added matrix with last two versions for microk8s in tests github action ([b301f19](https://github.com/canonical/iam-bundle/commit/b301f19ff0e5ec0aad8dbd4a982b68ad74edfafb))
* changed kratos revision to 386 ([99d6223](https://github.com/canonical/iam-bundle/commit/99d6223272e206b01025f573fcf42973d655bab9))
* includes self-sign-certificates-operator in the bundle ([d5a11c3](https://github.com/canonical/iam-bundle/commit/d5a11c32d0dee0702fa9f0ac9be612a2f84a220b))
* remove send-ca-cert relation ([f1f2562](https://github.com/canonical/iam-bundle/commit/f1f25624f9b82c1d8f2ef2628c19c9208366b783))
* updated components to latest release ([99d6223](https://github.com/canonical/iam-bundle/commit/99d6223272e206b01025f573fcf42973d655bab9))


### Bug Fixes

* add oauth_tools dependencies ([f5759ff](https://github.com/canonical/iam-bundle/commit/f5759ffd6ce052d0c8e22d6cf535aec92d0b7416))
* add tests for the device flow ([ee01bec](https://github.com/canonical/iam-bundle/commit/ee01bec5c5263785ed6a1cb585daceb082660d5b))
* allow for non-latest channels ([2998697](https://github.com/canonical/iam-bundle/commit/29986973a9f0e3138f03fd00f6b24f0306b3c33e))
* bump hydra version to support device flow ([d399948](https://github.com/canonical/iam-bundle/commit/d3999488cf315a3af511102c3894aec10fa0d225))
* bump kratos version ([bf0f0a1](https://github.com/canonical/iam-bundle/commit/bf0f0a161abd8839315f3ffa380ebcc6cc4d0296))
* bumped microk8s version to 1.28-strict/stable in CI ([5931af5](https://github.com/canonical/iam-bundle/commit/5931af51be6d64a8397feeb9c9d7f1e10d910fad))
* changed charmcraft channel to stable ([32a337f](https://github.com/canonical/iam-bundle/commit/32a337f455591cc0ae986a0fc38159ce678901f9))
* changed self-signed-certificates channel to latest/edge ([225d771](https://github.com/canonical/iam-bundle/commit/225d771f37de3812970dad5f39ff893fc7ea4bdf))
* correctly extract version from select-channel action ([4070b11](https://github.com/canonical/iam-bundle/commit/4070b11a44851bd7d998e2dafad5389ffc5b0bcb))
* fix the authorization code flow test case ([d93321a](https://github.com/canonical/iam-bundle/commit/d93321a16f41456293e5d54343ae6cd47f38a07c))
* include yaml in package data ([0a6caad](https://github.com/canonical/iam-bundle/commit/0a6caadf8032aa5108140759f8c57967ce1019f9))
* include yaml in package data ([81d7560](https://github.com/canonical/iam-bundle/commit/81d7560bb6c21ac397934e4727ae0d59f363dd51))
* make redirect URL HTTPS ([1e20267](https://github.com/canonical/iam-bundle/commit/1e2026777b57488c28cf428e30f3f96618b3d088))
* pin down the kratos image version because the latest kratos does not work with our canonical-forked hydra ([dbda188](https://github.com/canonical/iam-bundle/commit/dbda1883770a9f3ed0b731998c894b21becf98c5))
* pinned macaroonbakery to 1.3.2 ([99d6223](https://github.com/canonical/iam-bundle/commit/99d6223272e206b01025f573fcf42973d655bab9))
* Removed reference to pytest-asyncio. ([99d6223](https://github.com/canonical/iam-bundle/commit/99d6223272e206b01025f573fcf42973d655bab9))
* updated hydra_endpoints relation name ([b25173d](https://github.com/canonical/iam-bundle/commit/b25173d30431280cad55de9b8f49620d044ad715))
* updated test_authorization_code_flow ([5b12263](https://github.com/canonical/iam-bundle/commit/5b12263ac5c50664a12f4f63ca76f8e425753141))
* use pytest_plugins to import fixtures ([88f2609](https://github.com/canonical/iam-bundle/commit/88f260961bfebe6317cdc626c7928855298520b9))
* work around the singledispatch bug in lower python version ([f297694](https://github.com/canonical/iam-bundle/commit/f2976942134c32c1e197ec09266771b685484ce7))
