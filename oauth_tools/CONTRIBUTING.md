# Contributing to the oauth_tools module

## Overview

This document illustrates the processes and practices recommended for
contributing to the Identity Platform bundle.

- Generally, before developing bugs or enhancements to this bundle and tests,
  you should [open an issue](https://github.com/canonical/iam-bundle/issues)
  explaining your use case.
- All enhancements require review before being merged. Code review typically
  examines
    - code quality
    - test functionality
    - test coverage
- Please help us out in ensuring easy to review branches by rebasing your pull
  request branch onto
  the `main` branch. This also avoids merge commits and creates a linear Git
  commit history.

## Developing oauth_tools

`oauth_tools` is used both internally in the identity-platform bundle tests and on other charms that integrate with the identity platform. When making changes, we need to be careful not to break either of them.

### Versioning

TBD

### Kubeconfig

`oauth_tools` requires a kubeconfig file to use in order to make calls to the kubernetes API. By default it will use the config file located at `~/.kube/config`. You can override this by using the `TESTING_KUBECONFIG` environment variable.

### Debugging Playwright tests

There are some test cases depending
on [Playwright](https://playwright.dev/python/) to run. To debug the Playwright
test cases:

```shell
PWDEBUG=1 PYTHONPATH=. pytest
```


## Code style and quality enforcement

```shell
tox -e fmt           # update your code according to linting rules
tox -e lint          # code style
```


## Canonical Contributor Agreement

Canonical welcomes contributions to the Charmed Template Operator. Please check
out our [contributor agreement](https://ubuntu.com/legal/contributors) if you're
interested in contributing to the solution.
