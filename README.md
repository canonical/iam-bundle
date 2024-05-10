# Identity Platform Bundle

[![CharmHub Badge](https://charmhub.io/identity-platform/badge.svg)](https://charmhub.io/identity-platform)
![GitHub Tag](https://img.shields.io/github/v/tag/canonical/iam-bundle?label=release)
[![Juju](https://img.shields.io/badge/Juju%20-3.0+-%23E95420)](https://github.com/juju/juju)
[![License](https://img.shields.io/github/license/canonical/iam-bundle?label=License)](https://github.com/canonical/iam-bundle/blob/main/LICENSE)

[![Continuous Integration Status](https://github.com/canonical/iam-bundle/actions/workflows/on_push.yaml/badge.svg?branch=main)](https://github.com/canonical/iam-bundle/actions?query=branch%3Amain)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
[![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-1.0.0-%23FE5196.svg)](https://conventionalcommits.org)

This repository includes Identity Platform bundle definitions and tests. The
bundle includes the following charmed operators:

- [x] [kratos operator](https://github.com/canonical/kratos-operator)
- [x] [hydra operator](https://github.com/canonical/hydra-operator)
- [x] [identity platform login ui operator](https://github.com/canonical/identity-platform-login-ui-operator)
- [x] [kratos external idp integrator](https://github.com/canonical/kratos-external-idp-integrator)
- [x] [postgresql k8s operator](https://github.com/canonical/postgresql-k8s-operator)
- [x] [traefik k8s operator](https://github.com/canonical/traefik-k8s-operator)
- [x] [self-signed certificates operator](https://github.com/canonical/self-signed-certificates-operator)

## Deploy the bundle

To deploy the bundle from the CharmHub, run the following:

```shell
juju deploy identity-platform --channel <channel, e.g. edge> --trust
```

## Contributing

Please refer to the [contribution documentation](CONTRIBUTING.md) to learn how
to contribute to the project.
