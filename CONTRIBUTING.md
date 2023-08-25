# Contributing to Identity Platform Bundle

## Overview

This document illustrates the processes and practices recommended for
contributing to the Identity Platform bundle.

## Developing the bundle integration test

You can use the environments created by `tox` for test development:

```shell
$ tox --notest -e integration
$ source .tox/integration/bin/activate
```

### Debugging Playwright tests

There are some test cases depending
on [Playwright](https://playwright.dev/python/) to run. To debug the Playwright
test cases:

```
$ PWDEBUG=1 PYTHONPATH=. pytest
```

## Code style and quality enforcement

```shell
$ tox -e fmt           # update your code according to linting rules
$ tox -e lint          # code style
```

## Testing the bundle

```shell
$ tox -e integration   # integration test
```

In order to run the integration test against a deployed bundle, run

```shell
$ tox -e integration -- --model=<model name> --keep-models --no-deploy
```

## Deploy the bundle locally

Render the bundle file with desired channel:

```shell
$ tox -e render-<channel, e.g. edge>
```

or directly run the utility:

```shell
$ ./bundle_renderer.py bundle.yaml.j2 \
    -o render-<channel>.yaml \
    -c <channel> \
    --variables <key1>=<val1>,<key2>=<val2>
```

Use the rendered bundle file to deploy the bundle locally:

```shell
$ juju deploy ./bundle-<channel, e.g. edge>.yaml --trust
```

To deploy the bundle with a locally built charm and OCI image, update the bundle
file. Take an example of hydra charm:

```yaml
hydra:
  charm: <path to the local charm>
  resources:
    oci-image: <path to a local file / link to a public OCI image, e.g. ghcr.io/canonical/hydra:2.1.1>
```

## Upgrade the charms in the bundle

Please follow the instructions to upgrade a charm or charms in the bundle:

- Update the revision(s) of the target charm(s) by submitting a pull request
- Wait for the integration test to pass and team approval
- If integration test fails, either fix the problematic charm(s) and update the
  revision(s) in the pull request, or close and discard the pull request

> :rotating_light: **Note:**
>
> - The revision of a charm is expected to be the latest version that can be
    published to channels

## Publish the bundle

Currently, publishing the bundle is via
the [`publish` GitHub action](https://github.com/canonical/iam-bundle/actions/workflows/publish.yaml).

> :rotating_light: **Note:**
>
> - Only publishing to `edge` channel is supported for now

## Canonical Contributor Agreement

Canonical welcomes contributions to the Charmed Template Operator. Please check
out our [contributor agreement](https://ubuntu.com/legal/contributors) if you're
interested in contributing to the solution.
