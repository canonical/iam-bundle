# IAM Bundle
This repository hosts IAM bundle definitions and tests.

## Generate a bundle
In order to generate a bundle file, clone this repository and use the `render-{channel}` utility.

For example, to get the bundle from `edge` channel, run `tox -e render-edge`.

## Deploy a bundle
To deploy the bundle, run `juju deploy ./bundle-edge.yaml`
